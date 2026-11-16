"""The response policy checker: deterministic rules a hint must pass before it is shown.

The model is told the rules in its prompt, but an instruction is not a mechanism
(Lecture 11). This module is the mechanism. It checks each generated hint against
the assistance level the application chose, the student's current code, the
verified test results and the exercise's reference solution.

What it catches, by rule id:
  level_mismatch        the reply claims a different level from the one requested
  code_block            fenced code, or whole lines of code
  new_code              code statements (or, at levels 1-2, expressions) that are
                        not quoted from the student's code or the test evidence
  reveals_fix           text that matches a line of the reference solution
  disclosure_term       an exercise-specific giveaway, e.g. "numbers[0]"
  algorithm_outline     a numbered or bulleted step-by-step procedure
  too_specific          a line number, or the bug's location, in a level 1 hint
  too_vague             a level 2-3 hint that never points at a location
  explains_fault        a level 1-2 hint that explains why the code fails (heuristic:
                        causal wording such as "because" or ", so")
  repair_instruction    an exact edit instruction, e.g. "set the starting value to ..."
  unknown_evidence      a test id that does not exist in this run
  invalid_line          a line number that does not exist in the code
  contradicts_evidence  a claim about a test's status or value that the run disproves
  overclaim             a promise that a change will work or that code is correct
  length                too long (cognitive load) or too short to act on

The level NUMBER is enforced exactly. What each level MEANS is only checked
heuristically: explains_fault and repair_instruction catch common wordings, not
every way of explaining a cause or dictating an edit.

What it cannot catch: a paraphrase of the fix that avoids the exercise's giveaway
terms and the instruction patterns, an explanation worded without causal
connectives, or a wrong explanation of *why* a test fails. The first two are
limits of pattern matching; the last is why the interface labels every hint as an
unverified interpretation and shows the verified evidence beside it.

Rejection reasons quote the offending text, which can include the reference
solution, so they go to the developer log only. feedback_for_model() and
summary_for_student() give the model and the student fixed wordings that never
quote the hint, the solution or the giveaway terms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from codementor.exercises import Exercise, compact
from codementor.runner import PASSED, RunResult
from codementor.schema import HintResponse

LEVEL_NAMES = {1: "Concept", 2: "Location", 3: "Likely fault"}
MAX_WORDS = 90
MIN_WORDS = 6

CODE_SPAN = re.compile(r"`([^`\n]+)`")
LINE_REF = re.compile(r"\blines?\s+(\d+)", re.I)
TEST_REF = re.compile(r"\b(T\d+)\b")
STATEMENT = re.compile(
    r"^\s*(def\s|class\s|return\b|for\s.+\sin\s|while\s|if\s|elif\s|else\s*:|import\s|from\s.+\simport\s"
    r"|[A-Za-z_][\w.]*(\[[^\]]*\])?\s*(\+|-|\*|/|//|%)?=(?!=))"
)
EXPRESSION_CHARS = set("()[]+-*/%<>=!")
CODE_LINE = re.compile(
    r"^\s*((def|class)\s+\w+.*:|(for|while|if|elif)\b.*:|else\s*:|return\b[^.!?]*"
    r"|[A-Za-z_][\w.]*(\[[^\]]*\])?\s*(\+|-|\*|/|//|%)?=(?!=)[^.!?]*)\s*$"
)
STEP_LINE = re.compile(r"^\s*(\d+[.)]|[-*•]|step\s+\d+)\s+", re.I)
STATUS_CLAIM = re.compile(
    r"\b(T\d+)\b[^.;]{0,40}?\b(pass(?:es|ed|ing)?|fail(?:s|ed|ing)?|errors?|raise[sd]?|crash(?:es|ed)?|time[sd]? out|timed out)\b",
    re.I,
)
VALUE_CLAIM = re.compile(
    r"\b(T\d+)\b[^.;]{0,30}?\b(?:returns?|returned|gives?|gave|produces?|produced)\s+`?"
    r"(-?\d+(?:\.\d+)?|'[^']*'|\"[^\"]*\"|True|False|None|\[[^\]]*\])`?",
)
OVERCLAIMS = [
    r"\bwill (now )?(pass|work|be correct|fix)\b",
    r"\bguarantee",
    r"\b(this|that) (fixes|solves|will fix|will solve) (it|the (bug|problem|error))\b",
    r"\byour code (is|will be) (now )?correct\b",
    r"\b(definitely|certainly)\b",
    r"\ball (the )?tests will pass\b",
]
# Level meaning (heuristic). Levels 1-2 must not explain the cause; no level may dictate the edit.
EXPLANATION = [
    r"\bbecause\b",
    # ", so every negative is rejected" explains; ", so check line 3" only directs attention.
    r"[,;]\s*so\b(?!\s+(check|look|trace|examine|compare|try|think|consider|focus|see|read|print|test|step)\b)",
    r"\bso (that )?(every|no|nothing|none|any|the|it|this)\b",
    r"\bwhich (means|is why)\b",
    r"\b(this|that) is why\b",
    r"\b(causes|caused|causing)\b",
    r"\b(is|are) the (cause|reason)\b",
    r"\b(results?|resulting) in\b",
    r"\bleads? to\b",
]
REPAIR_INSTRUCTION = [
    r"(^|[.;:!?]\s+|\b(then|just|simply)\s+)(set|change|replace|initiali[sz]e|assign|switch|swap|rewrite|update)\b"
    r"[^.;!?]{0,80}?\b(to|with|into|by)\b",
    r"(^|[.;:!?]\s+)use\b[^.;!?]{0,60}\binstead\b",
    r"\bleave (the )?(rest|remaining|other)\b",
]


@dataclass
class Violation:
    rule: str
    detail: str


@dataclass
class PolicyContext:
    exercise: Exercise
    level: int
    student_code: str
    run: RunResult

    @property
    def bug_line_numbers(self) -> list[int]:
        return self.exercise.bug_line_numbers(self.student_code)

    @property
    def known_bug(self) -> bool:
        """The exercise's anticipated bug is still there, and nothing else is failing."""
        return bool(self.bug_line_numbers) and bool(self.run.failing_ids) and \
            self.run.failing_ids <= self.exercise.bug.expected_failing


@dataclass
class PolicyDecision:
    accepted: bool
    violations: list[Violation] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)

    def reasons(self) -> list[str]:
        """Full detail for the developer log. May quote the solution: never show it or send it on."""
        return [f"{v.rule}: {v.detail}" for v in self.violations]

    @property
    def rules(self) -> list[str]:
        return list(dict.fromkeys(v.rule for v in self.violations))


def _quoted(span: str, ctx: PolicyContext) -> bool:
    """Is this code span copied from the student's code or from the test evidence?"""
    needle = compact(span)
    if not needle:
        return True
    haystacks = [compact(ctx.student_code)]
    haystacks += [compact(text) for _, text in ctx.run.evidence().values()]
    haystacks += [compact(o.expected_repr) for o in ctx.run.outcomes]
    return any(needle in h for h in haystacks)


def _is_expression(span: str) -> bool:
    return any(ch in EXPRESSION_CHARS for ch in span)


def check_hint(response: HintResponse, ctx: PolicyContext) -> PolicyDecision:
    text = response.hint
    lowered = text.lower()
    level = ctx.level
    v: list[Violation] = []
    checks: list[str] = []

    def check(name: str) -> None:
        checks.append(name)

    # The application owns the level; the model's claim must match it.
    check("level_mismatch")
    if response.level != level:
        v.append(Violation("level_mismatch", f"reply says level {response.level}, requested {level}"))

    # Length: a hint is one or two sentences, not a lecture.
    check("length")
    words = len(text.split())
    if words > MAX_WORDS:
        v.append(Violation("length", f"{words} words (maximum {MAX_WORDS})"))
    elif words < MIN_WORDS:
        v.append(Violation("length", f"{words} words is too short to act on"))

    # Code: no blocks, no new statements, no new expressions below level 3.
    check("code_block")
    if "```" in text:
        v.append(Violation("code_block", "contains a fenced code block"))
    for line in text.splitlines():
        if CODE_LINE.match(line) and not _quoted(line, ctx):
            v.append(Violation("code_block", f"contains a line of code: {line.strip()[:60]}"))
            break

    check("new_code")
    spans = CODE_SPAN.findall(text)
    for span in spans:
        if _quoted(span, ctx):
            continue
        if STATEMENT.match(span):
            v.append(Violation("new_code", f"gives a replacement statement: `{span[:60]}`"))
        elif level < 3 and _is_expression(span):
            v.append(Violation("new_code", f"gives new code at level {level}: `{span[:60]}`"))

    # The reference solution and the exercise's giveaway terms.
    check("reveals_fix")
    hint_compact = compact(text)
    for fix_line in ctx.exercise.fix_lines():
        fix_compact = compact(fix_line)
        if len(fix_compact) >= 6 and fix_compact in hint_compact:
            v.append(Violation("reveals_fix", f"matches a line of the reference solution: {fix_line[:60]}"))
    for span in spans:
        span_compact = compact(span)
        if len(span_compact) >= 6 and not _quoted(span, ctx) and any(
            span_compact in compact(f) for f in ctx.exercise.fix_lines()
        ):
            v.append(Violation("reveals_fix", f"quotes part of the reference solution: `{span[:60]}`"))

    check("disclosure_term")
    for pattern in ctx.exercise.bug.disclosure_patterns:
        match = re.search(pattern, text, re.I)
        if match:
            v.append(Violation("disclosure_term", f"gives away the repair: '{match.group(0)}'"))

    check("algorithm_outline")
    steps = sum(1 for line in text.splitlines() if STEP_LINE.match(line))
    if steps >= 3:
        v.append(Violation("algorithm_outline", f"lays out {steps} steps, which reads as a procedure for the fix"))

    # Level boundaries: level 1 must not localise; levels 2-3 must.
    line_refs = [int(n) for n in LINE_REF.findall(text)]
    check("too_specific" if level == 1 else "too_vague")
    if level == 1:
        if line_refs:
            v.append(Violation("too_specific", "mentions a line number at level 1"))
        for pattern in ctx.exercise.bug.location_patterns:
            match = re.search(pattern, text, re.I)
            if match:
                v.append(Violation("too_specific", f"points at the bug's location at level 1: '{match.group(0)}'"))
                break
        for span in spans:
            if _quoted(span, ctx) and _is_expression(span) and compact(span) in compact(ctx.student_code):
                v.append(Violation("too_specific", f"quotes the code at level 1: `{span[:60]}`"))
                break
    elif not _points_at_location(text, spans, line_refs, ctx):
        v.append(Violation("too_vague", f"a level {level} hint has to point at a line, statement or condition"))

    # What the level means, not just its number. Heuristics: they catch common wordings,
    # not every way of explaining a cause or dictating an edit.
    if level <= 2:
        check("explains_fault")
        for pattern in EXPLANATION:
            match = re.search(pattern, text, re.I)
            if match:
                v.append(Violation("explains_fault", f"explains the cause at level {level}: '{match.group(0).strip()}'"))
                break
    check("repair_instruction")
    for pattern in REPAIR_INSTRUCTION:
        match = re.search(pattern, text, re.I | re.M)
        if match:
            v.append(Violation("repair_instruction", f"dictates the edit: '{match.group(0).strip()[:60]}'"))
            break

    # Factual claims that the verified run can settle.
    check("invalid_line")
    n_lines = len(ctx.student_code.splitlines())
    for n in line_refs:
        if not 1 <= n <= n_lines:
            v.append(Violation("invalid_line", f"refers to line {n}, but the code has {n_lines} lines"))

    check("unknown_evidence")
    evidence = ctx.run.evidence()
    cited = set(response.evidence_ids) | set(TEST_REF.findall(text))
    for eid in sorted(cited - set(evidence)):
        v.append(Violation("unknown_evidence", f"refers to {eid}, which is not in this run"))

    check("contradicts_evidence")
    v.extend(_contradictions(text, ctx))

    check("overclaim")
    for pattern in OVERCLAIMS:
        match = re.search(pattern, lowered)
        if match:
            v.append(Violation("overclaim", f"claims more than the tests show: '{match.group(0)}'"))
            break

    return PolicyDecision(accepted=not v, violations=v, checks=checks)


def _points_at_location(text: str, spans: list[str], line_refs: list[int], ctx: PolicyContext) -> bool:
    """Does a level 2-3 hint point somewhere specific in the code?"""
    n_lines = len(ctx.student_code.splitlines())
    if ctx.known_bug:
        bug_lines = ctx.bug_line_numbers
        if any(abs(n - b) <= 1 for n in line_refs for b in bug_lines):
            return True
        if any(re.search(p, text, re.I) for p in ctx.exercise.bug.location_patterns):
            return True
        bug_contents = [compact(line) for line in ctx.exercise.bug.lines]
        return any(compact(s) and (compact(s) in b or b in compact(s)) for s in spans for b in bug_contents)
    # Unknown bug: accept any real line reference or any quote from the student's code.
    if any(1 <= n <= n_lines for n in line_refs):
        return True
    return any(compact(s) in compact(ctx.student_code) for s in spans if compact(s))


def _contradictions(text: str, ctx: PolicyContext) -> list[Violation]:
    found = []
    for test_id, verb in STATUS_CLAIM.findall(text):
        outcome = ctx.run.outcome(test_id)
        if outcome is None:
            continue
        claims_pass = verb.lower().startswith("pass")
        if claims_pass and outcome.status != PASSED:
            found.append(Violation("contradicts_evidence", f"says {test_id} passes, but it {outcome.status}"))
        elif not claims_pass and outcome.status == PASSED:
            found.append(Violation("contradicts_evidence", f"says {test_id} {verb}, but it passed"))
    for test_id, value in VALUE_CLAIM.findall(text):
        outcome = ctx.run.outcome(test_id)
        if outcome is None or outcome.actual_repr is None:
            continue
        if compact(value) != compact(outcome.actual_repr):
            found.append(Violation("contradicts_evidence",
                                   f"says {test_id} returned {value}, but it returned {outcome.actual_repr}"))
    if re.search(r"\ball (the |your )?tests (pass|passed)\b", text, re.I) and ctx.run.failing_ids:
        found.append(Violation("contradicts_evidence", "says all tests pass, but some fail"))
    return found


# Requests in the student's message that try to get round the policy.
SOLUTION_REQUEST = [
    r"\b(give|show|tell|write|send|paste|provide)\b.{0,30}\b(answer|solution|fix|fixed code|correct code|full code|whole code|complete code|working code|the code)\b",
    r"\bjust (fix|solve|do) (it|this)\b",
    r"\bwhat('?s| is) the (answer|solution|fix)\b",
    r"\b(fix|correct|rewrite|solve|finish) (it|this|my code|the code|the function|this function) for me\b",
]
RULE_OVERRIDE = [
    r"\bignore (the|your|all|any|previous) (rules|instructions|policy|policies|levels?)\b",
    r"\b(i'?m|i am) (the|a|your) (teacher|instructor|lecturer|professor|ta|tutor|developer)\b",
    r"\b(level|mode) (4|four|max|maximum|unlimited)\b",
    r"\b(skip|bypass|disable|turn off) (the )?(levels?|rules|policy|checks?|filter)\b",
]


def detect_policy_requests(message: str) -> list[str]:
    """Label a student message that asks for the solution or tries to change the rules."""
    labels = []
    if any(re.search(p, message, re.I) for p in SOLUTION_REQUEST):
        labels.append("solution_request")
    if any(re.search(p, message, re.I) for p in RULE_OVERRIDE):
        labels.append("rule_override")
    return labels


# What the model and the student are told about a rejection. Fixed wording only: the
# detailed reasons above can quote the reference solution, so they never leave the log.
MODEL_REASONS = {
    "level_mismatch": "the level field did not match the level requested",
    "length": "it was too long or too short",
    "code_block": "it contained code",
    "new_code": "it contained code that is not quoted from the student's code or the test results",
    "reveals_fix": "it revealed the repair",
    "disclosure_term": "it used wording that gives away the repair",
    "algorithm_outline": "it laid out a step-by-step procedure",
    "too_specific": "it pointed at the bug's location, which is too specific for this level",
    "too_vague": "it did not point at a line, statement or condition",
    "explains_fault": "it explained the cause, which is beyond this level",
    "repair_instruction": "it told the student exactly what to change",
    "invalid_line": "it mentioned a line number that does not exist",
    "unknown_evidence": "it cited a test ID that is not in this run",
    "contradicts_evidence": "it contradicted the test results",
    "overclaim": "it claimed more than the tests show",
}
_TOO_MUCH = "gave away too much of the fix"
_BEYOND = "went beyond the current level"
_MISMATCH = "didn't match your code or test results"
STUDENT_CATEGORIES = {
    "reveals_fix": _TOO_MUCH, "disclosure_term": _TOO_MUCH, "code_block": _TOO_MUCH,
    "new_code": _TOO_MUCH, "algorithm_outline": _TOO_MUCH, "repair_instruction": _TOO_MUCH,
    "too_specific": _BEYOND, "explains_fault": _BEYOND, "level_mismatch": _BEYOND,
    "too_vague": "was too vague to act on",
    "invalid_line": _MISMATCH, "unknown_evidence": _MISMATCH, "contradicts_evidence": _MISMATCH,
    "overclaim": "claimed more than the tests show",
    "length": "was too long or too short",
}


def feedback_for_model(rules: list[str]) -> list[str]:
    """Why a hint was rejected, for the retry prompt. Names the rules, never quotes anything."""
    return list(dict.fromkeys(MODEL_REASONS.get(r, "it broke a hint rule") for r in rules))


def summary_for_student(rules: list[str]) -> list[str]:
    """Why a hint was rejected, for the interface. Plain categories, never quotes anything."""
    return list(dict.fromkeys(STUDENT_CATEGORIES.get(r, "broke a hint rule") for r in rules))

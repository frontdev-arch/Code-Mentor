# CodeMentor

Code Mentors overall aim is a Python debugging tutor for beginners with three hint levels and execution results shown separately from AI interpretation. This Stage 3 snapshot includes the complete local prototype: exercises, test runner, hint checks, interface and repeatable demonstrations. Hints are pre-written or simulated using fixed replies.

README prose word count: 1337 words (excludes fenced commands and the count line, includes headings/table text.)

## About this repository

This repository imports a locally developed prototype in stages. Stage 1 imported the exercise bank and restricted test runner. Stage 2 added hint controls, reply checks and tests across the exercise bank. Stage 3 imports the tutor workflow, interface, demonstrations and supporting documents.

## Project status

| Part                                                                  | Status in this snapshot        |
| --------------------------------------------------------------------- | ------------------------------ |
| 10 debugging exercises with tests, bug metadata and pre written hints | Included                       |
| Test runner with restrictions on what student code can do             | Included                       |
| Hint levels, reply schema and hint policy checker                     | Included |
| Tutor pipeline with a simulated AI and scripted demonstrations        | Included  |
| Interface (`app.py`)                                                  | Included  |

## Technology

- **Python 3.12 on macOS**: the configuration tested locally. The runner uses only the standard library.
- The runner relies on operating-system features that are unavailable on Windows. Other platforms and Python versions have not been tested here.
- **pytest**: all 159 tests in this snapshot passed in the latest check.
- **Streamlit** provides the browser interface. Offline mode uses pre-written hints. `ScriptedProvider` replays fixed replies for the demonstrations. Neither mode requires an API key.

## Running it

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest
.venv/bin/streamlit run app.py
```

Run these commands from the project folder, then open the local address displayed in the terminal. Choose an exercise, edit its code, select **Run tests** and request a hint. Use **More specific** to move through the three levels.

For the two simulated conversations, follow [the demo instructions](demo/README.md). Restart the app with the command for the chosen script and use exercise 1. The replies are fixed demonstrations, not evidence of how a live model would behave.

## Exercises and tests

Each `exercises/<id>/` folder holds:

- `exercise.json`: the exercise description, test inputs and expected answers, details of the bug and three pre-written hints
- `starter.py`: the buggy code the student starts from
- `solution.py`: a reference solution, used only for internal checks

`codementor/exercises.py` loads each folder and checks that key information is present, test names are unique and all three hint levels are included. It also checks that the text matching rules can be read. These checks do not catch every possible problem with an exercise. The hints and matching rules are used by the hint checker included in Stage 2.

`tests/test_runner.py` uses exercise 1 to check that results and errors are reported correctly. Code that takes too long is stopped and changes to test inputs do not affect other tests. It also checks restrictions on launching programs making network connections and accessing files and checks that a sample secret setting is not passed to student code.

`tests/test_exercises.py` runs every starter and reference solution through the runner and checks the pre-written hints against the hint rules. Separate tests cover hint levels, reply format and rejection of unsuitable hints.

## How the runner works

The runner runs student code separately from the tutor and applies five checks and restrictions:

1. **Check before running.** The runner checks the code for syntax errors and blocks imports that are not allowed for these exercises.
2. **Separate execution.** Each run starts a separate copy of Python in a temporary folder with only the settings it needs and no keyboard input.
3. **Time and resource limits.** The runner stops code that takes too long and limits its use of computer resources where the operating system supports this.
4. **Checks while running.** Python checks block selected actions including starting other programs and making network connections. File access is limited to the temporary run folder and files Python needs with an exception for the system file used to discard output. These checks do not provide complete protection against harmful code.
5. **macOS protection.** The operating system adds restrictions on network access, launching other programs, changing files outside the temporary run folder and reading files in user home folders.

## Development record

The prototype was developed locally before these imports. The commits group existing components; they do not represent the dates when each feature was first written.

- [Stage 1](https://github.com/frontdev-arch/Code-Mentor/commit/d54cfbd): exercise bank and restricted runner; 18 tests passed.
- [Stage 2](https://github.com/frontdev-arch/Code-Mentor/commit/3b03f05): hint levels, reply checks and exercise-bank tests; 135 tests passed.
- [Stage 3](https://github.com/frontdev-arch/Code-Mentor/commit/970c068): interface, tutor workflow and scripted demonstrations; 159 tests passed.

The following records connect the main problems, decisions and checks. The named tests are in the linked files.

| Problem and decision | Check and result |
| --- | --- |
| Student code could run indefinitely or access unrelated files. Runs were separated and restricted, with shorter waiting times to keep feedback responsive. | [Runner tests](tests/test_runner.py): `test_infinite_loop_times_out_per_test`, `test_runtime_layers_refuse_dangerous_operations` and `test_environment_secrets_are_not_visible_to_student_code` passed. These checks do not establish complete protection against malicious code. |
| A reply could keep the correct level number while explaining too much. Wording checks were added and narrowed to allow useful Level 3 explanations. | [Policy tests](tests/test_policy.py): `test_level_meaning_is_checked_not_just_the_number` rejects the recorded examples; `test_level_3_may_still_explain_the_fault_and_suggest_a_direction` preserves an acceptable example. Both passed; other paraphrases may escape detection. |
| Detailed rejection messages could repeat the solution to the student or in another model request. Fixed summaries replaced quoted offending text. | [Tutor tests](tests/test_tutor.py): `test_no_request_to_the_model_carries_the_solution_even_on_retries` and `test_rejection_shown_to_the_student_never_quotes_the_solution` passed. Detailed diagnostics remain in local logs. |
| Citing a failing test could be mistaken for a correct diagnosis. The interface labels the citation separately and keeps the explanation unverified. | [Tutor tests](tests/test_tutor.py): `test_citing_a_failing_test_is_recorded_as_a_citation_not_as_support` passed. [The wrong-diagnosis demo](demo/wrong_diagnosis.json) deliberately shows this limitation. |
| A hint could use old code, or retain too much detail after the problem changed. Code and questions are submitted together, changed code is tested again and changed failures reset the hint level. | [Tutor tests](tests/test_tutor.py): `test_changed_code_reruns_tests_before_the_hint` and `test_new_failing_set_resets_the_level` passed. Interface checks also exercised running code and requesting Levels 1–3 in offline and both scripted modes. |

All 159 automated tests passed in the latest audit. These results cover the supplied cases, not every possible reply or user behaviour. No learner study has been carried out.

### Submission review corrections

The review found that two interface messages overstated solution prevention and omitted automatic level resets. The wording now explains both limits. The architecture diagram now uses solid arrows for implemented information flows and labels the student code, inputs and settings sent to the runner's separate process. The solution-request storyboard was refreshed to match the interface. These are presentation corrections; the underlying hint rules are unchanged.

## Illustrations

- [Architecture diagram](docs/architecture.png): shows the system components and connections.
- [Storyboard 1](docs/storyboard1.png), [Storyboard 2](docs/storyboard2.png) and [Storyboard 3](docs/storyboard3.png): illustrate progressive hints, a solution request and a challenged diagnosis.

These files are included in the repository.


## Limitations

- The runner is intended for exercises on a local computer, not an online service that runs code from unknown users.
- macOS provides extra protection. The available restrictions depend on the operating system.
- Passing the supplied tests does not mean the code will work correctly for every possible input.
- Hint checks use rules that recognise particular wording. They can miss a reworded solution or an incorrect explanation, so passing the checks does not prove that a hint is correct.
- Simulated replies do not demonstrate live model reliability. Learning benefits have not been established through a learner study.

## AI assistance

I wrote a requirements specification for Code Mentor that set its core design. This include the three hint levels held in application state that the model cannot change, executable tests as evidence and also kept separate from AI interpretation. A deterministic policy checker with bounded retries and a fallback. The reference solution withheld from the model and isolated execution. 

I used Claude Code to implement the prototype and its tests from that specification and a proposed draft for the architecture diagram. I ran the prototype and checked its design against Assignment 1.

I then reviewed the submission and found the problems described in Section 4. Claude Code reproduced them and I decided how each was resolved. Plain rejection categories for students, rule names only for the model, heuristic level rules with softened claims. Claude Code implemented these changes and their regression tests.



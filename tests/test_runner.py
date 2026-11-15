"""The restricted runner: correct verdicts, clear errors, and each safety layer holding."""

import subprocess
import sys

import pytest

from codementor.runner import (ERROR, FAILED, LOAD_ERROR, PASSED, REJECTED, RUN_TIMEOUT, SYNTAX_ERROR,
                               TIMEOUT, values_match)

HEADER = "def find_max(numbers):\n"


def run_body(runner, find_max, body, precheck=True):
    return runner.run(find_max, HEADER + body, precheck=precheck)


def test_starter_results_are_observable(starter_run):
    t3 = starter_run.outcome("T3")
    assert t3.status == FAILED
    assert t3.expected_repr == "-1" and t3.actual_repr == "0"
    assert "should return -1 but returned 0" in t3.summary()
    assert starter_run.outcome("T1").status == PASSED


def test_syntax_error_is_reported_without_running(runner, find_max):
    run = runner.run(find_max, "def find_max(numbers)\n    return 1\n")
    assert run.status == SYNTAX_ERROR and run.error_line == 1
    assert run.outcomes == []


def test_missing_function_is_rejected(runner, find_max):
    run = runner.run(find_max, "def biggest(numbers):\n    return 1\n")
    assert run.status == REJECTED and "find_max" in run.message


def test_exception_reports_type_and_line(runner, find_max):
    run = run_body(runner, find_max, "    x = 1\n    return numbers[99]\n")
    o = run.outcome("T1")
    assert o.status == ERROR and o.error_type == "IndexError" and o.error_line == 3


def test_error_at_import_time_stops_all_tests(runner, find_max):
    run = runner.run(find_max, "print(undefined_name)\n" + HEADER + "    return 1\n")
    assert run.status == LOAD_ERROR and "NameError" in run.message
    assert all(o.status == "not_run" for o in run.outcomes)


def test_printing_does_not_break_results(runner, find_max):
    run = run_body(runner, find_max, "    print('x' * 100000)\n    return max(numbers)\n")
    assert run.all_passed
    assert run.outcome("T1").output.endswith("[output truncated]")


def test_infinite_loop_times_out_per_test(runner, find_max):
    body = "    if numbers[0] < 0:\n        while True:\n            pass\n    return max(numbers)\n"
    run = run_body(runner, find_max, body)
    assert run.outcome("T3").status == TIMEOUT
    assert run.outcome("T1").status == PASSED  # other tests still run


def test_swallowed_timeout_hits_the_wall_clock(runner, find_max):
    body = "    while True:\n        try:\n            while True:\n                pass\n        except BaseException:\n            pass\n"
    run = run_body(runner, find_max, body)
    assert run.status == RUN_TIMEOUT
    assert run.outcome("T1").status == TIMEOUT


def test_mutating_arguments_does_not_affect_other_tests(runner, find_max):
    run = run_body(runner, find_max, "    m = max(numbers)\n    numbers.clear()\n    return m\n")
    assert run.all_passed


def test_bool_is_not_accepted_for_int():
    assert not values_match(1, True)
    assert values_match(4.0, 4)
    assert not values_match([1, 2], (1, 2))


# Each safety layer, probed with the static check switched off.

def test_static_check_rejects_dangerous_imports(runner, find_max):
    run = runner.run(find_max, "import os\n" + HEADER + "    return 1\n")
    assert run.status == REJECTED and "'os'" in run.message


@pytest.mark.parametrize("body", [
    "    import subprocess\n    return subprocess.run(['/bin/echo', 'x']).returncode\n",
    "    import os\n    return os.system('echo x')\n",
    "    import socket\n    socket.create_connection(('1.1.1.1', 443), timeout=1)\n",
    "    return open('/etc/hosts', 'w').write('x')\n",
    "    import os\n    return os.listdir('/Users')\n",
])
def test_runtime_layers_refuse_dangerous_operations(runner, find_max, body):
    run = run_body(runner, find_max, body, precheck=False)
    o = run.outcome("T1")
    assert o.status == ERROR and o.error_type == "PermissionError", o.summary()


def test_environment_secrets_are_not_visible_to_student_code(runner, find_max, monkeypatch):
    monkeypatch.setenv("CODEMENTOR_TEST_SECRET", "sk-test-secret")
    run = run_body(runner, find_max, "    import os\n    return repr(dict(os.environ))\n", precheck=False)
    assert "sk-test-secret" not in run.outcome("T1").actual_repr


@pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS only")
def test_os_sandbox_blocks_reads_under_users(runner, tmp_path):
    """The OS layer on its own, without the audit hook."""
    workdir = str(tmp_path.resolve())
    profile = runner._sandbox_profile(workdir)
    code = "import os\ntry:\n    os.listdir('/Users')\n    print('allowed')\nexcept PermissionError:\n    print('blocked')\n"
    out = subprocess.run(["/usr/bin/sandbox-exec", "-p", profile, runner.python, "-I", "-S", "-c", code],
                         cwd=workdir, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert out.stdout.strip() == "blocked"

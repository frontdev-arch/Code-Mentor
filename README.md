# CodeMentor

Code Mentors overall aim is a Python debugging tutor for beginners with three hint levels and execution results shown separately from AI interpretation. Stage 2 snapshot contains the exercise bank, restricted test runner and checks for hint levels and content. It does not yet include the complete tutor workflow or an interface.

README prose word count: 1051 words (excludes fenced commands and the count line, includes headings/table text.)

## About this repository

This repository imports a locally developed prototype in stages. Stage 1 imported the exercise bank and restricted test runner. Stage 2 adds hint controls, reply checks and tests across the exercise bank.

## Project status

| Part                                                                  | Status in this snapshot        |
| --------------------------------------------------------------------- | ------------------------------ |
| 10 debugging exercises with tests, bug metadata and pre written hints | Included                       |
| Test runner with restrictions on what student code can do             | Included                       |
| Hint levels, reply schema and hint policy checker                     | Included |
| Tutor pipeline with a simulated AI and scripted demonstrations        | Not included in this snapshot  |
| Interface (`app.py`)                                                  | Not included in this snapshot  |

## Technology

- **Python 3.12 on macOS**: the configuration tested locally. The runner uses only the standard library.
- The runner relies on operating-system features that are unavailable on Windows. Other platforms and Python versions have not been tested here.
- **pytest**: all 135 tests in this snapshot passed in the latest check.

## Running it

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest             
```

This snapshot has no application interface

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

## Development decisions

- The expected answers are kept separate from the student code being run. The runner compares the returned answers with these expected results. This separation alone does not guarantee that deliberately harmful code cannot interfere with a result.
- Tests check the restrictions by trying to launch another program, make a network connection, write a file and list user home folders.
- The waiting time was shortened before stopping a test because code stuck in an endless loop took too long to report back.

### Stage 2: hint controls and checks

This import adds three components from the local prototype:

- `codementor/hint_controller.py` manages three hint levels: concept, location and likely fault. More detail requires an explicit request. A change in which tests fail resets the next hint to the first level so that help does not carry over unchanged to a different problem.
- `codementor/schema.py` checks that a reply contains the required information in the expected format. This catches incomplete or wrongly formatted replies before their content is checked.
- `codementor/policy.py` checks hints for the requested level, solution disclosure, references to test results and unsupported claims. Rejection summaries avoid repeating text that could reveal an answer.

The expanded suite passed all 135 tests in the latest check. It covers all ten exercise starters and reference solutions, pre-written hints, level changes and examples of acceptable and rejected replies. These checks make the components inspectable before the complete tutor workflow is imported. 

The interface, simulated tutor workflow and illustrated demonstrations are outside this snapshot.


## Limitations

- The runner is intended for exercises on a local computer, not an online service that runs code from unknown users.
- macOS provides extra protection. The available restrictions depend on the operating system.
- Passing the supplied tests does not mean the code will work correctly for every possible input.
- Hint checks use rules that recognise particular wording. They can miss a reworded solution or an incorrect explanation, so passing the checks does not prove that a hint is correct.
- The simulated tutor workflow and interface cannot be run from this snapshot.

## AI assistance

I used Claude Code to produce the ten debugging exercises, their bug metadata and pre-written hints, and the Python runner and automated test code. In addition to that, I used Claude Code to produce the hint controller, reply validation, hint-content checker and accompanying automated tests.

I then ran the Stage 1 test suite and checked the results, confirming that all 18 tests
passed. These tests cover reported results, syntax and loading errors, timeouts, argument mutation, selected restricted operations and exclusion of an environment test secret. This checks runner behaviour primarily using exercise 1. It does not establish that every exercise or hint is correct or that the runner is secure against arbitrary hostile code. I also ran the expanded test suite and checked the results, confirming that all 135 tests passed. These tests cover hint-level changes, incomplete replies, examples of unsuitable hints and checks across all ten exercises.


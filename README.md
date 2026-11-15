# CodeMentor

Code Mentors overall aim is a Python debugging tutor for beginners with three hint levels and execution results shown separately from AI interpretation. This snapshot contains only the exercise bank and restricted test runner. It does not provide hints or an interface.

README prose word count: 881 words (excludes fenced commands and the count line, includes headings/table text.)

## About this repository

This repository imports a locally developed prototype in stages. This snapshot contains the exercise bank and restricted test runner.

## Project status

| Part                                                                  | Status in this snapshot        |
| --------------------------------------------------------------------- | ------------------------------ |
| 10 debugging exercises with tests, bug metadata and pre written hints | Included                       |
| Test runner with restrictions on what student code can do             | Included                       |
| Hint levels, reply schema and hint policy checker                     | Not included in this snap shot |
| Tutor pipeline with a simulated AI and scripted demonstrations        | Not included in this snapshot  |
| Interface (`app.py`)                                                  | Not included in this snapshot  |

## Technology

- **Python 3.12 on macOS**: the configuration tested locally. The runner uses only the standard library.
- The runner relies on operating-system features that are unavailable on Windows. Other platforms and Python versions have not been tested here.
- **pytest**: all 18 tests in this snapshot passed in the latest local check.

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

`codementor/exercises.py` loads each folder and checks that key information is present, test names are unique and all three hint levels are included. It also checks that the text matching rules can be read. These checks do not catch every possible problem with an exercise. The hints and matching rules are used by the hint checker which should be available for commit in the next stage.

`tests/test_runner.py` uses exercise 1 to check that results and errors are reported correctly. Code that takes too long is stopped and changes to test inputs do not affect other tests. It also checks restrictions on launching programs making network connections and accessing files and checks that a sample secret setting is not passed to student code. 

`tests/test_exercises.py`  which runs every starter and solution through the runner arrives in import commit 2 because it also checks the hints against the policy checker.

## How the runner works

The runner runs student code separately from the tutor and applies five checks and restrictions:

1. **Check before running.** The runner checks the code for syntax errors and blocks imports that are not allowed for these exercises.
2. **Separate execution.** Each run starts a separate copy of Python in a temporary folder, with only the settings it needs and no keyboard input.
3. **Time and resource limits.** The runner stops code that takes too long and limits its use of computer resources where the operating system supports this.
4. **Checks while running.** Python checks block selected actions, including starting other programs and making network connections. File access is limited to the temporary run folder and files Python needs, with an exception for the system file used to discard output. These checks do not provide complete protection against harmful code.
5. **macOS protection.** The operating system adds restrictions on network access, launching other programs, changing files outside the temporary run folder and reading files in user home folders.

## Development decisions

- The expected answers are kept separate from the student code being run. The runner compares the returned answers with these expected results. This separation alone does not guarantee that deliberately harmful code cannot interfere with a result.
- Tests check the restrictions by trying to launch another program, make a network connection, write a file and list user home folders.
- The waiting time was shortened before stopping a test because code stuck in an endless loop took too long to report back.

The 18 Stage 1 tests passed in the latest local check. They check runner behaviour primarily on
exercise 1, not every starter, reference solution or hint in the ten-exercise bank. Full-bank and
policy validation belong to the complete prototypes test suite.

The report also describes changes to submitting code, explaining rejected hints without revealing answers, checking hint levels and labelling references to test results. Those features and their tests are outside this snapshot and will be documented in later commits. 


## Limitations

- The runner is intended for exercises on a local computer, not an online service that runs code from unknown users.
- macOS provides extra protection; the available restrictions depend on the operating system.
- Passing the supplied tests does not mean the code will work correctly for every possible input.
- Hint control, policy checking, simulated dialogue and the interface cannot be inspected or run from this snapshot.

## AI assistance

I used Claude Code to produce the ten debugging exercises, their bug metadata and pre-written
hints, and the Python runner and automated test code. I used this output as the implementation
basis for Stage 1.

I then ran the Stage 1 test suite and checked the results, confirming that all 18 tests
passed. These tests cover reported results, syntax and loading errors, timeouts, argument
mutation, selected restricted operations and exclusion of an environment test secret. This
checks runner behaviour primarily using exercise 1. It does not establish that every exercise
or hint is correct or that the runner is secure against arbitrary hostile code.


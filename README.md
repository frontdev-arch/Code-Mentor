# CodeMentor

Code Mentors overall aim is a Python debugging tutor for beginners with three hint levels and execution results shown separately from AI interpretation. This Stage 3 snapshot includes the complete local prototype: exercises, test runner, hint checks, interface and repeatable demonstrations. Hints are pre-written or simulated using fixed replies.

README prose word count: 1388 words (excludes fenced commands and the count line, includes headings/table text.)

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

## Development decisions

- The expected answers are kept separate from the student code being run. The runner compares the returned answers with these expected results. This separation alone does not guarantee that deliberately harmful code cannot interfere with a result.
- Tests check the restrictions by trying to launch another program, make a network connection, write a file and list user home folders.
- The waiting time was shortened before stopping a test because code stuck in an endless loop took too long to report back.

### Stage 2: hint controls and checks

This import adds three components from the local prototype:

- `codementor/hint_controller.py` manages three hint levels: concept, location and likely fault. More detail requires an explicit request. A change in which tests fail resets the next hint to the first level so that help does not carry over unchanged to a different problem.
- `codementor/schema.py` checks that a reply contains the required information in the expected format. This catches incomplete or wrongly formatted replies before their content is checked.
- `codementor/policy.py` checks hints for the requested level, solution disclosure, references to test results and unsupported claims. Rejection summaries avoid repeating text that could reveal an answer.

At the Stage 2 import, the expanded suite passed all 135 tests. It covers all ten exercise starters and reference solutions, pre-written hints, level changes and examples of acceptable and rejected replies. These checks make the components inspectable before the complete tutor workflow is imported.

### Stage 3: complete local interaction

- `codementor/tutor.py` connects test results, hint levels and reply checks. It retries rejected replies and uses pre-written guidance when suitable replies are unavailable, so the interaction can continue.
- `app.py` adds the interface. Code and questions are submitted together so a hint uses the current input. Test results appear separately from the tutor's interpretation. A reference to a failing test is labelled as a citation, not proof that the explanation is correct.
- `codementor/providers.py` supplies fixed simulated replies, while `prompts.py` prepares the request information. Rejection feedback avoids repeating text that could reveal a solution.
- `config.py` selects the mode and `eventlog.py` records runs and hint requests. Local records are saved in `logs/`, which Git ignores.
- `demo/` includes a rejected solution followed by an acceptable hint, and a wrong diagnosis that cites a real failing test. These demonstrate both the checks and their limits.

The complete suite passed **159 tests** after this import. Added tests cover retries, fallback hints, current-code checks, safe rejection feedback and both demonstration scripts. A separate interface smoke check loaded the app, ran an exercise and displayed a Level 1 hint. This is not a full usability evaluation.

Earlier imports: [Stage 1](https://github.com/frontdev-arch/Code-Mentor/commit/d54cfbd) and [Stage 2](https://github.com/frontdev-arch/Code-Mentor/commit/3b03f05).

## Report and illustrations

- [Project report](docs/Assignment%202%20report.docx): explains the design and interaction. Its submitted-commit field still needs the final submission version.
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

I used Claude Code to produce the ten debugging exercises, their bug metadata and pre-written hints, and the Python runner and automated test code. In addition to that, I used Claude Code to produce the hint controller, reply validation, hint-content checker and accompanying automated tests.

I then ran the Stage 1 test suite and checked the results, confirming that all 18 tests
passed. These tests cover reported results, syntax and loading errors, timeouts, argument mutation, selected restricted operations and exclusion of an environment test secret. This checks runner behaviour primarily using exercise 1. It does not establish that every exercise or hint is correct or that the runner is secure against arbitrary hostile code. I also ran the expanded test suite and checked the results, confirming that all 135 tests passed. These tests cover hint-level changes, incomplete replies, examples of unsuitable hints and checks across all ten exercises.


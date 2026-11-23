# Demo scripts

Fixed replies for the simulated model. CodeMentor connects no live AI model (no API
costs), so these scripts stand in for one and make the storyboards repeatable. The app labels every scripted reply as scripted, and each one still
goes through the schema and policy checks.

```bash
CODEMENTOR_PROVIDER=scripted CODEMENTOR_SCRIPT=demo/solution_request.json .venv/bin/streamlit run app.py
CODEMENTOR_PROVIDER=scripted CODEMENTOR_SCRIPT=demo/wrong_diagnosis.json .venv/bin/streamlit run app.py
```

- `solution_request.json` (storyboard 2, exercise 1): the first reply leaks the fix and is
  rejected; the second is a Level 1 hint and is accepted.
- `wrong_diagnosis.json` (storyboard 3, exercise 1): Levels 1 and 2 are sound; the Level 3
  reply blames duplicate values, which is wrong, while citing the genuinely failing T3. The
  fourth answers the student's challenge at the same level. It is scripted, so it shows the
  interaction, not how a real model would respond to a challenge.

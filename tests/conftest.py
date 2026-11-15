import json

import pytest

from codementor.exercises import load_exercises
from codementor.runner import TestRunner


@pytest.fixture(scope="session")
def exercises():
    return {e.id: e for e in load_exercises()}


@pytest.fixture(scope="session")
def runner():
    return TestRunner()


@pytest.fixture(scope="session")
def find_max(exercises):
    return exercises["ex01_find_max"]


@pytest.fixture(scope="session")
def starter_run(runner, find_max):
    return runner.run(find_max, find_max.starter_code)


def hint_json(hint, level, evidence=("T3",), unverified=False, concept="initialisation"):
    return json.dumps({"hint": hint, "target_concept": concept, "level": level,
                       "evidence_ids": list(evidence), "has_unverified_interpretation": unverified,
                       "rationale": "test"})

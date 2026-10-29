from dataclasses import dataclass

SEED = 20261022

MODES = {
    "starter": {
        "instructors": 2,
        "courses": 3,
        "learners": 20,
        "assignments": 8,
        "target_submissions": 40,
        "criteria_per_rubric": 3,
    },
    "full": {
        "instructors": 20,
        "courses": 50,
        "learners": 10_000,
        "assignments": 1_000,
        "target_submissions": 30_000,
        "criteria_per_rubric": 4,
    },
}


@dataclass(frozen=True)
class GeneratorConfig:
    mode: str
    seed: int
    instructors: int
    courses: int
    learners: int
    assignments: int
    target_submissions: int
    criteria_per_rubric: int


def resolve_config(mode: str, seed: int = SEED) -> GeneratorConfig:
    if mode not in MODES:
        raise ValueError("mode must be starter or full")
    payload = MODES[mode]
    return GeneratorConfig(mode=mode, seed=seed, **payload)

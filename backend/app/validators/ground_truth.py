import json
from pathlib import Path

SCENARIOS = [
    {
        "issue_type": "unenrolled_submission",
        "ground_truth": "anomaly",
        "affected_entity_type": "submission",
        "affected_entity_id": "FIXTURE",
        "expected_behavior": "Reject at application layer; detect in offline validation",
        "explanation": "A submission exists for a learner who is not enrolled in the course.",
    },
    {
        "issue_type": "grade_exceeds_rubric_max",
        "ground_truth": "anomaly",
        "affected_entity_type": "grade",
        "affected_entity_id": "FIXTURE",
        "expected_behavior": "Reject invalid criterion/raw scores",
        "explanation": "A posted grade has a raw or criterion score above the rubric maximum.",
    },
    {
        "issue_type": "duplicate_late_penalty",
        "ground_truth": "anomaly",
        "affected_entity_type": "grade_penalty",
        "affected_entity_id": "FIXTURE",
        "expected_behavior": "Apply each penalty at most once per submission version",
        "explanation": "Two late penalties are recorded for the same submission.",
    },
    {
        "issue_type": "appeal_grade_change_without_audit",
        "ground_truth": "anomaly",
        "affected_entity_type": "appeal",
        "affected_entity_id": "FIXTURE",
        "expected_behavior": "Commit grade change and audit atomically",
        "explanation": "An approved appeal changed a grade without a matching audit event.",
    },
]


def labelled_scenarios(anomalies: list[dict]) -> list[dict]:
    """Merge the injected rows (real entity ids) into the scenario descriptions."""
    by_type = {row["issue_type"]: row for row in SCENARIOS}
    rows = []
    for item in anomalies:
        base = by_type[item["issue_type"]]
        rows.append(
            {
                **base,
                "affected_entity_type": item["affected_entity_type"],
                "affected_entity_id": str(item["affected_entity_id"]),
            }
        )
    return rows


def write_ground_truth_templates(directory: Path, anomalies: list[dict] | None = None) -> None:
    """Write evaluation labels. Without `anomalies` the ids stay as FIXTURE placeholders."""
    rows_out = labelled_scenarios(anomalies) if anomalies else SCENARIOS
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "ground_truth.json").write_text(json.dumps(rows_out, indent=2), encoding="utf-8")
    lines = [
        "issue_type,ground_truth,affected_entity_type,affected_entity_id,expected_behavior,explanation"
    ]
    for row in rows_out:
        lines.append(
            ",".join(
                [
                    row["issue_type"],
                    row["ground_truth"],
                    row["affected_entity_type"],
                    row["affected_entity_id"],
                    '"' + row["expected_behavior"].replace('"', "'") + '"',
                    '"' + row["explanation"].replace('"', "'") + '"',
                ]
            )
        )
    (directory / "ground_truth.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (directory / "README.md").write_text(
        "These labels are evaluation-only. The detector never reads this file as a feature source.\n",
        encoding="utf-8",
    )

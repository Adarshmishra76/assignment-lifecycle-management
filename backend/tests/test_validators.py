"""Offline validator: each required anomaly is detected, clean data passes, ground truth is scored."""
import csv
import json
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.time import utcnow
from app.models import Assignment, AuditEvent, Grade, RubricScore, Submission
from app.validators.engine import _duplicate_penalties, compare_to_ground_truth, validate_database
from app.validators.ground_truth import SCENARIOS, write_ground_truth_templates
from tests.helpers import API

REQUIRED_ANOMALIES = {
    "unenrolled_submission",
    "grade_exceeds_rubric_max",
    "duplicate_late_penalty",
    "appeal_grade_change_without_audit",
}


def _types(report):
    return {finding["issue_type"] for finding in report["findings"]}


def _finding(report, issue_type):
    return [f for f in report["findings"] if f["issue_type"] == issue_type]


# ---- clean data ---------------------------------------------------------------------------------
def test_database_built_through_the_api_validates_clean(world):
    world.graded_submission(values=(50, 30))
    world.graded_submission(values=(60, 40), late=True)
    report = validate_database(world.db)
    assert report["status"] == "pass"
    assert report["anomaly_count"] == 0
    assert report["by_type"] == {}


def test_a_grade_exactly_at_the_rubric_maximum_is_not_flagged(world):
    world.graded_submission(values=(60, 40))
    assert validate_database(world.db)["status"] == "pass"


def test_an_approved_appeal_with_its_audit_event_is_clean(world):
    case = world.graded_submission()
    world.approved_appeal(case)
    assert validate_database(world.db)["status"] == "pass"


# ---- injected anomalies ---------------------------------------------------------------------------
def test_detects_submission_by_unenrolled_learner(world):
    case = world.graded_submission()
    outsider = world.add_learner(enroll=False)
    world.db.expire_all()
    version_id = world.db.get(Assignment, case.assignment.id).current_version_id
    rogue = Submission(
        public_id="SUB-9999999",
        assignment_id=case.assignment.id,
        assignment_version_id=version_id,
        learner_id=outsider.learner_id,
        version_number=1,
        submitted_at=utcnow(),
        is_late=False,
        status="submitted",
    )
    world.db.add(rogue)
    world.db.commit()

    report = validate_database(world.db)

    assert report["by_type"] == {"unenrolled_submission": 1}
    found = _finding(report, "unenrolled_submission")[0]
    assert (found["affected_entity_type"], found["affected_entity_id"]) == ("submission", rogue.id)


def test_detects_scores_above_the_rubric_maximum(world):
    case = world.graded_submission(values=(50, 30))
    world.db.expire_all()
    grade = world.db.get(Grade, case.grade_id)
    grade.raw_score = Decimal("120.00")  # rubric maximum is 100
    score = world.db.query(RubricScore).filter(RubricScore.grade_id == grade.id).first()
    score.score = Decimal("75.00")  # criterion maximum is 60 or 40
    world.db.commit()

    report = validate_database(world.db)

    entities = {(f["affected_entity_type"], f["affected_entity_id"]) for f in _finding(report, "grade_exceeds_rubric_max")}
    assert ("grade", grade.id) in entities
    assert ("rubric_score", score.id) in entities


def test_detects_approved_appeal_whose_grade_change_has_no_audit_event(world):
    case = world.graded_submission()
    appeal = world.approved_appeal(case)
    world.db.query(AuditEvent).filter(
        AuditEvent.entity_type == "grade", AuditEvent.entity_id == appeal["resulting_grade_id"]
    ).delete()
    world.db.commit()

    report = validate_database(world.db)

    assert report["by_type"] == {"appeal_grade_change_without_audit": 1}
    assert _finding(report, "appeal_grade_change_without_audit")[0]["affected_entity_id"] == appeal["id"]


def test_detects_is_late_flag_that_disagrees_with_the_deadline(world):
    case = world.graded_submission()
    world.db.expire_all()
    world.db.get(Submission, case.submission_id).is_late = True
    world.db.commit()
    assert "deadline_mismatch" in _types(validate_database(world.db))


def test_duplicate_penalty_check_flags_the_second_row_for_a_submission():
    """The unique constraint makes this state unreachable in SQL, so test the detector directly."""
    rows = [
        SimpleNamespace(id=1, submission_id=7, penalty_type="late"),
        SimpleNamespace(id=2, submission_id=7, penalty_type="late"),
        SimpleNamespace(id=3, submission_id=8, penalty_type="late"),
    ]

    class FakeScalars:
        def all(self):
            return rows

    class FakeDb:
        def scalars(self, *_args, **_kwargs):
            return FakeScalars()

    findings = _duplicate_penalties(FakeDb())
    assert [(f["issue_type"], f["affected_entity_id"]) for f in findings] == [("duplicate_late_penalty", 2)]


def test_detector_never_reads_ground_truth_files(world, monkeypatch):
    world.graded_submission()
    real_open, real_read = Path.open, Path.read_text

    def guarded_open(self, *args, **kwargs):
        assert "ground_truth" not in str(self), "validator opened a ground-truth file"
        return real_open(self, *args, **kwargs)

    def guarded_read(self, *args, **kwargs):
        assert "ground_truth" not in str(self), "validator read a ground-truth file"
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)
    monkeypatch.setattr(Path, "read_text", guarded_read)
    assert validate_database(world.db)["status"] == "pass"


# ---- ground-truth scoring --------------------------------------------------------------------------
def _label(issue_type, entity_id, truth="anomaly"):
    return {"issue_type": issue_type, "affected_entity_id": entity_id, "ground_truth": truth}


def _found(issue_type, entity_id):
    return {"issue_type": issue_type, "affected_entity_id": entity_id}


def test_perfect_detection_scores_one():
    labels = [_label("unenrolled_submission", "4"), _label("grade_exceeds_rubric_max", "9")]
    result = compare_to_ground_truth([_found("unenrolled_submission", 4), _found("grade_exceeds_rubric_max", 9)], labels)
    assert (result["true_positive"], result["false_positive"], result["false_negative"]) == (2, 0, 0)
    assert (result["precision"], result["recall"], result["f1"]) == (1, 1, 1)


def test_false_positive_and_false_negative_are_counted():
    labels = [_label("unenrolled_submission", "4"), _label("duplicate_late_penalty", "2")]
    found = [_found("unenrolled_submission", 4), _found("unenrolled_submission", 77)]
    result = compare_to_ground_truth(found, labels)
    assert (result["true_positive"], result["false_positive"], result["false_negative"]) == (1, 1, 1)
    assert result["precision"] == 0.5 and result["recall"] == 0.5 and result["f1"] == 0.5


def test_right_entity_with_wrong_issue_type_does_not_count():
    result = compare_to_ground_truth([_found("deadline_mismatch", 4)], [_label("unenrolled_submission", "4")])
    assert (result["true_positive"], result["false_positive"], result["false_negative"]) == (0, 1, 1)


def test_non_anomaly_labels_are_ignored_and_empty_inputs_score_zero():
    result = compare_to_ground_truth([], [_label("unenrolled_submission", "4", truth="normal")])
    assert (result["true_positive"], result["false_negative"]) == (0, 0)
    assert (result["precision"], result["recall"], result["f1"]) == (0, 0, 0)


def test_ground_truth_templates_cover_exactly_the_four_required_anomalies(tmp_path):
    write_ground_truth_templates(tmp_path)

    data = json.loads((tmp_path / "ground_truth.json").read_text(encoding="utf-8"))
    assert {row["issue_type"] for row in data} == REQUIRED_ANOMALIES
    assert len(data) == len(SCENARIOS) == 4

    with (tmp_path / "ground_truth.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["issue_type"] for row in rows} == REQUIRED_ANOMALIES
    assert {row["ground_truth"] for row in rows} == {"anomaly"}
    assert set(rows[0]) == {
        "issue_type", "ground_truth", "affected_entity_type", "affected_entity_id", "expected_behavior", "explanation",
    }


def test_committed_ground_truth_file_lists_the_required_anomalies():
    path = Path(__file__).resolve().parents[2] / "data" / "ground_truth" / "ground_truth.json"
    if not path.exists():
        pytest.skip("ground_truth.json is not present in this checkout")
    assert {row["issue_type"] for row in json.loads(path.read_text(encoding="utf-8"))} == REQUIRED_ANOMALIES


# ---- API access ------------------------------------------------------------------------------------
def test_validate_endpoint_is_limited_to_admins(world, monkeypatch):
    monkeypatch.setattr("app.api.v1.datasets.write_validation_report", lambda report: None)
    learner = world.add_learner()
    assert world.client.post(f"{API}/datasets/validate", headers=learner.headers).status_code == 403
    assert world.client.post(f"{API}/datasets/validate", headers=world.inst_h).status_code == 403
    ok = world.client.post(f"{API}/datasets/validate", headers=world.admin_h)
    assert ok.status_code == 200
    assert ok.json()["status"] == "pass"


# ---- penalty taken off more than once ------------------------------------------------------------------
def test_detects_a_late_penalty_that_was_taken_off_twice(world):
    case = world.graded_submission(late=True, values=(50, 30))
    world.db.expire_all()
    grade = world.db.get(Grade, case.grade_id)
    grade.final_score = grade.raw_score - 2 * grade.late_penalty_amount  # 80 - 16 = 64 instead of 72
    world.db.commit()

    report = validate_database(world.db)

    assert report["by_type"] == {"duplicate_late_penalty": 1}
    found = _finding(report, "duplicate_late_penalty")[0]
    assert (found["affected_entity_type"], found["affected_entity_id"]) == ("grade", case.grade_id)


def test_a_revised_late_grade_is_not_mistaken_for_a_double_penalty(world):
    case = world.graded_submission(late=True, values=(50, 30))
    world.approved_appeal(case, values=(60, 30))  # superseded grade (72) and revised grade (81) both stay in the table
    assert validate_database(world.db)["status"] == "pass"

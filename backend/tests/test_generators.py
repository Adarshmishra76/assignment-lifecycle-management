"""Synthetic data generator: determinism for seed 20261022, volumes, exports and checksums."""
import csv
import json
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import func, select

import app.core.database as database
from app.generators import pipeline
from app.generators.checksums import file_checksum, logical_checksum
from app.generators.config import MODES, SEED, resolve_config
from app.generators.pipeline import ENTITY_QUERIES, generate_dataset
from app.models import Submission
from app.validators.engine import compare_to_ground_truth, validate_database

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def restore_engine():
    """These tests build their own throw-away databases; put the global engine back afterwards."""
    saved = (database.engine, database.SessionLocal)
    opened = []
    yield opened
    for engine in opened:
        engine.dispose()
    database.engine, database.SessionLocal = saved


def _fresh_session(tmp_path, opened, name):
    engine = database.configure_engine(f"sqlite:///{tmp_path}/{name}.db")
    opened.append(engine)
    database.Base.metadata.create_all(engine)
    return database.SessionLocal()


def _table_checksums(session):
    return {
        name: logical_checksum([pipeline._row_dict(obj) for obj in session.scalars(select(model).order_by(model.id))])
        for name, model in ENTITY_QUERIES.items()
    }


# ---- configuration ------------------------------------------------------------------------------
def test_default_seed_is_the_agreed_one():
    assert SEED == 20261022
    assert resolve_config("starter").seed == 20261022


def test_full_mode_targets_the_required_volumes():
    full = resolve_config("full")
    assert (full.assignments, full.learners, full.target_submissions) == (1_000, 10_000, 30_000)
    assert MODES["starter"]["learners"] < MODES["full"]["learners"]


def test_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        resolve_config("huge")


# ---- determinism --------------------------------------------------------------------------------
def test_same_seed_yields_identical_data(tmp_path, restore_engine):
    first = _fresh_session(tmp_path, restore_engine, "one")
    first_result = generate_dataset(first, mode="starter", seed=20261022, export=False)
    first_sums = _table_checksums(first)
    first.close()

    second = _fresh_session(tmp_path, restore_engine, "two")
    second_result = generate_dataset(second, mode="starter", seed=20261022, export=False)
    second_sums = _table_checksums(second)
    second.close()

    assert first_result["counts"] == second_result["counts"]
    assert first_sums == second_sums
    assert all(len(value) == 64 for value in first_sums.values())


def test_different_seed_yields_different_data(tmp_path, restore_engine):
    first = _fresh_session(tmp_path, restore_engine, "seed_a")
    generate_dataset(first, mode="starter", seed=20261022, export=False)
    sums_a = _table_checksums(first)
    first.close()

    second = _fresh_session(tmp_path, restore_engine, "seed_b")
    generate_dataset(second, mode="starter", seed=7, export=False)
    sums_b = _table_checksums(second)
    second.close()

    assert sums_a != sums_b


def test_starter_counts_match_the_committed_manifest(tmp_path, restore_engine):
    manifest_path = PROJECT_ROOT / "data" / "manifests" / "starter_20261022.json"
    if not manifest_path.exists():
        pytest.skip("starter manifest is not present in this checkout")
    session = _fresh_session(tmp_path, restore_engine, "manifest")
    result = generate_dataset(session, mode="starter", seed=20261022, export=False)
    session.close()
    # Counts are stable; content checksums are not compared because Faker output can differ between versions.
    committed = json.loads(manifest_path.read_text(encoding="utf-8"))["counts"]
    assert result["counts"] == committed, (
        "committed starter data is out of date; regenerate it with "
        "`python -m app.generators.cli --mode starter --force` from backend/"
    )


def test_committed_ground_truth_uses_real_row_ids():
    path = PROJECT_ROOT / "data" / "ground_truth" / "ground_truth.json"
    if not path.exists():
        pytest.skip("ground_truth.json is not present in this checkout")
    labels = json.loads(path.read_text(encoding="utf-8"))
    assert all(str(row["affected_entity_id"]).isdigit() for row in labels), (
        "committed labels still contain FIXTURE placeholders; regenerate the starter data"
    )


def test_non_empty_database_is_refused_without_force(tmp_path, restore_engine):
    session = _fresh_session(tmp_path, restore_engine, "force")
    generate_dataset(session, mode="starter", export=False)
    before = session.scalar(select(func.count()).select_from(Submission))
    with pytest.raises(ValueError, match="not empty"):
        generate_dataset(session, mode="starter", export=False)
    assert session.scalar(select(func.count()).select_from(Submission)) == before
    session.close()


def test_generated_references_are_consistent(tmp_path, restore_engine):
    session = _fresh_session(tmp_path, restore_engine, "refs")
    counts = generate_dataset(session, mode="starter", export=False)["counts"]
    starter = MODES["starter"]
    assert counts["learners"] == starter["learners"]
    assert counts["assignments"] == counts["rubrics"] == counts["assignment_versions"] == starter["assignments"]
    assert counts["rubric_criteria"] == counts["rubrics"] * starter["criteria_per_rubric"]
    assert counts["users"] == 3 + starter["instructors"] + starter["learners"]
    session.close()


# ---- export -------------------------------------------------------------------------------------
def _export(tmp_path, restore_engine, monkeypatch, name):
    out = tmp_path / f"data_{name}"
    monkeypatch.setattr(pipeline, "DATA", out)
    session = _fresh_session(tmp_path, restore_engine, name)
    result = generate_dataset(session, mode="starter", seed=20261022, export=True)
    session.close()
    return out, result


def test_export_writes_csv_json_manifest_and_matching_checksums(tmp_path, restore_engine, monkeypatch):
    out, result = _export(tmp_path, restore_engine, monkeypatch, "export")
    starter = out / "starter"
    manifest = json.loads((starter / "manifest.json").read_text(encoding="utf-8"))
    assert manifest == json.loads((out / "manifests" / "starter_20261022.json").read_text(encoding="utf-8"))
    assert manifest["seed"] == 20261022 and manifest["mode"] == "starter"

    for name in ENTITY_QUERIES:
        csv_path, json_path = starter / f"{name}.csv", starter / f"{name}.json"
        assert csv_path.exists() and json_path.exists(), name
        expected = result["counts"][name]
        assert len(pd.read_csv(csv_path)) == expected
        assert len(json.loads(json_path.read_text(encoding="utf-8"))) == expected
        entry = manifest["checksums"][name]
        assert entry["row_count"] == expected
        assert entry["csv_sha256"] == file_checksum(csv_path)
        assert entry["json_sha256"] == file_checksum(json_path)


def test_export_logical_checksums_are_reproducible(tmp_path, restore_engine, monkeypatch):
    _, first = _export(tmp_path, restore_engine, monkeypatch, "repeat_a")
    _, second = _export(tmp_path, restore_engine, monkeypatch, "repeat_b")
    logical = lambda result: {k: v["logical_sha256"] for k, v in result["export"]["checksums"].items()}  # noqa: E731
    assert logical(first) == logical(second)


def test_export_also_writes_the_ground_truth_labels(tmp_path, restore_engine, monkeypatch):
    out, _ = _export(tmp_path, restore_engine, monkeypatch, "labels")
    with (out / "ground_truth" / "ground_truth.csv").open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 4


# ---- full size (slow) ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.skipif(not os.getenv("RUN_SLOW"), reason="set RUN_SLOW=1 to generate the full dataset")
def test_full_mode_reaches_the_required_volumes(tmp_path, restore_engine):
    session = _fresh_session(tmp_path, restore_engine, "full")
    result = generate_dataset(session, mode="full", seed=20261022, export=False)
    counts = result["counts"]
    assert counts["learners"] == 10_000
    assert counts["assignments"] == 1_000
    assert session.scalar(select(func.count()).select_from(Submission)) == 30_000
    assert len(result["anomalies"]) == 4
    session.close()


# ---- injected anomalies, ground truth, volumes, SQL ----------------------------------------------------------
REQUIRED = [
    "unenrolled_submission",
    "grade_exceeds_rubric_max",
    "duplicate_late_penalty",
    "appeal_grade_change_without_audit",
]


@pytest.fixture()
def starter_export(tmp_path, restore_engine, monkeypatch):
    out = tmp_path / "data"
    monkeypatch.setattr(pipeline, "DATA", out)
    session = _fresh_session(tmp_path, restore_engine, "starter")
    result = generate_dataset(session, mode="starter", seed=20261022, export=True)
    yield SimpleNamespace(session=session, result=result, out=out)
    session.close()


def _labels(starter_export):
    with (starter_export.out / "ground_truth" / "ground_truth.csv").open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_generated_dataset_contains_each_required_anomaly_exactly_once(starter_export):
    report = validate_database(starter_export.session)
    assert report["by_type"] == {name: 1 for name in REQUIRED}


def test_ground_truth_labels_point_at_the_rows_the_validator_finds(starter_export):
    labels = _labels(starter_export)
    assert [row["issue_type"] for row in labels] == REQUIRED
    assert all(row["affected_entity_id"].isdigit() for row in labels)

    report = validate_database(starter_export.session)
    score = compare_to_ground_truth(report["findings"], labels)

    assert (score["true_positive"], score["false_positive"], score["false_negative"]) == (4, 0, 0)
    assert score["f1"] == 1


def test_anomaly_ids_are_reproducible_for_a_seed(tmp_path, restore_engine, monkeypatch):
    runs = []
    for name in ("run_a", "run_b"):
        monkeypatch.setattr(pipeline, "DATA", tmp_path / f"data_{name}")
        session = _fresh_session(tmp_path, restore_engine, name)
        runs.append(generate_dataset(session, mode="starter", seed=20261022, export=True)["anomalies"])
        session.close()
    assert runs[0] == runs[1] and len(runs[0]) == 4


def test_total_submissions_equal_the_configured_target(starter_export):
    total = starter_export.session.scalar(select(func.count()).select_from(Submission))
    assert total == MODES["starter"]["target_submissions"]
    assert starter_export.result["counts"]["submissions"] == total


def test_force_regenerates_over_an_existing_dataset(starter_export):
    session = starter_export.session
    again = generate_dataset(session, mode="starter", seed=20261022, force=True, export=False)
    assert again["counts"] == starter_export.result["counts"]
    assert again["anomalies"] == starter_export.result["anomalies"]


def test_sql_export_rebuilds_the_same_database(starter_export, tmp_path, restore_engine):
    sql = (starter_export.out / "starter" / "seed.sql").read_text(encoding="utf-8")
    assert "INSERT INTO" in sql

    engine = database.configure_engine(f"sqlite:///{tmp_path}/rebuilt.db")
    restore_engine.append(engine)
    database.Base.metadata.create_all(engine)
    raw = sqlite3.connect(tmp_path / "rebuilt.db")
    try:
        raw.executescript(sql)
        for name, model in ENTITY_QUERIES.items():
            count = raw.execute(f"SELECT COUNT(*) FROM {model.__tablename__}").fetchone()[0]
            assert count == starter_export.result["counts"][name], name
        assert raw.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        raw.close()

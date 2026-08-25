"""Tests for the used-seed registry."""

from simulation.seed_registry import load_used_seeds, record_seed


def test_load_missing_file_returns_empty(tmp_path):
    assert load_used_seeds(tmp_path / "nope.json") == []


def test_load_broken_file_returns_empty(tmp_path):
    f = tmp_path / "used.json"
    f.write_text("not json", encoding="utf-8")
    assert load_used_seeds(f) == []


def test_record_then_load(tmp_path):
    f = tmp_path / "used.json"
    assert record_seed(12345, f) is True
    assert load_used_seeds(f) == [12345]


def test_record_deduplicates(tmp_path):
    f = tmp_path / "used.json"
    record_seed(7, f)
    assert record_seed(7, f) is False
    assert load_used_seeds(f) == [7]


def test_record_keeps_sorted_unique_list(tmp_path):
    f = tmp_path / "used.json"
    record_seed(9, f)
    record_seed(3, f)
    record_seed(9, f)
    assert load_used_seeds(f) == [3, 9]

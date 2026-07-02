"""Unit tests for the SQLiteAdapter that backs the MCP tools.

Run:
    pytest
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import SQLiteAdapter, ValidationError
from init_db import create_database


@pytest.fixture()
def adapter(tmp_path):
    db_path = str(tmp_path / "test.db")
    create_database(db_path)
    return SQLiteAdapter(db_path)


def test_list_tables(adapter):
    assert set(adapter.list_tables()) == {"students", "courses", "enrollments"}


def test_get_table_schema(adapter):
    schema = adapter.get_table_schema("students")
    names = {c["name"] for c in schema}
    assert names == {"id", "name", "cohort", "email"}


def test_get_table_schema_unknown_table(adapter):
    with pytest.raises(ValidationError):
        adapter.get_table_schema("not_a_table")


def test_search_all_rows(adapter):
    result = adapter.search("students")
    assert result["count"] == 5


def test_search_with_filter(adapter):
    result = adapter.search("students", filters=[{"column": "cohort", "op": "=", "value": "A1"}])
    assert result["count"] == 3
    assert all(row["cohort"] == "A1" for row in result["rows"])


def test_search_with_in_operator(adapter):
    result = adapter.search("courses", filters=[{"column": "code", "op": "in", "value": ["CS101", "AI301"]}])
    assert result["count"] == 2


def test_search_pagination(adapter):
    result = adapter.search("students", limit=2, offset=0, order_by="id")
    assert len(result["rows"]) == 2
    assert result["rows"][0]["id"] == 1


def test_search_unknown_table_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.search("not_a_table")


def test_search_unknown_column_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.search("students", columns=["not_a_column"])


def test_search_unsupported_operator_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.search("students", filters=[{"column": "cohort", "op": "DROP TABLE", "value": "A1"}])


def test_search_limit_out_of_range_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.search("students", limit=10_000)


def test_insert_row(adapter):
    result = adapter.insert(
        "students", {"name": "Test Student", "cohort": "A1", "email": "test@example.com"}
    )
    assert result["inserted"]["name"] == "Test Student"
    assert result["row_id"] is not None

    found = adapter.search("students", filters=[{"column": "email", "op": "=", "value": "test@example.com"}])
    assert found["count"] == 1


def test_insert_empty_values_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.insert("students", {})


def test_insert_unknown_column_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.insert("students", {"not_a_column": "value"})


def test_aggregate_count(adapter):
    result = adapter.aggregate("students", "count")
    assert result["rows"][0]["value"] == 5


def test_aggregate_avg_with_group_by(adapter):
    result = adapter.aggregate("enrollments", "avg", column="score", group_by="term")
    terms = {row["term"] for row in result["rows"]}
    assert terms == {"Fall2025", "Spring2026"}


def test_aggregate_unsupported_metric_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.aggregate("students", "median", column="id")


def test_aggregate_missing_column_rejected(adapter):
    with pytest.raises(ValidationError):
        adapter.aggregate("enrollments", "avg")

"""SQLite adapter used by the MCP server.

Every method that touches SQL validates table/column/operator names against
the live schema (via sqlite_master / PRAGMA table_info) before building a
query, and always executes with bound parameters. No user-controlled string
is ever concatenated directly into SQL.
"""

import sqlite3
from typing import Any


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


ALLOWED_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "like", "in"}
ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}
MAX_LIMIT = 200


class SQLiteAdapter:
    """Thin, validated data-access layer over a SQLite database file."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> list[dict[str, Any]]:
        self._validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [
            {
                "name": row["name"],
                "type": row["type"],
                "notnull": bool(row["notnull"]),
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        ]

    # -- validation helpers -------------------------------------------------

    def _validate_table(self, table: str) -> list[str]:
        tables = self.list_tables()
        if table not in tables:
            raise ValidationError(
                f"Unknown table '{table}'. Valid tables: {', '.join(tables)}"
            )
        return tables

    def _valid_columns(self, table: str) -> set[str]:
        return {col["name"] for col in self.get_table_schema(table)}

    def _validate_columns(self, table: str, columns) -> set[str]:
        valid_cols = self._valid_columns(table)
        for col in columns:
            if col not in valid_cols:
                raise ValidationError(
                    f"Unknown column '{col}' in table '{table}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )
        return valid_cols

    def _validate_filters(self, table: str, filters):
        valid_cols = self._valid_columns(table)
        clauses = []
        params: list[Any] = []
        for f in filters or []:
            if not isinstance(f, dict) or "column" not in f or "value" not in f:
                raise ValidationError(
                    "Each filter must be an object with 'column', 'op', and 'value'."
                )
            column = f["column"]
            op = str(f.get("op", "=")).lower()
            value = f["value"]

            if column not in valid_cols:
                raise ValidationError(
                    f"Unknown column '{column}' in table '{table}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )
            if op not in ALLOWED_OPERATORS:
                raise ValidationError(
                    f"Unsupported filter operator '{op}'. "
                    f"Allowed operators: {', '.join(sorted(ALLOWED_OPERATORS))}"
                )

            if op == "in":
                if not isinstance(value, (list, tuple)) or len(value) == 0:
                    raise ValidationError(
                        f"Operator 'in' for column '{column}' requires a non-empty list value."
                    )
                placeholders = ", ".join(["?"] * len(value))
                clauses.append(f'"{column}" IN ({placeholders})')
                params.extend(value)
            elif op == "like":
                clauses.append(f'"{column}" LIKE ?')
                params.append(value)
            else:
                sql_op = "<>" if op == "!=" else op
                clauses.append(f'"{column}" {sql_op} ?')
                params.append(value)

        return clauses, params

    # -- tool operations ------------------------------------------------

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: list[dict] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        self._validate_table(table)
        valid_cols = self._valid_columns(table)

        if columns:
            self._validate_columns(table, columns)
            select_cols = ", ".join(f'"{c}"' for c in columns)
        else:
            select_cols = "*"

        where_clauses, params = self._validate_filters(table, filters)
        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        order_sql = ""
        if order_by:
            if order_by not in valid_cols:
                raise ValidationError(
                    f"Unknown order_by column '{order_by}' in table '{table}'. "
                    f"Valid columns: {', '.join(sorted(valid_cols))}"
                )
            direction = "DESC" if descending else "ASC"
            order_sql = f' ORDER BY "{order_by}" {direction}'

        try:
            limit = int(limit)
            offset = int(offset)
        except (TypeError, ValueError):
            raise ValidationError("limit and offset must be integers.")
        if limit < 1 or limit > MAX_LIMIT:
            raise ValidationError(f"limit must be between 1 and {MAX_LIMIT}.")
        if offset < 0:
            raise ValidationError("offset must be >= 0.")

        sql = f'SELECT {select_cols} FROM "{table}"{where_sql}{order_sql} LIMIT ? OFFSET ?'
        params = params + [limit, offset]

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {
            "rows": [dict(row) for row in rows],
            "count": len(rows),
            "limit": limit,
            "offset": offset,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        self._validate_table(table)
        if not values or not isinstance(values, dict):
            raise ValidationError("insert requires a non-empty 'values' object.")
        self._validate_columns(table, values.keys())

        columns = list(values.keys())
        placeholders = ", ".join(["?"] * len(columns))
        col_sql = ", ".join(f'"{c}"' for c in columns)
        sql = f'INSERT INTO "{table}" ({col_sql}) VALUES ({placeholders})'

        with self.connect() as conn:
            cursor = conn.execute(sql, [values[c] for c in columns])
            conn.commit()
            inserted_id = cursor.lastrowid
            row = conn.execute(
                f'SELECT * FROM "{table}" WHERE rowid = ?', (inserted_id,)
            ).fetchone()

        return {"inserted": dict(row) if row else values, "row_id": inserted_id}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: list[dict] | None = None,
        group_by: str | None = None,
    ) -> dict[str, Any]:
        self._validate_table(table)
        valid_cols = self._valid_columns(table)

        metric = str(metric).lower()
        if metric not in ALLOWED_METRICS:
            raise ValidationError(
                f"Unsupported metric '{metric}'. "
                f"Allowed metrics: {', '.join(sorted(ALLOWED_METRICS))}"
            )
        if metric != "count" and not column:
            raise ValidationError(f"metric '{metric}' requires a 'column'.")
        if column and column not in valid_cols:
            raise ValidationError(
                f"Unknown column '{column}' in table '{table}'. "
                f"Valid columns: {', '.join(sorted(valid_cols))}"
            )
        if group_by and group_by not in valid_cols:
            raise ValidationError(
                f"Unknown group_by column '{group_by}' in table '{table}'. "
                f"Valid columns: {', '.join(sorted(valid_cols))}"
            )

        target = f'"{column}"' if column else "*"
        metric_sql = f"{metric.upper()}({target}) AS value"
        select_sql = f'{group_by + ", " if group_by else ""}{metric_sql}'.strip()
        if group_by:
            select_sql = f'"{group_by}" AS {group_by}, {metric_sql}'

        where_clauses, params = self._validate_filters(table, filters)
        where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        group_sql = f' GROUP BY "{group_by}"' if group_by else ""

        sql = f'SELECT {select_sql} FROM "{table}"{where_sql}{group_sql}'

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {"rows": [dict(row) for row in rows]}

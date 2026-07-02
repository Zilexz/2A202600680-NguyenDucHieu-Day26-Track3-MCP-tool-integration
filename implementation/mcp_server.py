"""FastMCP server exposing a small SQLite database (students / courses /
enrollments) through search / insert / aggregate tools plus schema resources.
"""

import json
import os
import sys

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from db import SQLiteAdapter, ValidationError
from init_db import DEFAULT_DB_PATH, create_database

DB_PATH = os.environ.get("SQLITE_LAB_DB", DEFAULT_DB_PATH)

if not os.path.exists(DB_PATH):
    create_database(DB_PATH)

mcp = FastMCP("SQLite Lab MCP Server")
adapter = SQLiteAdapter(DB_PATH)


@mcp.tool(name="search")
def search(
    table: str,
    columns: list[str] | None = None,
    filters: list[dict] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict:
    """Search rows in a table.

    Args:
        table: table name (see schema://database for valid tables).
        columns: optional subset of columns to return; all columns if omitted.
        filters: optional list of {"column", "op", "value"}.
            op is one of =, !=, >, >=, <, <=, like, in.
        limit: max rows to return (1-200, default 20).
        offset: rows to skip for pagination (default 0).
        order_by: optional column to sort by.
        descending: sort descending instead of ascending.
    """
    try:
        result = adapter.search(
            table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as e:
        raise ToolError(str(e))
    return {"table": table, **result}


@mcp.tool(name="insert")
def insert(table: str, values: dict) -> dict:
    """Insert a single row into a table.

    Args:
        table: table name (see schema://database for valid tables).
        values: mapping of column name to value for the new row.
    """
    try:
        result = adapter.insert(table, values)
    except ValidationError as e:
        raise ToolError(str(e))
    return {"table": table, **result}


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: list[dict] | None = None,
    group_by: str | None = None,
) -> dict:
    """Compute an aggregate metric over a table.

    Args:
        table: table name (see schema://database for valid tables).
        metric: one of count, avg, sum, min, max.
        column: column to aggregate; required for avg/sum/min/max.
        filters: optional list of {"column", "op", "value"}.
        group_by: optional column to group results by.
    """
    try:
        result = adapter.aggregate(
            table, metric, column=column, filters=filters, group_by=group_by
        )
    except ValidationError as e:
        raise ToolError(str(e))
    return {"table": table, "metric": metric, **result}


@mcp.resource("schema://database")
def database_schema() -> str:
    """Full schema (all tables and columns) as JSON."""
    tables = adapter.list_tables()
    schema = {t: adapter.get_table_schema(t) for t in tables}
    return json.dumps(schema, indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Schema for a single table as JSON."""
    try:
        schema = adapter.get_table_schema(table_name)
    except ValidationError as e:
        raise ToolError(str(e))
    return json.dumps({table_name: schema}, indent=2)


if __name__ == "__main__":
    if "--http" in sys.argv:
        port = int(os.environ.get("PORT", 8090))
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run()

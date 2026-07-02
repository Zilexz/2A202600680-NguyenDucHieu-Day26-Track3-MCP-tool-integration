"""Repeatable verification script for mcp_server.py.

Spawns the server over stdio (like a real MCP client would) and checks:
1. the server starts and initializes
2. search / insert / aggregate are discoverable
3. schema://database and schema://table/{name} are discoverable and readable
4. valid tool calls return useful results
5. invalid tool calls return clear errors (isError=True)

Run:
    python verify_server.py
"""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

FAILURES: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {label}" + (f" - {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(label)


async def main() -> None:
    params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Server initialized.\n")

            # 1. Tool discovery
            tools_result = await session.list_tools()
            tool_names = {t.name for t in tools_result.tools}
            print("Discovered tools:", ", ".join(sorted(tool_names)))
            for name in ("search", "insert", "aggregate"):
                check(f"tool '{name}' discoverable", name in tool_names)

            # 2. Resource / resource-template discovery
            resources_result = await session.list_resources()
            templates_result = await session.list_resource_templates()
            resource_uris = {str(r.uri) for r in resources_result.resources}
            template_uris = {t.uriTemplate for t in templates_result.resourceTemplates}
            print("Discovered resources:", resource_uris or "(none)")
            print("Discovered resource templates:", template_uris or "(none)")
            check("schema://database discoverable", "schema://database" in resource_uris)
            check(
                "schema://table/{table_name} discoverable",
                "schema://table/{table_name}" in template_uris,
            )

            # 3. Read resources
            db_schema = await session.read_resource("schema://database")
            print("\nschema://database ->")
            print(db_schema.contents[0].text[:300], "...\n")
            check("schema://database readable", len(db_schema.contents) > 0)

            table_schema = await session.read_resource("schema://table/students")
            print("schema://table/students ->")
            print(table_schema.contents[0].text)
            check("schema://table/students readable", len(table_schema.contents) > 0)

            # 4. Valid tool calls
            search_result = await session.call_tool(
                "search", {"table": "students", "filters": [{"column": "cohort", "op": "=", "value": "A1"}]}
            )
            print("search(students, cohort=A1) ->", search_result.content[0].text)
            check("search valid call succeeds", not search_result.isError)

            insert_result = await session.call_tool(
                "insert",
                {
                    "table": "students",
                    "values": {"name": "Verify Bot", "cohort": "A1", "email": "verify.bot@example.com"},
                },
            )
            print("insert(students, Verify Bot) ->", insert_result.content[0].text)
            check("insert valid call succeeds", not insert_result.isError)

            aggregate_result = await session.call_tool(
                "aggregate",
                {"table": "enrollments", "metric": "avg", "column": "score", "group_by": "term"},
            )
            print("aggregate(enrollments, avg score by term) ->", aggregate_result.content[0].text)
            check("aggregate valid call succeeds", not aggregate_result.isError)

            # 5. Invalid tool calls should fail clearly
            bad_table = await session.call_tool("search", {"table": "not_a_real_table"})
            print("\nsearch(not_a_real_table) -> isError =", bad_table.isError)
            check("search on unknown table is rejected", bad_table.isError)

            bad_column = await session.call_tool(
                "search", {"table": "students", "filters": [{"column": "not_a_column", "op": "=", "value": 1}]}
            )
            check("search on unknown column is rejected", bad_column.isError)

            bad_operator = await session.call_tool(
                "search", {"table": "students", "filters": [{"column": "cohort", "op": "DROP", "value": "A1"}]}
            )
            check("search with unsupported operator is rejected", bad_operator.isError)

            bad_aggregate = await session.call_tool(
                "aggregate", {"table": "students", "metric": "median", "column": "id"}
            )
            check("aggregate with unsupported metric is rejected", bad_aggregate.isError)

            empty_insert = await session.call_tool("insert", {"table": "students", "values": {}})
            check("insert with empty values is rejected", empty_insert.isError)

    print("\n" + "=" * 50)
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for f in FAILURES:
            print(" -", f)
        sys.exit(1)
    print("All checks passed.")


if __name__ == "__main__":
    asyncio.run(main())

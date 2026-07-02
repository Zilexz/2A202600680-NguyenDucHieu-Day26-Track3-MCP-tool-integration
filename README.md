# Lab: Build a Database MCP Server with FastMCP and SQLite

## Goal

Build a Model Context Protocol (MCP) server using FastMCP that exposes a small database through:

- `search`
- `insert`
- `aggregate`

You must also expose the database schema as an MCP resource, test the server with Inspector or equivalent tooling, and show the server working from at least one MCP client.

## Learning Outcomes

By the end of this lab, students should be able to:

- explain what MCP tools and resources are
- build a FastMCP server in Python
- connect FastMCP to a SQLite database
- safely validate database requests before executing SQL
- expose dynamic schema context through `@mcp.resource(...)`
- test tool schemas, normal calls, and error responses
- connect the server to an MCP client such as Claude Code, Codex, or Gemini CLI

## Required Features

### Part 1: MCP Server

Implement a FastMCP server that exposes exactly these tool categories:

1. `search`
2. `insert`
3. `aggregate`

Your server may use SQLite for the main implementation. If you want to support PostgreSQL too, design the code so the database layer can be swapped later.

### Part 2: Resource

Expose database schema information as MCP resources:

- one resource for the full database schema
- one dynamic resource template for a single table schema

Suggested URIs:

- `schema://database`
- `schema://table/{table_name}`

### Part 3: Validation and Error Handling

Your tools must reject unsafe or invalid requests:

- unknown table names
- unknown column names
- unsupported filter operators
- invalid aggregate requests
- empty inserts

Do not build SQL by blindly concatenating raw user input.

### Part 4: Testing and Verification

Verify all of the following:

1. the server starts correctly
2. the three tools are discoverable
3. the schema resource is discoverable
4. valid tool calls return useful results
5. invalid tool calls return clear errors
6. at least one MCP client can connect and use the server

### Part 5: Demo Deliverables

Prepare:

- GitHub repository
- setup instructions
- tool descriptions
- testing steps
- at least one client configuration example
- short demo video, around 2 minutes

Inspector screenshots are recommended if you use MCP Inspector.

## Suggested Project Structure

```text
implementation/
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  tests/
    test_server.py
```

## Recommended Data Model

Use a small relational dataset so `search`, `insert`, and `aggregate` are easy to demo. Example:

- `students`
- `courses`
- `enrollments`

## Example Tasks to Demonstrate

- search all students in cohort `A1`
- insert a new student
- count rows in a table
- compute average score by cohort
- read the full schema resource
- read `schema://table/students`
- show an invalid request, such as searching a missing table

## FastMCP and Inspector References

- FastMCP quickstart: https://gofastmcp.com/v2/getting-started/quickstart
- FastMCP resources: https://gofastmcp.com/v2/servers/resources
- MCP Inspector: https://modelcontextprotocol.io/docs/tools/inspector

## Client Setup Notes

### Claude Code

Anthropic documents local JSON config and `claude mcp add` flows here:

- https://code.claude.com/docs/en/mcp

Claude Code supports MCP resources via `@server:resource-uri` references and supports environment variable expansion in `.mcp.json`.

### Codex

OpenAI documents Codex MCP setup here:

- https://developers.openai.com/learn/docs-mcp

Codex supports MCP server configuration through the CLI and `~/.codex/config.toml`.

### Gemini CLI

Gemini CLI has a built-in MCP manager. In the verified local workflow, the simplest path is:

```bash
gemini mcp add sqlite-lab /ABSOLUTE/PATH/TO/python /ABSOLUTE/PATH/TO/implementation/mcp_server.py --description "SQLite lab FastMCP server" --timeout 10000
gemini mcp list
```

Gemini CLI also documents configuration details here:

- https://github.com/google-gemini/gemini-cli/blob/main/docs/reference/configuration.md

Expected outcome:

- the server appears as `Connected`
- Gemini can discover `search`, `insert`, and `aggregate`
- a headless smoke test works with `gemini --allowed-mcp-server-names sqlite-lab --yolo -p "..."`

### Antigravity

Antigravity commonly uses an `mcp_config.json` file with a shape similar to Gemini CLI. Verify the current product behavior in your installed version before grading against exact UI steps.

## Deliverable Checklist

- working FastMCP server
- SQLite database and seed data
- `search`, `insert`, `aggregate` tools
- schema resource and schema resource template
- verification steps
- automated tests or repeatable verification script
- client configuration example
- README with setup and demo steps
- Inspector startup command or helper script
- at least one verified Gemini CLI or Claude/Codex client test

## Bonus

Optional bonus:

- add authentication for SSE or HTTP transport
- support both SQLite and PostgreSQL with the same MCP surface
- add richer output annotations or pagination

---

## Implementation (Student Submission)

The working implementation lives in [`implementation/`](implementation/).

### Setup

```bash
cd implementation
python -m venv .venv
source .venv/Scripts/activate      # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python init_db.py                  # creates and seeds implementation/lab.db
python mcp_server.py               # runs the MCP server over stdio (default transport)
```

For an HTTP/SSE demo instead of stdio:

```bash
python mcp_server.py --http        # serves at http://localhost:8090/mcp
```

### Data model

SQLite database with three tables: `students`, `courses`, `enrollments` (seeded with sample rows). Schema is defined and (re)created by `init_db.py`, so it is fully reproducible.

### Tools

| Tool | Description |
|---|---|
| `search(table, columns?, filters?, limit?, offset?, order_by?, descending?)` | Filtered, paginated row search. `filters` is a list of `{"column", "op", "value"}`; `op` ∈ `=, !=, >, >=, <, <=, like, in`. |
| `insert(table, values)` | Inserts one row (`values` = column→value map) and returns the inserted row + row id. |
| `aggregate(table, metric, column?, filters?, group_by?)` | `metric` ∈ `count, avg, sum, min, max`, with optional filters and `GROUP BY`. |

All three validate `table`/`column`/`operator`/`metric` against the live schema before building any SQL, and always execute with bound parameters — no string concatenation of user input into SQL.

### Resources

- `schema://database` — full schema (all tables/columns) as JSON.
- `schema://table/{table_name}` — schema for a single table as JSON.

### Testing and verification

```bash
# Unit tests for the SQLite adapter (validation, search/insert/aggregate)
pytest

# Full MCP protocol verification: spawns the real server over stdio,
# checks tool/resource discovery, valid calls, and that invalid calls
# (unknown table/column/operator/metric, empty insert) fail with a clear error.
python verify_server.py

# Interactive inspection (opens MCP Inspector in the browser)
./start_inspector.sh
```

`verify_server.py` output (abridged) — all checks pass, invalid calls correctly return `isError = True`:

```
[PASS] tool 'search' discoverable
[PASS] tool 'insert' discoverable
[PASS] tool 'aggregate' discoverable
[PASS] schema://database discoverable
[PASS] schema://table/{table_name} discoverable
[PASS] search valid call succeeds
[PASS] insert valid call succeeds
[PASS] aggregate valid call succeeds
[PASS] search on unknown table is rejected
[PASS] search on unknown column is rejected
[PASS] search with unsupported operator is rejected
[PASS] aggregate with unsupported metric is rejected
[PASS] insert with empty values is rejected
All checks passed.
```

### Client configuration example (Claude Code)

Copy [`implementation/.mcp.json.example`](implementation/.mcp.json.example) to `.mcp.json` and replace the path with the absolute path to `mcp_server.py` on your machine:

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"],
      "env": {}
    }
  }
}
```

Then reference resources directly in Claude Code with `@sqlite-lab:schema://database`.

Equivalent setup commands for Gemini CLI and Codex are in [`Tips.md`](Tips.md).
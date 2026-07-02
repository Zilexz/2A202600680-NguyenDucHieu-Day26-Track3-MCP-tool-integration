#!/usr/bin/env bash
# Launch MCP Inspector against mcp_server.py (stdio transport).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector "$(command -v python)" mcp_server.py

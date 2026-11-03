# MCP integration

**Optional Extension.** AOS records the MCP declaration shape currently implemented by dotagents. It does not require a manager to start servers, expose tools, or implement a gateway.

```toml
[mcp]

[[mcp.servers]]
name = "docs"
transport = "stdio"
command = "node"
args = ["server.js"]
env = { MODE = "read-only" }
env_passthrough = ["DOCS_TOKEN"]
timeout = 30

[[mcp.skills]]
name = "search-docs"
server = "docs"
```

## Fields and validation

`mcp` is a table containing only `servers` and `skills` in dotagents. Both are arrays of tables. Server names are unique within one overlay and skill names are unique within one overlay; each is a tool-name segment matching `[A-Za-z0-9][A-Za-z0-9_.-]*`.

- Every server requires `name`, `transport`, and a positive numeric `timeout` if supplied (default 60 seconds).
- `transport = "stdio"` requires a non-empty `command`. Optional `args` is an array of strings; `env` maps valid environment names to string values; `env_passthrough` is a list of unique valid environment names.
- `transport = "streamable-http"` requires an absolute `http` or `https` URL without embedded username/password or fragment. Optional `headers_env` maps valid HTTP header names to valid environment variable names.
- `mcp.skills` entries contain exactly `name` and `server`. The named server MUST be declared in the same overlay. Dotagents also requires a matching `skills/<name>/SKILL.md` in that overlay.

Environment values in `env` are literal strings in the manifest. Do not put credentials there. `env_passthrough` and `headers_env` name variables; the manager obtains their values from its environment. Credential resolution, process environment inheritance, authorization, and permission scopes are implementation-defined.

## Gateway behavior

Dotagents' optional gateway starts servers when tools are listed, prefixes server tools with the server name (or a configured namespace), and forwards calls. Its gateway implementation and tool-to-skill presentation are not part of the portable declaration. Server/tool collisions and unavailable servers are runtime concerns. See the [MCP specification](https://modelcontextprotocol.io/specification/) for protocol behavior.

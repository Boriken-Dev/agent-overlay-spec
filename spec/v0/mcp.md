# MCP integration

**Optional Extension.** AOS records the MCP server declaration dotagents implements. It does not
require a consumer to start servers, expose tools, or run a gateway.

```toml
[mcp]

[[mcp.servers]]
name = "docs"
transport = "stdio"
command = "node"
args = ["server.js"]
env = { MODE = "read-only", DOCS_TOKEN = { provider = "env", key = "DOCS_TOKEN" } }
timeout = 30

[[mcp.servers]]
name = "remote-docs"
transport = "streamable-http"
url = "https://mcp.example.org/agent"
headers_env = { Authorization = "DOCS_AUTHORIZATION" }

[[mcp.skills]]
name = "search-docs"
server = "docs"
```

## Fields and validation

`mcp` holds only `servers` and `skills`, both arrays of mappings. Server names are unique within one
overlay, and so are skill names; each matches `[A-Za-z0-9][A-Za-z0-9_.-]*`.

- Every server has `name` and `transport`, and optionally a positive, finite `timeout` in seconds
  (default 60).
- `transport = "stdio"` requires a non-empty `command`. Optional: `args`, an array of strings;
  `env`, a mapping of variable name to [env value](environment.md#env); `env_passthrough`, unique
  variable names copied from the consumer's own environment when set.
- `transport = "streamable-http"` requires an absolute `http` or `https` `url`, with no user
  information and no fragment. Optional: `headers_env`, a mapping of HTTP header name to a variable
  name whose value, from the consumer's own environment, is sent as that header.
- `mcp.skills` entries hold exactly `name` and `server`. The server MUST be declared in the same
  overlay, and `skills/<name>/SKILL.md` MUST exist.

**Proposed:** an `env` value may be any [env value](environment.md#env), including a path under the
root and a secret reference; dotagents takes strings only. A stdio server starts with the overlay
root as its working directory, so `args = ["server.js"]` names the overlay's file; dotagents starts
it in the gateway's own working directory. A `command` without a separator is found on the `PATH`
the overlay runs with, after its [path additions](environment.md#path-additions).

`env_passthrough` and `headers_env` read the consumer's own environment: each is a
[weakening](security.md#weakenings), `env-passthrough`. A literal `env` value is in the overlay for
anyone to read, so a credential never goes there; a secret reference does.

## Gateway behaviour

dotagents' optional gateway starts servers when tools are listed, prefixes each server's tools with
its name (or a configured namespace), and forwards calls. That gateway and how tools are presented
as skills are not part of the declaration. Name collisions and unavailable servers are runtime
concerns; see the [MCP specification](https://modelcontextprotocol.io/specification/) for the
protocol.

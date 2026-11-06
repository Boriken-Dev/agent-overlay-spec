# Security considerations

An overlay is data, but its instructions steer an agent, and it can carry scripts, dependency lists,
setup steps, environment and server declarations. **Conformance does not establish trust or
safety.** A consumer treats an overlay from elsewhere as untrusted until its user or administrator
decides to trust it, and then pins what was trusted.

## Reading is safe by construction

Reading a manifest executes nothing, reads no other file, and consults no environment
([static reading](manifest.md#static-reading)). A consumer can therefore show a user everything an
overlay would do (its environment, path additions, setup, runtime, servers, hooks and weakenings) before
any of it happens, from the manifest and the overlay's list of files, which decides the
[defaults](package.md#defaults). YAML [tags, anchors, aliases and merge keys](manifest.md#restricted-yaml)
are refused because general YAML loaders construct objects or expand documents from them, a few hundred
bytes into billions of nodes; they are refused where they stand, since a check after expanding comes too
late. JSON duplicate keys are refused because two readers would disagree on which value wins.

A reader bounds the size and nesting of what it reads, by settings with defaults, and holds the depth
bound while parsing, so text deep enough to exhaust a recursive parser's stack is a refusal, not a
crash. [The split](manifest.md#the-split) works on bytes and reads nothing past its bound, so it spends
nothing on a body it is not asked for, however large.

## The body of `OVERLAY.md`

A body is [context](harness.md#context), and context is instruction: it steers the agent with the
standing a `CONTEXT.md` has, so it reaches an agent only from an overlay the user accepted. Showing an
overlay is not giving it to an agent:

- a store or a viewer shows a body as text, marked as the overlay's, renders no HTML in it and fetches
  nothing it links to, and never adds it to an agent's context to describe the overlay;
- what is in the fence reaches an agent only as the fields that are instructions by definition: its
  `routing` lines and the rules files it names, both shown [before installing](catalog.md#before-installing).
  No other field, not `about`, not a block a viewer could not read, and never the fence as text: an
  unclosed or malformed block in `OVERLAY.md` is refused, not shown to an agent, and
  [no field names a manifest](manifest.md#fields) as a rules file or anything else;
- every byte of `OVERLAY.md` is under the [tree digest](integrity.md#tree-digest), so a pin covers the
  body as it covers `CONTEXT.md`.

Two readers that disagree about where a block ends would apply one manifest and show another, or send
an agent what another reader took for metadata, so [the split](manifest.md#the-split) is byte-exact and
held by vectors.

## Trust and sources

A consumer shows source and revision before it first activates an overlay, and the difference before
it updates one. A branch or a registry entry can change after review; a [pin](integrity.md#pins)
cannot. A mismatched pin is a refusal, never a warning.

## Weakenings

A **weakening** is a choice looser than the default, declared by an overlay or made by a consumer.
AOS does not forbid them: a user may need an overlay whose setup downloads a toolchain. It requires
that each is **reported, never applied silently**: in a log line, a status view or the user
interface, each time the overlay is activated, with an identifier, the overlay, and a subject (a
variable name or a path), never a value. A consumer MAY refuse any weakening by its own policy, and
then reports the refusal the same way.

| Id | When |
| --- | --- |
| `unpinned` | An overlay is activated without a [pin](integrity.md#pins), or a [skill from elsewhere](skills.md#resolving-a-name) is named without one. The subject is the overlay, or the skill. |
| `setup-network` | The selected [setup](runtime.md#setup) variant declares `network = true`, or a [default setup](runtime.md#default-scripts) is selected. |
| `network-not-enforced` | The selected setup variant declares no network, and the consumer cannot deny it one. |
| `no-timeout` | The selected setup variant or an [env script](environment.md#env-scripts) that runs has `timeout = 0`. |
| `env-script` | An env script runs, declared or by default. |
| `hook` | An overlay's or a scope's [hooks](hooks.md) are on, and one runs at an event. The subject is the event. |
| `script-not-run` | A [default script](runtime.md#default-scripts) is present and none can run on this OS with the consumer's interpreters. The subject is each file. |
| `env-passthrough` | A granted value is read from the consumer's own environment: an env value with `provider = "env"`, an MCP `env_passthrough` or `headers_env` entry. The subject is the variable read. |
| `secret-read` | A granted [secret reference](environment.md#secret-references) is resolved for the overlay. The subject is the reference (`secret:<name>`, `file:<key>`, `<provider>:<key>`). |
| `env-sensitive` | An overlay sets a [sensitive variable](#sensitive-variables) through `env`, an env file or an env script, or adds to one other than `PATH`, `PYTHONPATH` and `NODE_PATH` through `paths`. The subject is the variable. |
| `unlocked-dependencies` | A [dependency file](runtime.md#dependencies) is not pinned: a Python file without a hash on every requirement (a declared `requirements` is never one), or a `package.json` without a `package-lock.json`. The subject is the file; for a shared or named environment that is not pinned, the environment (`python:shared`, `node:<name>`), reported to every member. |
| `deps-network` | A dependency file is installed, which needs the network. The subject is the file. |
| `insecure-transport` | An MCP server is reached over plain `http` on a host other than loopback, or a [skill from elsewhere](skills.md#declaring-skills) is fetched over plain `http` or `git://`. The subject is the server, or the skill. |
| `private-source` | A skill from elsewhere is fetched from a private network address. The subject is the skill. |
| `skill-keys` | A fetched skill's front matter holds a key other than `name`, `description`, `license`, `compatibility` and `metadata`. The subject is the skill and the key. |

A consumer's own settings can weaken too (a disabled sandbox, a raised limit); a consumer reports
those the same way, under identifiers of its own.

### Sensitive variables

Variables that change how programs find and load code, which startup or configuration files run,
which certificates are trusted, where packages come from, or where network traffic and an agent's
own API calls go. Names compare without regard to ASCII case. A name is sensitive when it:

- is one of `PATH`, `PATHEXT`, `HOME`, `USERPROFILE`, `SHELL`, `COMSPEC`, `SYSTEMROOT`, `BASH_ENV`,
  `ENV`, `ZDOTDIR`, `PROMPT_COMMAND`, `IFS`, `EDITOR`, `VISUAL`, `PAGER`, `LESSOPEN`, `LESSCLOSE`,
  `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `APPDATA`, `LOCALAPPDATA`, `TMPDIR`, `TEMP`, `TMP`,
  `PSMODULEPATH`, `CLASSPATH`, `JAVA_TOOL_OPTIONS`, `_JAVA_OPTIONS`, `JDK_JAVA_OPTIONS`,
  `PERL5OPT`, `PERL5LIB`, `RUBYOPT`, `RUBYLIB`, `RUSTFLAGS`, `GOPROXY`, `GONOSUMDB`, `GONOSUMCHECK`,
  `GOPRIVATE`, `GOFLAGS`, `SSH_ASKPASS`, `SSLKEYLOGFILE`, `REQUESTS_CA_BUNDLE`, `CURL_CA_BUNDLE`, and
  `CLAUDE_CONFIG_DIR` and `CODEX_HOME`, which point a harness at another configuration, with its own
  permissions and hooks;
- starts with `LD_`, `DYLD_`, `GIT_`, `PYTHON`, `NODE_`, `NPM_CONFIG_`, `PIP_`, `UV_`, `CARGO_`,
  `RUSTC_`, `DOTNET_`, `COR_`, `CORECLR_` or `SSL_`;
- ends with `_PROXY` or `_BASE_URL`.

A consumer MAY treat more names as sensitive; it MUST treat at least these.

## Execution and dependencies

Setup, env scripts, commands and dependency installation run only under an explicit policy of the
user or administrator: installing an overlay is a trust decision, fetching one is not. A consumer
runs setup outside the agent's sandbox, in its [phases](runtime.md#setup-phases) (`install` on
the first add, `sync` on every sync, `remove` on removal), bounded by a timeout, with the network
denied unless declared, and with the overlay root read-only where it can. Dependencies are
installed before setup, from a lock in hash-checking mode where the file is pinned, into
[environments](runtime.md#environments) outside every root that are read-only in the sandbox.

Starting an MCP server, running a command and running an env script are the same decision as
setup: code from the overlay runs. A hook is that decision and one more, [below](#hooks). Overlays an overlay `requires` are shown and accepted like the
ones asked for, never installed silently.

`env.<ext>` and `setup.<ext>` [run by default](runtime.md#default-scripts), without a manifest.
That moves no decision: a default script runs only in an overlay the consumer has activated, never
in one it fetched or only read, with the same timeout, process group and state directory as a
declared one, and every run is reported. A default setup is taken to need the network and reported
as such, since nothing in it says otherwise. Dependencies install by default only from
`lib/python/requirements.txt` and `lib/node/package.json`, each install reported as
`deps-network`; nothing else runs by default, and a command is exposed only by a `scripts` entry.

An overlay's files under an [excluded name](package.md#layout) (`__pycache__`, `node_modules`,
`.venv`, `.git`, ...) are not part of the overlay and are not covered by its digest, yet Python,
Node.js and Git load code from them implicitly. So a consumer never installs them, counts any such
entry in an installed copy as a [mismatch](integrity.md#pins), and runs Python from an overlay with
`PYTHONPYCACHEPREFIX` pointing outside the root, so no bytecode is ever written or read there.

## Hooks

A [hook](hooks.md) is the overlay's code running at every session, outside the sandbox, and some events
tell it what the user typed or what a tool is about to do. Activating an overlay is therefore not enough
to run one:

- **Off until allowed at a digest.** Hooks run only while the overlay's tree digest is the one at which
  the user allowed them. Any change of a file turns them off again, so an update cannot start running a
  changed hook at the next session; an overlay with a guard that fails closed is not activated meanwhile.
  Nothing an overlay, a catalog or a project holds allows them; the user's own configuration needs no
  allowance. The allowance covers hooks alone: an update that adds an env script or a setup runs under
  the decision to activate the overlay, which is why every run of either is reported.
- **Reach is the user's.** A hook runs outside the sandbox with the user's access and the network, so it
  can read what a harness keeps on disk, transcripts included, whatever its payload says. Its listing
  says so; a hook is code the user trusts, and the payload rules bound only what it is handed.
- **Declared statically, shown first.** Every event, its script, its `match`, timeout and
  `on_failure`, and what its payload holds is in the manifest and the list of files, and
  [listed before installing](catalog.md#before-installing).
- **Told little.** A payload holds the event's own keys and nothing else: never the environment, a
  variable, a secret or another overlay's data. Events that carry the user's words or a tool's input
  (`prompt`, `pre-tool`, `post-tool`) reach a hook only when its manifest names them. A hook gets its own
  overlay's environment, not the session's.
- **Tightens, never grants.** A hook adds context, blocks, denies or asks. There is no output that
  approves, any other decision is refused as `grant`, and a consumer never hands a harness the hook's own
  output or exit status, so a harness's own approval vocabulary cannot pass through it. Variables are
  only those the manifest's `sets` names, and reach a shell through a loader, with no decision attached,
  never in the command's text. Text a hook shows holds no control or reordering character, and a tool of
  a kind the consumer cannot place runs every guard.
- **Project hooks run from a copy.** A project's hooks are allowed at the digest of every file beside
  their configuration and run from the consumer's copy of those bytes, since the agent can write into
  the project between two events.
- **Bounded.** Time, for each run and for each event, output and payload are bounded by settings with
  defaults; a run is stopped, and everything it started ended, when its time runs out.
- **Fails visibly.** A failure is reported with its cause and never quoted. It refuses the event only
  when the author asked for that (`on_failure = "refuse"`), so a guard fails closed, and an output a
  consumer cannot apply on a harness is reported, never dropped.

## Paths and filenames

A consumer refuses archive entries and declared paths that leave the root after normalization and
symbolic links, absolute paths, drive and device paths, and links inside the tree. Every member path
of a digest and every declared path is a [relative path](manifest.md#fields), which refuses the
names a platform would alias or alter (another case of an excluded name, a trailing dot or space, a
device name, a short name, `:`), and the [tree digest](integrity.md#tree-digest) refuses two paths
equal under ASCII case. A consumer SHOULD also refuse two paths equal after Unicode case folding and
normalization (NFC), which some filesystems hold as one file.

## Credentials and network

An overlay never holds a secret value: it holds [secret references](environment.md#secret-references),
and reads only what the consumer's configuration grants it. A consumer never logs, displays or
stores a resolved value, gives each overlay's processes only that overlay's environment, and SHOULD
start them from an environment it chose rather than everything it inherited.
[Substitution](environment.md#secrets-and-substitution) never reads a variable that holds a
resolved secret, so no part of one is copied into another variable, and a consumer shows a
substituted value as written, never its result. Substitution runs nothing and reads no file.
MCP servers can reach data and networks; a consumer shows each server, its transport and the
variables it reads before starting it.

## Stores, catalogs and icons

[Store metadata and catalogs](catalog.md) are informational, and untrusted:

- **Text.** A store shows informational fields, `name` and `description` as plain text: never
  rendered as Markdown or HTML, never put into an agent's context as instructions. It shows
  `homepage` and `repository` as links the user may open, and fetches neither by itself, since a
  fetch tells a third party who is looking. A line refuses bidirectional overrides so that what is
  shown reads as its characters do.
- **Icons are untrusted images.** Image decoders have a long record of memory-safety flaws, and a
  small file can declare dimensions that take far more memory to decode. A store accepts PNG and
  WebP only, never SVG; checks the size and the header's dimensions against its limits before
  decoding; decodes with a maintained decoder and, where it can, in a memory-safe language or a
  process with no access to the user's data; shows pixels only, nothing an image carries besides
  them; and never fetches an image a field names, since an icon is a file beside the manifest or
  the catalog.
- **Catalogs are advertising.** An entry can take another overlay's name, summary or icon, so a
  store shows each entry's source and its catalog's label, and after fetching shows the overlay's
  own manifest, not the catalog's claims. What an overlay would do is computed from that manifest
  and the overlay's files [before installing](catalog.md#before-installing), and a catalog's `pin`
  is checked like any pin. A catalog from a repository or a URL cannot name a source on the
  consumer's machine.
- **Names across catalogs** are never resolved silently: a name two catalogs offer is shown
  qualified by catalog, and installing it unqualified asks the user.

## Skills from elsewhere

An overlay's [`skills`](skills.md) can make a consumer fetch code and instructions the overlay's digest
does not cover, so naming a source is a request, and only the user's yes grants it:

- **Who may name a source.** Anyone who writes a manifest may ask for a source, and it asks for nothing
  on the consumer's machine: [local sources, this machine's addresses and credentials are
  refused](skills.md#declaring-skills), a private address and plain transports are reported, and the
  fetch carries none of the user's credentials and follows no redirect to another host. The source
  shown is the one fetched: an `@` in an authority is user information, and a source holds no control
  or reordering character.
  What is fetched is what the user accepted: the overlay and its skills [together](catalog.md#before-installing),
  each source shown first, and fetching never happens before that, for an overlay from a project or a
  catalog above all. A source is reached with the consumer's own network position and Git transports, as
  an overlay's source is, so the consumer limits those as [distribution](distribution.md#source-form) says.
- **A name resolving to code.** A bare name is resolved by the catalogs the user chose, never by the
  overlay, so an overlay can only ask for what those already offer, under a name it chose. That can still
  be another skill than its author meant, so each is shown with its source before it is accepted, a name
  two catalogs offer is never picked by itself, and the overlay's pin is only as good as the entry: a
  name with no pin is reported `unpinned` each time.
- **Fetching is not running.** A skill is instructions and files: [nothing in it runs by default, and
  nothing in it is read as an overlay](skills.md#fetching). So a skill cannot name further skills, and a
  fetched tree's digest is checked before any file of it is parsed.
- **A skill is what it says.** A skill whose `SKILL.md` gives another name than the one accepted is
  refused, so a fetched skill cannot take a trusted skill's place in a harness by naming itself after it,
  and a skill from elsewhere never takes a name another overlay's skill holds unless the configuration
  says so. Its front matter keys are shown and those that could grant or run anything reported, since a
  harness may honour them; its `description`, which a harness shows the agent before the skill is used,
  is the author's text, accepted with the source.

## Collisions and updates

Overlay names, root variables, commands, skills, servers and tools can collide. A consumer detects
collisions before activation and reports which identity wins, or refuses. An update can change
instructions or code; a pin and a reviewable difference make it a decision rather than an accident.

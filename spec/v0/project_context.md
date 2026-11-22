# Project context files

**Optional Extension, Proposed.** A project keeps the instructions for the agents that work in it in
one standard place, so that every consumer finds the same files in the same order, and one that runs
a harness which does not load them itself can hand them over. This section says which files, in what
order, which of them a consumer feeds and when. It is about the project's own files; an overlay's
[`context`](harness.md#context) is a different thing and follows its own rule.

## The files

A directory of a project has up to two **places** where context files live:

1. the directory itself, and
2. each directory named by `AGENTS_DIR` inside it, in the order listed (`.agents` by default).

A place holds the files whose name matches a pattern of `AGENTS_CONTEXT` (`AGENTS.md` and
`AGENTS.*.md` by default). So the default files of one directory are `AGENTS.md`, `AGENTS.*.md`,
`.agents/AGENTS.md` and `.agents/AGENTS.*.md`, where `AGENTS.local.md` and its like are the user's own
unshared files.

### The variables

| Variable | Value | Default |
| --- | --- | --- |
| `AGENTS_DIR` | Names of the directories, inside a project directory, that hold context files | `.agents` |
| `AGENTS_CONTEXT` | Name patterns of the context files in each place | `AGENTS.md` and `AGENTS.*.md` |

Each is a list separated by the platform's path-list separator (`;` on Windows, `:` elsewhere), as
`PATH` is, so several directories and several patterns can be named. A consumer reads them from the
environment its session starts with. An unset variable, and one with no valid entry, has the
default. Empty entries are dropped and a repeated entry counts once, at its first place.

- An `AGENTS_DIR` entry is one directory name: no `/` or `\`, and neither `.` nor `..`. A directory may
  be a link to a directory.
- An `AGENTS_CONTEXT` entry is a file name pattern, with no `/` or `\`. `*` matches any run of
  characters, none included, and every other character matches itself, in the case it is written.
  A pattern without `*` is one name.
- An entry of either kind that breaks these rules is ignored, and the consumer reports each as
  ignored. The others still apply.

A name is **local** when it has the form `<stem>.local.<extension>`, such as `AGENTS.local.md`: the
user's own file for the project, which is not shared and is never committed.

### The order of a directory

The files of one directory are listed in this order, and a later file overrides an earlier one:

1. the files that are not local, place by place (the directory, then each `AGENTS_DIR` entry in its
   order);
2. then the local files, place by place in the same order.

Within a place, the files come pattern by pattern in the order of `AGENTS_CONTEXT`; the names a pattern
matches are in byte order of their UTF-8, and a file an earlier pattern matched is not listed again. The
default of one directory is therefore `AGENTS.md`, `AGENTS.<name>.md` in name order, `.agents/AGENTS.md`,
`.agents/AGENTS.<name>.md`, then `AGENTS.local.md`, `.agents/AGENTS.local.md`: the `.agents` copy beats the
plain file beside it, and a local file beats both.

Only a regular file is a context file, or a link to one. A directory named like a context file is not
read. Names are compared as the directory lists them, in the case they have, whatever the file system's
own rule.

### The walk

A session has a **project root** (`AGENTS_PROJECT_ROOT`) and a **working directory**. The levels are the
root and each directory below it down to the working directory, broadest first, and the files are the
files of each level in the order above, level by level: the deeper directory overrides the broader. A
working directory that is not inside the root, or a session with no root, has one level, the working
directory. A directory whose name is an `AGENTS_DIR` entry is not a level: its files are the place of the
directory above it. Context above the root, such as the user's own instructions for every project, is
not part of this rule.

## Feeding them

A harness loads some of these files itself, and a consumer MUST NOT hand over what the harness already
reads, which would show the agent each twice. The consumer knows, for each harness, the paths relative
to a level's directory that the harness loads for itself (`AGENTS.md` for one that reads that name at each
level). It leaves those out and says it did, and it feeds every other file of the walk.

A consumer that runs an agent session with a harness that does not load the project's context hands the
text of these files to the agent with the other context it starts the session with, each with its path, so
that the agent can tell which file said what, and the same [bound](harness.md#context) applies to the
total. A file that is not UTF-8 text, or that would pass the bound, is not fed, and the consumer says
which and why.

**A change of directory.** When the agent's working directory changes, and the consumer can learn of it
(a hook, an event of the session, a command the consumer ran), it feeds the files of the levels the
session has not yet received, in the same order. Entering a directory again, and going back to a broader
one, feeds nothing new. A session that learns of no change feeds only the levels of the directory it
started in.

> **Status:** no released consumer reads `AGENTS_DIR` or `AGENTS_CONTEXT` yet.

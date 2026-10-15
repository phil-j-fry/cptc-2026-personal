"""compile.py: assemble everyone's findings into report-ready Markdown.

Reads the finding files in the working copy (yours and teammates' in
incoming/), writes report-ready tables and a combined findings file to build/,
and checks every finding against checklists/50-report-qa.md.

Usage: python3 tools/compile.py [--root PATH] [--index PATH] [--final]

Python 3 standard library only. It never runs commands and never opens a
network connection; it only reads files in the working copy (Markdown and
the findings index CSV) and writes its generated files under build/.
"""

import argparse
import re
from pathlib import Path

# One template marker, complete from `[[` to `]]`. Read it aloud as:
#   \[\[            two opening brackets
#   [A-Z_]+         a name in capitals and underscores (HOST, NOTE, CHOOSE...)
#   (?:             then, optionally:
#     :             a colon,
#     (?:(?!\[\[).)*?  then any text, as little as possible, that never
#                    starts a new `[[`
#   )?
#   \]\]            two closing brackets
# Requiring a capital right after `[[` skips bash tests like `[[ -f x ]]`.
# DOTALL lets `.` match line breaks, so a NOTE spanning several lines is one
# marker. The "never starts a new `[[`" rule means a marker missing its `]]`
# stops matching at the next marker instead of swallowing it.
MARKER_RE = re.compile(r"\[\[[A-Z_]+(?::(?:(?!\[\[).)*?)?\]\]", re.DOTALL)

# The start of a leftover marker: `[[`, a capitalised name, then `:` or `]]`.
# This is the exact pattern from the grep in checklists/50-report-qa.md, so the
# tool and the manual check agree. Why two regexes: MARKER_RE needs a whole
# marker so it can strip it; this one needs only the start, so it also reports
# a marker whose `]]` is missing (e.g. `[[NOTE: never closed`).
# Limit: a bare `[[HOST` with no `:` or `]]` is not caught. The manual
# `grep -rnF '[['` sweep in checklists/50-report-qa.md covers that case.
LEFTOVER_RE = re.compile(r"\[\[[A-Z_]+(:|\]\])")


def strip_markers(text):
    """Return text with every complete marker removed.

    Used before "does this field have a value?" checks, so an unfilled
    `[[SEVERITY_RATIONALE]]` doesn't count as text.
    """
    return MARKER_RE.sub("", text)


def scan_leftover_markers(file_name, text):
    """Return every leftover marker as (file_name, line_number, matched_text).

    Line numbers start at 1, as in an editor, so QA can print file:line.
    The number of hits is the "unresolved markers" count used for READY/DRAFT.
    """
    hits = []
    # Split on "\n" only, like grep -n. splitlines() would also break on rarer
    # characters (form feed, Unicode line separators) and shift the numbers.
    for line_number, line in enumerate(text.split("\n"), start=1):
        for match in LEFTOVER_RE.finditer(line):
            hits.append((file_name, line_number, match.group(0)))
    return hits


def expand_path(text):
    """Turn a command-line path into a Path, expanding a leading ~."""
    # The shell doesn't always expand ~ for us: a quoted value such as
    # --root "~/cptc-work" reaches Python as a literal "~", and so does a path
    # passed in by another program instead of typed at a shell.
    return Path(text).expanduser()


def parse_args(argv=None):
    """Read the command-line options. argv=None means use sys.argv."""
    parser = argparse.ArgumentParser(
        description="Assemble findings into report-ready Markdown and check them for QA problems.",
    )
    parser.add_argument(
        "--root",
        type=expand_path,
        # Default to the working copy, never the current folder: running from
        # inside the repo clone must not compile (or write build/ into) the clone.
        default=Path("~/cptc-work").expanduser(),
        help="the working copy to read from (default: ~/cptc-work)",
    )
    parser.add_argument(
        "--index",
        type=expand_path,
        default=None,
        help="the findings index CSV (default: <root>/tracker/findings-index.csv)",
    )
    parser.add_argument(
        "--final",
        action="store_true",
        help="pre-submission check: every QA problem is an error and the exit code is 1 if any check fails",
    )
    return parser.parse_args(argv)


class RootError(Exception):
    """The --root folder can't be used. The message says why, for the user."""


def validate_root(root):
    """Return the root as a full resolved path, or raise RootError.

    Only checks; it never creates anything, so a refused root is left as found.
    """
    root = Path(root).resolve()
    if not root.exists():
        raise RootError("root folder not found: " + str(root))
    if not root.is_dir():
        raise RootError("root is not a folder: " + str(root))
    # The working copy has no .git; the repo clone does. Writing build/ or
    # reading event files inside the clone risks committing client data to
    # this public repo. exists() also catches a .git file (worktrees, submodules).
    if (root / ".git").exists():
        raise RootError(
            "this looks like the git clone (" + str(root) + " has .git); "
            "run on the working copy, e.g. ~/cptc-work"
        )
    return root


def resolve_in_root(root, path):
    """Return path as a full resolved path inside root, or raise RootError.

    A relative path is taken relative to root. The error names the path the
    user gave and where it really points, so they can see which one is wrong.
    """
    # Check `..` as a whole path part, not as text: "a..b.md" is a fine
    # filename, but "../x" or "findings/../../x" climbs out of the folder.
    if ".." in Path(path).parts:
        raise RootError("path contains '..': " + str(path))
    root = Path(root).resolve()
    # resolve() follows symlinks, so a link is judged by where it really
    # points: a link to another place in the working copy is fine, but a link
    # (e.g. incoming/alice) to somewhere outside it is refused.
    # If path is absolute, `root / path` is just path (a pathlib rule), so an
    # absolute --index is checked by the same containment test below.
    resolved = (root / path).resolve()
    if resolved != root and root not in resolved.parents:
        raise RootError(
            "path is outside the root: " + str(path) + " -> " + str(resolved)
        )
    return resolved

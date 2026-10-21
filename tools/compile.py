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
import csv
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

# The start of a leftover marker: `[[` followed by a capitalised name. This is
# the same pattern as the grep in checklists/50-report-qa.md, so the tool and
# the manual check agree. Why two regexes: MARKER_RE needs a whole marker so
# it can strip it; this one needs only the start, so it also reports a marker
# whose `]]` is missing (e.g. `[[NOTE: never closed`, or a bare `[[HOST`).
# Catching every unfinished marker is what lets a READY finding be trusted.
# A bash test like `[[ -f x ]]` has a space after `[[`, so it isn't reported.
LEFTOVER_RE = re.compile(r"\[\[[A-Z_]+")


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
        help="the findings index CSV; a relative path is taken from the root (default: <root>/tracker/findings-index.csv)",
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


def finding_folders(root):
    """Return the folders that hold findings, relative to root.

    These are findings/ and incoming/<name>/findings/ for each teammate.
    Every folder is checked with resolve_in_root() before anything inside it
    is listed, so a symlink pointing outside the root raises RootError even
    when the place it points to holds no findings.
    """
    folders = [Path("findings")]
    incoming = resolve_in_root(root, "incoming")
    if incoming.is_dir():
        for owner in incoming.iterdir():
            owner_folder = Path("incoming") / owner.name
            # Check where the entry points before asking if it is a folder:
            # is_dir() follows a symlink, so it would look outside first.
            if resolve_in_root(root, owner_folder).is_dir():
                folders.append(owner_folder / "findings")
    for folder in folders:
        resolve_in_root(root, folder)
    return folders


def discover_findings(root):
    """Return every finding file to compile, sorted by path.

    Looks in exactly two places: <root>/findings/F-*.md (your own findings)
    and <root>/incoming/*/findings/F-*.md (each teammate's mirror). Raises
    RootError if a folder or file there points outside the root.
    """
    root = Path(root).resolve()
    findings = []
    for folder in finding_folders(root):
        for path in (root / folder).glob("F-*.md"):
            # A single finding file can be a symlink too, so check it as well.
            resolve_in_root(root, folder / path.name)
            # Skip anything that isn't a plain file, e.g. a folder named F-x.md.
            if path.is_file():
                findings.append(path)
    # glob() and iterdir() return names in whatever order the disk lists
    # them. Sorting makes every run give the same order: findings/ sorts
    # before incoming/. This only lists names; incoming/ is never opened for
    # writing (R18).
    return sorted(findings)


# The finding's title line, e.g. `### F-001: Default admin password`. The ID
# is F- plus three digits, or the unfilled `[[FINDING_ID]]` marker of an early
# draft. Any number of `#` is accepted here so a wrong level can be reported
# instead of the title going missing.
HEADING_RE = re.compile(r"^(#+)[ \t]+(F-\d{3}|\[\[FINDING_ID\]\])[ \t]*:[ \t]*(.*)$")

# The ID at the start of a finding's filename, e.g. F-001 in F-001-web01.md.
# \b stops F-0012-x.md from reading as F-001.
FILENAME_ID_RE = re.compile(r"^F-\d{3}\b")


def find_title_heading(text):
    """Return (line_number, match) for the first title heading, or None."""
    # Split on "\n" only, so line numbers match grep -n (see above).
    for line_number, line in enumerate(text.split("\n"), start=1):
        # rstrip() also drops the "\r" a Windows line ending leaves behind.
        match = HEADING_RE.match(line.rstrip())
        if match:
            return line_number, match
    return None


def parse_finding_heading(file_name, text):
    """Return a finding's ID and title, read from its heading line.

    The result is a dict:
      id                the finding ID, or None if neither the heading nor
                        the filename has one
      title             the text after "ID:", as written, or None
      line              the heading's line number (from 1), or None
      heading_markers   leftover markers on the heading line, e.g. 1 for an
                        unfilled [[FINDING_ID]]
      diagnostics       (file_name, line_number, message) problems
    Heading problems (ID mismatch, wrong heading level, no heading, no
    title) are reported only here, so no other check repeats them.
    """
    match = FILENAME_ID_RE.match(Path(file_name).name)
    filename_id = match.group(0) if match else None
    result = {"id": filename_id, "title": None, "line": None,
              "heading_markers": 0, "diagnostics": []}
    found = find_title_heading(text)
    if found is None:
        result["diagnostics"].append(
            (file_name, 1, "no finding title heading like '### F-NNN: Title'"))
        return result

    line_number, heading = found
    hashes, heading_id, title = heading.groups()
    result["title"] = title
    result["line"] = line_number
    # group(0) is the whole heading line, since HEADING_RE runs from ^ to $.
    result["heading_markers"] = len(LEFTOVER_RE.findall(heading.group(0)))
    # Findings use ### for the title and #### for sections, so they nest
    # under the report's "## 5. Detailed Findings" without changes.
    if hashes != "###":
        result["diagnostics"].append(
            (file_name, line_number, "title is a " + hashes + " heading, not ###"))
    # A blank title has no marker, so the leftover check can't see it; this
    # warning is what reports it.
    if not title:
        result["diagnostics"].append((file_name, line_number, "heading has no title text"))
    if heading_id.startswith("F-"):
        # The heading is what goes into the report, so its ID wins; a
        # different filename ID is flagged so one of them gets fixed.
        result["id"] = heading_id
        if filename_id is not None and filename_id != heading_id:
            result["diagnostics"].append(
                (file_name, line_number,
                 "heading ID " + heading_id + " does not match filename ID " + filename_id))
    elif filename_id is None:
        # An unfilled [[FINDING_ID]] uses the filename's ID (set above); if
        # the filename has none either, report it.
        result["diagnostics"].append(
            (file_name, line_number, "no finding ID in the heading or the filename"))
    return result


# The labelled detail lines every finding must have, as in templates/finding.md.
FIELD_LABELS = ["Severity", "CVSS 3.1", "Why this severity",
                "Affected assets", "Status", "References"]

# A labelled list line, e.g. `- **Severity:** High`. Spaces around the dash,
# the label and the colon are allowed, so `-  ** Severity :**  High` still
# counts. Group 1 is the label, group 2 the rest of the line.
LABEL_LINE_RE = re.compile(r"^[ \t]*-[ \t]+\*\*[ \t]*([^*:]+?)[ \t]*:[ \t]*\*\*[ \t]*(.*?)[ \t]*$")

# On the CVSS 3.1 line, the vector is between backticks and the score is in
# parentheses: `CVSS:3.1/AV:N/...` (9.8).
CVSS_VECTOR_RE = re.compile(r"`([^`]*)`")
CVSS_SCORE_RE = re.compile(r"\(([^)]*)\)")


def parse_labelled_fields(file_name, text):
    """Return a finding's labelled details, read from its `- **Label:**` lines.

    The result is a dict:
      fields        label -> {"value": rest of the line as written, markers
                    included, "line": line number from 1}, for each label
                    in FIELD_LABELS that was found
      cvss_vector   the text between backticks on the CVSS 3.1 line, or None
      cvss_score    the text in parentheses on the CVSS 3.1 line, or None
      diagnostics   (file_name, label, message) for each missing label;
                    (file_name, line_number, message) for each duplicate
    A missing label is reported, never raised, so one bad file can't stop
    the whole compile.
    """
    fields = {}
    duplicates = []
    # Split on "\n" only, so line numbers match grep -n (see above).
    for line_number, line in enumerate(text.split("\n"), start=1):
        # rstrip() also drops the "\r" a Windows line ending leaves behind,
        # which would otherwise end up inside every value.
        match = LABEL_LINE_RE.match(line.rstrip())
        # Other labels (Likelihood, Immediate...) aren't needed by compile
        # and are ignored.
        if match and match.group(1) in FIELD_LABELS:
            label = match.group(1)
            if label not in fields:
                fields[label] = {"value": match.group(2), "line": line_number}
            else:
                # The first line wins; flag each extra one so a wrong value
                # can't slip into the report. Unlike a missing label it has a
                # real line, so it is (file_name, line_number, message).
                duplicates.append((file_name, line_number, "duplicate " + label
                                   + " line; line " + str(fields[label]["line"]) + " is used"))

    result = {"fields": fields, "cvss_vector": None, "cvss_score": None,
              "diagnostics": []}
    for label in FIELD_LABELS:
        if label not in fields:
            result["diagnostics"].append(
                (file_name, label, "missing labelled line '- **" + label + ":**'"))
    result["diagnostics"].extend(duplicates)

    if "CVSS 3.1" in fields:
        cvss = fields["CVSS 3.1"]["value"]
        vector = CVSS_VECTOR_RE.search(cvss)
        if vector:
            result["cvss_vector"] = vector.group(1)
            # Look for the score only outside the backticks, so brackets in
            # a mistyped vector can't be read as the score.
            cvss = cvss[:vector.start()] + cvss[vector.end():]
        score = CVSS_SCORE_RE.search(cvss)
        if score:
            result["cvss_score"] = score.group(1)
    return result


# Severity levels from most to least severe. The position in this list is the
# sort order; a finding with no severity sorts after all of them.
SEVERITIES = ["Critical", "High", "Medium", "Low", "Informational"]

# One level as a whole word. Case-sensitive on purpose: the template offers
# these exact words, so "high" or "HIGH" means the line wasn't filled in
# properly, and \b stops "Highest" from counting as High.
SEVERITY_RE = re.compile(r"\b(Critical|High|Medium|Low|Informational)\b")


def severity_value(file_name, fields):
    """Return (severity, diagnostics) for one finding.

    `fields` is the "fields" dict from parse_labelled_fields(). severity is
    the first level word on the Severity line, or None.
    """
    if "Severity" not in fields:
        # parse_labelled_fields() already reported the missing line, so
        # don't report the same problem twice.
        return None, []
    field = fields["Severity"]
    # Strip markers first: an unfilled [[CHOOSE: Critical / High / ...]]
    # contains every level word, and must not read as Critical.
    match = SEVERITY_RE.search(strip_markers(field["value"]))
    if match:
        return match.group(1), []
    return None, [(file_name, field["line"],
                   "no severity (Critical, High, Medium, Low or Informational); sorted last")]


def finding_sort_key(finding_id, severity):
    """Return the key that sorts findings Critical first, then by ID.

    A finding with no severity (None) sorts after Informational.
    """
    if severity in SEVERITIES:
        rank = SEVERITIES.index(severity)
    else:
        rank = len(SEVERITIES)
    # IDs are F- plus three digits, so sorting them as text sorts them by
    # number. A finding with no ID at all (None) uses "" so it still sorts.
    return (rank, finding_id or "")


# Where the findings index lives in the working copy when --index isn't given.
DEFAULT_INDEX = Path("tracker") / "findings-index.csv"


def load_index_ids(root, index, final):
    """Return (ids, diagnostics) from the findings index CSV.

    ids maps each finding_id to its line in the file, or is None when the
    index can't be used, which turns off the missing/extra ID comparison.
    Each diagnostic is (level, file, line, message), level "warning" or
    "error". Line 0 means the problem is with the whole file, not one line.
    Raises RootError if the index is outside the root.
    """
    if index is None:
        index = DEFAULT_INDEX
    # A relative --index is taken from the root, like every other path.
    path = resolve_in_root(root, index)
    shown = path.relative_to(Path(root).resolve()).as_posix()
    if not path.exists():
        return None, [("warning", shown, 0,
                       "findings index not found; ID comparison skipped")]

    # A broken index is a QA problem, not a crash, so the other outputs are
    # still written: a warning while drafting, an error in --final.
    problem_level = "error" if final else "warning"
    try:
        # utf-8-sig drops the invisible marker spreadsheet programs put at
        # the start of a CSV, which would otherwise hide the finding_id name.
        # newline="" is what the csv module needs to read quoted line breaks.
        with path.open(encoding="utf-8-sig", newline="") as handle:
            # strict=True makes a badly quoted line an error instead of a guess.
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            rows = [(reader.line_num, row) for row in reader]
    except (csv.Error, UnicodeDecodeError) as error:
        return None, [(problem_level, shown, 0,
                       "findings index is not a readable CSV (" + str(error) + "); ID comparison skipped")]

    if header is None:
        return None, [("warning", shown, 1,
                       "findings index is empty; ID comparison skipped")]
    columns = [name.strip() for name in header]
    if "finding_id" not in columns:
        return None, [(problem_level, shown, 1,
                       "findings index has no finding_id column; ID comparison skipped")]
    column = columns.index("finding_id")
    ids = {}
    for line_number, row in rows:
        if len(row) > column and row[column].strip():
            ids.setdefault(row[column].strip(), line_number)
    if not ids:
        # An empty index would flag every finding as "extra", so treat a
        # file with only the header row as absent.
        return None, [("warning", shown, 1,
                       "findings index has no rows; ID comparison skipped")]
    return ids, []


# Older-style placeholders from before the [[...]] markers, one regex each.
# They can appear legitimately (e.g. "TODO" in quoted output), so they are
# always warnings, even in --final.
OLDER_LEFTOVER_PATTERNS = [
    re.compile(r"<<"),
    re.compile(r"TODO"),
    re.compile(r"F-XXX"),
    re.compile(r"IR-XXX"),
    # \b on both sides: only a bare XX, not the XX in XXE or F-XXX.
    re.compile(r"\bXX\b"),
    re.compile(r"YYYY"),
    re.compile(r"HH:MM"),
]

# An inline code span, e.g. `cat << EOF` or ``a ` inside``. Read it as: a run
# of backticks (group 1), then as little text as possible, then the same run
# again. Code is copied output, not prose, so it isn't checked.
CODE_SPAN_RE = re.compile(r"(`+).*?\1")


def hide_todo_marker_words(text):
    """Return text with the word TODO blanked inside every [[TODO: ...]] marker."""
    # The leftover-marker check already reports these markers, so their TODO
    # isn't reported twice (OQ-02). Other words inside them still count.
    for marker in MARKER_RE.findall(text):
        if marker.startswith("[[TODO:"):
            # Spaces, not "", so nothing else on the line moves or joins.
            text = text.replace(marker, marker.replace("TODO", "    "))
    return text


def scan_older_leftovers(file_name, text):
    """Return every older-style leftover as (file_name, line_number, matched_text).

    Skips fenced code blocks and `code spans`. Inside markers, only the TODO
    of a [[TODO: ...]] marker is skipped; e.g. F-XXX inside a NOTE still counts.
    """
    # Done on the whole text, so a marker spanning lines is handled. Only the
    # letters TODO change, never line breaks, so line numbers stay the same.
    text = hide_todo_marker_words(text)
    hits = []
    fence = None  # the ``` or ~~~ that opened the code block we are in
    # Split on "\n" only, so line numbers match grep -n (see above).
    for line_number, line in enumerate(text.split("\n"), start=1):
        stripped = line.lstrip()
        if fence is None and (stripped.startswith("```") or stripped.startswith("~~~")):
            fence = stripped[:3]
            continue
        if fence is not None:
            # Only the same kind of fence closes the block.
            if stripped.startswith(fence):
                fence = None
            continue
        # A space, not "", so X`code`X can't become a bare XX.
        line = CODE_SPAN_RE.sub(" ", line)
        for pattern in OLDER_LEFTOVER_PATTERNS:
            for match in pattern.finditer(line):
                hits.append((file_name, line_number, match.group(0)))
    return hits


# The heading that starts a finding's reproduction steps, as in the template.
REPRODUCTION_HEADING_RE = re.compile(r"^####[ \t]+Reproduction steps[ \t]*$")

# A ### or #### heading, which ends the reproduction section. ##### and
# deeper don't match: after three or four #, a space or tab must follow.
SECTION_END_RE = re.compile(r"^#{3,4}[ \t]")

# A numbered step: optional indent, digits, a dot, then a space or tab, e.g.
# "1. " or "  12.\t". The space after the dot matters: pasted output often
# starts with an IP address (10.0.0.5 dc01), which must not count as a step.
STEP_RE = re.compile(r"^[ \t]*\d+\.[ \t]")


def reproduction_section(text):
    """Return (heading_line_number, section_text), or None if there is no section.

    The section is every line after `#### Reproduction steps` up to the next
    ### or #### heading (or the end of the file).
    """
    lines = text.split("\n")
    for index, line in enumerate(lines):
        # rstrip() also drops the "\r" a Windows line ending leaves behind.
        if REPRODUCTION_HEADING_RE.match(line.rstrip()):
            section = []
            for section_line in lines[index + 1:]:
                if SECTION_END_RE.match(section_line):
                    break
                section.append(section_line)
            return index + 1, "\n".join(section)
    return None


def remove_note_markers(text):
    """Return text with every complete [[NOTE: ...]] marker removed."""
    for marker in MARKER_RE.findall(text):
        if marker.startswith("[[NOTE:"):
            text = text.replace(marker, "")
    return text


def check_reproduction(file_name, text):
    """Return a list of reproduction-step problems; an empty list means it passes.

    Passes when the section has at least one numbered step and at least as
    many `Expected:` lines as steps. Each problem is (file_name, line_number,
    message), or (file_name, "Reproduction steps", message) if the section is
    missing, like a missing labelled line.
    """
    found = reproduction_section(text)
    if found is None:
        return [(file_name, "Reproduction steps",
                 "missing '#### Reproduction steps' section")]
    line_number, section = found
    # The template's NOTE holds an example step and an Expected: line. Remove
    # NOTEs first so an untouched template can't pass off that example.
    section = remove_note_markers(section)
    steps = 0
    expected = 0
    for line in section.split("\n"):
        if STEP_RE.match(line):
            steps += 1
        # lstrip(): the template indents Expected: under its step.
        if line.lstrip().startswith("Expected:"):
            expected += 1
    if steps >= 1 and expected >= steps:
        return []
    return [(file_name, line_number,
             "reproduction steps: " + str(steps) + " numbered steps, "
             + str(expected) + " Expected: lines; need at least 1 step and an Expected: line for each")]


def has_text(value):
    """Return True if value, with markers removed, has a letter or digit.

    Punctuation left over from the template, like the "()" of an unfilled
    `[[CVSS_VECTOR]]` ([[CVSS_SCORE]]), doesn't count as a value.
    """
    # isalnum() is True for any Unicode letter or digit, so a value written
    # in another alphabet (e.g. an accented name) still counts.
    for character in strip_markers(value):
        if character.isalnum():
            return True
    return False


def missing_required_fields(fields):
    """Return the labels a finding needs for READY but has no value for.

    `fields` is the "fields" dict from parse_labelled_fields(). The required
    labels are FIELD_LABELS, the same six it reads (OQ-14). Reproduction
    steps are not one of them; check_reproduction() checks those separately.
    """
    missing = []
    for label in FIELD_LABELS:
        if label not in fields or not has_text(fields[label]["value"]):
            missing.append(label)
    return missing


def check_references(file_name, fields):
    """Return a list of reference problems; an empty list means it passes.

    Passes when the References line has "http" in it. Only that labelled line
    is checked: a link elsewhere in the finding doesn't count. Each problem
    is (file_name, line_number, message).
    """
    if "References" not in fields:
        # parse_labelled_fields() already reported the missing line, so
        # don't report the same problem twice.
        return []
    field = fields["References"]
    # Strip markers first, so a link inside a NOTE's example isn't taken as
    # a real reference.
    if "http" in strip_markers(field["value"]):
        return []
    return [(file_name, field["line"], "References line has no http link")]


# A full CVSS 3.1 base vector (OQ-09): all eight metrics in the standard
# order, each with one of its allowed letters, and nothing extra. One shared
# constant, so the notebook's CVSS_VECTOR warning can use the same rule (N4-03).
FULL_CVSS31_VECTOR_RE = re.compile(
    r"^CVSS:3\.1/AV:[NALP]/AC:[LH]/PR:[NHL]/UI:[NR]/S:[UC]/C:[NLH]/I:[NLH]/A:[NLH]$")


def check_cvss_version(file_name, fields, cvss_vector):
    """Return a list of CVSS-vector problems; an empty list means it passes.

    `fields` and `cvss_vector` come from parse_labelled_fields(). The vector
    must be a full CVSS 3.1 vector unless it is still the [[CVSS_VECTOR]]
    placeholder. Each problem is (file_name, line_number, message).
    """
    if "CVSS 3.1" not in fields:
        # parse_labelled_fields() already reported the missing line.
        return []
    field = fields["CVSS 3.1"]
    vector = cvss_vector
    if vector is None:
        # No backticks on the line (e.g. just "9.8"): check the whole value,
        # so a score typed in place of the vector is still reported.
        vector = field["value"]
    # Only an unfilled [[CVSS_VECTOR]] placeholder is skipped (closed or not):
    # the leftover-marker check already reports it (OQ-05). Any other marker
    # doesn't hide a bad vector, and an empty vector is reported too.
    if "[[CVSS_VECTOR" in vector:
        return []
    if FULL_CVSS31_VECTOR_RE.match(vector):
        return []
    return [(file_name, field["line"],
             "CVSS vector is not a full CVSS 3.1 vector: " + vector)]

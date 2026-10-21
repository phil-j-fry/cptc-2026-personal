"""Tests for tools/compile.py."""

import support  # puts tools/ on the import path, so it must come first
import compile

import re
import unittest


class StripMarkersTests(unittest.TestCase):
    def test_named_marker(self):
        self.assertEqual(compile.strip_markers("Host: [[HOST]] up"), "Host:  up")

    def test_choose_marker(self):
        text = "- **Severity:** [[CHOOSE: Critical / High / Low]]"
        self.assertEqual(compile.strip_markers(text), "- **Severity:** ")

    def test_todo_marker(self):
        self.assertEqual(compile.strip_markers("a [[TODO: root cause]] b"), "a  b")

    def test_multiline_note(self):
        text = "before\n[[NOTE: line one\n1. `cmd`\n   Expected: x]]\nafter"
        self.assertEqual(compile.strip_markers(text), "before\n\nafter")

    def test_adjacent_markers(self):
        self.assertEqual(compile.strip_markers("[[DATE]][[TIME]]!"), "!")

    def test_marker_starting_inside_another(self):
        # The outer NOTE can't contain `[[`, so only the inner marker is a
        # complete match; the outer one is left for the leftover check to find.
        text = "[[NOTE: see [[HOST]] here]]"
        self.assertEqual(compile.strip_markers(text), "[[NOTE: see  here]]")

    def test_unclosed_marker_does_not_swallow_next(self):
        text = "[[HOST and [[PORT]] end"
        self.assertEqual(compile.strip_markers(text), "[[HOST and  end")

    def test_unclosed_note_does_not_swallow_next(self):
        text = "[[NOTE: never closed\n[[HOST]] end"
        self.assertEqual(compile.strip_markers(text), "[[NOTE: never closed\n end")

    def test_bash_test_is_not_a_marker(self):
        text = "if [[ -f x ]]; then echo yes; fi"
        self.assertEqual(compile.strip_markers(text), text)

    def test_real_finding_template(self):
        path = support.TOOLS_DIR.parent / "templates" / "finding.md"
        stripped = compile.strip_markers(path.read_text(encoding="utf-8"))
        self.assertIsNone(re.search(r"\[\[[A-Z]", stripped))
        # The example inside the Reproduction steps NOTE must not survive,
        # or it would look like real steps to the reproduction check.
        self.assertNotIn("nxc smb", stripped)
        self.assertNotIn("Expected:", stripped)


class ScanLeftoverMarkersTests(unittest.TestCase):
    def test_complete_todo_and_unclosed_markers_reported(self):
        text = "line one\n- **Host:** [[HOST]]\n[[TODO: text]]\n\n[[NOTE: never closed\n"
        hits = compile.scan_leftover_markers("findings/F-001-x.md", text)
        self.assertEqual(hits, [
            ("findings/F-001-x.md", 2, "[[HOST"),
            ("findings/F-001-x.md", 3, "[[TODO"),
            ("findings/F-001-x.md", 5, "[[NOTE"),
        ])

    def test_bare_name_reported_and_bash_test_not(self):
        # A bare `[[HOST` (no `:` or `]]`) is still an unfinished marker, so it
        # must count; a bash test has a space after `[[` and is not a marker.
        text = "if [[ -f x ]]; then\n[[HOST\n"
        self.assertEqual(compile.scan_leftover_markers("f.md", text), [("f.md", 2, "[[HOST")])

    def test_count_equals_regex_hits(self):
        text = "[[DATE]] [[TIME]]\n[[CHOOSE: a / b]] and [[ -f x ]]\n"
        hits = compile.scan_leftover_markers("f.md", text)
        self.assertEqual(len(hits), len(compile.LEFTOVER_RE.findall(text)))
        self.assertEqual([hit[1] for hit in hits], [1, 1, 2])


class ValidateRootTests(unittest.TestCase):
    def test_root_without_git_passes(self):
        root = support.make_worktree(self, {"findings/F-001-x.md": "x\n"})
        self.assertEqual(compile.validate_root(root), root.resolve())

    def test_root_with_git_is_refused_and_nothing_created(self):
        root = support.make_worktree(self, {".git/HEAD": "ref: refs/heads/main\n"})
        before = sorted(root.rglob("*"))
        with self.assertRaisesRegex(compile.RootError, "git clone"):
            compile.validate_root(root)
        self.assertFalse((root / "build").exists())
        self.assertEqual(sorted(root.rglob("*")), before)

    def test_git_file_is_refused(self):
        # A worktree or submodule has a .git file instead of a folder.
        root = support.make_worktree(self, {".git": "gitdir: elsewhere\n"})
        with self.assertRaises(compile.RootError):
            compile.validate_root(root)

    def test_missing_root_is_refused(self):
        root = support.make_worktree(self)
        with self.assertRaisesRegex(compile.RootError, "not found"):
            compile.validate_root(root / "no-such-folder")
        self.assertFalse((root / "no-such-folder").exists())

    def test_file_as_root_is_refused(self):
        root = support.make_worktree(self, {"report.md": "x\n"})
        with self.assertRaisesRegex(compile.RootError, "not a folder"):
            compile.validate_root(root / "report.md")


class ResolveInRootTests(unittest.TestCase):
    def setUp(self):
        self.root = support.make_worktree(self, {
            "findings/F-001-x.md": "x\n",
            "findings/a..b.md": "x\n",
        })
        # A second worktree stands in for "somewhere outside the root", so the
        # tests never point at anything outside tools/tests/.tmp/.
        self.outside = support.make_worktree(self, {"findings/F-009-y.md": "y\n"})

    def test_normal_child_passes(self):
        resolved = compile.resolve_in_root(self.root, "findings/F-001-x.md")
        self.assertEqual(resolved, self.root.resolve() / "findings" / "F-001-x.md")

    def test_double_dot_inside_a_filename_passes(self):
        resolved = compile.resolve_in_root(self.root, "findings/a..b.md")
        self.assertEqual(resolved.name, "a..b.md")

    def test_symlink_inside_root_passes(self):
        (self.root / "latest").symlink_to(self.root / "findings")
        resolved = compile.resolve_in_root(self.root, "latest/F-001-x.md")
        self.assertEqual(resolved, self.root.resolve() / "findings" / "F-001-x.md")

    def test_absolute_path_inside_root_passes(self):
        # A real `--index ~/cptc-work/tracker/findings-index.csv` is absolute
        # once ~ is expanded, and must be allowed when it is inside the root.
        index = self.root.resolve() / "tracker" / "findings-index.csv"
        self.assertEqual(compile.resolve_in_root(self.root, index), index)

    def test_dot_dot_part_is_refused(self):
        with self.assertRaisesRegex(compile.RootError, re.escape("../x")):
            compile.resolve_in_root(self.root, "../x")

    def test_absolute_outside_path_is_refused(self):
        target = str(self.outside / "findings")
        with self.assertRaisesRegex(compile.RootError, re.escape(target)):
            compile.resolve_in_root(self.root, target)

    def test_index_outside_root_is_refused(self):
        index = self.outside / "tracker" / "findings-index.csv"
        with self.assertRaisesRegex(compile.RootError, re.escape(str(index))):
            compile.resolve_in_root(self.root, index)

    def test_symlinked_incoming_folder_outside_root_is_refused(self):
        (self.root / "incoming").mkdir()
        (self.root / "incoming" / "alice").symlink_to(self.outside)
        with self.assertRaisesRegex(compile.RootError, re.escape("incoming/alice")):
            compile.resolve_in_root(self.root, "incoming/alice/findings/F-009-y.md")


class DiscoverFindingsTests(unittest.TestCase):
    def test_only_local_and_incoming_findings_returned_in_path_order(self):
        finding = support.make_complete_finding()
        root = support.make_worktree(self, {
            "incoming/bob/findings/F-001-sql-injection.md": finding,
            "incoming/alice/findings/F-001-default-password.md": finding,
            "findings/F-001-default-password.md": finding,
            # Each of these must be left out:
            "findings/G-001.md": "x\n",
            "findings/F-002-notes.txt": "x\n",
            "findings/drafts/F-003-nested.md": "x\n",
            "incoming/alice/notes/F-004-study.md": "x\n",
            "incoming/alice/field-notes/alice/NOTE-recon.md": "x\n",
            "notes/F-005-study.md": "x\n",
        })
        found = compile.discover_findings(root)
        relative = [path.relative_to(root.resolve()).as_posix() for path in found]
        self.assertEqual(relative, [
            "findings/F-001-default-password.md",
            "incoming/alice/findings/F-001-default-password.md",
            "incoming/bob/findings/F-001-sql-injection.md",
        ])

    def test_folder_named_like_a_finding_is_skipped(self):
        root = support.make_worktree(self, {"findings/F-001-x.md/inside.md": "x\n"})
        self.assertEqual(compile.discover_findings(root), [])

    def test_no_findings_folders_returns_empty_list(self):
        root = support.make_worktree(self)
        self.assertEqual(compile.discover_findings(root), [])

    def test_incoming_symlinked_outside_root_is_refused(self):
        root = support.make_worktree(self, {"findings/F-001-x.md": "x\n"})
        outside = support.make_worktree(self, {"findings/F-009-y.md": "y\n"})
        (root / "incoming").mkdir()
        (root / "incoming" / "alice").symlink_to(outside)
        with self.assertRaisesRegex(compile.RootError, re.escape("incoming/alice")):
            compile.discover_findings(root)

    def test_outside_symlink_with_no_findings_is_still_refused(self):
        # The link must be refused before its target is listed, not only
        # when a finding happens to be found there.
        root = support.make_worktree(self)
        outside = support.make_worktree(self, {"other/readme.md": "y\n"})
        (root / "incoming").mkdir()
        (root / "incoming" / "alice").symlink_to(outside)
        with self.assertRaisesRegex(compile.RootError, re.escape("incoming/alice")):
            compile.discover_findings(root)

    def test_incoming_entry_symlinked_to_outside_file_is_refused(self):
        root = support.make_worktree(self)
        outside = support.make_worktree(self, {"readme.md": "y\n"})
        (root / "incoming").mkdir()
        (root / "incoming" / "alice").symlink_to(outside / "readme.md")
        with self.assertRaisesRegex(compile.RootError, re.escape("incoming/alice")):
            compile.discover_findings(root)

    def test_findings_folder_symlinked_outside_root_is_refused(self):
        root = support.make_worktree(self)
        outside = support.make_worktree(self, {"F-009-y.md": "y\n"})
        (root / "findings").symlink_to(outside)
        with self.assertRaisesRegex(compile.RootError, re.escape("findings")):
            compile.discover_findings(root)

    def test_finding_file_symlinked_outside_root_is_refused(self):
        root = support.make_worktree(self, {"findings/F-001-x.md": "x\n"})
        outside = support.make_worktree(self, {"F-009-y.md": "y\n"})
        (root / "findings" / "F-009-y.md").symlink_to(outside / "F-009-y.md")
        with self.assertRaisesRegex(compile.RootError, re.escape("F-009-y.md")):
            compile.discover_findings(root)

    def test_symlink_inside_root_is_allowed(self):
        root = support.make_worktree(self, {"shared/findings/F-002-y.md": "y\n"})
        (root / "incoming").mkdir()
        (root / "incoming" / "bob").symlink_to(root / "shared")
        found = compile.discover_findings(root)
        self.assertEqual([path.name for path in found], ["F-002-y.md"])

    def test_incoming_is_not_changed(self):
        root = support.make_worktree(self, {
            "incoming/alice/findings/F-001-x.md": support.make_complete_finding(),
        })
        incoming = root / "incoming"
        before = [(path, path.stat().st_mtime_ns) for path in sorted(incoming.rglob("*"))]
        compile.discover_findings(root)
        after = [(path, path.stat().st_mtime_ns) for path in sorted(incoming.rglob("*"))]
        self.assertEqual(after, before)


class ParseFindingHeadingTests(unittest.TestCase):
    def test_filled_heading(self):
        text = support.make_complete_finding("F-001", "Default admin password on web01")
        result = compile.parse_finding_heading("findings/F-001-default-password.md", text)
        self.assertEqual(result, {
            "id": "F-001",
            "title": "Default admin password on web01",
            "line": 1,
            "heading_markers": 0,
            "diagnostics": [],
        })

    def test_marker_heading_uses_filename_id_and_counts_marker(self):
        text = "### [[FINDING_ID]]: SMB signing not required\n\n- **Severity:** High\n"
        result = compile.parse_finding_heading("incoming/alice/findings/F-007-smb.md", text)
        self.assertEqual(result["id"], "F-007")
        self.assertEqual(result["title"], "SMB signing not required")
        self.assertEqual(result["heading_markers"], 1)
        self.assertEqual(result["diagnostics"], [])

    def test_untouched_template_heading(self):
        path = support.TOOLS_DIR.parent / "templates" / "finding.md"
        result = compile.parse_finding_heading("findings/F-003-x.md", path.read_text(encoding="utf-8"))
        self.assertEqual(result["id"], "F-003")
        self.assertEqual(result["title"], "[[FINDING_TITLE]]")
        self.assertEqual(result["heading_markers"], 2)

    def test_heading_and_filename_mismatch(self):
        text = support.make_complete_finding("F-002")
        result = compile.parse_finding_heading("findings/F-001-x.md", text)
        self.assertEqual(result["id"], "F-002")
        self.assertEqual(result["diagnostics"], [
            ("findings/F-001-x.md", 1, "heading ID F-002 does not match filename ID F-001"),
        ])

    def test_two_hashes_instead_of_three(self):
        text = "Intro line\n## F-001: Default admin password\n"
        result = compile.parse_finding_heading("findings/F-001-x.md", text)
        self.assertEqual(result["id"], "F-001")
        self.assertEqual(result["line"], 2)
        self.assertEqual(result["diagnostics"], [
            ("findings/F-001-x.md", 2, "title is a ## heading, not ###"),
        ])

    def test_no_heading_falls_back_to_filename_id(self):
        result = compile.parse_finding_heading("findings/F-001-x.md", "Default admin password\n")
        self.assertEqual(result["id"], "F-001")
        self.assertIsNone(result["title"])
        self.assertEqual(result["diagnostics"], [
            ("findings/F-001-x.md", 1, "no finding title heading like '### F-NNN: Title'"),
        ])

    def test_blank_title_is_reported(self):
        result = compile.parse_finding_heading("findings/F-001-x.md", "### F-001:  \n")
        self.assertEqual(result["title"], "")
        self.assertEqual(result["diagnostics"], [
            ("findings/F-001-x.md", 1, "heading has no title text"),
        ])

    def test_marker_heading_without_filename_id(self):
        # A library entry such as L03-*.md has no F-NNN in its name.
        text = "### [[FINDING_ID]]: SMB signing not required\n"
        result = compile.parse_finding_heading("findings-library/L03-smb.md", text)
        self.assertIsNone(result["id"])
        self.assertEqual(result["diagnostics"], [
            ("findings-library/L03-smb.md", 1, "no finding ID in the heading or the filename"),
        ])

    def test_windows_line_ending_is_not_part_of_the_title(self):
        text = "### F-001: Default admin password\r\n- **Severity:** High\r\n"
        result = compile.parse_finding_heading("findings/F-001-x.md", text)
        self.assertEqual(result["title"], "Default admin password")
        self.assertEqual(result["diagnostics"], [])

    def test_four_digit_filename_is_not_read_as_three(self):
        text = "### [[FINDING_ID]]: x\n"
        result = compile.parse_finding_heading("findings/F-0012-x.md", text)
        self.assertIsNone(result["id"])


class ParseLabelledFieldsTests(unittest.TestCase):
    def test_complete_finding_returns_all_six_labels_and_cvss_parts(self):
        result = compile.parse_labelled_fields("findings/F-001-x.md", support.make_complete_finding())
        fields = result["fields"]
        self.assertEqual(sorted(fields), sorted(compile.FIELD_LABELS))
        self.assertEqual(fields["Severity"], {"value": "Critical", "line": 3})
        self.assertEqual(fields["CVSS 3.1"]["value"],
                         "`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8)")
        self.assertTrue(fields["Why this severity"]["value"].startswith("We logged in"))
        self.assertEqual(fields["Affected assets"]["value"],
                         "web01 (10.0.0.1), http://10.0.0.1/login, admin")
        self.assertEqual(fields["Status"]["value"], "Exploited")
        self.assertIn("https://example.invalid/", fields["References"]["value"])
        self.assertEqual(result["cvss_vector"], "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")
        self.assertEqual(result["cvss_score"], "9.8")
        self.assertEqual(result["diagnostics"], [])

    def test_missing_label_is_reported_not_raised(self):
        text = support.make_complete_finding().replace(
            "- **Status:** Exploited\n", "")
        result = compile.parse_labelled_fields("findings/F-001-x.md", text)
        self.assertNotIn("Status", result["fields"])
        self.assertEqual(result["diagnostics"], [
            ("findings/F-001-x.md", "Status", "missing labelled line '- **Status:**'"),
        ])

    def test_duplicate_label_is_reported_and_first_line_wins(self):
        text = support.make_complete_finding().replace(
            "- **Severity:** Critical\n",
            "- **Severity:** Critical\n- **Severity:** Low\n- **Severity:** High\n")
        result = compile.parse_labelled_fields("findings/F-001-x.md", text)
        self.assertEqual(result["fields"]["Severity"], {"value": "Critical", "line": 3})
        self.assertEqual(result["diagnostics"], [
            ("findings/F-001-x.md", 4, "duplicate Severity line; line 3 is used"),
            ("findings/F-001-x.md", 5, "duplicate Severity line; line 3 is used"),
        ])

    def test_extra_whitespace_is_tolerated(self):
        text = "  -   ** Severity :**   High  \n-\t**Status:**\tConfirmed\n"
        fields = compile.parse_labelled_fields("f.md", text)["fields"]
        self.assertEqual(fields["Severity"], {"value": "High", "line": 1})
        self.assertEqual(fields["Status"], {"value": "Confirmed", "line": 2})

    def test_windows_line_endings_leave_no_carriage_return(self):
        text = "- **Severity:** High\r\n- **Status:** Confirmed\r\n"
        fields = compile.parse_labelled_fields("f.md", text)["fields"]
        self.assertEqual(fields["Severity"], {"value": "High", "line": 1})
        self.assertEqual(fields["Status"], {"value": "Confirmed", "line": 2})

    def test_untouched_template_keeps_markers_as_written(self):
        path = support.TOOLS_DIR.parent / "templates" / "finding.md"
        result = compile.parse_labelled_fields("findings/F-001-x.md", path.read_text(encoding="utf-8"))
        self.assertEqual(result["diagnostics"], [])
        self.assertEqual(result["fields"]["Severity"]["value"],
                         "[[CHOOSE: Critical / High / Medium / Low / Informational]]")
        self.assertEqual(result["cvss_vector"], "[[CVSS_VECTOR]]")
        self.assertEqual(result["cvss_score"], "[[CVSS_SCORE]]")

    def test_cvss_without_backticks_or_parentheses(self):
        text = "- **CVSS 3.1:** 9.8\n"
        result = compile.parse_labelled_fields("f.md", text)
        self.assertIsNone(result["cvss_vector"])
        self.assertIsNone(result["cvss_score"])

    def test_score_is_not_read_from_inside_the_vector(self):
        text = "- **CVSS 3.1:** `CVSS:3.1/AV:N (typo)` (7.5)\n"
        result = compile.parse_labelled_fields("f.md", text)
        self.assertEqual(result["cvss_vector"], "CVSS:3.1/AV:N (typo)")
        self.assertEqual(result["cvss_score"], "7.5")

    def test_empty_file_reports_every_label(self):
        result = compile.parse_labelled_fields("f.md", "")
        self.assertEqual([d[1] for d in result["diagnostics"]], compile.FIELD_LABELS)


def severity_of(line):
    """Parse one Severity line the way compile does: label first, then level."""
    fields = compile.parse_labelled_fields("findings/F-001-x.md", line + "\n")["fields"]
    return compile.severity_value("findings/F-001-x.md", fields)


class SeverityValueTests(unittest.TestCase):
    def test_filled_level(self):
        self.assertEqual(severity_of("- **Severity:** High"), ("High", []))

    def test_unfilled_choose_yields_no_severity_and_warns(self):
        line = "- **Severity:** [[CHOOSE: Critical / High / Medium / Low / Informational]]"
        self.assertEqual(severity_of(line), (None, [
            ("findings/F-001-x.md", 1,
             "no severity (Critical, High, Medium, Low or Informational); sorted last"),
        ]))

    def test_lowercase_yields_no_severity(self):
        severity, diagnostics = severity_of("- **Severity:** high")
        self.assertIsNone(severity)
        self.assertEqual(len(diagnostics), 1)

    def test_part_of_a_word_does_not_count(self):
        self.assertIsNone(severity_of("- **Severity:** Highest")[0])

    def test_first_level_wins_and_markers_are_stripped(self):
        # The library's default Medium, with its NOTE still attached.
        line = "- **Severity:** Medium [[NOTE: Library default; High if exploited.]]"
        self.assertEqual(severity_of(line), ("Medium", []))
        self.assertEqual(severity_of("- **Severity:** Low (was High)")[0], "Low")

    def test_missing_line_is_not_reported_twice(self):
        # parse_labelled_fields() already reports the missing label.
        self.assertEqual(compile.severity_value("f.md", {}), (None, []))


class FindingSortKeyTests(unittest.TestCase):
    def test_severity_order_then_missing_then_id(self):
        findings = [
            ("F-009", None),
            ("F-004", "Informational"),
            ("F-002", "Low"),
            ("F-007", "Critical"),
            ("F-003", None),
            ("F-005", "High"),
            ("F-006", "Medium"),
            ("F-001", "High"),
        ]
        ordered = sorted(findings, key=lambda f: compile.finding_sort_key(*f))
        self.assertEqual(ordered, [
            ("F-007", "Critical"),
            ("F-001", "High"),
            ("F-005", "High"),
            ("F-006", "Medium"),
            ("F-002", "Low"),
            ("F-004", "Informational"),
            ("F-003", None),
            ("F-009", None),
        ])

    def test_missing_id_still_sorts(self):
        self.assertEqual(compile.finding_sort_key(None, None), (5, ""))


INDEX_HEADER = "finding_id,title,severity,cvss_score,owner,status,in_report\n"


class LoadIndexIdsTests(unittest.TestCase):
    def test_default_index_loads_an_f001_row(self):
        root = support.make_worktree(self, {
            "tracker/findings-index.csv": INDEX_HEADER + "F-001,Default password,High,9.8,alice,done,yes\n",
        })
        self.assertEqual(compile.load_index_ids(root, None, False), ({"F-001": 2}, []))

    def test_explicit_in_root_index_wins(self):
        root = support.make_worktree(self, {
            "tracker/findings-index.csv": INDEX_HEADER + "F-001,x,,,,,\n",
            "lead/index.csv": INDEX_HEADER + "F-002,y,,,,,\n",
        })
        self.assertEqual(compile.load_index_ids(root, "lead/index.csv", False), ({"F-002": 2}, []))
        absolute = root.resolve() / "lead" / "index.csv"
        self.assertEqual(compile.load_index_ids(root, absolute, True), ({"F-002": 2}, []))

    def test_explicit_index_outside_root_is_refused(self):
        root = support.make_worktree(self)
        outside = support.make_worktree(self, {"index.csv": INDEX_HEADER + "F-001,x,,,,,\n"})
        with self.assertRaises(compile.RootError):
            compile.load_index_ids(root, outside / "index.csv", False)

    def test_absent_index_warns_and_skips_comparison(self):
        root = support.make_worktree(self)
        for final in (False, True):
            self.assertEqual(compile.load_index_ids(root, None, final), (None, [
                ("warning", "tracker/findings-index.csv", 0,
                 "findings index not found; ID comparison skipped"),
            ]))

    def test_header_only_index_warns_and_skips_comparison(self):
        root = support.make_worktree(self, {"tracker/findings-index.csv": INDEX_HEADER + "\n"})
        for final in (False, True):
            self.assertEqual(compile.load_index_ids(root, None, final), (None, [
                ("warning", "tracker/findings-index.csv", 1,
                 "findings index has no rows; ID comparison skipped"),
            ]))

    def test_empty_file_warns_and_skips_comparison(self):
        root = support.make_worktree(self, {"tracker/findings-index.csv": ""})
        ids, diagnostics = compile.load_index_ids(root, None, True)
        self.assertIsNone(ids)
        self.assertEqual([d[0] for d in diagnostics], ["warning"])

    def test_malformed_csv_is_warning_in_draft_and_error_in_final(self):
        root = support.make_worktree(self, {
            "tracker/findings-index.csv": INDEX_HEADER + '"F-001"x,y\n',
        })
        for final, level in ((False, "warning"), (True, "error")):
            ids, diagnostics = compile.load_index_ids(root, None, final)
            self.assertIsNone(ids)
            self.assertEqual(len(diagnostics), 1)
            self.assertEqual(diagnostics[0][:3], (level, "tracker/findings-index.csv", 0))
            self.assertIn("not a readable CSV", diagnostics[0][3])

    def test_missing_finding_id_column_is_warning_in_draft_and_error_in_final(self):
        root = support.make_worktree(self, {
            "tracker/findings-index.csv": "title,severity\nDefault password,High\n",
        })
        for final, level in ((False, "warning"), (True, "error")):
            self.assertEqual(compile.load_index_ids(root, None, final), (None, [
                (level, "tracker/findings-index.csv", 1,
                 "findings index has no finding_id column; ID comparison skipped"),
            ]))

    def test_spreadsheet_bom_and_spaces_are_tolerated(self):
        # Excel saves "UTF-8 CSV" with an invisible marker before the header.
        root = support.make_worktree(self, {
            "tracker/findings-index.csv": "﻿title, finding_id\nx, F-003 \ny,\n",
        })
        self.assertEqual(compile.load_index_ids(root, None, False), ({"F-003": 2}, []))


class ScanOlderLeftoversTests(unittest.TestCase):
    def scan(self, text):
        return [hit[2] for hit in compile.scan_older_leftovers("f.md", text)]

    def test_each_pattern_found_in_prose_with_line(self):
        text = "a << b\nTODO fix\nsee F-XXX and IR-XXX\nport XX open\nYYYY at HH:MM\n"
        self.assertEqual(compile.scan_older_leftovers("f.md", text), [
            ("f.md", 1, "<<"), ("f.md", 2, "TODO"), ("f.md", 3, "F-XXX"),
            ("f.md", 3, "IR-XXX"), ("f.md", 4, "XX"), ("f.md", 5, "YYYY"),
            ("f.md", 5, "HH:MM"),
        ])

    def test_xxe_is_not_bare_xx(self):
        self.assertEqual(self.scan("XXE injection in XXXL form"), [])

    def test_fenced_and_inline_code_skipped(self):
        text = "```\ncat << EOF\nTODO XX\n```\nrun `echo TODO F-XXX` here\nafter TODO\n"
        self.assertEqual(compile.scan_older_leftovers("f.md", text), [("f.md", 6, "TODO")])

    def test_tilde_fence_skipped_and_fence_kinds_not_mixed(self):
        text = "~~~\nTODO\n```\nYYYY\n~~~\nafter TODO\n"
        self.assertEqual(compile.scan_older_leftovers("f.md", text), [("f.md", 6, "TODO")])

    def test_double_backtick_span_skipped(self):
        self.assertEqual(self.scan("run ``TODO ` F-XXX`` then YYYY"), ["YYYY"])

    def test_code_span_does_not_join_xs(self):
        self.assertEqual(self.scan("X`code`X"), [])

    def test_todo_inside_todo_marker_skipped(self):
        self.assertEqual(self.scan("[[TODO: root cause]] and [[TODO: a\nTODO b]]"), [])

    def test_other_patterns_inside_markers_still_reported(self):
        self.assertEqual(self.scan("[[NOTE: use F-XXX\nthen YYYY]]"), ["F-XXX", "YYYY"])
        self.assertEqual(self.scan("[[TODO: fill F-XXX]]"), ["F-XXX"])

    def test_todo_inside_other_marker_still_reported(self):
        self.assertEqual(self.scan("[[NOTE: TODO later]]"), ["TODO"])


class CheckReproductionTests(unittest.TestCase):
    def finding(self, steps):
        return "### F-001: T\n\n#### Reproduction steps\n" + steps + "\n#### Evidence\nx\n"

    def test_two_steps_two_indented_expected_pass(self):
        text = self.finding("1. `cmd one`\n   Expected: a\n2. `cmd two`\n   Expected: b\n")
        self.assertEqual(compile.check_reproduction("f.md", text), [])

    def test_one_expected_fails_two_steps(self):
        text = self.finding("1. `cmd one`\n   Expected: a\n2. `cmd two`\n")
        self.assertEqual(compile.check_reproduction("f.md", text), [
            ("f.md", 3, "reproduction steps: 2 numbered steps, 1 Expected: lines; "
                        "need at least 1 step and an Expected: line for each"),
        ])

    def test_ip_first_output_lines_are_not_steps(self):
        # Pasted output such as /etc/hosts starts lines with an IP address.
        text = self.finding("1. `cat /etc/hosts`\n   Expected: the host list\n"
                            "```\n10.0.0.5 dc01\n10.0.0.6 web01\n```\n")
        self.assertEqual(compile.check_reproduction("f.md", text), [])

    def test_no_steps_fails(self):
        problems = compile.check_reproduction("f.md", self.finding("Expected: a\n"))
        self.assertIn("0 numbered steps", problems[0][2])

    def test_untouched_template_fails_despite_note_example(self):
        path = support.TOOLS_DIR.parent / "templates" / "finding.md"
        text = path.read_text(encoding="utf-8")
        # The NOTE's example really is in the section, so this test means something.
        self.assertIn("Expected:", compile.reproduction_section(text)[1])
        problems = compile.check_reproduction("templates/finding.md", text)
        self.assertEqual(len(problems), 1)
        self.assertIn("0 numbered steps, 0 Expected: lines", problems[0][2])

    def test_complete_finding_passes(self):
        text = support.make_complete_finding()
        self.assertEqual(compile.check_reproduction("f.md", text), [])

    def test_steps_after_next_heading_not_counted(self):
        text = self.finding("1. `cmd`\n") + "   Expected: a\n"
        self.assertEqual(len(compile.check_reproduction("f.md", text)), 1)

    def test_deeper_heading_does_not_end_section(self):
        text = self.finding("1. `cmd`\n##### detail\n   Expected: a\n")
        self.assertEqual(compile.check_reproduction("f.md", text), [])

    def test_windows_line_endings(self):
        text = self.finding("1. `cmd`\n   Expected: a\n").replace("\n", "\r\n")
        self.assertEqual(compile.check_reproduction("f.md", text), [])

    def test_missing_section_reported(self):
        self.assertEqual(compile.check_reproduction("f.md", "### F-001: T\n"), [
            ("f.md", "Reproduction steps", "missing '#### Reproduction steps' section"),
        ])


class HasTextTests(unittest.TestCase):
    def test_punctuation_only_remnants_are_missing(self):
        # Untouched template values once their markers are stripped.
        self.assertFalse(compile.has_text("[[HOST]] ([[HOST_IP]]), [[URL]], [[ACCOUNT]]"))
        self.assertFalse(compile.has_text("() ,"))
        self.assertFalse(compile.has_text("`[[CVSS_VECTOR]]` ([[CVSS_SCORE]])"))
        self.assertFalse(compile.has_text("`` ()"))
        self.assertFalse(compile.has_text("[[SEVERITY_RATIONALE]] [[NOTE: One line.]]"))
        self.assertFalse(compile.has_text(""))

    def test_filled_values_pass(self):
        self.assertTrue(compile.has_text("web01 (10.0.0.1)"))
        self.assertTrue(compile.has_text("`` (9)"))
        self.assertTrue(compile.has_text("Café"))

    def test_untouched_template_fields_missing(self):
        path = support.TOOLS_DIR.parent / "templates" / "finding.md"
        fields = compile.parse_labelled_fields("t.md", path.read_text(encoding="utf-8"))["fields"]
        # References is not missing: see the next test (DECISIONS 2026-10-20 C-11).
        self.assertEqual(compile.missing_required_fields(fields), [
            "Severity", "CVSS 3.1", "Why this severity", "Affected assets", "Status"])

    def test_untouched_references_remnant_counts_as_present(self):
        # "CWE-, ATT&CK ," has letters, so it counts as text (user decision,
        # option A). Its leftover markers still keep the finding from READY,
        # and the reference check (C-12) still fails it for having no http link.
        value = "CWE-[[CWE_ID]], ATT&CK [[ATTACK_TECHNIQUE_ID]], [[REFERENCE_URL]]"
        self.assertTrue(compile.has_text(value))

    def test_complete_finding_has_no_missing_fields(self):
        fields = compile.parse_labelled_fields("f.md", support.make_complete_finding())["fields"]
        self.assertEqual(compile.missing_required_fields(fields), [])

    def test_absent_label_counts_as_missing(self):
        text = support.make_complete_finding().replace("- **Status:**", "- **State:**")
        fields = compile.parse_labelled_fields("f.md", text)["fields"]
        self.assertEqual(compile.missing_required_fields(fields), ["Status"])

    def test_one_blank_value_counted_once(self):
        lines = []
        for line in support.make_complete_finding().split("\n"):
            if line.startswith("- **Why this severity:**"):
                line = "- **Why this severity:** [[SEVERITY_RATIONALE]] ."
            lines.append(line)
        fields = compile.parse_labelled_fields("f.md", "\n".join(lines))["fields"]
        self.assertEqual(compile.missing_required_fields(fields), ["Why this severity"])

    def test_reproduction_does_not_affect_missing_fields(self):
        text = support.make_complete_finding()
        no_steps = text.split("#### Reproduction steps")[0]
        self.assertNotEqual(compile.check_reproduction("f.md", no_steps), [])
        fields = compile.parse_labelled_fields("f.md", no_steps)["fields"]
        self.assertEqual(compile.missing_required_fields(fields), [])


class CheckReferencesTests(unittest.TestCase):
    def check(self, text):
        fields = compile.parse_labelled_fields("f.md", text)["fields"]
        return compile.check_references("f.md", fields)

    def test_references_without_http_fails(self):
        self.assertEqual(self.check("- **References:** CWE-798, ATT&CK T1078\n"),
                         [("f.md", 1, "References line has no http link")])

    def test_https_link_passes(self):
        self.assertEqual(self.check("- **References:** CWE-798, https://example.invalid/advisory\n"), [])

    def test_link_outside_the_labelled_line_does_not_count(self):
        text = "- **References:** CWE-798\n\nSee https://example.invalid for more.\n"
        self.assertEqual(self.check(text), [("f.md", 1, "References line has no http link")])

    def test_link_inside_a_marker_does_not_count(self):
        text = "- **References:** [[REFERENCE_URL]] [[NOTE: e.g. https://example.invalid]]\n"
        self.assertEqual(len(self.check(text)), 1)

    def test_untouched_template_fails(self):
        path = support.TOOLS_DIR.parent / "templates" / "finding.md"
        self.assertEqual(len(self.check(path.read_text(encoding="utf-8"))), 1)

    def test_complete_finding_passes(self):
        self.assertEqual(self.check(support.make_complete_finding()), [])

    def test_missing_line_not_reported_twice(self):
        self.assertEqual(self.check("- **Severity:** High\n"), [])


class CheckCvssVersionTests(unittest.TestCase):
    def check(self, cvss_line):
        parsed = compile.parse_labelled_fields("f.md", "- **CVSS 3.1:** " + cvss_line + "\n")
        return compile.check_cvss_version("f.md", parsed["fields"], parsed["cvss_vector"])

    def test_cvss_31_vector_passes(self):
        self.assertEqual(self.check("`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8)"), [])

    def test_cvss_30_vector_fails_with_line(self):
        self.assertEqual(self.check("`CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8)"), [
            ("f.md", 1, "CVSS vector is not a full CVSS 3.1 vector: "
                        "CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"),
        ])

    def test_bare_score_fails(self):
        self.assertEqual(self.check("9.8"),
                         [("f.md", 1, "CVSS vector is not a full CVSS 3.1 vector: 9.8")])
        self.assertEqual(len(self.check("`9.8`")), 1)

    def test_missing_metric_fails(self):
        self.assertEqual(len(self.check("`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H` (9.8)")), 1)

    def test_reordered_metrics_fail(self):
        self.assertEqual(len(self.check("`CVSS:3.1/AC:L/AV:N/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8)")), 1)

    def test_extra_metric_fails(self):
        self.assertEqual(len(self.check("`CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/E:P` (9.8)")), 1)

    def test_unfilled_vector_marker_skipped(self):
        self.assertEqual(self.check("`[[CVSS_VECTOR]]` ([[CVSS_SCORE]])"), [])
        self.assertEqual(self.check("`[[CVSS_VECTOR` (9.8)"), [])

    def test_other_marker_does_not_hide_wrong_version(self):
        self.assertEqual(len(self.check("`CVSS:3.0/AV:N [[TODO: fix]]` (9.8)")), 1)

    def test_empty_vector_fails(self):
        self.assertEqual(self.check("`` (9.8)"),
                         [("f.md", 1, "CVSS vector is not a full CVSS 3.1 vector: ")])
        self.assertEqual(len(self.check("`` ()")), 1)

    def test_complete_finding_passes(self):
        parsed = compile.parse_labelled_fields("f.md", support.make_complete_finding())
        self.assertEqual(compile.check_cvss_version("f.md", parsed["fields"], parsed["cvss_vector"]), [])

    def test_missing_line_not_reported_twice(self):
        self.assertEqual(compile.check_cvss_version("f.md", {}, None), [])


if __name__ == "__main__":
    unittest.main()

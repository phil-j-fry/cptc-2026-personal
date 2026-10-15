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


if __name__ == "__main__":
    unittest.main()

"""Tests for tools/notebook.py."""

import support  # puts tools/ on the import path, so it must come first
import notebook
import compile

import ast
import contextlib
import http.client
import io
import json
import os
import socket
import string
import threading
import unittest
from html.parser import HTMLParser
from http.server import HTTPServer
from unittest import mock
from urllib.parse import quote


class StartupTests(unittest.TestCase):
    def test_git_root_exits_before_anything_is_created(self):
        root = support.make_worktree(self, {".git/HEAD": "ref: refs/heads/main\n"})
        before = sorted(root.rglob("*"))
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), \
                mock.patch.object(notebook, "HTTPServer") as server_class:
            exit_code = notebook.main(["--name", "alice", "--root", str(root)])
        self.assertEqual(exit_code, 2)
        self.assertTrue(printed.getvalue().startswith(
            "notebook failed: this looks like the git clone"))
        # Nothing was created: no server, no field-notes/alice/, no state file.
        server_class.assert_not_called()
        self.assertEqual(sorted(root.rglob("*")), before)

    def test_parser_has_no_bind_address_option(self):
        # The server always binds to 127.0.0.1 (Constraint 2), so there must
        # be no option that could expose it to the network.
        for option in ["--host", "--bind", "--address", "--listen"]:
            with self.subTest(option=option), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    notebook.parse_args(["--name", "alice", option, "0.0.0.0"])

    def test_port_must_be_a_real_port_number(self):
        self.assertEqual(notebook.parse_args(["--name", "alice", "--port", "9000"]).port, 9000)
        for port in ["0", "65536", "-1", "abc", "\u0663"]:
            with self.subTest(port=port), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    notebook.parse_args(["--name", "alice", "--port", port])


class ServeTests(unittest.TestCase):
    def setUp(self):
        self.root = support.make_worktree(self, {"findings/F-001-x.md": "x\n"})

    def run_main(self, port):
        """Run main() with the server faked; Ctrl+C stops it at once."""
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed), \
                mock.patch.object(notebook, "HTTPServer") as server_class:
            server = server_class.return_value
            server.server_address = ("127.0.0.1", port)
            server.serve_forever.side_effect = KeyboardInterrupt
            exit_code = notebook.main(["--name", "alice", "--root", str(self.root),
                                       "--port", str(port)])
        return exit_code, printed.getvalue(), server_class

    def test_serves_on_literal_loopback_and_prints_the_url(self):
        exit_code, printed, server_class = self.run_main(9123)
        self.assertEqual(exit_code, 0)
        server_class.assert_called_once_with(("127.0.0.1", 9123), notebook.NotebookHandler)
        server = server_class.return_value
        self.assertGreaterEqual(len(server.token), 43)
        self.assertEqual(server.settings["name"], "alice")
        self.assertIn("http://127.0.0.1:9123\n", printed)
        self.assertIn("Local only", printed)
        server.server_close.assert_called_once_with()

    def test_real_server_listens_on_127_0_0_1_with_a_token(self):
        server = notebook.make_server({"port": 0})
        self.addCleanup(server.server_close)
        self.assertEqual(server.server_address[0], "127.0.0.1")
        self.assertEqual(server.RequestHandlerClass, notebook.NotebookHandler)
        second = notebook.make_server({"port": 0})
        self.addCleanup(second.server_close)
        self.assertNotEqual(server.token, second.token)

    def test_port_in_use_exits_readably(self):
        taken = HTTPServer(("127.0.0.1", 0), notebook.NotebookHandler)
        self.addCleanup(taken.server_close)
        port = taken.server_address[1]
        printed = io.StringIO()
        # If main() ever got a server anyway, Ctrl+C stops it instead of the
        # test hanging forever.
        with contextlib.redirect_stdout(printed), \
                mock.patch.object(HTTPServer, "serve_forever", side_effect=KeyboardInterrupt):
            exit_code = notebook.main(["--name", "alice", "--root", str(self.root),
                                       "--port", str(port)])
        self.assertEqual(exit_code, 2)
        self.assertTrue(printed.getvalue().startswith(
            "notebook failed: can't listen on 127.0.0.1:" + str(port)))

    def test_page_needs_no_network_address(self):
        # Constraint 1: no CDN or other outside file; the page works offline.
        self.assertNotIn("http", notebook.APP_PAGE)
        self.assertNotIn("//", notebook.APP_PAGE)


class ModuleSafetyTests(unittest.TestCase):
    """Constraint 3, tested the same way as compile.py's (Chunk N1 D2)."""

    TREE = ast.parse((support.TOOLS_DIR / "notebook.py").read_text(encoding="utf-8"))

    def test_only_safe_modules_are_imported(self):
        imported = set()
        for node in ast.walk(self.TREE):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module)
        # No subprocess. os is for $LOGDIR and the tick-state file's safe
        # write; the test below checks that os.system and os.popen never appear.
        self.assertEqual(imported, {"argparse", "html", "json", "os", "re", "secrets", "sys", "tempfile",
                                    "http.server", "pathlib", "urllib.parse", "compile"})

    def test_no_command_running_call_appears(self):
        names = set()
        for node in ast.walk(self.TREE):
            if isinstance(node, ast.Attribute):
                names.add(node.attr)
            elif isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.alias):
                # Imported names too, so "from os import popen" is caught.
                names.add(node.name)
        for name in ("subprocess", "system", "popen", "Popen", "exec", "eval"):
            with self.subTest(name=name):
                self.assertNotIn(name, names)


class SlugifyTests(unittest.TestCase):
    def test_spec_example(self):
        self.assertEqual(notebook.slugify(" ../A  B!! "), "a-b")

    def test_leading_trailing_and_repeated_hyphens_disappear(self):
        self.assertEqual(notebook.slugify("--smb---signing--"), "smb-signing")

    def test_length_is_at_most_40_with_no_hyphen_at_the_cut(self):
        # The 40th character is a space, which becomes "-" and is then stripped.
        slug = notebook.slugify("a" * 39 + " bcd")
        self.assertEqual(slug, "a" * 39)
        self.assertLessEqual(len(notebook.slugify("x" * 100)), 40)

    def test_punctuation_only_is_refused(self):
        with self.assertRaises(ValueError):
            notebook.slugify("!!! ../ ---")


class ValidateNnnTests(unittest.TestCase):
    def test_three_digits_pass(self):
        self.assertEqual(notebook.validate_nnn("000"), "000")
        self.assertEqual(notebook.validate_nnn("999"), "999")

    def test_other_values_fail(self):
        # "123\n" and Arabic-Indic digits would pass a plain re.match(r"^\d{3}$").
        for text in ["1", "01", "1000", "abc", "123\n", "١٢٣"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                notebook.validate_nnn(text)


class NameOptionTests(unittest.TestCase):
    def test_name_is_slugged(self):
        self.assertEqual(notebook.parse_args(["--name", "Alice Smith"]).name, "alice-smith")

    def test_name_with_nothing_usable_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            notebook.parse_args(["--name", "../"])


class PathWrapperTests(unittest.TestCase):
    def setUp(self):
        self.root = support.make_worktree(self, {
            "findings/F-001-x.md": "x\n",
            "incoming/bob/findings/F-002-y.md": "y\n",
        })
        self.logdir = support.make_worktree(self, {"alice_20261107T0900Z.log": "log\n"})
        # A third folder stands in for "somewhere outside", still inside .tmp/.
        self.outside = support.make_worktree(self, {"secret.md": "s\n"})

    def assert_refused(self, call, named):
        with self.assertRaises(compile.RootError) as caught:
            call()
        self.assertIn(named, str(caught.exception))

    def test_root_child_read_and_write_pass(self):
        expected = self.root.resolve() / "findings" / "F-001-x.md"
        self.assertEqual(notebook.readable_path(self.root, "findings/F-001-x.md"), expected)
        self.assertEqual(notebook.writable_path(self.root, self.logdir, "findings/F-001-x.md"),
                         expected)

    def test_log_read_passes(self):
        resolved = notebook.readable_log_path(self.logdir, "alice_20261107T0900Z.log")
        self.assertEqual(resolved, self.logdir.resolve() / "alice_20261107T0900Z.log")

    def test_log_write_outside_root_fails(self):
        log = self.logdir / "alice_20261107T0900Z.log"
        self.assert_refused(lambda: notebook.writable_path(self.root, self.logdir, log), str(log))

    def test_log_write_inside_root_fails(self):
        # $LOGDIR may point into the working copy; it is still read-only.
        logdir = self.root / "logs"
        self.assert_refused(
            lambda: notebook.writable_path(self.root, logdir, "logs/alice.log"), "logs/alice.log")

    def test_incoming_write_fails_but_read_passes(self):
        path = "incoming/bob/findings/F-002-y.md"
        self.assertEqual(notebook.readable_path(self.root, path), self.root.resolve() / path)
        self.assert_refused(lambda: notebook.writable_path(self.root, self.logdir, path), path)

    def test_write_through_link_into_incoming_fails(self):
        (self.root / "bob-link").symlink_to(self.root / "incoming" / "bob")
        path = "bob-link/findings/F-002-y.md"
        self.assert_refused(lambda: notebook.writable_path(self.root, self.logdir, path), path)

    def test_write_where_linked_incoming_points_fails(self):
        # incoming/ is itself a link, so its files really live in shared/.
        root = support.make_worktree(self, {"shared/bob/findings/F-002-y.md": "y\n"})
        (root / "incoming").symlink_to(root / "shared")
        path = "shared/bob/findings/F-002-y.md"
        self.assert_refused(lambda: notebook.writable_path(root, self.logdir, path), path)

    def test_write_where_linked_logdir_points_fails(self):
        # $LOGDIR is a link to logs/ inside the root.
        (self.root / "logs").mkdir()
        (self.root / "loglink").symlink_to(self.root / "logs")
        self.assert_refused(
            lambda: notebook.writable_path(self.root, self.root / "loglink", "logs/a.log"),
            "logs/a.log")

    def test_dot_dot_fails(self):
        self.assert_refused(lambda: notebook.readable_path(self.root, "../x.md"), "../x.md")

    def test_absolute_outside_fails(self):
        target = str(self.outside / "secret.md")
        self.assert_refused(lambda: notebook.writable_path(self.root, self.logdir, target), target)

    def test_symlink_resolving_outside_fails(self):
        (self.root / "field-notes").mkdir()
        (self.root / "field-notes" / "alice").symlink_to(self.outside)
        self.assert_refused(
            lambda: notebook.readable_path(self.root, "field-notes/alice/secret.md"),
            "field-notes/alice/secret.md")

    # Path.resolve() raises ValueError for a NUL byte; each wrapper turns it
    # into the same RootError as any other refused path, naming it.
    NUL_PATH = "findings/F-001\x00.md"

    def test_nul_byte_read_is_refused(self):
        self.assert_refused(lambda: notebook.readable_path(self.root, self.NUL_PATH),
                            "F-001\\x00.md")

    def test_nul_byte_log_read_is_refused(self):
        self.assert_refused(lambda: notebook.readable_log_path(self.logdir, self.NUL_PATH),
                            "F-001\\x00.md")

    def test_nul_byte_write_is_refused(self):
        self.assert_refused(
            lambda: notebook.writable_path(self.root, self.logdir, self.NUL_PATH),
            "F-001\\x00.md")

    def test_symlink_inside_root_passes(self):
        (self.root / "latest").symlink_to(self.root / "findings")
        expected = self.root.resolve() / "findings" / "F-001-x.md"
        self.assertEqual(notebook.readable_path(self.root, "latest/F-001-x.md"), expected)
        self.assertEqual(notebook.writable_path(self.root, self.logdir, "latest/F-001-x.md"),
                         expected)


def file_bytes(root):
    """Return every file under root as {relative path: bytes}, to spot any change."""
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


class ServerTestCase(unittest.TestCase):
    """Starts a real notebook server on 127.0.0.1 for each test; no tests of its own."""

    def setUp(self):
        self.root = support.make_worktree(self, {"findings/F-001-x.md": "original\n"})
        # Fake routes stand in for the real ones the feature tasks add: the
        # POST one changes a file, so a refused POST must leave it unchanged.
        self.calls = []
        routes = {"/test-read": self.fake_get}
        posts = {"/test-write": self.fake_post}
        for patcher in [mock.patch.dict(notebook.GET_ROUTES, routes),
                        mock.patch.dict(notebook.POST_ROUTES, posts)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        # Port 0 lets the OS pick a free port; the address is always 127.0.0.1.
        self.server = HTTPServer(("127.0.0.1", 0), notebook.NotebookHandler)
        self.server.token = notebook.make_token()
        # Resolved, as load_settings() does for a real run.
        self.logdir = support.make_worktree(self)
        self.server.settings = {"root": self.root.resolve(), "name": "alice",
                                "logdir": self.logdir.resolve()}
        self.port = self.server.server_address[1]
        # A short poll interval keeps shutdown() quick at the end of each test.
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.before = file_bytes(self.root)

    def fake_get(self, handler):
        self.calls.append("GET")
        notebook.send_text(handler, 200, "ok")

    def fake_post(self, handler):
        self.calls.append("POST")
        (self.root / "findings" / "F-001-x.md").write_text("changed\n", encoding="utf-8")
        notebook.send_text(handler, 200, "ok")

    def send_full(self, method, path, host, token=None):
        """Send one request with exactly these headers; return (response, body text).

        `host` is one Host value, or a list to send the header more than once.
        """
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(connection.close)
        connection.putrequest(method, path, skip_host=True)
        for value in host if isinstance(host, list) else [host]:
            connection.putheader("Host", value)
        if token is not None:
            connection.putheader("X-CPTC-Token", token)
        connection.putheader("Content-Length", "0")
        connection.endheaders()
        response = connection.getresponse()
        return response, response.read().decode("utf-8")

    def send(self, method, path, host, token=None):
        """Like send_full(), but return (status, body text)."""
        response, body = self.send_full(method, path, host, token)
        return response.status, body

    def assert_refused(self, method, host, token=None):
        path = "/test-read" if method == "GET" else "/test-write"
        status, body = self.send(method, path, host, token)
        self.assertEqual((status, body), (403, "refused: use http://127.0.0.1:" + str(self.port)))
        self.assertEqual(self.calls, [])
        self.assertEqual(file_bytes(self.root), self.before)

    def good_host(self):
        return "127.0.0.1:" + str(self.port)

    def assert_safe_headers(self, response):
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
        cors = [name for name, _ in response.getheaders()
                if name.lower().startswith("access-control-")]
        self.assertEqual(cors, [])


class RequestGuardTests(ServerTestCase):
    def test_wrong_host_get_is_refused(self):
        self.assert_refused("GET", "evil.example:" + str(self.port))

    def test_localhost_name_is_refused(self):
        self.assert_refused("GET", "localhost:" + str(self.port))

    def test_host_without_port_is_refused(self):
        self.assert_refused("GET", "127.0.0.1")

    def test_second_host_header_is_refused(self):
        self.assert_refused("GET", [self.good_host(), "evil.example:" + str(self.port)])

    def test_wrong_host_post_with_token_is_refused(self):
        self.assert_refused("POST", "evil.example:" + str(self.port), self.server.token)

    def test_post_without_token_is_refused(self):
        self.assert_refused("POST", self.good_host())

    def test_post_with_wrong_token_is_refused(self):
        self.assert_refused("POST", self.good_host(), "not-the-token")

    def test_non_ascii_token_is_refused_not_crashed(self):
        self.assert_refused("POST", self.good_host(), "t\u00e9st")

    def test_exact_host_get_and_token_post_succeed(self):
        self.assertEqual(self.send("GET", "/test-read", self.good_host()), (200, "ok"))
        self.assertEqual(self.send("POST", "/test-write", self.good_host(), self.server.token),
                         (200, "ok"))
        self.assertEqual(self.calls, ["GET", "POST"])
        self.assertEqual(file_bytes(self.root)["findings/F-001-x.md"], b"changed\n")

    def test_other_methods_get_a_plain_501(self):
        # Only GET and POST have routes (Chunk N1 D3): any other method gets
        # the server's 501 as plain text with the safety headers, whatever
        # the Host. That its connection closes is tested below.
        for method in ["PUT", "OPTIONS", "HEAD", "BREW"]:
            for host in [self.good_host(), "evil.example:" + str(self.port)]:
                with self.subTest(method=method, host=host):
                    response, body = self.send_full(method, "/test-write", host,
                                                    self.server.token)
                    self.assertEqual(response.status, 501)
                    self.assertEqual(response.getheader("Content-Type"),
                                     "text/plain; charset=utf-8")
                    self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                    self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
                    # http.client never reads a HEAD response's body; the
                    # raw-socket test below checks it is empty.
                    if method != "HEAD":
                        self.assertEqual(body, "Unsupported method ('" + method + "')")
        self.assertEqual(self.calls, [])
        self.assertEqual(file_bytes(self.root), self.before)

    def test_head_501_has_no_body(self):
        # HTTP says a HEAD response has headers only.
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            sock.sendall(("HEAD / HTTP/1.0\r\nHost: " + self.good_host()
                          + "\r\n\r\n").encode("ascii"))
            reply = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                reply += chunk
        head, separator, body = reply.partition(b"\r\n\r\n")
        self.assertTrue(head.startswith(b"HTTP/1.0 501"), head)
        self.assertEqual(separator, b"\r\n\r\n")
        self.assertEqual(body, b"")

    def send_with_smuggled_get(self, method):
        """Send `method` with a wrong Host whose unread body is a whole GET
        with the right Host, on an HTTP/1.1 (kept-open) server; return the
        raw reply. If the connection stayed open, the server would answer
        that GET too, past the Host check."""
        smuggled = ("GET /test-read HTTP/1.1\r\nHost: " + self.good_host()
                    + "\r\n\r\n").encode("ascii")
        request = (method + " /test-write HTTP/1.1\r\nHost: evil.example:" + str(self.port)
                   + "\r\nContent-Length: " + str(len(smuggled)) + "\r\n\r\n").encode("ascii")
        reply = b""
        with mock.patch.object(notebook.NotebookHandler, "protocol_version", "HTTP/1.1"), \
                socket.create_connection(("127.0.0.1", self.port), timeout=2) as sock:
            sock.sendall(request + smuggled)
            try:
                while True:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    reply += chunk
            except socket.timeout:
                # If the connection stays open, the read ends here instead
                # of at a close.
                pass
        return reply

    def test_refused_request_body_is_never_read_as_a_second_request(self):
        reply = self.send_with_smuggled_get("POST")
        self.assertEqual(reply.count(b"HTTP/1.1 "), 1)
        self.assertTrue(reply.startswith(b"HTTP/1.1 403"))
        self.assertEqual(self.calls, [])

    def test_501_body_is_never_read_as_a_second_request(self):
        for method in ["PUT", "OPTIONS", "HEAD", "BREW"]:
            with self.subTest(method=method):
                reply = self.send_with_smuggled_get(method)
                self.assertEqual(reply.count(b"HTTP/1.1 "), 1)
                self.assertTrue(reply.startswith(b"HTTP/1.1 501"))
        self.assertEqual(self.calls, [])

    def test_tokens_differ_each_run(self):
        self.assertNotEqual(notebook.make_token(), notebook.make_token())
        self.assertGreaterEqual(len(notebook.make_token()), 43)


class ResponseHeaderTests(ServerTestCase):
    DATA_TYPES = ["application/json", "text/plain; charset=utf-8"]

    def fake_json(self, handler):
        notebook.send_json(handler, 200, {"files": ["findings/F-001-x.md"]})

    def fake_log(self, handler):
        notebook.send_text(handler, 200, "<script>alert(1)</script>\n")

    def test_every_built_route_only_slash_is_html(self):
        # The real route tables, not the fake routes: every route a feature
        # task adds is checked here automatically.
        routes = [(method, path)
                  for method, table in [("GET", notebook.GET_ROUTES), ("POST", notebook.POST_ROUTES)]
                  for path in table if not path.startswith("/test-")]
        self.assertIn(("GET", "/"), routes)
        for method, path in routes:
            with self.subTest(method=method, path=path):
                response, _ = self.send_full(method, path, self.good_host(), self.server.token)
                self.assert_safe_headers(response)
                content_type = response.getheader("Content-Type")
                if path == "/":
                    self.assertEqual(content_type, "text/html; charset=utf-8")
                else:
                    self.assertIn(content_type, self.DATA_TYPES)

    def test_helpers_send_data_types_never_html(self):
        with mock.patch.dict(notebook.GET_ROUTES, {"/test-json": self.fake_json,
                                                   "/test-log": self.fake_log}):
            response, body = self.send_full("GET", "/test-json", self.good_host())
            self.assertEqual(response.getheader("Content-Type"), "application/json")
            self.assertEqual(json.loads(body), {"files": ["findings/F-001-x.md"]})
            self.assert_safe_headers(response)
            # A <script> in a log goes out as plain text, so it never runs.
            response, body = self.send_full("GET", "/test-log", self.good_host())
            self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
            self.assertEqual(body, "<script>alert(1)</script>\n")
            self.assert_safe_headers(response)

    def test_refusals_and_errors_have_the_headers(self):
        wrong_host = "evil.example:" + str(self.port)
        for method, path, host, status in [("GET", "/test-read", wrong_host, 403),
                                           ("POST", "/test-write", self.good_host(), 403),
                                           ("GET", "/nothing-here", self.good_host(), 404),
                                           ("PUT", "/", self.good_host(), 501)]:
            with self.subTest(method=method, path=path):
                response, _ = self.send_full(method, path, host)
                self.assertEqual(response.status, status)
                self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
                self.assert_safe_headers(response)

    def test_stdlib_error_is_text_with_the_headers(self):
        # Over 100 headers gets the server's own 431, which would otherwise
        # be an HTML page without the safety headers.
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as sock:
            sock.sendall(b"GET / HTTP/1.0\r\n" + b"X-Filler: x\r\n" * 101 + b"\r\n")
            reply = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                reply += chunk
        head, _, body = reply.decode("utf-8").partition("\r\n\r\n")
        lines = head.split("\r\n")
        self.assertTrue(lines[0].startswith("HTTP/1.0 431"), lines[0])
        headers = dict(line.split(": ", 1) for line in lines[1:])
        self.assertEqual(headers["Content-Type"], "text/plain; charset=utf-8")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual([name for name in headers if name.lower().startswith("access-control-")], [])
        self.assertNotIn("<", body)


class ChecklistTests(ServerTestCase):
    """N2-01: checklists are listed and read live from disk, read only."""

    FIRST = "# AD checklist\n\n- [ ] Run the fake scan\n<script>alert(1)</script>\r\n"

    def setUp(self):
        super().setUp()
        # A third folder stands in for "somewhere outside", still inside .tmp/.
        self.outside = support.make_worktree(self, {"secret.md": "outside secret\n"})

    def write(self, relative_path, text):
        support.write_fake_file(self.root, relative_path, text)

    def get_list(self):
        response, body = self.send_full("GET", "/checklists", self.good_host())
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Content-Type"), "application/json")
        self.assert_safe_headers(response)
        return json.loads(body)["checklists"]

    def get_checklist(self, path):
        """GET one checklist; return (response, body text)."""
        return self.send_full("GET", "/checklist?path=" + quote(path), self.good_host())

    def assert_read(self, path, text):
        response, body = self.get_checklist(path)
        self.assertEqual((response.status, body), (200, text))
        self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
        self.assert_safe_headers(response)

    def assert_read_refused(self, path, named):
        response, body = self.get_checklist(path)
        self.assertEqual(response.status, 403)
        self.assertTrue(body.startswith("refused: "), body)
        self.assertIn(named, body)
        self.assertNotIn("outside secret", body)
        self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
        self.assert_safe_headers(response)

    def test_checklists_sort_by_name(self):
        # Created in reverse order, so the list can't just follow the disk.
        self.write("checklists/20-web.md", "web\n")
        self.write("checklists/10-ad.md", "ad\n")
        expected = ["checklists/10-ad.md", "checklists/20-web.md"]
        self.assertEqual(notebook.list_checklists(self.root), expected)
        self.assertEqual(self.get_list(), expected)

    def test_missing_folder_is_an_empty_list(self):
        self.assertEqual(notebook.list_checklists(self.root), [])
        self.assertEqual(self.get_list(), [])

    def test_only_md_files_directly_in_the_folder_are_listed(self):
        self.write("checklists/10-ad.md", "ad\n")
        self.write("checklists/notes.txt", "not markdown\n")
        self.write("checklists/old/90-old.md", "in a subfolder\n")
        (self.root / "checklists" / "folder.md").mkdir()
        self.assertEqual(self.get_list(), ["checklists/10-ad.md"])

    def test_subfolder_checklist_is_not_read(self):
        self.write("checklists/old/90-old.md", "in a subfolder\n")
        self.assert_read_refused("checklists/old/90-old.md", "not a checklist: checklists/old/90-old.md")

    def test_other_file_in_the_root_is_not_read(self):
        self.assert_read_refused("findings/F-001-x.md", "not a checklist: findings/F-001-x.md")

    def test_listed_checklist_reads_its_exact_text(self):
        self.write("checklists/10-ad.md", self.FIRST)
        self.assert_read("checklists/10-ad.md", self.FIRST)

    def test_edit_on_disk_shows_on_the_next_read(self):
        self.write("checklists/10-ad.md", self.FIRST)
        self.assert_read("checklists/10-ad.md", self.FIRST)
        self.write("checklists/10-ad.md", "- [ ] A new task\n")
        self.assert_read("checklists/10-ad.md", "- [ ] A new task\n")

    def test_listing_and_reading_change_no_bytes(self):
        self.write("checklists/10-ad.md", self.FIRST)
        before = file_bytes(self.root)
        self.get_list()
        self.assert_read("checklists/10-ad.md", self.FIRST)
        self.assert_read("checklists/10-ad.md", self.FIRST)
        self.assertEqual(file_bytes(self.root), before)

    def test_symlink_inside_root_is_read_live(self):
        self.write("shared/10-ad.md", "first\n")
        (self.root / "checklists").mkdir()
        (self.root / "checklists" / "10-ad.md").symlink_to(self.root / "shared" / "10-ad.md")
        self.assertEqual(self.get_list(), ["checklists/10-ad.md"])
        self.assert_read("checklists/10-ad.md", "first\n")
        self.write("shared/10-ad.md", "second\n")
        self.assert_read("checklists/10-ad.md", "second\n")

    def test_linked_folder_inside_root_lists_and_reads(self):
        self.write("shared/10-ad.md", "ad\n")
        (self.root / "checklists").symlink_to(self.root / "shared")
        self.assertEqual(self.get_list(), ["checklists/10-ad.md"])
        self.assert_read("checklists/10-ad.md", "ad\n")

    def test_linked_folder_outside_root_is_refused_without_its_names(self):
        (self.root / "checklists").symlink_to(self.outside)
        response, body = self.send_full("GET", "/checklists", self.good_host())
        self.assertEqual(response.status, 403)
        self.assertTrue(body.startswith("refused: path is outside the root: checklists -> "), body)
        self.assertNotIn("secret.md", body)
        self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
        self.assert_safe_headers(response)
        self.assert_read_refused("checklists/secret.md", "outside the root: checklists/secret.md")

    def test_symlink_pointing_outside_is_refused(self):
        (self.root / "checklists").mkdir()
        (self.root / "checklists" / "10-ad.md").symlink_to(self.outside / "secret.md")
        self.assert_read_refused("checklists/10-ad.md", "outside the root: checklists/10-ad.md")

    def test_dot_dot_is_refused(self):
        self.write("checklists/10-ad.md", "ad\n")
        self.assert_read_refused("checklists/../../secret.md", "'..': checklists/../../secret.md")

    def test_absolute_outside_path_is_refused(self):
        target = str(self.outside / "secret.md")
        self.assert_read_refused(target, "outside the root: " + target)

    def test_missing_or_repeated_path_gets_a_400(self):
        self.write("checklists/10-ad.md", "ad\n")
        for path in ["/checklist", "/checklist?path=",
                     "/checklist?path=checklists/10-ad.md&path=checklists/10-ad.md"]:
            with self.subTest(path=path):
                response, body = self.send_full("GET", path, self.good_host())
                self.assertEqual(response.status, 400)
                self.assertIn("give one checklist", body)
                self.assert_safe_headers(response)

    def test_nul_byte_in_the_path_is_refused_not_dropped(self):
        # Only a hand-typed URL can carry one; the answer must still be text.
        for route in ["/checklist", "/checklist-view"]:
            with self.subTest(route=route):
                response, body = self.send_full("GET", route + "?path=checklists/%00.md",
                                                self.good_host())
                self.assertEqual(response.status, 403)
                self.assertTrue(body.startswith("refused: "), body)
                self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
                self.assert_safe_headers(response)

    def test_bom_is_dropped_and_crlf_kept(self):
        # A checklist saved by Windows Notepad starts with a BOM.
        (self.root / "checklists").mkdir()
        (self.root / "checklists" / "10-ad.md").write_bytes(b"\xef\xbb\xbf# AD\r\n- [ ] Scan\r\n")
        self.assert_read("checklists/10-ad.md", "# AD\r\n- [ ] Scan\r\n")

    def test_windows_1252_file_gets_a_readable_error(self):
        (self.root / "checklists").mkdir()
        (self.root / "checklists" / "10-ad.md").write_bytes("- [ ] Café\n".encode("cp1252"))
        response, body = self.get_checklist("checklists/10-ad.md")
        self.assertEqual(response.status, 500)
        self.assertTrue(body.startswith("can't read the checklist: "), body)
        self.assertIn("10-ad.md is not UTF-8 text", body)
        self.assert_safe_headers(response)


class ChecklistRecordTests(unittest.TestCase):
    """N2-02: task lines become keyed records, every other line stays text (OQ-08)."""

    PATH = "checklists/10-ad.md"

    def records(self, text, path=PATH):
        return notebook.checklist_records(path, text)

    def tasks(self, text, path=PATH):
        return [record for record in self.records(text, path) if record["type"] == "task"]

    def keys(self, text, path=PATH):
        return [record["key"] for record in self.tasks(text, path)]

    def key(self, text, occurrence, path=PATH):
        return notebook.task_key(path, text, occurrence)

    def test_unticked_task_line(self):
        self.assertEqual(self.records("- [ ] Run the fake scan"), [
            {"type": "task", "key": '["checklists/10-ad.md", "Run the fake scan", 1]',
             "text": "Run the fake scan", "checked": False}])

    def test_ticked_task_line(self):
        self.assertEqual(self.records("- [x] Run the fake scan"), [
            {"type": "task", "key": '["checklists/10-ad.md", "Run the fake scan", 1]',
             "text": "Run the fake scan", "checked": True}])

    def test_repeated_text_gets_the_next_occurrence(self):
        text = "- [ ] Save evidence\n- [ ] Other task\nSome prose\n- [ ] Save evidence\n"
        self.assertEqual(self.keys(text), [self.key("Save evidence", 1),
                                           self.key("Other task", 1),
                                           self.key("Save evidence", 2)])

    def test_each_text_and_each_checklist_counts_from_one(self):
        text = "- [ ] A\n- [ ] B\n- [ ] A\n- [ ] B\n"
        self.assertEqual(self.keys(text), [self.key("A", 1), self.key("B", 1),
                                           self.key("A", 2), self.key("B", 2)])
        other = "checklists/20-web.md"
        self.assertEqual(self.keys("- [ ] A\n", other), [self.key("A", 1, other)])

    def test_same_text_in_two_checklists_gets_two_keys(self):
        first = self.keys("- [ ] Save evidence\n", "checklists/10-ad.md")
        second = self.keys("- [ ] Save evidence\n", "checklists/20-web.md")
        self.assertNotEqual(first, second)

    def test_unchanged_task_keeps_its_key_when_other_lines_change(self):
        before = self.keys("# AD\n- [ ] Run the scan\n- [ ] Save evidence\n")
        after = self.keys("# AD (edited)\n\nNew prose\n- [ ] Run the scan\n"
                          "- [ ] A new task\n- [ ] Save evidence\n")
        self.assertIn(before[0], after)
        self.assertIn(before[1], after)

    def test_edited_task_gets_a_new_unticked_key(self):
        old_keys = set(self.keys("- [ ] Run the scan\n"))
        # Any change to the text, even a space or a full stop, is a new task.
        for edited in ["- [ ] Run the scan.", "- [ ] Run  the scan", "- [ ] run the scan"]:
            with self.subTest(edited=edited):
                (task,) = self.tasks(edited)
                self.assertNotIn(task["key"], old_keys)
                self.assertFalse(task["checked"])

    def test_other_lines_stay_text_in_order(self):
        lines = ["# AD checklist", "", "Some **bold** prose", "> a quote",
                 "| a | b |", "- a plain bullet", "1. a numbered step"]
        self.assertEqual(self.records("\n".join(lines)),
                         [{"type": "text", "text": line} for line in lines])

    def test_task_inside_a_code_block_stays_text(self):
        lines = ["```", "- [ ] not a task", "```", "~~~", "- [x] not a task",
                 "```", "- [ ] still not a task", "~~~", "- [ ] A real task"]
        records = self.records("\n".join(lines))
        self.assertEqual([record["type"] for record in records], ["text"] * 8 + ["task"])

    def test_shorter_fence_inside_a_longer_one_doesnt_end_it(self):
        lines = ["````", "```", "- [ ] not a task", "````", "- [ ] A real task"]
        records = self.records("\n".join(lines))
        self.assertEqual([record["type"] for record in records], ["text"] * 4 + ["task"])

    def test_fence_with_text_after_it_doesnt_end_a_block(self):
        lines = ["```", "```python", "- [ ] not a task", "```", "- [ ] A real task"]
        records = self.records("\n".join(lines))
        self.assertEqual([record["type"] for record in records], ["text"] * 4 + ["task"])

    def test_four_space_indented_fence_starts_no_block(self):
        # Four spaces make an indented code line, not a fence; three still fence.
        records = self.records("    ```\n- [ ] A real task\n   ```\n- [ ] not a task\n")
        self.assertEqual([record["type"] for record in records],
                         ["text", "task", "text", "text", "text"])

    def test_near_misses_stay_text(self):
        for line in ["  - [ ] indented", "* [ ] star bullet", "- [X] capital X",
                     "- [] no space", "- [ ]no space after", "- [ ] ", "- [ ]",
                     "-  [ ] two spaces", "- [y] other mark"]:
            with self.subTest(line=line):
                self.assertEqual(self.records(line), [{"type": "text", "text": line}])

    def test_windows_line_endings_keep_the_same_keys(self):
        lf = "# AD\n- [ ] Run the scan\n- [x] Save evidence\n"
        self.assertEqual(self.records(lf.replace("\n", "\r\n")), self.records(lf))

    def test_reading_and_parsing_change_no_bytes(self):
        root = support.make_worktree(self)
        path = root / "checklists" / "10-ad.md"
        path.parent.mkdir()
        path.write_bytes(b"# AD\r\n- [ ] Run the scan\r\n- [x] Save evidence\r\n")
        before = file_bytes(root)
        tasks = self.tasks(notebook.read_checklist(root, self.PATH))
        self.assertEqual([task["text"] for task in tasks], ["Run the scan", "Save evidence"])
        self.assertEqual(file_bytes(root), before)


class ChecklistStateTests(unittest.TestCase):
    """N2-03: ticks are saved to field-notes/<name>/checklist-state.json."""

    STATE = "field-notes/alice/checklist-state.json"
    CHECKLIST = "- [ ] Run the scan\n- [x] Save evidence\n"

    def setUp(self):
        self.root = support.make_worktree(self, {"checklists/10-ad.md": self.CHECKLIST})
        self.logdir = support.make_worktree(self, {"alice_20261107T0900Z.log": "log\n"})
        # A third folder stands in for "somewhere outside", still inside .tmp/.
        self.outside = support.make_worktree(self)

    def save(self, state):
        notebook.save_checklist_state(self.root, self.logdir, "alice", state)

    def load(self):
        return notebook.load_checklist_state(self.root, "alice")

    def tasks(self, text):
        return [record for record in notebook.checklist_records("checklists/10-ad.md", text)
                if record["type"] == "task"]

    def assert_state_error(self, call, text):
        with self.assertRaises(notebook.StateError) as caught:
            call()
        self.assertIn(self.STATE, str(caught.exception))
        self.assertIn(text, str(caught.exception))

    def assert_save_refused(self, named):
        before = file_bytes(self.root)
        with self.assertRaises(compile.RootError) as caught:
            self.save({"k": True})
        self.assertIn(named, str(caught.exception))
        self.assertEqual(file_bytes(self.root), before)
        self.assertEqual(file_bytes(self.outside), {})

    def test_nothing_saved_yet_is_empty(self):
        self.assertEqual(self.load(), {})

    def test_save_makes_the_folders_and_writes_only_the_state_file(self):
        before = file_bytes(self.root)
        self.save({"k": True})
        after = file_bytes(self.root)
        # One new file, and no temp file left behind.
        self.assertEqual(set(after) - set(before), {self.STATE})
        self.assertEqual({path: after[path] for path in before}, before)

    def test_ticks_and_unticks_survive_a_reload(self):
        keys = [task["key"] for task in self.tasks(self.CHECKLIST)]
        self.save({keys[0]: True, keys[1]: False})
        self.assertEqual(self.load(), {keys[0]: True, keys[1]: False})
        self.save({keys[0]: False, keys[1]: True})
        self.assertEqual(self.load(), {keys[0]: False, keys[1]: True})

    def test_saved_tick_wins_over_the_file_mark_both_ways(self):
        unticked, ticked = self.tasks(self.CHECKLIST)
        state = {unticked["key"]: True, ticked["key"]: False}
        self.assertTrue(notebook.task_checked(unticked, state))
        self.assertFalse(notebook.task_checked(ticked, state))

    def test_unsaved_task_shows_the_file_mark(self):
        unticked, ticked = self.tasks(self.CHECKLIST)
        self.assertFalse(notebook.task_checked(unticked, {}))
        self.assertTrue(notebook.task_checked(ticked, {}))

    def test_edited_task_doesnt_keep_the_old_tick(self):
        unticked, ticked = self.tasks(self.CHECKLIST)
        state = {unticked["key"]: True, ticked["key"]: False}
        edited_unticked, edited_ticked = self.tasks("- [ ] Run the scan.\n- [x] Save evidence!\n")
        self.assertFalse(notebook.task_checked(edited_unticked, state))
        self.assertTrue(notebook.task_checked(edited_ticked, state))

    def test_broken_json_is_a_readable_error(self):
        support.write_fake_file(self.root, self.STATE, '{"k": tru')
        self.assert_state_error(self.load, "can't be read")

    def test_non_utf8_file_is_a_readable_error(self):
        support.write_fake_file(self.root, self.STATE, "")
        (self.root / self.STATE).write_bytes('{"café": true}'.encode("cp1252"))
        self.assert_state_error(self.load, "can't be read")

    def test_wrong_shape_is_refused(self):
        for text in ["[]", '"ticks"', "null", '{"k": 1}', '{"k": "true"}', '{"k": null}']:
            with self.subTest(text=text):
                support.write_fake_file(self.root, self.STATE, text)
                self.assert_state_error(self.load, "")

    def test_wrong_shape_is_never_saved(self):
        before = file_bytes(self.root)
        for state in [[], {"k": 1}, {"k": "true"}, {1: True}, {True: True}, {None: False}]:
            with self.subTest(state=state):
                self.assert_state_error(lambda: self.save(state), "")
                # No state file and no temp file: nothing was written.
                self.assertEqual(file_bytes(self.root), before)

    def test_wrong_shape_never_replaces_a_saved_state(self):
        self.save({"k": True})
        before = file_bytes(self.root)
        self.assert_state_error(lambda: self.save({1: False}), "a task key is not text: 1")
        self.assertEqual(file_bytes(self.root), before)

    def test_linked_folder_inside_root_is_used(self):
        (self.root / "shared" / "alice").mkdir(parents=True)
        (self.root / "field-notes").mkdir()
        (self.root / "field-notes" / "alice").symlink_to(self.root / "shared" / "alice")
        self.save({"k": True})
        self.assertTrue((self.root / "shared" / "alice" / "checklist-state.json").is_file())
        self.assertEqual(self.load(), {"k": True})

    def test_linked_state_file_inside_root_is_refused(self):
        # DECISIONS 2026-10-28 Chunk N2 CR-1 (user, A): the state file itself
        # must be a plain file, even when its link stays inside the root.
        support.write_fake_file(self.root, "field-notes/bob/checklist-state.json",
                                '{"bob-key": true}')
        (self.root / "field-notes" / "alice").mkdir()
        (self.root / self.STATE).symlink_to(self.root / "field-notes" / "bob" /
                                            "checklist-state.json")
        self.assert_save_refused("is a link, not a plain file: " + self.STATE)
        with self.assertRaises(compile.RootError) as caught:
            self.load()
        self.assertIn("is a link, not a plain file: " + self.STATE, str(caught.exception))

    def test_linked_folder_outside_root_is_refused(self):
        (self.root / "field-notes").mkdir()
        (self.root / "field-notes" / "alice").symlink_to(self.outside)
        self.assert_save_refused("outside the root: " + self.STATE)

    def test_linked_state_file_outside_root_is_refused(self):
        (self.root / "field-notes" / "alice").mkdir(parents=True)
        (self.root / self.STATE).symlink_to(self.outside / "state.json")
        self.assert_save_refused("outside the root: " + self.STATE)

    def test_linked_folder_into_incoming_is_refused(self):
        (self.root / "incoming" / "bob").mkdir(parents=True)
        (self.root / "field-notes").mkdir()
        (self.root / "field-notes" / "alice").symlink_to(self.root / "incoming" / "bob")
        self.assert_save_refused("incoming/ is read-only, not writing: " + self.STATE)

    def test_linked_folder_into_the_log_folder_is_refused(self):
        # $LOGDIR may point into the working copy; it is still read-only.
        self.logdir = self.root / "logs"
        self.logdir.mkdir()
        (self.root / "field-notes").mkdir()
        (self.root / "field-notes" / "alice").symlink_to(self.logdir)
        self.assert_save_refused("the log folder is read-only, not writing: " + self.STATE)

    def test_failed_save_keeps_the_old_state_and_no_temp_file(self):
        self.save({"k": True})
        before = file_bytes(self.root)
        with mock.patch.object(notebook.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.save({"k": False})
        self.assertEqual(file_bytes(self.root), before)
        self.assertEqual(self.load(), {"k": True})

    def test_loading_and_saving_change_no_checklist_bytes(self):
        before = file_bytes(self.root / "checklists")
        self.load()
        self.save({task["key"]: True for task in self.tasks(self.CHECKLIST)})
        self.load()
        self.assertEqual(file_bytes(self.root / "checklists"), before)


class ChecklistViewTests(ServerTestCase):
    """N2-04: the checklist view's data and the tick POST behind its checkboxes."""

    STATE = "field-notes/alice/checklist-state.json"
    CHECKLIST = "# AD\n<script>alert(1)</script>\n- [ ] Run the scan\n- [x] Save evidence\n"

    def setUp(self):
        super().setUp()
        support.write_fake_file(self.root, "checklists/10-ad.md", self.CHECKLIST)
        self.scan_key = notebook.task_key("checklists/10-ad.md", "Run the scan", 1)
        self.evidence_key = notebook.task_key("checklists/10-ad.md", "Save evidence", 1)

    def view(self):
        response, body = self.send_full("GET", "/checklist-view?path=checklists/10-ad.md",
                                         self.good_host())
        self.assertEqual(response.status, 200, body)
        self.assertEqual(response.getheader("Content-Type"), "application/json")
        self.assert_safe_headers(response)
        return json.loads(body)

    def shown(self):
        """Return {task text: shown tick} from the view."""
        return {record["text"]: record["checked"]
                for record in self.view()["records"] if record["type"] == "task"}

    def post(self, body, token="default", host=None):
        """POST raw body bytes to the tick route; token is a value, a list
        (sent more than once), None (not sent) or "default" (this run's)."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(connection.close)
        connection.putrequest("POST", "/checklist-state", skip_host=True)
        connection.putheader("Host", host or self.good_host())
        tokens = [self.server.token] if token == "default" else token
        for value in tokens if isinstance(tokens, list) else ([] if tokens is None else [tokens]):
            connection.putheader("X-CPTC-Token", value)
        connection.putheader("Content-Type", "application/json")
        connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        self.assert_safe_headers(response)
        self.assertIn(response.getheader("Content-Type"),
                      ["application/json", "text/plain; charset=utf-8"])
        return response.status, text

    def tick(self, key, checked):
        return self.post(json.dumps({"key": key, "checked": checked}).encode("utf-8"))

    def assert_refused_unchanged(self, status_wanted, body, **post_options):
        before = file_bytes(self.root)
        status, text = self.post(body, **post_options)
        self.assertEqual(status, status_wanted, text)
        self.assertEqual(file_bytes(self.root), before)
        return text

    def test_view_lists_records_in_order_as_data(self):
        data = self.view()
        self.assertEqual(data["path"], "checklists/10-ad.md")
        self.assertIsNone(data["state_error"])
        self.assertEqual(data["records"], [
            {"type": "text", "text": "# AD"},
            # Sent as JSON data; the page shows it with textContent, so it never runs.
            {"type": "text", "text": "<script>alert(1)</script>"},
            {"type": "task", "key": self.scan_key, "text": "Run the scan", "checked": False},
            {"type": "task", "key": self.evidence_key, "text": "Save evidence", "checked": True},
            {"type": "text", "text": ""}])

    def test_view_errors_are_plain_text(self):
        for path, status in [("/checklist-view", 400),
                             ("/checklist-view?path=../x.md", 403),
                             ("/checklist-view?path=findings/F-001-x.md", 403)]:
            with self.subTest(path=path):
                response, _ = self.send_full("GET", path, self.good_host())
                self.assertEqual(response.status, status)
                self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
                self.assert_safe_headers(response)

    def test_saved_ticks_win_over_the_file_marks(self):
        support.write_fake_file(self.root, self.STATE, json.dumps(
            {self.scan_key: True, self.evidence_key: False}))
        self.assertEqual(self.shown(), {"Run the scan": True, "Save evidence": False})

    def test_tick_changes_one_key_and_keeps_the_rest(self):
        other_key = notebook.task_key("checklists/20-web.md", "Other task", 1)
        support.write_fake_file(self.root, self.STATE, json.dumps({other_key: True}))
        self.assertEqual(self.tick(self.scan_key, True),
                         (200, json.dumps({"key": self.scan_key, "checked": True})))
        self.assertEqual(notebook.load_checklist_state(self.root, "alice"),
                         {other_key: True, self.scan_key: True})
        self.assertEqual(self.shown(), {"Run the scan": True, "Save evidence": True})

    def test_tick_and_untick_leave_the_checklist_unchanged(self):
        before = (self.root / "checklists" / "10-ad.md").read_bytes()
        self.assertEqual(self.tick(self.evidence_key, False)[0], 200)
        self.assertEqual(self.shown(), {"Run the scan": False, "Save evidence": False})
        self.assertEqual(self.tick(self.evidence_key, True)[0], 200)
        self.assertEqual(self.shown(), {"Run the scan": False, "Save evidence": True})
        self.assertEqual((self.root / "checklists" / "10-ad.md").read_bytes(), before)

    def test_post_with_the_pages_token_succeeds(self):
        # Carry-forward (N1-08): the token the page carries is the one that works.
        _, page = self.send_full("GET", "/", self.good_host())
        parts = PageParts()
        parts.feed(page)
        body = json.dumps({"key": self.scan_key, "checked": True}).encode("utf-8")
        self.assertEqual(self.post(body, token=parts.tokens[0])[0], 200)

    def test_missing_token_is_refused(self):
        self.assert_refused_unchanged(403, b'{"key": "k", "checked": true}', token=None)

    def test_wrong_token_is_refused(self):
        self.assert_refused_unchanged(403, b'{"key": "k", "checked": true}', token="wrong")

    def test_repeated_token_is_refused(self):
        self.assert_refused_unchanged(403, b'{"key": "k", "checked": true}',
                                      token=[self.server.token, self.server.token])

    def test_wrong_host_is_refused(self):
        self.assert_refused_unchanged(403, b'{"key": "k", "checked": true}',
                                      host="evil.example:" + str(self.port))

    def test_bad_tick_bodies_are_refused(self):
        for body in [b'{"key": "k", "checked": tru', b"[]", b'"tick"',
                     b'{"key": "k"}', b'{"checked": true}',
                     b'{"key": "k", "checked": true, "extra": 1}',
                     b'{"key": 1, "checked": true}', b'{"key": null, "checked": true}',
                     b'{"key": "k", "checked": 1}', b'{"key": "k", "checked": "true"}',
                     b'{"key": "caf\xe9", "checked": true}', b""]:
            with self.subTest(body=body):
                text = self.assert_refused_unchanged(400, body)
                self.assertEqual(text, 'send {"key": "<task key>", "checked": true or false}')

    def test_oversized_tick_is_refused_unread(self):
        text = self.assert_refused_unchanged(400, b" " * (notebook.MAX_TICK_BYTES + 1))
        self.assertTrue(text.startswith("send one tick as JSON, at most "), text)

    def test_broken_state_file_refuses_the_tick_and_stays_unchanged(self):
        support.write_fake_file(self.root, self.STATE, '{"k": tru')
        text = self.assert_refused_unchanged(
            500, json.dumps({"key": self.scan_key, "checked": True}).encode("utf-8"))
        self.assertTrue(text.startswith("tick not saved: " + self.STATE + " can't be read"), text)

    def test_broken_state_file_still_shows_the_checklist(self):
        support.write_fake_file(self.root, self.STATE, '{"k": tru')
        data = self.view()
        self.assertTrue(data["state_error"].startswith(self.STATE + " can't be read"))
        self.assertEqual({record["text"]: record["checked"]
                          for record in data["records"] if record["type"] == "task"},
                         {"Run the scan": False, "Save evidence": True})

    def test_linked_state_file_refuses_the_tick(self):
        # The probe from Chunk N2 CR-1: alice's state file linked to bob's.
        support.write_fake_file(self.root, "field-notes/bob/checklist-state.json",
                                '{"bob-key": true}')
        (self.root / "field-notes" / "alice").mkdir()
        (self.root / self.STATE).symlink_to(self.root / "field-notes" / "bob" /
                                            "checklist-state.json")
        text = self.assert_refused_unchanged(
            403, json.dumps({"key": self.scan_key, "checked": True}).encode("utf-8"))
        self.assertEqual(text, "refused: the tick-state file is a link, not a plain file: "
                         + self.STATE)

    def test_refused_state_path_is_a_403(self):
        outside = support.make_worktree(self)
        (self.root / "field-notes").mkdir()
        (self.root / "field-notes" / "alice").symlink_to(outside)
        text = self.assert_refused_unchanged(
            403, json.dumps({"key": self.scan_key, "checked": True}).encode("utf-8"))
        self.assertTrue(text.startswith("refused: "), text)
        self.assertEqual(file_bytes(outside), {})


class OwnFileTests(ServerTestCase):
    """N2-05: the left column's list of the person's own files."""

    def setUp(self):
        super().setUp()
        # A fresh, empty working copy per test; the route uses it as the root.
        self.home = support.make_worktree(self)
        self.server.settings["root"] = self.home.resolve()
        # A third folder stands in for "somewhere outside", still inside .tmp/.
        self.outside = support.make_worktree(self, {"secret.md": "outside\n"})

    def write(self, *paths):
        for path in paths:
            support.write_fake_file(self.home, path, "x\n")

    def get_files(self):
        """GET /files; check it is safe JSON that matches list_own_files()."""
        before = file_bytes(self.home)
        response, body = self.send_full("GET", "/files", self.good_host())
        self.assertEqual(response.status, 200, body)
        self.assertEqual(response.getheader("Content-Type"), "application/json")
        self.assert_safe_headers(response)
        self.assertEqual(file_bytes(self.home), before)
        data = json.loads(body)
        files, refused = notebook.list_own_files(self.home, "alice")
        self.assertEqual(data, {"files": files, "refused": refused})
        return data

    def test_no_folders_yet_is_an_empty_list(self):
        self.assertEqual(self.get_files(), {"files": [], "refused": []})
        self.assertEqual(list(self.home.iterdir()), [])

    def test_every_prefix_is_listed_in_filename_order(self):
        # Written out of order, so the list can't just follow the disk.
        self.write("field-notes/alice/SU-0915.md", "findings/F-002-sqli.md",
                   "field-notes/alice/NOTE-recon.md", "field-notes/alice/IR-001-outage.md",
                   "findings/F-001-default-creds.md", "field-notes/alice/INJ-press.md")
        self.assertEqual(self.get_files()["files"], [
            "findings/F-001-default-creds.md", "findings/F-002-sqli.md",
            "field-notes/alice/INJ-press.md", "field-notes/alice/IR-001-outage.md",
            "field-notes/alice/NOTE-recon.md", "field-notes/alice/SU-0915.md"])

    def test_sorted_by_filename_not_by_folder(self):
        # "field-notes/..." sorts before "findings/..." as a path, but by
        # filename "F-" comes before "NOTE-".
        self.write("field-notes/alice/NOTE-a.md", "findings/F-001-a.md")
        self.assertEqual(self.get_files()["files"],
                         ["findings/F-001-a.md", "field-notes/alice/NOTE-a.md"])

    def test_same_filename_in_both_folders_keeps_both(self):
        self.write("findings/NOTE-x.md", "field-notes/alice/NOTE-x.md")
        self.assertEqual(self.get_files()["files"],
                         ["field-notes/alice/NOTE-x.md", "findings/NOTE-x.md"])

    def test_other_peoples_and_shared_files_are_left_out(self):
        self.write("findings/F-001-a.md", "incoming/bob/findings/F-002-b.md",
                   "incoming/bob/field-notes/bob/NOTE-b.md", "notes/NOTE-study.md",
                   "field-notes/bob/NOTE-bob.md", "field-notes/NOTE-top.md", "NOTE-root.md")
        self.assertEqual(self.get_files()["files"], ["findings/F-001-a.md"])

    def test_other_files_subfolders_and_md_folders_are_left_out(self):
        # findings/old/F-001-a.md has the same name as a listed file, so a
        # search of subfolders would show F-001-a.md twice.
        self.write("findings/F-001-a.md", "findings/F-001-a.txt", "findings/old/F-001-a.md",
                   "findings/old/F-009-old.md", "field-notes/alice/screens/NOTE-x.md")
        (self.home / "field-notes" / "alice" / "NOTE-folder.md").mkdir()
        self.assertEqual(self.get_files()["files"], ["findings/F-001-a.md"])

    def test_links_inside_the_root_are_listed_by_their_own_path(self):
        self.write("shared/F-001-a.md", "elsewhere/NOTE-b.md")
        (self.home / "findings").symlink_to(self.home / "shared")
        (self.home / "field-notes" / "alice").mkdir(parents=True)
        (self.home / "field-notes" / "alice" / "NOTE-b.md").symlink_to(
            self.home / "elsewhere" / "NOTE-b.md")
        self.assertEqual(self.get_files(), {
            "files": ["findings/F-001-a.md", "field-notes/alice/NOTE-b.md"], "refused": []})

    def test_folder_linked_outside_is_refused_and_not_looked_into(self):
        self.write("field-notes/alice/NOTE-a.md")
        (self.home / "findings").symlink_to(self.outside)
        data = self.get_files()
        # The other folder still lists: one bad link doesn't hide the rest.
        self.assertEqual(data["files"], ["field-notes/alice/NOTE-a.md"])
        self.assertEqual(len(data["refused"]), 1)
        self.assertTrue(data["refused"][0].startswith("path is outside the root: findings -> "))
        self.assertNotIn("secret.md", json.dumps(data))

    def test_file_linked_outside_is_refused_not_listed(self):
        self.write("findings/F-001-a.md")
        (self.home / "findings" / "F-002-b.md").symlink_to(self.outside / "secret.md")
        data = self.get_files()
        self.assertEqual(data["files"], ["findings/F-001-a.md"])
        self.assertEqual(len(data["refused"]), 1)
        self.assertTrue(data["refused"][0].startswith(
            "path is outside the root: findings/F-002-b.md -> "))


class NewFileTypeTests(unittest.TestCase):
    """N3-01: the New file table, through new_file_type()."""

    def test_note(self):
        self.assertEqual(notebook.new_file_type("Note"), {
            "path": "field-notes/{name}/NOTE-{slug}.md",
            "needs_nnn": False,
            "template": None,
            "library": False,
        })

    def test_incident_report(self):
        self.assertEqual(notebook.new_file_type("Incident report"), {
            "path": "field-notes/{name}/IR-{nnn}-{slug}.md",
            "needs_nnn": True,
            "template": "templates/incident-report.md",
            "library": False,
        })

    def test_status_update(self):
        self.assertEqual(notebook.new_file_type("Status update"), {
            "path": "field-notes/{name}/SU-{slug}.md",
            "needs_nnn": False,
            "template": "templates/status-update.md",
            "library": False,
        })

    def test_inject_response(self):
        self.assertEqual(notebook.new_file_type("Inject response"), {
            "path": "field-notes/{name}/INJ-{slug}.md",
            "needs_nnn": False,
            "template": "templates/inject-response.md",
            "library": False,
        })

    def test_finding(self):
        # The default template; "library" says a findings-library/ entry may
        # be picked instead. No real library file is read here.
        self.assertEqual(notebook.new_file_type("Finding"), {
            "path": "findings/F-{nnn}-{slug}.md",
            "needs_nnn": True,
            "template": "templates/finding.md",
            "library": True,
        })

    def test_exactly_five_types(self):
        self.assertEqual(list(notebook.NEW_FILE_TYPES), [
            "Note", "Incident report", "Status update", "Inject response", "Finding"])

    def test_only_ir_and_finding_need_a_number(self):
        # needs_nnn and the {nnn} slot in the path must agree for every type.
        for type_name, entry in notebook.NEW_FILE_TYPES.items():
            with self.subTest(type_name=type_name):
                self.assertEqual(entry["needs_nnn"], "{nnn}" in entry["path"])
                self.assertEqual(entry["needs_nnn"], type_name in ["Incident report", "Finding"])

    def test_paths_use_fixed_folders_and_only_name_nnn_slug(self):
        # The folder is written in the table; the only parts filled in later
        # are the slugged name, the checked number and the slugged title.
        for type_name, entry in notebook.NEW_FILE_TYPES.items():
            with self.subTest(type_name=type_name):
                if type_name == "Finding":
                    self.assertTrue(entry["path"].startswith("findings/F-"))
                else:
                    self.assertTrue(entry["path"].startswith("field-notes/{name}/"))
                fields = {field for _, field, _, _ in string.Formatter().parse(entry["path"])
                          if field is not None}
                self.assertLessEqual(fields, {"name", "nnn", "slug"})
                self.assertIn("slug", fields)

    def test_named_templates_exist_in_the_repo(self):
        # Guards against a typo in a template path: each one is a real file.
        repo = support.TOOLS_DIR.parent
        templates = [entry["template"] for entry in notebook.NEW_FILE_TYPES.values()
                     if entry["template"] is not None]
        self.assertEqual(len(templates), 4)
        for template in templates:
            with self.subTest(template=template):
                self.assertTrue((repo / template).is_file())

    def test_unknown_type_is_refused(self):
        with self.assertRaises(ValueError) as caught:
            notebook.new_file_type("Task")
        self.assertIn("unknown file type: 'Task'", str(caught.exception))
        self.assertIn("Note, Incident report, Status update, Inject response, Finding",
                      str(caught.exception))

    def test_near_misses_are_refused(self):
        for type_name in ["note", "NOTE", " Note", "Note ", "", "Incident Report", "finding"]:
            with self.subTest(type_name=type_name), self.assertRaises(ValueError):
                notebook.new_file_type(type_name)

    def test_a_type_that_isnt_text_is_refused(self):
        # A JSON body could send a list or null; a list would otherwise raise
        # TypeError ("unhashable") instead of the readable ValueError.
        for type_name in [None, 1, ["Note"], {"Note": 1}]:
            with self.subTest(type_name=type_name), self.assertRaises(ValueError):
                notebook.new_file_type(type_name)

    def test_changing_a_returned_entry_leaves_the_table_alone(self):
        entry = notebook.new_file_type("Note")
        entry["path"] = "../x.md"
        self.assertEqual(notebook.new_file_type("Note")["path"],
                         "field-notes/{name}/NOTE-{slug}.md")


class LibraryTests(unittest.TestCase):
    """N3-02: findings-library/ entries and their starting titles.

    Every test builds its own fake root, so the real findings-library/ is never read.
    """

    def setUp(self):
        self.home = support.make_worktree(self)
        # A second folder stands in for "somewhere outside", still inside .tmp/.
        self.outside = support.make_worktree(self, {
            "secret.md": support.make_library_entry(title="Outside secret title")})

    def write(self, path, text):
        support.write_fake_file(self.home, path, text)

    def write_bytes(self, path, data):
        (self.home / path).parent.mkdir(parents=True, exist_ok=True)
        (self.home / path).write_bytes(data)

    def listed(self):
        """list_library(), checking that it changed no file anywhere in the root."""
        before = file_bytes(self.home)
        result = notebook.list_library(self.home)
        self.assertEqual(file_bytes(self.home), before)
        return result

    def test_missing_folder_is_empty_and_creates_nothing(self):
        self.assertEqual(self.listed(), ([], []))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_empty_folder_is_empty(self):
        (self.home / "findings-library").mkdir()
        self.assertEqual(self.listed(), ([], []))

    def test_readme_is_never_an_entry(self):
        self.write("findings-library/README.md", "# Findings library\n")
        self.assertEqual(self.listed(), ([], []))
        with self.assertRaises(compile.RootError) as caught:
            notebook.read_library_entry(self.home, "findings-library/README.md")
        self.assertIn("findings-library/README.md", str(caught.exception))

    def test_two_entries_and_their_titles(self):
        self.write("findings-library/smb-signing.md",
                   support.make_library_entry(title="SMB signing not required"))
        self.write("findings-library/default-creds.md",
                   support.make_library_entry(title="Default admin password"))
        self.write("findings-library/README.md", "# Findings library\n")
        self.assertEqual(self.listed(), ([
            {"path": "findings-library/default-creds.md", "title": "Default admin password"},
            {"path": "findings-library/smb-signing.md", "title": "SMB signing not required"},
        ], []))

    def test_sorted_whatever_order_the_disk_gives(self):
        # The Mac's disk happens to list names in order, so hand back the
        # listing reversed to prove the code sorts it itself.
        self.write("findings-library/a.md", support.make_library_entry(title="A"))
        self.write("findings-library/b.md", support.make_library_entry(title="B"))
        real_glob = notebook.Path.glob
        with mock.patch.object(notebook.Path, "glob",
                               lambda folder, pattern: reversed(sorted(real_glob(folder, pattern)))):
            self.assertEqual(notebook.library_paths(self.home),
                             ["findings-library/a.md", "findings-library/b.md"])

    def test_title_is_returned_exactly(self):
        # Punctuation, double spaces, a trailing space and non-ASCII text all stay.
        title = "Kerberoast: svc_sql (RC4) — weak  pässwörd | 100% "
        self.write("findings-library/a.md", support.make_library_entry(title=title))
        self.assertEqual(self.listed()[0], [{"path": "findings-library/a.md", "title": title}])

    def test_unfilled_title_marker_is_returned_as_written(self):
        # An entry copied straight from templates/finding.md: no title invented.
        self.write("findings-library/a.md", "### [[FINDING_ID]]: [[FINDING_TITLE]]\n")
        self.assertEqual(self.listed()[0][0]["title"], "[[FINDING_TITLE]]")

    def test_first_heading_wins_and_prose_before_it_is_ignored(self):
        self.write("findings-library/a.md",
                   "Some prose first.\n#1 is not a heading (no space after #).\n\n"
                   "### [[FINDING_ID]]: First title\n\n"
                   "### [[FINDING_ID]]: Second title\n")
        self.assertEqual(self.listed(), (
            [{"path": "findings-library/a.md", "title": "First title"}], []))

    def test_titles_and_paths_come_from_disk(self):
        self.write("findings-library/a.md", support.make_library_entry(title="Old title"))
        self.assertEqual(self.listed()[0], [{"path": "findings-library/a.md", "title": "Old title"}])
        (self.home / "findings-library/a.md").rename(self.home / "findings-library/b.md")
        self.write("findings-library/b.md", support.make_library_entry(title="New title"))
        self.assertEqual(self.listed()[0], [{"path": "findings-library/b.md", "title": "New title"}])

    def test_only_md_files_directly_in_the_folder(self):
        self.write("findings-library/good.md", support.make_library_entry(title="Good"))
        self.write("findings-library/notes.txt", support.make_library_entry(title="Text file"))
        self.write("findings-library/old/nested.md", support.make_library_entry(title="Nested"))
        (self.home / "findings-library/folder.md").mkdir()
        self.assertEqual(self.listed(), (
            [{"path": "findings-library/good.md", "title": "Good"}], []))

    def test_wrong_first_heading_is_refused_and_named(self):
        # One bad entry is refused with its reason; the good one still lists.
        self.write("findings-library/good.md", support.make_library_entry(title="Good"))
        self.write("findings-library/filled.md", "### F-001: Already numbered\n")
        self.write("findings-library/level.md", "## [[FINDING_ID]]: Wrong level\n")
        self.write("findings-library/top.md", "# Notes\n\n### [[FINDING_ID]]: Under a title\n")
        self.write("findings-library/spaces.md", "###  [[FINDING_ID]]: Two spaces\n")
        self.write("findings-library/none.md", "No heading at all.\n")
        self.write("findings-library/empty.md", "")
        entries, refused = self.listed()
        self.assertEqual(entries, [{"path": "findings-library/good.md", "title": "Good"}])
        self.assertEqual(refused, [
            "findings-library/empty.md: no heading; a library entry starts with "
            "'### [[FINDING_ID]]: <title>'",
            "findings-library/filled.md: first heading doesn't start with "
            "'### [[FINDING_ID]]: ': '### F-001: Already numbered'",
            "findings-library/level.md: first heading doesn't start with "
            "'### [[FINDING_ID]]: ': '## [[FINDING_ID]]: Wrong level'",
            "findings-library/none.md: no heading; a library entry starts with "
            "'### [[FINDING_ID]]: <title>'",
            "findings-library/spaces.md: first heading doesn't start with "
            "'### [[FINDING_ID]]: ': '###  [[FINDING_ID]]: Two spaces'",
            "findings-library/top.md: first heading doesn't start with "
            "'### [[FINDING_ID]]: ': '# Notes'",
        ])

    def test_library_title_directly(self):
        self.assertEqual(notebook.library_title("x.md", "### [[FINDING_ID]]: T\n"), "T")
        with self.assertRaises(ValueError) as caught:
            notebook.library_title("findings-library/x.md", "## [[FINDING_ID]]: T\n")
        self.assertTrue(str(caught.exception).startswith("findings-library/x.md: "))

    def test_folder_link_inside_the_root_is_used(self):
        self.write("shared/library/a.md", support.make_library_entry(title="Linked folder"))
        (self.home / "findings-library").symlink_to(self.home / "shared/library")
        self.assertEqual(self.listed(), (
            [{"path": "findings-library/a.md", "title": "Linked folder"}], []))

    def test_folder_link_outside_the_root_is_refused(self):
        # DECISIONS 2026-10-29 Chunk N3 D1: the folder itself linked outside
        # is one refusal in the list, so the New form still opens.
        (self.home / "findings-library").symlink_to(self.outside)
        entries, refused = self.listed()
        self.assertEqual(entries, [])
        self.assertEqual(len(refused), 1)
        self.assertTrue(refused[0].startswith("path is outside the root: findings-library -> "),
                        refused[0])
        self.assertNotIn("secret.md", refused[0])
        self.assertNotIn("Outside secret title", refused[0])
        # library_paths() itself still refuses it, so a create can't read
        # an entry through the link.
        with self.assertRaises(compile.RootError):
            notebook.library_paths(self.home)

    def test_file_link_inside_the_root_is_listed_under_its_own_path(self):
        self.write("shared/real.md", support.make_library_entry(title="Target title"))
        (self.home / "findings-library").mkdir()
        (self.home / "findings-library/linked.md").symlink_to(self.home / "shared/real.md")
        self.assertEqual(self.listed(), (
            [{"path": "findings-library/linked.md", "title": "Target title"}], []))

    def test_file_link_outside_the_root_is_refused_not_read(self):
        self.write("findings-library/good.md", support.make_library_entry(title="Good"))
        (self.home / "findings-library/linked.md").symlink_to(self.outside / "secret.md")
        entries, refused = self.listed()
        self.assertEqual(entries, [{"path": "findings-library/good.md", "title": "Good"}])
        self.assertEqual(len(refused), 1)
        self.assertTrue(refused[0].startswith(
            "path is outside the root: findings-library/linked.md -> "))
        self.assertNotIn("Outside secret title", refused[0])

    def test_outside_link_is_checked_before_anything_follows_it(self):
        # is_file() follows a link, so it must never run on a link that the
        # path check hasn't passed yet (adversary, N3-02 round 1).
        self.write("findings-library/good.md", support.make_library_entry(title="Good"))
        link = self.home / "findings-library/linked.md"
        link.symlink_to(self.outside / "secret.md")
        followed = []
        real_is_file = notebook.Path.is_file

        def recording_is_file(path):
            followed.append(path)
            return real_is_file(path)

        with mock.patch.object(notebook.Path, "is_file", recording_is_file):
            entries, refused = notebook.list_library(self.home)
        self.assertEqual(entries, [{"path": "findings-library/good.md", "title": "Good"}])
        self.assertEqual(len(refused), 1)
        self.assertNotIn(link, followed)
        self.assertNotIn(self.outside / "secret.md", [path.resolve() for path in followed])

    def test_outside_link_to_a_folder_or_nothing_is_refused_not_dropped(self):
        self.write("findings-library/good.md", support.make_library_entry(title="Good"))
        (self.home / "findings-library/to-folder.md").symlink_to(self.outside)
        (self.home / "findings-library/dangling.md").symlink_to(self.outside / "missing.md")
        entries, refused = self.listed()
        self.assertEqual(entries, [{"path": "findings-library/good.md", "title": "Good"}])
        self.assertEqual(len(refused), 2)
        self.assertTrue(refused[0].startswith(
            "path is outside the root: findings-library/dangling.md -> "))
        self.assertTrue(refused[1].startswith(
            "path is outside the root: findings-library/to-folder.md -> "))

    def test_read_entry_refuses_a_folder_named_like_an_entry(self):
        (self.home / "findings-library/folder.md").mkdir(parents=True)
        with self.assertRaises(compile.RootError) as caught:
            notebook.read_library_entry(self.home, "findings-library/folder.md")
        self.assertIn("findings-library/folder.md", str(caught.exception))

    def test_read_entry_returns_the_text_unchanged(self):
        text = support.make_library_entry(title="Read me")
        self.write("findings-library/a.md", text)
        self.assertEqual(notebook.read_library_entry(self.home, "findings-library/a.md"), text)

    def test_read_entry_refuses_dot_dot(self):
        self.write("findings-library/a.md", support.make_library_entry())
        with self.assertRaises(compile.RootError) as caught:
            notebook.read_library_entry(self.home, "findings-library/../findings-library/a.md")
        self.assertIn("findings-library/../findings-library/a.md", str(caught.exception))

    def test_read_entry_refuses_an_absolute_path_outside(self):
        path = str(self.outside / "secret.md")
        with self.assertRaises(compile.RootError) as caught:
            notebook.read_library_entry(self.home, path)
        self.assertIn(path, str(caught.exception))

    def test_read_entry_refuses_a_nul_byte(self):
        self.write("findings-library/a.md", support.make_library_entry())
        with self.assertRaises(compile.RootError) as caught:
            notebook.read_library_entry(self.home, "findings-library/a.md\x00")
        self.assertIn("findings-library/a.md", str(caught.exception))

    def test_read_entry_refuses_a_file_outside_the_library(self):
        self.write("findings/F-001-x.md", support.make_library_entry())
        self.write("findings-library/old/nested.md", support.make_library_entry())
        for path in ["findings/F-001-x.md", "findings-library/old/nested.md"]:
            with self.subTest(path=path), self.assertRaises(compile.RootError) as caught:
                notebook.read_library_entry(self.home, path)
            self.assertIn(path, str(caught.exception))

    def test_bom_is_dropped(self):
        self.write_bytes("findings-library/a.md",
                         b"\xef\xbb\xbf### [[FINDING_ID]]: Saved by Notepad\n")
        self.assertEqual(self.listed()[0][0]["title"], "Saved by Notepad")

    def test_windows_line_ending_leaves_no_carriage_return(self):
        self.write_bytes("findings-library/a.md",
                         b"### [[FINDING_ID]]: Windows title\r\n\r\n#### Summary\r\n")
        self.assertEqual(self.listed()[0][0]["title"], "Windows title")

    def test_windows_1252_entry_is_refused_and_named(self):
        self.write("findings-library/good.md", support.make_library_entry(title="Good"))
        self.write_bytes("findings-library/cp1252.md", "### [[FINDING_ID]]: Café\n".encode("cp1252"))
        entries, refused = self.listed()
        self.assertEqual(entries, [{"path": "findings-library/good.md", "title": "Good"}])
        self.assertEqual(len(refused), 1)
        self.assertIn("cp1252.md is not UTF-8 text", refused[0])


class NumberTests(unittest.TestCase):
    """N3-03: the F-NNN collision warning and the suggested IR number."""

    BAD_NUMBERS = ["6", "01", "1000", "abc", "00a", "123\n", "١٢٣", "0\x007", "", " 007"]

    def setUp(self):
        self.home = support.make_worktree(self)
        # A second folder stands in for "somewhere outside", still inside .tmp/.
        # It holds names that would change every result if they were followed.
        self.outside = support.make_worktree(self, {
            "F-007-outside.md": "x\n", "IR-500-outside.md": "x\n",
            "findings/F-007-outside.md": "x\n", "field-notes/eve/IR-500-outside.md": "x\n",
            "eve/IR-500-outside.md": "x\n"})

    def write(self, *paths):
        for path in paths:
            support.write_fake_file(self.home, path, "x\n")

    def link(self, path, target):
        (self.home / path).parent.mkdir(parents=True, exist_ok=True)
        (self.home / path).symlink_to(target)

    def warnings(self, nnn="007"):
        """finding_id_warnings(), checking that it changed and created nothing."""
        before = file_bytes(self.home)
        before_names = sorted(self.home.rglob("*"))
        result = notebook.finding_id_warnings(self.home, nnn)
        self.assertEqual(file_bytes(self.home), before)
        self.assertEqual(sorted(self.home.rglob("*")), before_names)
        return result

    def suggestion(self):
        """suggest_ir_number(), checking that it changed and created nothing."""
        before = file_bytes(self.home)
        before_names = sorted(self.home.rglob("*"))
        result = notebook.suggest_ir_number(self.home)
        self.assertEqual(file_bytes(self.home), before)
        self.assertEqual(sorted(self.home.rglob("*")), before_names)
        return result

    # Case 1 and 12: one number check for both types.

    def test_good_numbers_pass(self):
        for nnn in ["000", "006", "999"]:
            with self.subTest(nnn=nnn):
                self.assertEqual(notebook.validate_nnn(nnn), nnn)
                self.assertEqual(self.warnings(nnn), ([], []))

    def test_bad_numbers_fail(self):
        # IR and F numbers both go through validate_nnn(); the collision
        # check uses it too, so a bad number never reaches a file search.
        for nnn in self.BAD_NUMBERS:
            with self.subTest(nnn=nnn):
                with self.assertRaises(ValueError):
                    notebook.validate_nnn(nnn)
                with self.assertRaises(ValueError):
                    notebook.finding_id_warnings(self.home, nnn)

    def test_suggestion_is_not_reserved_and_can_be_replaced(self):
        self.write("field-notes/alice/IR-004-a.md")
        self.assertEqual(self.suggestion(), ("005", []))
        # Nothing was written, so the same suggestion comes back, and any
        # valid number may be typed instead.
        self.assertEqual(self.suggestion(), ("005", []))
        self.assertEqual(notebook.validate_nnn("006"), "006")
        with self.assertRaises(ValueError):
            notebook.validate_nnn("6")

    # Case 2: nothing there yet.

    def test_missing_folders(self):
        self.assertEqual(self.warnings(), ([], []))
        self.assertEqual(self.suggestion(), ("001", []))
        self.assertEqual(list(self.home.iterdir()), [])

    # Cases 3-7: finding collisions.

    def test_local_finding_collides(self):
        self.write("findings/F-007-old.md")
        self.assertEqual(self.warnings(), (
            ["F-007 already exists: findings/F-007-old.md"], []))

    def test_incoming_finding_collides_without_local_findings(self):
        self.write("incoming/alice/findings/F-007-other.md")
        self.assertEqual(self.warnings(), (
            ["F-007 already exists: incoming/alice/findings/F-007-other.md"], []))

    def test_every_collision_is_reported_in_path_order(self):
        self.write("incoming/zed/findings/F-007-z.md", "incoming/bob/findings/F-007-b.md",
                   "findings/F-007-mine.md", "incoming/bob/findings/F-007-a.md",
                   "findings/F-008-other.md")
        self.assertEqual(self.warnings(), ([
            "F-007 already exists: findings/F-007-mine.md",
            "F-007 already exists: incoming/bob/findings/F-007-a.md",
            "F-007 already exists: incoming/bob/findings/F-007-b.md",
            "F-007 already exists: incoming/zed/findings/F-007-z.md",
        ], []))

    def test_path_order_whatever_order_the_disk_gives(self):
        # The Mac's disk happens to list names in order, so hand back every
        # listing reversed to prove the code sorts them itself.
        self.write("incoming/bob/findings/F-007-a.md", "incoming/bob/findings/F-007-b.md",
                   "incoming/zed/findings/F-007-z.md", "incoming/eve/findings/F-007-e.md")
        self.link("incoming/zed-link", self.outside)
        self.link("incoming/amy-link", self.outside)
        real_glob, real_iterdir = notebook.Path.glob, notebook.Path.iterdir
        with mock.patch.object(notebook.Path, "glob",
                               lambda folder, pattern: reversed(sorted(real_glob(folder, pattern)))), \
                mock.patch.object(notebook.Path, "iterdir",
                                  lambda folder: reversed(sorted(real_iterdir(folder)))):
            warnings, refused = notebook.finding_id_warnings(self.home, "007")
        self.assertEqual(warnings, [
            "F-007 already exists: incoming/bob/findings/F-007-a.md",
            "F-007 already exists: incoming/bob/findings/F-007-b.md",
            "F-007 already exists: incoming/eve/findings/F-007-e.md",
            "F-007 already exists: incoming/zed/findings/F-007-z.md"])
        self.assertEqual(len(refused), 2)
        self.assertTrue(refused[0].startswith("path is outside the root: incoming/amy-link -> "))
        self.assertTrue(refused[1].startswith("path is outside the root: incoming/zed-link -> "))

    def test_refused_file_links_in_path_order_whatever_order_the_disk_gives(self):
        # File-level refusals come from glob(), so they need sorting too
        # (adversary, N3-03 round 1).
        self.link("findings/F-007-a.md", self.outside / "F-007-outside.md")
        self.link("findings/F-007-z.md", self.outside / "F-007-outside.md")
        self.link("field-notes/alice/IR-500-a.md", self.outside / "IR-500-outside.md")
        self.link("field-notes/alice/IR-500-z.md", self.outside / "IR-500-outside.md")
        real_glob = notebook.Path.glob
        with mock.patch.object(notebook.Path, "glob",
                               lambda folder, pattern: reversed(sorted(real_glob(folder, pattern)))):
            warnings, finding_refused = notebook.finding_id_warnings(self.home, "007")
            suggestion, ir_refused = notebook.suggest_ir_number(self.home)
        self.assertEqual((warnings, suggestion), ([], "001"))
        self.assertEqual(len(finding_refused), 2)
        self.assertTrue(finding_refused[0].startswith(
            "path is outside the root: findings/F-007-a.md -> "))
        self.assertTrue(finding_refused[1].startswith(
            "path is outside the root: findings/F-007-z.md -> "))
        self.assertEqual(len(ir_refused), 2)
        self.assertTrue(ir_refused[0].startswith(
            "path is outside the root: field-notes/alice/IR-500-a.md -> "))
        self.assertTrue(ir_refused[1].startswith(
            "path is outside the root: field-notes/alice/IR-500-z.md -> "))

    def test_no_collision(self):
        # An owner folder whose name holds "F-007" doesn't make its F-008 collide.
        self.write("findings/F-006-a.md", "incoming/bob/findings/F-008-b.md",
                   "incoming/F-007-team/findings/F-008-t.md")
        self.assertEqual(self.warnings(), ([], []))

    def test_near_miss_names_dont_collide(self):
        self.write("findings/F-070-a.md", "findings/F-0070-a.md", "findings/F-007x.md",
                   "findings/F-07-a.md", "findings/F-007-a.txt", "findings/F-007_a.md",
                   "findings/old/F-007-a.md", "F-007-top.md", "field-notes/alice/F-007-a.md",
                   "incoming/bob/F-007-a.md", "incoming/bob/findings/old/F-007-a.md",
                   "notes/F-007-a.md")
        (self.home / "findings/F-007-folder.md").mkdir()
        self.assertEqual(self.warnings(), ([], []))
        # The same folder with a correctly named file does collide; so does
        # a name with no slug, which compile.py reads as F-007 too.
        self.write("findings/F-007-real.md", "findings/F-007.md")
        self.assertEqual(self.warnings(), ([
            "F-007 already exists: findings/F-007-real.md",
            "F-007 already exists: findings/F-007.md"], []))

    # Cases 8-11 and 13: the suggested IR number.

    def test_first_ir_is_001(self):
        self.write("field-notes/alice/NOTE-a.md", "field-notes/alice/IR-xyz.md")
        self.assertEqual(self.suggestion(), ("001", []))

    def test_highest_across_local_and_incoming(self):
        self.write("field-notes/alice/IR-001-a.md", "incoming/bob/field-notes/bob/IR-004-b.md")
        self.assertEqual(self.suggestion(), ("005", []))

    def test_every_local_and_incoming_person_counts(self):
        # No name is built in: any field-notes/<name>/ counts, locally and
        # inside any incoming/<owner>/.
        self.write("field-notes/carol/IR-002-c.md",
                   "incoming/dave/field-notes/erin/IR-003-e.md")
        self.assertEqual(self.suggestion(), ("004", []))

    def test_numeric_maximum(self):
        # The highest is neither the first nor the last file scanned, and
        # appears twice; the next number is still suggested once.
        self.write("field-notes/alice/IR-009-a.md", "field-notes/alice/IR-010-b.md",
                   "incoming/bob/field-notes/bob/IR-010-c.md",
                   "incoming/zed/field-notes/zed/IR-003-z.md")
        self.assertEqual(self.suggestion(), ("011", []))

    def test_names_that_dont_count(self):
        self.write("field-notes/alice/IR-002-a.md",
                   "field-notes/alice/IR-01-a.md", "field-notes/alice/IR-1000-a.md",
                   "field-notes/alice/IR-abc.md", "field-notes/alice/IR-٠٠٩-a.md",
                   "field-notes/alice/ir-009-a.md", "field-notes/alice/SU-009-a.md",
                   "field-notes/alice/XIR-009-a.md", "field-notes/alice/IR-009-a.txt",
                   "field-notes/alice/IR-009x.md", "field-notes/alice/old/IR-009-a.md",
                   "field-notes/IR-009-a.md", "IR-009-a.md", "findings/IR-009-a.md",
                   "incoming/bob/IR-009-a.md", "incoming/bob/field-notes/IR-009-a.md",
                   "incoming/bob/findings/IR-009-a.md", "notes/IR-009-a.md")
        (self.home / "field-notes/alice/IR-009-folder.md").mkdir()
        self.assertEqual(self.suggestion(), ("003", []))

    def test_ir_without_a_slug_counts(self):
        self.write("field-notes/alice/IR-004.md")
        self.assertEqual(self.suggestion(), ("005", []))

    def test_999_in_use_leaves_nothing_to_suggest(self):
        self.write("field-notes/alice/IR-001-a.md", "incoming/bob/field-notes/bob/IR-999-z.md")
        self.assertEqual(self.suggestion(), (None, []))
        self.assertEqual(notebook.NO_IR_NUMBER_LEFT,
                         "IR-999 is in use, so there is no next three-digit IR number"
                         " to suggest: type one in.")
        # The field still takes any valid number the user types.
        self.assertEqual(notebook.validate_nnn("002"), "002")

    # Case 14: links that stay inside the root.

    def test_links_inside_the_root_count_under_their_own_paths(self):
        self.write("shared/bob/findings/F-007-b.md", "shared/carol/F-007-c.md",
                   "shared/real.md", "shared/notes/IR-006-n.md",
                   "shared/dave-notes/dave/IR-008-d.md")
        self.link("incoming/bob", self.home / "shared/bob")
        self.link("incoming/carol/findings", self.home / "shared/carol")
        self.link("findings/F-007-linked.md", self.home / "shared/real.md")
        self.link("field-notes/alice", self.home / "shared/notes")
        self.link("incoming/dave/field-notes", self.home / "shared/dave-notes")
        self.assertEqual(self.warnings(), ([
            "F-007 already exists: findings/F-007-linked.md",
            "F-007 already exists: incoming/bob/findings/F-007-b.md",
            "F-007 already exists: incoming/carol/findings/F-007-c.md"], []))
        self.assertEqual(self.suggestion(), ("009", []))

    def test_linked_ir_file_inside_the_root_counts(self):
        self.write("shared/real.md")
        self.link("field-notes/alice/IR-012-linked.md", self.home / "shared/real.md")
        self.assertEqual(self.suggestion(), ("013", []))

    # Case 15: links pointing outside the root. Each level is its own test.

    def assert_one_refusal(self, refused, path):
        self.assertEqual(len(refused), 1, refused)
        self.assertTrue(refused[0].startswith("path is outside the root: " + path + " -> "),
                        refused[0])

    # DECISIONS 2026-10-29 Chunk N3 D1: a top-level folder linked outside is
    # one refusal in the list; the rest of the scan still counts.

    def test_findings_folder_linked_outside_is_refused_incoming_still_counts(self):
        self.link("findings", self.outside / "findings")
        self.write("incoming/bob/findings/F-007-b.md")
        warnings, refused = self.warnings()
        self.assertEqual(warnings, ["F-007 already exists: incoming/bob/findings/F-007-b.md"])
        self.assert_one_refusal(refused, "findings")
        self.assertNotIn("F-007-outside", refused[0])

    def test_incoming_folder_linked_outside_is_refused_local_still_counts(self):
        self.link("incoming", self.outside)
        self.write("findings/F-007-mine.md", "field-notes/alice/IR-002-a.md")
        warnings, refused = self.warnings()
        self.assertEqual(warnings, ["F-007 already exists: findings/F-007-mine.md"])
        self.assert_one_refusal(refused, "incoming")
        suggestion, refused = self.suggestion()
        self.assertEqual(suggestion, "003")
        self.assert_one_refusal(refused, "incoming")
        warnings, refused = self.ir_warnings("002")
        self.assertEqual(warnings, ["IR-002 already exists: field-notes/alice/IR-002-a.md"])
        self.assert_one_refusal(refused, "incoming")
        self.assertNotIn("outside.md", refused[0])

    def test_field_notes_folder_linked_outside_is_refused_incoming_still_counts(self):
        self.link("field-notes", self.outside / "field-notes")
        self.write("incoming/bob/field-notes/bob/IR-004-b.md")
        suggestion, refused = self.suggestion()
        self.assertEqual(suggestion, "005")
        self.assert_one_refusal(refused, "field-notes")
        self.assertNotIn("IR-500", refused[0])

    def test_every_refusal_comes_back_in_path_order(self):
        self.link("field-notes", self.outside / "field-notes")
        self.link("incoming/eve", self.outside)
        self.link("incoming/bob/field-notes/bob/IR-500-l.md", self.outside / "IR-500-outside.md")
        self.write("incoming/bob/field-notes/bob/IR-003-b.md")
        for refused in [self.suggestion()[1], self.ir_warnings("003")[1]]:
            self.assertEqual(len(refused), 3, refused)
            self.assertTrue(refused[0].startswith("path is outside the root: field-notes -> "))
            self.assertTrue(refused[1].startswith(
                "path is outside the root: incoming/bob/field-notes/bob/IR-500-l.md -> "))
            self.assertTrue(refused[2].startswith("path is outside the root: incoming/eve -> "))
        self.assertEqual(self.suggestion()[0], "004")

    # DECISIONS 2026-10-29 Chunk N3 D2: a typed IR number already in use warns.

    def ir_warnings(self, nnn):
        """ir_number_warnings(), checking that it changed and created nothing."""
        before = file_bytes(self.home)
        before_names = sorted(self.home.rglob("*"))
        result = notebook.ir_number_warnings(self.home, nnn)
        self.assertEqual(file_bytes(self.home), before)
        self.assertEqual(sorted(self.home.rglob("*")), before_names)
        return result

    def test_local_ir_number_collides(self):
        self.write("field-notes/alice/IR-007-old.md")
        self.assertEqual(self.ir_warnings("007"), (
            ["IR-007 already exists: field-notes/alice/IR-007-old.md"], []))

    def test_incoming_ir_number_collides(self):
        self.write("incoming/bob/field-notes/bob/IR-007-b.md")
        self.assertEqual(self.ir_warnings("007"), (
            ["IR-007 already exists: incoming/bob/field-notes/bob/IR-007-b.md"], []))

    def test_every_ir_collision_in_path_order(self):
        self.write("incoming/zed/field-notes/zed/IR-007-z.md", "field-notes/carol/IR-007-c.md",
                   "incoming/bob/field-notes/erin/IR-007-e.md", "field-notes/alice/IR-007.md",
                   "field-notes/alice/IR-008-other.md")
        real_glob, real_iterdir = notebook.Path.glob, notebook.Path.iterdir
        with mock.patch.object(notebook.Path, "glob",
                               lambda folder, pattern: reversed(sorted(real_glob(folder, pattern)))), \
                mock.patch.object(notebook.Path, "iterdir",
                                  lambda folder: reversed(sorted(real_iterdir(folder)))):
            warnings, refused = notebook.ir_number_warnings(self.home, "007")
        self.assertEqual(warnings, [
            "IR-007 already exists: field-notes/alice/IR-007.md",
            "IR-007 already exists: field-notes/carol/IR-007-c.md",
            "IR-007 already exists: incoming/bob/field-notes/erin/IR-007-e.md",
            "IR-007 already exists: incoming/zed/field-notes/zed/IR-007-z.md"])
        self.assertEqual(refused, [])

    def test_ir_near_misses_dont_collide(self):
        self.write("field-notes/alice/IR-07-a.md", "field-notes/alice/IR-0070-a.md",
                   "field-notes/alice/IR-007x.md", "field-notes/alice/IR-007_x.md",
                   "field-notes/alice/ir-007-a.md", "field-notes/alice/IR-007-a.txt",
                   "field-notes/alice/old/IR-007-a.md", "field-notes/IR-007-a.md",
                   "IR-007-a.md", "findings/IR-007-a.md", "incoming/bob/field-notes/IR-007-a.md",
                   "field-notes/alice/IR-٠٠٧-a.md")
        (self.home / "field-notes/alice/IR-007-folder.md").mkdir()
        self.assertEqual(self.ir_warnings("007"), ([], []))

    def test_no_ir_collision(self):
        self.write("field-notes/alice/IR-006-a.md", "incoming/bob/field-notes/bob/IR-008-b.md")
        self.assertEqual(self.ir_warnings("007"), ([], []))

    def test_refused_ir_link_doesnt_hide_a_collision(self):
        self.write("incoming/bob/field-notes/bob/IR-007-b.md")
        self.link("field-notes/alice/IR-007-linked.md", self.outside / "IR-500-outside.md")
        warnings, refused = self.ir_warnings("007")
        self.assertEqual(warnings, ["IR-007 already exists: incoming/bob/field-notes/bob/IR-007-b.md"])
        self.assert_one_refusal(refused, "field-notes/alice/IR-007-linked.md")

    def test_ir_warning_needs_a_good_number(self):
        for nnn in self.BAD_NUMBERS:
            with self.subTest(nnn=nnn), self.assertRaises(ValueError):
                notebook.ir_number_warnings(self.home, nnn)

    def test_owner_folder_linked_outside_is_refused_others_still_count(self):
        self.write("incoming/bob/findings/F-007-b.md", "incoming/bob/field-notes/bob/IR-002-b.md")
        self.link("incoming/eve", self.outside)
        warnings, refused = self.warnings()
        self.assertEqual(warnings, ["F-007 already exists: incoming/bob/findings/F-007-b.md"])
        self.assert_one_refusal(refused, "incoming/eve")
        suggestion, refused = self.suggestion()
        self.assertEqual(suggestion, "003")
        self.assert_one_refusal(refused, "incoming/eve")

    def test_owner_findings_folder_linked_outside_is_refused(self):
        self.write("findings/F-007-mine.md")
        self.link("incoming/eve/findings", self.outside / "findings")
        warnings, refused = self.warnings()
        self.assertEqual(warnings, ["F-007 already exists: findings/F-007-mine.md"])
        self.assert_one_refusal(refused, "incoming/eve/findings")

    def test_owner_field_notes_folder_linked_outside_is_refused(self):
        self.write("field-notes/alice/IR-002-a.md")
        self.link("incoming/eve/field-notes", self.outside / "field-notes")
        suggestion, refused = self.suggestion()
        self.assertEqual(suggestion, "003")
        self.assert_one_refusal(refused, "incoming/eve/field-notes")

    def test_person_folder_linked_outside_is_refused(self):
        self.write("field-notes/alice/IR-002-a.md")
        self.link("field-notes/eve", self.outside / "eve")
        self.link("incoming/bob/field-notes/eve", self.outside / "eve")
        suggestion, refused = self.suggestion()
        self.assertEqual(suggestion, "003")
        self.assertEqual(len(refused), 2, refused)
        self.assertTrue(refused[0].startswith(
            "path is outside the root: field-notes/eve -> "))
        self.assertTrue(refused[1].startswith(
            "path is outside the root: incoming/bob/field-notes/eve -> "))

    def test_finding_file_linked_outside_is_refused(self):
        self.write("findings/F-007-mine.md")
        self.link("incoming/bob/findings/F-007-linked.md", self.outside / "F-007-outside.md")
        warnings, refused = self.warnings()
        self.assertEqual(warnings, ["F-007 already exists: findings/F-007-mine.md"])
        self.assert_one_refusal(refused, "incoming/bob/findings/F-007-linked.md")

    def test_ir_file_linked_outside_is_refused(self):
        self.write("field-notes/alice/IR-002-a.md")
        self.link("field-notes/alice/IR-500-linked.md", self.outside / "IR-500-outside.md")
        suggestion, refused = self.suggestion()
        self.assertEqual(suggestion, "003")
        self.assert_one_refusal(refused, "field-notes/alice/IR-500-linked.md")

    def test_outside_link_is_checked_before_anything_follows_it(self):
        # is_file() and is_dir() follow a link, so neither may run on a link
        # that hasn't passed the path check (the N3-02 round-1 lesson).
        links = [self.home / "incoming/eve", self.home / "incoming/bob/findings/F-007-l.md",
                 self.home / "field-notes/eve"]
        self.link("incoming/eve", self.outside)
        self.link("incoming/bob/findings/F-007-l.md", self.outside / "F-007-outside.md")
        self.link("field-notes/eve", self.outside / "eve")
        followed = []
        real_is_file, real_is_dir = notebook.Path.is_file, notebook.Path.is_dir

        def recording_is_file(path):
            followed.append(path)
            return real_is_file(path)

        def recording_is_dir(path):
            followed.append(path)
            return real_is_dir(path)

        with mock.patch.object(notebook.Path, "is_file", recording_is_file), \
                mock.patch.object(notebook.Path, "is_dir", recording_is_dir):
            notebook.finding_id_warnings(self.home, "007")
            notebook.suggest_ir_number(self.home)
        for link in links:
            self.assertNotIn(link, followed)
        outside = self.outside.resolve()
        for path in followed:
            self.assertNotIn(outside, [path.resolve()] + list(path.resolve().parents))

    # Case 17: read live from disk.

    def test_results_follow_the_disk(self):
        self.assertEqual(self.warnings(), ([], []))
        self.assertEqual(self.suggestion(), ("001", []))
        self.write("incoming/bob/findings/F-007-new.md", "field-notes/alice/IR-041-a.md")
        self.assertEqual(self.warnings(), (
            ["F-007 already exists: incoming/bob/findings/F-007-new.md"], []))
        self.assertEqual(self.suggestion(), ("042", []))
        (self.home / "field-notes/alice/IR-041-a.md").rename(
            self.home / "field-notes/alice/IR-070-a.md")
        self.assertEqual(self.suggestion(), ("071", []))


def tree(root):
    """Every name under root (links not followed) with its bytes, link target or "folder"."""
    found = {}
    for folder, dirs, files in os.walk(str(root)):
        for name in dirs + files:
            path = os.path.join(folder, name)
            key = os.path.relpath(path, str(root))
            if os.path.islink(path):
                found[key] = "link -> " + os.readlink(path)
            elif os.path.isdir(path):
                found[key] = "folder"
            else:
                with open(path, "rb") as handle:
                    found[key] = handle.read()
    return found


# Fake templates with look-alike and unrelated markers, so a test can see that
# only the exact ID and title markers are filled (N3-04 cases 2-6).
FAKE_TEMPLATES = {
    "templates/incident-report.md": (
        "# Incident Report [[IR_ID]]\n\n"
        "- **ID:** [[IR_ID]]\n"
        "- **Not IDs:** [[IR_ID_EXTRA]] [[ IR_ID ]] [[ir_id]] [[IR_ID] [[FINDING_ID]]\n"
        "- **Host:** [[HOST]] [[CHOOSE: Yes / No]]\n"
        "[[NOTE: Keep this note,\nacross two lines.]]\n"),
    "templates/status-update.md": (
        "# Status update\n\n- **Time:** [[DATE]] [[TIME]]\n"
        "- **Refs:** [[IR_ID]] [[FINDING_ID]] [[FINDING_TITLE]]\n"),
    "templates/inject-response.md": (
        "# Inject response\n\n- **Sent:** [[DATE_SENT]] [[TIME_SENT]]\n"
        "- **Refs:** [[IR_ID]] [[FINDING_ID]]\n"),
    "templates/finding.md": (
        "### [[FINDING_ID]]: [[FINDING_TITLE]]\n\n"
        "- **Severity:** [[CHOOSE: Critical / High / Low]]\n"
        "- `evidence/[[FINDING_ID]]-01.png`: [[WHAT_IT_SHOWS]]\n"
        "- **Not IDs:** [[FINDING_ID_EXTRA]] [[FINDING_TITLE_X]] [[IR_ID]] [[PREVIOUS_FINDING_ID]]\n"
        "[[NOTE: Keep this note,\nacross two lines.]]\n"),
}

# A fake library entry: a filled heading, a later heading of the same form,
# and markers that must stay as they are.
LIBRARY_ENTRY = (
    "### [[FINDING_ID]]: SMB signing not required\n\n"
    "- **Severity:** High\n"
    "- **Affected assets:** [[HOST]] ([[HOST_IP]])\n"
    "- `evidence/[[FINDING_ID]]-01.png`: [[WHAT_IT_SHOWS]] [[FINDING_ID_EXTRA]]\n\n"
    "### [[FINDING_ID]]: Related note kept as written\n")


class CreateNewFileTests(unittest.TestCase):
    """N3-04: create_new_file(), the New form's one write."""

    def setUp(self):
        self.home = support.make_worktree(self, FAKE_TEMPLATES)
        self.logs = support.make_worktree(self)
        # A third folder stands in for "somewhere outside", still inside .tmp/.
        self.outside = support.make_worktree(self, {
            "secret.md": "outside\n",
            "library/entry.md": LIBRARY_ENTRY,
            "templates/finding.md": "### [[FINDING_ID]]: outside template\n"})

    def create(self, type_name, title, nnn=None, library=None):
        return notebook.create_new_file(self.home, self.logs, "alice", type_name, title,
                                        nnn=nnn, library=library)

    def text(self, path):
        with (self.home / path).open(encoding="utf-8", newline="") as handle:
            return handle.read()

    def link(self, path, target):
        (self.home / path).parent.mkdir(parents=True, exist_ok=True)
        (self.home / path).symlink_to(target)

    def write(self, path, text):
        support.write_fake_file(self.home, path, text)

    def assert_refused(self, error, *args, **kwargs):
        """The call raises error before the first folder or file is made; nothing changes."""
        before = (tree(self.home), tree(self.outside), tree(self.logs))
        with mock.patch.object(notebook.Path, "mkdir", side_effect=AssertionError("mkdir ran")), \
                mock.patch.object(notebook.os, "makedirs", side_effect=AssertionError("makedirs ran")):
            with self.assertRaises(error) as caught:
                self.create(*args, **kwargs)
        self.assertEqual((tree(self.home), tree(self.outside), tree(self.logs)), before)
        return str(caught.exception)

    def assert_created(self, path, *args, **kwargs):
        """The call creates exactly path (plus any folders it needs) and changes nothing else."""
        before = tree(self.home)
        result = self.create(*args, **kwargs)
        after = tree(self.home)
        self.assertEqual(result[0], path)
        new_names = set(after) - set(before)
        self.assertIn(path, new_names)
        for name in new_names - {path}:
            self.assertEqual(after[name], "folder", name)
            self.assertTrue(path.startswith(name + "/"), name)
        for name in before:
            self.assertEqual(after[name], before[name], name)
        return result

    # Cases 1-5: each type lands at its literal path.

    def test_note(self):
        result = self.assert_created("field-notes/alice/NOTE-quick-note.md", "Note", "Quick Note")
        self.assertEqual(result, ("field-notes/alice/NOTE-quick-note.md", [], []))
        self.assertEqual(self.text("field-notes/alice/NOTE-quick-note.md"), "")

    def test_incident_report(self):
        self.assert_created("field-notes/alice/IR-007-incident-title.md",
                            "Incident report", "Incident Title", nnn="007")
        self.assertEqual(self.text("field-notes/alice/IR-007-incident-title.md"), (
            "# Incident Report IR-007\n\n"
            "- **ID:** IR-007\n"
            "- **Not IDs:** [[IR_ID_EXTRA]] [[ IR_ID ]] [[ir_id]] [[IR_ID] [[FINDING_ID]]\n"
            "- **Host:** [[HOST]] [[CHOOSE: Yes / No]]\n"
            "[[NOTE: Keep this note,\nacross two lines.]]\n"))

    def test_status_update_is_a_byte_copy(self):
        self.assert_created("field-notes/alice/SU-status-title.md", "Status update", "Status Title")
        self.assertEqual(self.text("field-notes/alice/SU-status-title.md"),
                         FAKE_TEMPLATES["templates/status-update.md"])

    def test_inject_response_is_a_byte_copy(self):
        self.assert_created("field-notes/alice/INJ-inject-title.md", "Inject response", "Inject Title")
        self.assertEqual(self.text("field-notes/alice/INJ-inject-title.md"),
                         FAKE_TEMPLATES["templates/inject-response.md"])

    def test_finding_from_the_template(self):
        self.assert_created("findings/F-042-finding-title.md", "Finding", "Finding Title", nnn="042")
        self.assertEqual(self.text("findings/F-042-finding-title.md"), (
            "### F-042: Finding Title\n\n"
            "- **Severity:** [[CHOOSE: Critical / High / Low]]\n"
            "- `evidence/F-042-01.png`: [[WHAT_IT_SHOWS]]\n"
            "- **Not IDs:** [[FINDING_ID_EXTRA]] [[FINDING_TITLE_X]] [[IR_ID]] [[PREVIOUS_FINDING_ID]]\n"
            "[[NOTE: Keep this note,\nacross two lines.]]\n"))

    def test_real_templates_get_their_ids(self):
        # The repo's own templates, copied in: the ID and title land where
        # templates/README.md says, and nothing else changes.
        repo = support.TOOLS_DIR.parent
        for name in ["incident-report.md", "finding.md"]:
            source = (repo / "templates" / name).read_bytes()
            (self.home / "templates" / name).write_bytes(source)
        self.create("Incident report", "Real IR", nnn="003")
        self.create("Finding", "Real finding", nnn="004")
        ir_text = (self.home / "field-notes/alice/IR-003-real-ir.md").read_bytes()
        f_text = (self.home / "findings/F-004-real-finding.md").read_bytes()
        repo_ir = (repo / "templates/incident-report.md").read_bytes()
        repo_f = (repo / "templates/finding.md").read_bytes()
        self.assertEqual(ir_text, repo_ir.replace(b"[[IR_ID]]", b"IR-003"))
        self.assertEqual(f_text, repo_f.replace(b"[[FINDING_ID]]", b"F-004")
                         .replace(b"[[FINDING_TITLE]]", b"Real finding"))
        self.assertIn(b"[[PREVIOUS_FINDING_ID]]", f_text)

    # Case 7: a free-text title goes in exactly as typed.

    def test_title_exactly_as_typed(self):
        title = "Admin | `id` $HOME café [[HOST]] [[FINDING_ID]] \\ end "
        result = self.create("Finding", title, nnn="001")
        self.assertEqual(result[0], "findings/F-001-" + notebook.slugify(title) + ".md")
        self.assertEqual(result[0], "findings/F-001-admin-id-home-caf-host-finding-id-end.md")
        first_line = self.text(result[0]).split("\n")[0]
        # The title's own [[FINDING_ID]] is not filled: values are never rescanned.
        self.assertEqual(first_line, "### F-001: " + title)

    # Cases 8-11: library findings.

    def add_library(self, name="smb.md", text=LIBRARY_ENTRY):
        self.write("findings-library/" + name, text)
        return "findings-library/" + name

    def test_library_title_unchanged(self):
        entry = self.add_library()
        result = self.create("Finding", "SMB signing not required", nnn="009", library=entry)
        self.assertEqual(result[0], "findings/F-009-smb-signing-not-required.md")
        self.assertEqual(self.text(result[0]), LIBRARY_ENTRY.replace("[[FINDING_ID]]", "F-009"))

    def test_library_title_edited(self):
        entry = self.add_library()
        result = self.create("Finding", "SMB signing off on DC01", nnn="010", library=entry)
        self.assertEqual(result[0], "findings/F-010-smb-signing-off-on-dc01.md")
        self.assertEqual(self.text(result[0]), (
            "### F-010: SMB signing off on DC01\n\n"
            "- **Severity:** High\n"
            "- **Affected assets:** [[HOST]] ([[HOST_IP]])\n"
            "- `evidence/F-010-01.png`: [[WHAT_IT_SHOWS]] [[FINDING_ID_EXTRA]]\n\n"
            "### F-010: Related note kept as written\n"))

    def test_library_title_edited_with_prose_and_crlf(self):
        entry = self.add_library("crlf.md", "Intro line.\r\n### [[FINDING_ID]]: Old\r\nBody [[HOST]]\r\n")
        result = self.create("Finding", "New", nnn="011", library=entry)
        self.assertEqual((self.home / result[0]).read_bytes(),
                         b"Intro line.\r\n### F-011: New\r\nBody [[HOST]]\r\n")

    def test_library_title_with_markers_is_exact(self):
        entry = self.add_library()
        result = self.create("Finding", "x [[FINDING_ID]] [[FINDING_TITLE]]", nnn="012", library=entry)
        self.assertEqual(self.text(result[0]).split("\n")[0],
                         "### F-012: x [[FINDING_ID]] [[FINDING_TITLE]]")

    def test_library_finding_title_marker_is_filled(self):
        # The spec: the new file has [[FINDING_TITLE]] filled with the title,
        # wherever the text came from.
        entry = self.add_library("t.md", "### [[FINDING_ID]]: Old\n\nSee [[FINDING_TITLE]].\n")
        result = self.create("Finding", "New title", nnn="013", library=entry)
        self.assertEqual(self.text(result[0]), "### F-013: New title\n\nSee New title.\n")

    def test_library_bad_heading_is_refused(self):
        entry = self.add_library("bad.md", "## [[FINDING_ID]]: Wrong level\n")
        message = self.assert_refused(ValueError, "Finding", "T", nnn="001", library=entry)
        self.assertIn("findings-library/bad.md", message)

    def test_library_readme_is_refused(self):
        entry = self.add_library("README.md", "# Library\n")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001", library=entry)
        self.assertIn("findings-library/README.md", message)

    def test_library_subfolder_entry_is_refused(self):
        entry = self.add_library("old/smb.md")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001", library=entry)
        self.assertIn("findings-library/old/smb.md", message)

    def test_library_path_outside_the_folder_is_refused(self):
        self.write("findings/F-001-x.md", LIBRARY_ENTRY)
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="002",
                                      library="findings/F-001-x.md")
        self.assertIn("findings/F-001-x.md", message)

    def test_library_dot_dot_is_refused(self):
        self.add_library()
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001",
                                      library="findings-library/../findings-library/smb.md")
        self.assertIn("findings-library/../findings-library/smb.md", message)

    def test_library_absolute_path_outside_is_refused(self):
        path = str(self.outside / "library/entry.md")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001", library=path)
        self.assertIn(path, message)

    def test_library_nul_is_refused(self):
        self.add_library()
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001",
                                      library="findings-library/smb.md\x00")
        self.assertIn("findings-library/smb.md", message)

    def test_library_entry_linked_outside_is_refused(self):
        self.link("findings-library/linked.md", self.outside / "library/entry.md")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001",
                                      library="findings-library/linked.md")
        self.assertIn("findings-library/linked.md", message)

    def test_library_entry_linked_inside_is_used(self):
        self.write("shared/entry.md", LIBRARY_ENTRY)
        self.link("findings-library/linked.md", self.home / "shared/entry.md")
        result = self.create("Finding", "SMB signing not required", nnn="001",
                             library="findings-library/linked.md")
        self.assertEqual(self.text(result[0]), LIBRARY_ENTRY.replace("[[FINDING_ID]]", "F-001"))

    def test_library_that_isnt_text_is_refused(self):
        self.assert_refused(ValueError, "Finding", "T", nnn="001", library=["findings-library/smb.md"])

    def test_library_only_for_findings(self):
        entry = self.add_library()
        for type_name, nnn in [("Note", None), ("Incident report", "001"),
                               ("Status update", None), ("Inject response", None)]:
            with self.subTest(type_name=type_name):
                message = self.assert_refused(ValueError, type_name, "T", nnn=nnn, library=entry)
                self.assertIn("only a Finding can start from the findings library", message)

    def test_finding_without_library_uses_only_the_template(self):
        self.add_library()
        with mock.patch.object(notebook, "read_library_entry",
                               side_effect=AssertionError("library read")):
            result = self.create("Finding", "Plain", nnn="001")
        self.assertTrue(self.text(result[0]).startswith("### F-001: Plain\n"))

    # Cases 12, 13 and 22: the number.

    def test_typed_number_is_used_not_the_suggestion(self):
        self.write("field-notes/alice/IR-004-old.md", "x\n")
        self.assertEqual(notebook.suggest_ir_number(self.home)[0], "005")
        result = self.create("Incident report", "Next", nnn="006")
        self.assertEqual(result[0], "field-notes/alice/IR-006-next.md")
        self.assertTrue(self.text(result[0]).startswith("# Incident Report IR-006\n"))

    def test_bad_numbers_are_refused(self):
        for type_name in ["Incident report", "Finding"]:
            for nnn in ["6", "0006", "123\n", "١٢٣", "", None, 7, ["007"]]:
                with self.subTest(type_name=type_name, nnn=nnn):
                    message = self.assert_refused(ValueError, type_name, "T", nnn=nnn)
                    self.assertTrue("three digits" in message, message)

    def test_types_without_a_number_refuse_one(self):
        for type_name in ["Note", "Status update", "Inject response"]:
            with self.subTest(type_name=type_name):
                message = self.assert_refused(ValueError, type_name, "T", nnn="007")
                self.assertIn(type_name + " has no number", message)

    def test_missing_number_never_picks_one(self):
        with mock.patch.object(notebook, "suggest_ir_number",
                               side_effect=AssertionError("suggestion used")):
            self.assert_refused(ValueError, "Incident report", "T", nnn=None)
            self.assert_refused(ValueError, "Finding", "T", nnn=None)
            self.create("Incident report", "T", nnn="001")

    # Case 14: the slug.

    def test_dot_dot_title_stays_in_its_folder(self):
        result = self.create("Note", "../A  B!!")
        self.assertEqual(result[0], "field-notes/alice/NOTE-a-b.md")

    def test_empty_slug_is_refused(self):
        for title in ["", "!!!", "../", " - "]:
            with self.subTest(title=title):
                self.assert_refused(ValueError, "Note", title)

    def test_title_that_isnt_text_is_refused(self):
        self.assert_refused(ValueError, "Note", None)

    def test_nul_and_percent_00_never_reach_the_path(self):
        self.assertEqual(self.create("Note", "a\x00b")[0], "field-notes/alice/NOTE-a-b.md")
        self.assertEqual(self.create("Note", "a%00b")[0], "field-notes/alice/NOTE-a-00b.md")

    def test_unknown_type_is_refused(self):
        self.assert_refused(ValueError, "Task", "T")

    # Cases 15 and 16: something already at the output path.

    def test_existing_file_is_refused_and_unchanged(self):
        self.write("field-notes/alice/NOTE-taken.md", "mine\n")
        stat_before = os.stat(str(self.home / "field-notes/alice/NOTE-taken.md"))
        message = self.assert_refused(compile.RootError, "Note", "Taken")
        self.assertIn("field-notes/alice/NOTE-taken.md", message)
        self.assertIn("choose a different title", message)
        stat_after = os.stat(str(self.home / "field-notes/alice/NOTE-taken.md"))
        self.assertEqual((stat_after.st_mtime_ns, stat_after.st_size),
                         (stat_before.st_mtime_ns, stat_before.st_size))

    def test_output_link_inside_the_root_is_refused(self):
        self.write("shared/target.md", "target\n")
        self.link("field-notes/alice/NOTE-x.md", self.home / "shared/target.md")
        self.assert_refused(compile.RootError, "Note", "x")

    def test_output_link_outside_is_refused(self):
        self.link("field-notes/alice/NOTE-x.md", self.outside / "secret.md")
        self.assert_refused(compile.RootError, "Note", "x")

    def test_output_broken_link_is_refused(self):
        self.link("field-notes/alice/NOTE-x.md", self.home / "missing.md")
        self.assert_refused(compile.RootError, "Note", "x")

    def test_output_folder_is_refused(self):
        (self.home / "field-notes/alice/NOTE-x.md").mkdir(parents=True)
        self.assert_refused(compile.RootError, "Note", "x")

    def test_output_hard_link_is_refused(self):
        self.write("shared/target.md", "target\n")
        (self.home / "field-notes/alice").mkdir(parents=True)
        os.link(str(self.home / "shared/target.md"), str(self.home / "field-notes/alice/NOTE-x.md"))
        self.assert_refused(compile.RootError, "Note", "x")

    # Cases 17 and 18: the folders on the way.

    def test_destination_folders_linked_inside_are_used(self):
        (self.home / "shared/f").mkdir(parents=True)
        (self.home / "shared/notes").mkdir(parents=True)
        self.link("findings", self.home / "shared/f")
        self.link("field-notes", self.home / "shared/notes")
        self.assertEqual(self.create("Finding", "Linked", nnn="001")[0], "findings/F-001-linked.md")
        self.assertTrue((self.home / "shared/f/F-001-linked.md").is_file())
        self.assertEqual(self.create("Note", "Linked")[0], "field-notes/alice/NOTE-linked.md")
        self.assertTrue((self.home / "shared/notes/alice/NOTE-linked.md").is_file())

    def test_own_folder_linked_inside_is_used(self):
        (self.home / "shared/alice").mkdir(parents=True)
        self.link("field-notes/alice", self.home / "shared/alice")
        self.create("Note", "Linked")
        self.assertTrue((self.home / "shared/alice/NOTE-linked.md").is_file())

    def test_findings_linked_outside_is_refused(self):
        self.link("findings", self.outside)
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001")
        self.assertIn("findings/F-001-t.md", message)

    def test_field_notes_linked_outside_is_refused(self):
        self.link("field-notes", self.outside)
        self.assert_refused(compile.RootError, "Note", "T")

    def test_own_folder_linked_outside_is_refused(self):
        self.link("field-notes/alice", self.outside)
        self.assert_refused(compile.RootError, "Note", "T")

    def test_own_folder_linked_into_incoming_is_refused(self):
        (self.home / "incoming/bob/field-notes/bob").mkdir(parents=True)
        self.link("field-notes/alice", self.home / "incoming/bob/field-notes/bob")
        message = self.assert_refused(compile.RootError, "Note", "T")
        self.assertIn("incoming/ is read-only", message)

    def test_own_folder_linked_into_the_log_folder_is_refused(self):
        logs = self.home / "logs"
        logs.mkdir()
        self.logs = logs
        self.link("field-notes/alice", logs)
        message = self.assert_refused(compile.RootError, "Note", "T")
        self.assertIn("the log folder is read-only", message)

    def test_file_in_the_way_of_field_notes(self):
        self.write("field-notes", "a file\n")
        message = self.assert_refused(compile.RootError, "Note", "T")
        self.assertIn("field-notes", message)

    def test_file_in_the_way_of_the_own_folder(self):
        self.write("field-notes/alice", "a file\n")
        message = self.assert_refused(compile.RootError, "Note", "T")
        self.assertIn("field-notes/alice", message)

    def test_broken_link_in_the_way_of_findings(self):
        self.link("findings", self.home / "missing-folder")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001")
        self.assertIn("findings", message)

    # Cases 19 and 20: the template.

    def test_templates_folder_linked_inside_is_used(self):
        (self.home / "templates").rename(self.home / "shared-templates")
        self.link("templates", self.home / "shared-templates")
        self.create("Incident report", "T", nnn="001")
        self.assertTrue(self.text("field-notes/alice/IR-001-t.md").startswith("# Incident Report IR-001"))

    def test_template_file_linked_inside_is_used(self):
        (self.home / "templates/finding.md").rename(self.home / "real-finding.md")
        self.link("templates/finding.md", self.home / "real-finding.md")
        self.create("Finding", "T", nnn="001")
        self.assertTrue(self.text("findings/F-001-t.md").startswith("### F-001: T\n"))

    def test_templates_folder_linked_outside_is_refused(self):
        (self.home / "templates").rename(self.home / "old-templates")
        self.link("templates", self.outside / "templates")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001")
        self.assertIn("templates/finding.md", message)

    def test_template_file_linked_outside_is_refused(self):
        (self.home / "templates/finding.md").unlink()
        self.link("templates/finding.md", self.outside / "templates/finding.md")
        message = self.assert_refused(compile.RootError, "Finding", "T", nnn="001")
        self.assertIn("templates/finding.md", message)

    def test_missing_template_is_refused(self):
        (self.home / "templates/status-update.md").unlink()
        message = self.assert_refused(compile.InputError, "Status update", "T")
        self.assertIn("templates/status-update.md", message)

    def test_template_that_is_a_folder_is_refused(self):
        (self.home / "templates/status-update.md").unlink()
        (self.home / "templates/status-update.md").mkdir()
        message = self.assert_refused(compile.InputError, "Status update", "T")
        self.assertIn("templates/status-update.md", message)

    def test_template_not_utf8_is_refused(self):
        (self.home / "templates/status-update.md").write_bytes("# Café\n".encode("cp1252"))
        message = self.assert_refused(compile.InputError, "Status update", "T")
        self.assertIn("status-update.md is not UTF-8 text", message)

    def test_unreadable_template_is_refused(self):
        path = self.home / "templates/status-update.md"
        path.chmod(0)
        self.addCleanup(path.chmod, 0o644)
        if os.access(str(path), os.R_OK):
            self.skipTest("running as a user who can read any file")
        # Checked by hand: tree() can't read this file either.
        with self.assertRaises(OSError) as caught:
            self.create("Status update", "T")
        self.assertIn("templates/status-update.md", str(caught.exception))
        self.assertFalse((self.home / "field-notes").exists())

    def test_crlf_template_keeps_its_line_endings(self):
        (self.home / "templates/incident-report.md").write_bytes(
            b"# Incident Report [[IR_ID]]\r\n\r\n- caf\xc3\xa9 [[HOST]]\r\n")
        self.create("Incident report", "T", nnn="001")
        self.assertEqual((self.home / "field-notes/alice/IR-001-t.md").read_bytes(),
                         b"# Incident Report IR-001\r\n\r\n- caf\xc3\xa9 [[HOST]]\r\n")

    def test_bom_is_dropped(self):
        (self.home / "templates/status-update.md").write_bytes(b"\xef\xbb\xbf# Status\n")
        self.create("Status update", "T")
        self.assertEqual((self.home / "field-notes/alice/SU-t.md").read_bytes(), b"# Status\n")

    # Case 21: duplicate IDs warn but don't block.

    def test_duplicate_finding_id_warns_and_still_creates(self):
        self.write("findings/F-007-old.md", "x\n")
        self.write("incoming/zed/findings/F-007-z.md", "x\n")
        self.write("incoming/bob/findings/F-007-b.md", "x\n")
        self.link("incoming/eve", self.outside)
        result = self.create("Finding", "New", nnn="007")
        self.assertEqual(result[0], "findings/F-007-new.md")
        self.assertEqual(result[1], [
            "F-007 already exists: findings/F-007-old.md",
            "F-007 already exists: incoming/bob/findings/F-007-b.md",
            "F-007 already exists: incoming/zed/findings/F-007-z.md"])
        self.assertEqual(len(result[2]), 1)
        self.assertTrue(result[2][0].startswith("path is outside the root: incoming/eve -> "))
        self.assertTrue((self.home / "findings/F-007-new.md").is_file())

    def test_other_types_get_no_warnings(self):
        self.write("findings/F-007-old.md", "x\n")
        self.assertEqual(self.create("Incident report", "T", nnn="007")[1:], ([], []))

    # DECISIONS 2026-10-29 Chunk N3 D1 and D2 at create time.

    def test_finding_is_created_with_incoming_linked_outside(self):
        self.link("incoming", self.outside)
        result = self.create("Finding", "Linked incoming", nnn="007")
        self.assertEqual(result[0], "findings/F-007-linked-incoming.md")
        self.assertEqual(result[1], [])
        self.assertEqual(len(result[2]), 1)
        self.assertTrue(result[2][0].startswith("path is outside the root: incoming -> "))
        self.assertTrue((self.home / result[0]).is_file())

    def test_duplicate_ir_number_warns_and_still_creates(self):
        self.write("field-notes/alice/IR-007-old.md", "x\n")
        self.write("incoming/bob/field-notes/bob/IR-007-b.md", "x\n")
        self.link("incoming/eve", self.outside)
        result = self.create("Incident report", "New", nnn="007")
        self.assertEqual(result[0], "field-notes/alice/IR-007-new.md")
        self.assertEqual(result[1], [
            "IR-007 already exists: field-notes/alice/IR-007-old.md",
            "IR-007 already exists: incoming/bob/field-notes/bob/IR-007-b.md"])
        self.assertEqual(len(result[2]), 1)
        self.assertTrue(result[2][0].startswith("path is outside the root: incoming/eve -> "))
        self.assertTrue((self.home / result[0]).is_file())

    def test_ir_warning_uses_the_typed_number_not_the_suggestion(self):
        self.write("field-notes/alice/IR-004-old.md", "x\n")
        self.assertEqual(notebook.suggest_ir_number(self.home)[0], "005")
        self.assertEqual(self.create("Incident report", "Reuse", nnn="004")[1],
                         ["IR-004 already exists: field-notes/alice/IR-004-old.md"])
        self.assertEqual(self.create("Incident report", "Next", nnn="005")[1:], ([], []))

    # DECISIONS 2026-10-29 Chunk N3 D5: a title is one line.

    def test_title_with_a_line_break_is_refused(self):
        types = [("Note", None), ("Incident report", "001"), ("Status update", None),
                 ("Inject response", None), ("Finding", "001")]
        titles = ["\nStart", "Mid\ndle", "End\n", "\rStart", "Mid\rdle", "End\r",
                  "\r\nStart", "Mid\r\ndle", "End\r\n",
                  "Legit\n- **Severity:** Critical", "Legit\r- **Severity:** Critical"]
        for type_name, nnn in types:
            for title in titles:
                with self.subTest(type_name=type_name, title=title):
                    message = self.assert_refused(ValueError, type_name, title, nnn=nnn)
                    self.assertEqual(message, "the title must be one line, with no line breaks")

    def test_line_break_is_refused_before_anything_is_read(self):
        self.write("findings-library/smb.md", LIBRARY_ENTRY)
        stop = AssertionError("ran before the title check")
        with mock.patch.object(notebook, "read_template", side_effect=stop), \
                mock.patch.object(notebook, "read_library_entry", side_effect=stop), \
                mock.patch.object(notebook, "finding_id_warnings", side_effect=stop), \
                mock.patch.object(notebook, "ir_number_warnings", side_effect=stop), \
                mock.patch.object(notebook, "check_new_file_path", side_effect=stop):
            self.assert_refused(ValueError, "Finding", "a\nb", nnn="001",
                                library="findings-library/smb.md")
            self.assert_refused(ValueError, "Incident report", "a\rb", nnn="001")

    def test_other_titles_are_not_refused_by_the_line_rule(self):
        for title, path in [("Back\\nslash", "field-notes/alice/NOTE-back-nslash.md"),
                            ("Tab\there", "field-notes/alice/NOTE-tab-here.md"),
                            ("  spaced  out  ", "field-notes/alice/NOTE-spaced-out.md")]:
            with self.subTest(title=title):
                self.assertEqual(self.create("Note", title)[0], path)

    # Case 23: checked before anything changes.

    def test_refusals_come_before_the_first_folder(self):
        # assert_refused patches mkdir to fail, so each of these is caught
        # before any folder is made; a fresh root has no field-notes/ yet.
        self.assertFalse((self.home / "field-notes").exists())
        self.assert_refused(ValueError, "Task", "T")
        self.assert_refused(ValueError, "Note", "!!!")
        self.assert_refused(ValueError, "Finding", "T", nnn="7")
        self.assert_refused(compile.RootError, "Finding", "T", nnn="001",
                            library="findings-library/missing.md")
        (self.home / "templates/finding.md").unlink()
        self.assert_refused(compile.InputError, "Finding", "T", nnn="001")
        self.assertFalse((self.home / "field-notes").exists())
        self.assertFalse((self.home / "findings").exists())

    # Case 24: the exclusive create.

    def test_file_that_appears_after_the_checks_is_never_overwritten(self):
        self.write("field-notes/alice/NOTE-race.md", "someone else's\n")
        real_lexists = os.path.lexists

        def lexists_misses_the_new_file(path):
            # Pretend the file wasn't there when checked, as if it appeared
            # between the check and the open.
            if str(path).endswith("NOTE-race.md"):
                return False
            return real_lexists(path)

        with mock.patch.object(notebook.os.path, "lexists", lexists_misses_the_new_file):
            with self.assertRaises(compile.RootError) as caught:
                self.create("Note", "Race")
        self.assertIn("field-notes/alice/NOTE-race.md", str(caught.exception))
        self.assertEqual(self.text("field-notes/alice/NOTE-race.md"), "someone else's\n")

    def test_a_failed_write_leaves_no_half_file(self):
        with mock.patch.object(notebook, "fill_new_file_markers", return_value=object()):
            with self.assertRaises(TypeError):
                self.create("Status update", "Half")
        self.assertFalse((self.home / "field-notes/alice/SU-half.md").exists())


class NewFileRouteTests(ServerTestCase):
    """N3-05: GET /new-data and POST /new-file, the New form's two routes."""

    FIELDS = {"type": "Note", "title": "T", "nnn": None, "library": None}

    def setUp(self):
        super().setUp()
        # A fresh root with only the fake templates, so nothing else is there.
        self.home = support.make_worktree(self, FAKE_TEMPLATES)
        self.server.settings["root"] = self.home.resolve()
        self.outside = support.make_worktree(self, {"secret.md": "outside\n",
                                                    "eve/IR-500-x.md": "x\n"})

    def write(self, path, text="x\n"):
        support.write_fake_file(self.home, path, text)

    def link(self, path, target):
        (self.home / path).parent.mkdir(parents=True, exist_ok=True)
        (self.home / path).symlink_to(target)

    def new_data(self, status=200):
        before = tree(self.home)
        response, body = self.send_full("GET", "/new-data", self.good_host())
        self.assertEqual(response.status, status, body)
        self.assert_safe_headers(response)
        self.assertEqual(tree(self.home), before)
        if status == 200:
            self.assertEqual(response.getheader("Content-Type"), "application/json")
            return json.loads(body)
        self.assertEqual(response.getheader("Content-Type"), "text/plain; charset=utf-8")
        return body

    def post(self, body, token="default", host=None, length=None):
        """POST raw body bytes to /new-file; return (status, text, content type).

        token: a value, a list (sent more than once), None (not sent) or
        "default" (this run's). length: the Content-Length to send, or None
        for the body's real length, or False to send none.
        """
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(connection.close)
        connection.putrequest("POST", "/new-file", skip_host=True)
        connection.putheader("Host", host or self.good_host())
        tokens = [self.server.token] if token == "default" else token
        for value in tokens if isinstance(tokens, list) else ([] if tokens is None else [tokens]):
            connection.putheader("X-CPTC-Token", value)
        connection.putheader("Content-Type", "application/json")
        if length is not False:
            connection.putheader("Content-Length", str(len(body)) if length is None else length)
        connection.endheaders(body)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        self.assert_safe_headers(response)
        return response.status, text, response.getheader("Content-Type")

    def create(self, **fields):
        body = dict(self.FIELDS)
        body.update(fields)
        return self.post(json.dumps(body).encode("utf-8"))

    def assert_not_created(self, status_wanted, text_start, *post_args, **post_options):
        """The POST is refused with this status and text, and nothing changes."""
        before = (tree(self.home), tree(self.outside))
        status, text, content_type = self.post(*post_args, **post_options)
        self.assertEqual(status, status_wanted, text)
        self.assertEqual(content_type, "text/plain; charset=utf-8")
        self.assertTrue(text.startswith(text_start), text)
        self.assertEqual((tree(self.home), tree(self.outside)), before)
        return text

    def body(self, **fields):
        body = dict(self.FIELDS)
        body.update(fields)
        return json.dumps(body).encode("utf-8")

    # Cases 1-3 and 12: the New form's data.

    def test_new_data_lists_types_library_and_suggestion(self):
        self.write("findings-library/b-smb.md", "### [[FINDING_ID]]: SMB <script>x</script>\n")
        self.write("findings-library/a-creds.md", "### [[FINDING_ID]]: Default creds\n")
        self.write("findings-library/bad.md", "## [[FINDING_ID]]: Wrong level\n")
        self.write("findings-library/README.md", "# Library\n")
        self.write("field-notes/alice/IR-004-a.md")
        self.link("incoming/eve", self.outside)
        data = self.new_data()
        self.assertEqual(data["types"], [
            {"name": "Note", "needs_nnn": False, "library": False},
            {"name": "Incident report", "needs_nnn": True, "library": False},
            {"name": "Status update", "needs_nnn": False, "library": False},
            {"name": "Inject response", "needs_nnn": False, "library": False},
            {"name": "Finding", "needs_nnn": True, "library": True}])
        self.assertEqual(data["library"], [
            {"path": "findings-library/a-creds.md", "title": "Default creds"},
            {"path": "findings-library/b-smb.md", "title": "SMB <script>x</script>"}])
        self.assertEqual(data["library_refused"], [
            "findings-library/bad.md: first heading doesn't start with "
            "'### [[FINDING_ID]]: ': '## [[FINDING_ID]]: Wrong level'"])
        self.assertEqual(data["ir_suggestion"], "005")
        self.assertEqual(data["ir_note"], "")
        self.assertEqual(len(data["ir_refused"]), 1)
        self.assertTrue(data["ir_refused"][0].startswith("path is outside the root: incoming/eve -> "))
        self.assertEqual(sorted(data), ["ir_note", "ir_refused", "ir_suggestion", "library",
                                        "library_refused", "types"])

    def test_new_data_on_an_empty_root(self):
        empty = support.make_worktree(self)
        self.server.settings["root"] = empty.resolve()
        response, body = self.send_full("GET", "/new-data", self.good_host())
        self.assertEqual(response.status, 200, body)
        data = json.loads(body)
        self.assertEqual([kind["name"] for kind in data["types"]], list(notebook.NEW_FILE_TYPES))
        self.assertEqual((data["library"], data["library_refused"], data["ir_suggestion"],
                          data["ir_note"], data["ir_refused"]), ([], [], "001", "", []))
        self.assertEqual(list(empty.iterdir()), [])

    # DECISIONS 2026-10-29 Chunk N3 D1: a top-level link outside is reported
    # in its refused list, and the New form still opens.

    def test_new_data_library_folder_linked_outside_still_opens(self):
        self.link("findings-library", self.outside)
        data = self.new_data()
        self.assertEqual(len(data["types"]), 5)
        self.assertEqual(data["library"], [])
        self.assertEqual(len(data["library_refused"]), 1)
        self.assertTrue(data["library_refused"][0].startswith(
            "path is outside the root: findings-library -> "))
        self.assertNotIn("secret.md", data["library_refused"][0])
        self.assertEqual((data["ir_suggestion"], data["ir_refused"]), ("001", []))

    def test_new_data_field_notes_linked_outside_still_opens(self):
        self.link("field-notes", self.outside)
        self.write("incoming/bob/field-notes/bob/IR-004-b.md")
        # A refused IR scan doesn't touch the library list.
        self.write("findings-library/good.md", "### [[FINDING_ID]]: Good\n")
        data = self.new_data()
        self.assertEqual((data["library"], data["library_refused"]),
                         ([{"path": "findings-library/good.md", "title": "Good"}], []))
        self.assertEqual(data["ir_suggestion"], "005")
        self.assertEqual(len(data["ir_refused"]), 1)
        self.assertTrue(data["ir_refused"][0].startswith("path is outside the root: field-notes -> "))

    def test_new_data_incoming_linked_outside_still_opens(self):
        self.link("incoming", self.outside)
        self.write("field-notes/alice/IR-002-a.md")
        data = self.new_data()
        self.assertEqual(data["ir_suggestion"], "003")
        self.assertEqual(len(data["ir_refused"]), 1)
        self.assertTrue(data["ir_refused"][0].startswith("path is outside the root: incoming -> "))

    def test_new_data_all_three_linked_outside_still_opens(self):
        outside2 = support.make_worktree(self)
        outside3 = support.make_worktree(self)
        self.link("findings-library", self.outside)
        self.link("field-notes", outside2)
        self.link("incoming", outside3)
        data = self.new_data()
        self.assertEqual([kind["name"] for kind in data["types"]], list(notebook.NEW_FILE_TYPES))
        self.assertEqual((data["library"], data["ir_suggestion"], data["ir_note"]), ([], "001", ""))
        self.assertEqual(len(data["library_refused"]), 1)
        self.assertTrue(data["library_refused"][0].startswith(
            "path is outside the root: findings-library -> "))
        self.assertEqual(len(data["ir_refused"]), 2)
        self.assertTrue(data["ir_refused"][0].startswith("path is outside the root: field-notes -> "))
        self.assertTrue(data["ir_refused"][1].startswith("path is outside the root: incoming -> "))

    def test_new_data_bad_entry_doesnt_hide_good_ones(self):
        self.write("findings-library/good.md", "### [[FINDING_ID]]: Good\n")
        self.link("findings-library/linked.md", self.outside / "secret.md")
        data = self.new_data()
        self.assertEqual(data["library"], [{"path": "findings-library/good.md", "title": "Good"}])
        self.assertEqual(len(data["library_refused"]), 1)
        self.assertTrue(data["library_refused"][0].startswith(
            "path is outside the root: findings-library/linked.md -> "))

    def test_no_ir_number_left(self):
        self.write("incoming/bob/field-notes/bob/IR-999-z.md")
        data = self.new_data()
        self.assertEqual((data["ir_suggestion"], data["ir_note"]), (None, notebook.NO_IR_NUMBER_LEFT))
        status, text, _ = self.create(type="Incident report", title="Typed", nnn="500")
        self.assertEqual(status, 200, text)
        self.assertEqual(json.loads(text)["path"], "field-notes/alice/IR-500-typed.md")

    def test_library_title_marker_is_returned_as_written(self):
        # N3 stop flag (case 27): an entry copied straight from the template
        # gives the literal title "[[FINDING_TITLE]]", which the page puts in
        # the title box as it is. The user decides at the N3 stop.
        self.write("findings-library/raw.md", "### [[FINDING_ID]]: [[FINDING_TITLE]]\n")
        self.assertEqual(self.new_data()["library"],
                         [{"path": "findings-library/raw.md", "title": "[[FINDING_TITLE]]"}])

    # Cases 4, 5, 10 and 11: creating.

    def test_each_type_is_created(self):
        for fields, path in [
                ({"type": "Note", "title": "Quick Note"}, "field-notes/alice/NOTE-quick-note.md"),
                ({"type": "Incident report", "title": "DB down", "nnn": "007"},
                 "field-notes/alice/IR-007-db-down.md"),
                ({"type": "Status update", "title": "Noon"}, "field-notes/alice/SU-noon.md"),
                ({"type": "Inject response", "title": "Inject 1"}, "field-notes/alice/INJ-inject-1.md"),
                ({"type": "Finding", "title": "Weak creds", "nnn": "042"}, "findings/F-042-weak-creds.md")]:
            with self.subTest(path=path):
                status, text, content_type = self.create(**fields)
                self.assertEqual(status, 200, text)
                self.assertEqual(content_type, "application/json")
                self.assertEqual(json.loads(text), {"path": path, "warnings": [], "refused": []})
                self.assertTrue((self.home / path).is_file())
        self.assertEqual((self.home / "field-notes/alice/IR-007-db-down.md").read_text(encoding="utf-8"),
                         FAKE_TEMPLATES["templates/incident-report.md"].replace("[[IR_ID]]\n", "IR-007\n"))
        self.assertTrue((self.home / "findings/F-042-weak-creds.md").read_text(encoding="utf-8")
                        .startswith("### F-042: Weak creds\n"))

    def test_library_finding_is_created(self):
        self.write("findings-library/smb.md", LIBRARY_ENTRY)
        status, text, _ = self.create(type="Finding", title="SMB signing off", nnn="010",
                                      library="findings-library/smb.md")
        self.assertEqual(status, 200, text)
        path = json.loads(text)["path"]
        self.assertEqual(path, "findings/F-010-smb-signing-off.md")
        self.assertTrue((self.home / path).read_text(encoding="utf-8")
                        .startswith("### F-010: SMB signing off\n"))

    def test_fields_go_to_create_new_file_as_sent(self):
        real = notebook.create_new_file
        with mock.patch.object(notebook, "create_new_file", wraps=real) as wrapped:
            self.create(type="Note", title="A")
            self.create(type="Incident report", title="B", nnn="003")
            self.create(type="Finding", title="C", nnn="004")
            self.write("findings-library/smb.md", LIBRARY_ENTRY)
            self.create(type="Finding", title="D", nnn="005", library="findings-library/smb.md")
        root, logdir = self.home.resolve(), self.logdir.resolve()
        self.assertEqual(wrapped.call_args_list, [
            mock.call(root, logdir, "alice", "Note", "A", nnn=None, library=None),
            mock.call(root, logdir, "alice", "Incident report", "B", nnn="003", library=None),
            mock.call(root, logdir, "alice", "Finding", "C", nnn="004", library=None),
            mock.call(root, logdir, "alice", "Finding", "D", nnn="005",
                      library="findings-library/smb.md")])

    def test_duplicate_finding_warnings_come_back(self):
        self.write("findings/F-007-old.md")
        self.write("incoming/zed/findings/F-007-z.md")
        self.write("incoming/bob/findings/F-007-b.md")
        self.link("incoming/eve", self.outside)
        status, text, _ = self.create(type="Finding", title="New", nnn="007")
        self.assertEqual(status, 200, text)
        data = json.loads(text)
        self.assertEqual(data["path"], "findings/F-007-new.md")
        self.assertEqual(data["warnings"], [
            "F-007 already exists: findings/F-007-old.md",
            "F-007 already exists: incoming/bob/findings/F-007-b.md",
            "F-007 already exists: incoming/zed/findings/F-007-z.md"])
        self.assertEqual(len(data["refused"]), 1)
        self.assertTrue(data["refused"][0].startswith("path is outside the root: incoming/eve -> "))

    def test_duplicate_ir_number_warns_and_is_created(self):
        # DECISIONS 2026-10-29 Chunk N3 D2: a typed IR number already in use
        # warns, like F-NNN; the file is still created.
        self.write("incoming/bob/field-notes/bob/IR-003-b.md")
        self.write("field-notes/alice/IR-003-a.md")
        self.link("incoming/eve", self.outside)
        status, text, _ = self.create(type="Incident report", title="Mine", nnn="003")
        self.assertEqual(status, 200, text)
        data = json.loads(text)
        self.assertEqual(data["path"], "field-notes/alice/IR-003-mine.md")
        self.assertEqual(data["warnings"], [
            "IR-003 already exists: field-notes/alice/IR-003-a.md",
            "IR-003 already exists: incoming/bob/field-notes/bob/IR-003-b.md"])
        self.assertEqual(len(data["refused"]), 1)
        self.assertTrue(data["refused"][0].startswith("path is outside the root: incoming/eve -> "))

    def test_finding_create_with_incoming_linked_outside(self):
        self.link("incoming", self.outside)
        status, text, _ = self.create(type="Finding", title="Still made", nnn="007")
        self.assertEqual(status, 200, text)
        data = json.loads(text)
        self.assertEqual((data["path"], data["warnings"]), ("findings/F-007-still-made.md", []))
        self.assertEqual(len(data["refused"]), 1)
        self.assertTrue(data["refused"][0].startswith("path is outside the root: incoming -> "))

    def test_title_with_a_line_break_is_refused(self):
        # DECISIONS 2026-10-29 Chunk N3 D5: a hand-made, token-carrying POST
        # can't add a second "- **Severity:**" line through the title.
        for title in ["Legit\n- **Severity:** Critical", "Legit\r- **Severity:** Critical",
                      "Legit\r\n- **Severity:** Critical"]:
            with self.subTest(title=title):
                text = self.assert_not_created(
                    400, "not created: the title must be one line, with no line breaks",
                    self.body(type="Finding", title=title, nnn="001"))
                self.assertNotIn("Severity", text)
                self.assertNotIn("Legit", text)

    # Cases 6-9: refused requests.

    def test_bad_fields_are_refused(self):
        bodies = [
            json.dumps({"type": "Note", "title": "T", "nnn": None}),
            json.dumps(dict(self.FIELDS, extra=1)),
            json.dumps(dict(self.FIELDS, filename="x.md")),
            json.dumps(dict(self.FIELDS, path="findings/x.md")),
            json.dumps(["Note", "T"]), json.dumps("Note"), json.dumps(None),
            json.dumps(dict(self.FIELDS, type=1)),
            json.dumps(dict(self.FIELDS, title=["T"])),
            json.dumps(dict(self.FIELDS, nnn=7)),
            json.dumps(dict(self.FIELDS, library={"path": "x"})),
        ]
        with mock.patch.object(notebook, "create_new_file", side_effect=AssertionError("called")):
            for body in bodies:
                with self.subTest(body=body):
                    self.assert_not_created(400, 'send {"type": ', body.encode("utf-8"))

    def test_bad_values_are_refused_by_the_create_step(self):
        for fields, text_start in [
                ({"type": "Task"}, "not created: unknown file type: 'Task'"),
                ({"title": "!!!"}, "not created: no letters or digits"),
                ({"type": "Finding", "nnn": "7"}, "not created: the number must be exactly three digits"),
                ({"type": "Finding", "nnn": None}, "not created: the number must be exactly three digits"),
                ({"nnn": "007"}, "not created: Note has no number"),
                ({"library": "findings-library/x.md"}, "not created: only a Finding can start")]:
            with self.subTest(fields=fields):
                self.assert_not_created(400, text_start, self.body(**fields))

    def test_bad_bodies_are_refused(self):
        too_big = str(notebook.MAX_NEW_FILE_BYTES + 1)
        cases = [(b"", False), (b"{}", "abc"), (b"{}", "-1"), (b"{}", too_big), (b"{}", "1e3"),
                 (b"", None), (b"\xff\xfe", None), (b"{not json", None),
                 (b"x" * (notebook.MAX_NEW_FILE_BYTES + 1), None)]
        with mock.patch.object(notebook, "create_new_file", side_effect=AssertionError("called")):
            for body, length in cases:
                with self.subTest(body=body[:20], length=length):
                    self.assert_not_created(400, "send one new file as JSON", body, length=length)

    def test_a_short_body_doesnt_hang_the_server(self):
        # Content-Length says 50, but only 2 bytes come: the read gives up
        # after the handler's timeout, and the server goes on answering.
        # The real timeout is set (the stdlib default, None, waits forever);
        # the test shortens it so it runs quickly.
        self.assertEqual(notebook.NotebookHandler.timeout, 10)
        with mock.patch.object(notebook.NotebookHandler, "timeout", 0.5), \
                mock.patch.object(notebook, "create_new_file", side_effect=AssertionError("called")):
            self.assert_not_created(400, "send one new file as JSON", b"{}", length="50")
        status, _ = self.send("GET", "/files", self.good_host())
        self.assertEqual(status, 200)

    def test_guard_refuses_before_anything(self):
        other_run = notebook.make_token()
        with mock.patch.object(notebook, "create_new_file", side_effect=AssertionError("called")):
            for options in [{"host": "evil.example:" + str(self.port)}, {"token": None},
                            {"token": "wrong"}, {"token": [self.server.token] * 2},
                            {"token": other_run}]:
                with self.subTest(options=options):
                    self.assert_not_created(403, "refused: use http://127.0.0.1:", self.body(),
                                            **options)

    def test_token_from_the_served_page_works(self):
        _, page = self.send_full("GET", "/", self.good_host())
        parts = PageParts()
        parts.feed(page)
        status, text, _ = self.post(self.body(title="From page"), token=parts.tokens[0])
        self.assertEqual(status, 200, text)

    def test_errors_keep_their_reason(self):
        self.write("field-notes/alice/NOTE-taken.md", "mine\n")
        self.assert_not_created(403, "refused: already exists, choose a different title: "
                                "field-notes/alice/NOTE-taken.md", self.body(title="Taken"))
        (self.home / "templates/status-update.md").write_bytes("# Café\n".encode("cp1252"))
        text = self.assert_not_created(500, "not created: ", self.body(type="Status update"))
        self.assertIn("status-update.md is not UTF-8 text", text)
        with mock.patch.object(notebook, "create_new_file",
                               side_effect=PermissionError(13, "Permission denied", "templates/x.md")):
            text = self.assert_not_created(500, "not created: ", self.body())
        self.assertIn("Permission denied: 'templates/x.md'", text)

    # Cases 13 and 14: routes and GETs.

    def test_routes_are_in_the_tables(self):
        self.assertIs(notebook.GET_ROUTES["/new-data"], notebook.send_new_data)
        self.assertIs(notebook.POST_ROUTES["/new-file"], notebook.save_new_file)

    def test_gets_change_nothing(self):
        self.write("findings-library/a.md", "### [[FINDING_ID]]: A\n")
        before = tree(self.home)
        for path in ["/", "/files", "/new-data"]:
            with self.subTest(path=path):
                status, _ = self.send("GET", path, self.good_host())
                self.assertEqual(status, 200)
                self.assertEqual(tree(self.home), before)


class PageParts(HTMLParser):
    """Collects what a test needs from the app page: tags inside <nav> and
    <main>, the text a person would see, and the token in its <meta> tag."""

    def __init__(self):
        super().__init__()
        self.open = []
        self.inside = {"nav": [], "main": []}
        self.visible_text = []
        self.tokens = []

    def handle_starttag(self, tag, attrs):
        if tag == "meta" and dict(attrs).get("name") == "cptc-token":
            self.tokens.append(dict(attrs).get("content"))
        for column in self.inside:
            if column in self.open:
                self.inside[column].append((tag, dict(attrs).get("id")))
        self.open.append(tag)

    def handle_endtag(self, tag):
        if tag in self.open:
            del self.open[len(self.open) - 1 - self.open[::-1].index(tag)]

    def handle_data(self, data):
        hidden = {"title", "style", "script"}
        if data.strip() and not hidden.intersection(self.open):
            self.visible_text.append(data.strip())


class AppShellTests(ServerTestCase):
    def get_page(self):
        response, page = self.send_full("GET", "/", self.good_host())
        self.assertEqual(response.status, 200)
        parts = PageParts()
        parts.feed(page)
        return page, parts

    def test_nav_has_the_file_list_new_and_checklists(self):
        page, parts = self.get_page()
        self.assertEqual(parts.inside["nav"], [("button", "theme-toggle"),
                                               ("div", "file-list"),
                                               ("button", "new-button"),
                                               ("button", "checklists-button")])
        self.assertEqual(parts.inside["main"], [])
        # No Logs/Export/Compile controls yet: the only words on the page
        # are the three buttons'.
        self.assertEqual(parts.visible_text, ["Light / dark", "New", "Checklists"])
        # The file list loads when the page opens.
        self.assertIn("\nloadFiles();\n</script>", page)

    def test_page_carries_this_runs_token_once(self):
        page, parts = self.get_page()
        self.assertEqual(parts.tokens, [self.server.token])
        self.assertNotIn(notebook.TOKEN_SLOT, page)

    def test_token_is_escaped_in_the_page(self):
        # A real token never has these characters; this proves escape() runs.
        self.server.token = 'x"><script>alert(1)</script>'
        page, parts = self.get_page()
        self.assertEqual(parts.tokens, [self.server.token])
        self.assertNotIn('x"><script>', page)

    def test_script_builds_text_safely_and_posts_the_token(self):
        page, _ = self.get_page()
        self.assertNotIn("innerHTML", page)
        self.assertNotIn("outerHTML", page)
        self.assertNotIn("insertAdjacentHTML", page)
        self.assertNotIn("document.write", page)
        # Both POSTs (a tick and a new file) send the token.
        self.assertEqual(page.count('"X-CPTC-Token": TOKEN'), 2)
        self.assertEqual(page.count("fetch("), 5)
        self.assertIn('fetch("/new-file", {\n      method: "POST",', page)
        self.assertIn('box.type = "checkbox";', page)
        self.assertIn("made.textContent = text;", page)
        # A box is locked while its save is pending and, if the save fails,
        # goes back to its value from before the click (not just flipped).
        self.assertIn("box.disabled = true;", page)
        self.assertIn("box.checked = !wanted;", page)

    def test_new_form_sends_only_type_title_number_and_library(self):
        page, _ = self.get_page()
        # The request is built from these four fields and nothing else: no
        # file name or path field, and a number or library entry only when
        # the type uses one.
        self.assertIn("var request = {\n"
                      "      type: kind.name,\n"
                      "      title: title.value,\n"
                      "      nnn: kind.needs_nnn ? nnn.value : null,\n"
                      "      library: kind.library && library.value ? library.value : null\n"
                      "    };", page)
        self.assertIn("body: JSON.stringify(request)", page)
        # A one-line title box; there is no textarea on the page yet.
        self.assertIn('title.type = "text";', page)
        self.assertNotIn("textarea", page)
        # Hidden fields follow the type the server describes.
        self.assertIn("nnnRow.hidden = !kind.needs_nnn;", page)
        self.assertIn("libraryRow.hidden = !kind.library;", page)

    def test_refused_reasons_and_the_new_file_are_shown(self):
        page, _ = self.get_page()
        for line in ["data.refused.forEach(function (reason) {",
                     "data.library_refused.forEach(function (reason) {",
                     "data.ir_refused.forEach(function (reason) {",
                     "result.warnings.forEach(function (warning) {",
                     "result.refused.forEach(function (reason) {",
                     "loadFiles(result.path);"]:
            with self.subTest(line=line):
                self.assertIn(line, page)
        # After a create the IR suggestion is fetched again, so two incident
        # reports in a row don't both get the same number (Chunk N3 CR-1).
        self.assertIn("loadFiles(result.path);\n        refreshSuggestion();", page)
        self.assertIn('function refreshSuggestion() {\n    fetch("/new-data")', page)

    def test_follows_system_dark_mode_and_has_a_toggle(self):
        page, _ = self.get_page()
        self.assertIn("@media (prefers-color-scheme: dark)", page)
        self.assertIn(':root[data-theme="dark"]', page)
        self.assertIn(':root[data-theme="light"]', page)
        self.assertIn('getElementById("theme-toggle").addEventListener("click"', page)


if __name__ == "__main__":
    unittest.main()

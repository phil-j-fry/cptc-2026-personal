"""Tests for tools/notebook.py."""

import support  # puts tools/ on the import path, so it must come first
import notebook
import compile

import ast
import contextlib
import http.client
import io
import json
import socket
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

    def test_nav_has_only_the_theme_and_checklists_buttons(self):
        page, parts = self.get_page()
        self.assertEqual(parts.inside["nav"], [("button", "theme-toggle"),
                                               ("button", "checklists-button")])
        self.assertEqual(parts.inside["main"], [])
        # No file lists or New/Logs/Export/Compile controls yet: the only
        # words on the page are the two buttons'.
        self.assertEqual(parts.visible_text, ["Light / dark", "Checklists"])

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
        self.assertIn('"X-CPTC-Token": TOKEN', page)
        self.assertIn('box.type = "checkbox";', page)
        self.assertIn("made.textContent = text;", page)
        # A box is locked while its save is pending and, if the save fails,
        # goes back to its value from before the click (not just flipped).
        self.assertIn("box.disabled = true;", page)
        self.assertIn("box.checked = !wanted;", page)

    def test_follows_system_dark_mode_and_has_a_toggle(self):
        page, _ = self.get_page()
        self.assertIn("@media (prefers-color-scheme: dark)", page)
        self.assertIn(':root[data-theme="dark"]', page)
        self.assertIn(':root[data-theme="light"]', page)
        self.assertIn('getElementById("theme-toggle").addEventListener("click"', page)


if __name__ == "__main__":
    unittest.main()

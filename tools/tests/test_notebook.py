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
        # No subprocess. os is only for $LOGDIR; the test below checks that
        # os.system and os.popen never appear.
        self.assertEqual(imported, {"argparse", "json", "os", "re", "secrets", "sys",
                                    "http.server", "pathlib", "compile"})

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

    def assert_safe_headers(self, response):
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.getheader("X-Frame-Options"), "DENY")
        cors = [name for name, _ in response.getheaders()
                if name.lower().startswith("access-control-")]
        self.assertEqual(cors, [])

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


class PageParts(HTMLParser):
    """Collects what a test needs from the app page: tags inside <nav> and
    <main>, and the text a person would see."""

    def __init__(self):
        super().__init__()
        self.open = []
        self.inside = {"nav": [], "main": []}
        self.visible_text = []

    def handle_starttag(self, tag, attrs):
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

    def test_two_empty_columns_with_only_the_theme_button(self):
        page, parts = self.get_page()
        self.assertEqual(parts.inside["nav"], [("button", "theme-toggle")])
        self.assertEqual(parts.inside["main"], [])
        # No file lists or New/Checklists/Logs/Export/Compile controls yet:
        # the only words on the page are the button's.
        self.assertEqual(parts.visible_text, ["Light / dark"])

    def test_follows_system_dark_mode_and_has_a_toggle(self):
        page, _ = self.get_page()
        self.assertIn("@media (prefers-color-scheme: dark)", page)
        self.assertIn(':root[data-theme="dark"]', page)
        self.assertIn(':root[data-theme="light"]', page)
        self.assertIn('getElementById("theme-toggle").addEventListener("click"', page)


if __name__ == "__main__":
    unittest.main()

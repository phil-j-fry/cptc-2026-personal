"""notebook.py: a local web page for checklists, field notes and templates.

Each tester runs it on their own box. It reads and writes the same Markdown
files the repo already uses, in the working copy.

Usage: python3 tools/notebook.py --name alice [--root ~/cptc-work] [--port 8765]

Python 3 standard library only. It never runs commands, and it has no option
to serve on any address but 127.0.0.1. It uses compile.py's root check;
compile.py imports nothing from here.
"""

import argparse
import json
import os
import re
import secrets
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import compile

# Any run of characters that aren't allowed in a slug.
NOT_SLUG_RE = re.compile(r"[^a-z0-9-]+")
# Two or more hyphens in a row.
REPEATED_HYPHENS_RE = re.compile(r"-{2,}")
SLUG_MAX_LENGTH = 40


def slugify(text):
    """Return text as a short filename part, e.g. "Admin Panel!" -> "admin-panel".

    Raises ValueError if nothing usable is left, e.g. for "!!!".
    """
    slug = text.lower()
    # Only a-z, 0-9 and "-" survive, so a title can't add "/", "..", spaces
    # or any other character that changes where a file is saved.
    slug = NOT_SLUG_RE.sub("-", slug)
    slug = REPEATED_HYPHENS_RE.sub("-", slug)
    # Trim before stripping the end hyphens, so a cut that lands just after
    # a "-" doesn't leave one at the end.
    slug = slug[:SLUG_MAX_LENGTH].strip("-")
    if not slug:
        raise ValueError("no letters or digits to make a file name from: " + repr(text))
    return slug


# The number in IR-NNN and F-NNN: exactly three ASCII digits. [0-9], not \d,
# because \d also matches other scripts' digits (e.g. Arabic-Indic), and
# fullmatch() is used because "$" would also accept a trailing newline.
NNN_RE = re.compile(r"[0-9]{3}")


def validate_nnn(text):
    """Return text if it is a three-digit number like 007, else raise ValueError.

    It only checks the format. The number itself is typed in by the user;
    this never picks or reserves one.
    """
    if not NNN_RE.fullmatch(text):
        raise ValueError("the number must be exactly three digits, e.g. 007: " + repr(text))
    return text


def is_inside(path, folder):
    """Return True if path is folder itself or anything below it."""
    return path == folder or folder in path.parents


def readable_path(root, path):
    """Return path, resolved, if it is inside the working copy; else raise RootError."""
    # One shared check (OQ-13): `..`, an absolute path outside the root, and a
    # symlink pointing outside are all refused by compile.py, with the path
    # named, while a symlink that stays inside the root is allowed (OQ-17).
    return compile.resolve_in_root(root, path)


def readable_log_path(logdir, path):
    """Return path, resolved, if it is inside the log folder; else raise RootError.

    The log folder is only ever read: there is no writable version of this.
    """
    # The same check as the working copy, with the log folder as the root.
    return compile.resolve_in_root(logdir, path)


def writable_path(root, logdir, path):
    """Return path, resolved, if the notebook may write it; else raise RootError.

    It must be inside the working copy, and not inside incoming/ or the
    log folder, which are read-only.
    """
    resolved = compile.resolve_in_root(root, path)
    # Both folders are resolved, so a symlink can't be used to write into them
    # through another name.
    incoming = (Path(root) / "incoming").resolve()
    if is_inside(resolved, incoming):
        # incoming/ holds teammates' copied files, which the tools only read
        # (R18); each person edits their own files on their own box.
        raise compile.RootError("incoming/ is read-only, not writing: " + str(path))
    if is_inside(resolved, Path(logdir).resolve()):
        # Logs are evidence: the notebook shows them but never changes them.
        raise compile.RootError("the log folder is read-only, not writing: " + str(path))
    return resolved


def name_option(text):
    """Turn --name into the slug used for field-notes/<name>/, e.g. "Alice Smith" -> "alice-smith"."""
    try:
        return slugify(text)
    except ValueError as error:
        # argparse shows this message with its usage line, instead of a traceback.
        raise argparse.ArgumentTypeError(str(error))


def make_token():
    """Return a new random token for this run (Constraint 8)."""
    # Put in the app's own page; other sites can't read that page, so they
    # can't learn it, and without it their POSTs are refused.
    return secrets.token_urlsafe(32)


def request_refusal(method, headers, port, token):
    """Return the 403 text if a request must be refused, or None to allow it.

    Every GET and POST needs Host exactly 127.0.0.1:<port>; a POST also
    needs the X-CPTC-Token header with this run's token.
    """
    refusal = "refused: use http://127.0.0.1:" + str(port)
    # A page on another site can make the browser send requests here. An
    # exact Host stops DNS rebinding, where an attacker's domain is pointed
    # at 127.0.0.1: the browser then sends that domain as the Host.
    # get_all() so a request can't sneak a second Host header past the check.
    if headers.get_all("Host") != ["127.0.0.1:" + str(port)]:
        return refusal
    if method == "POST":
        given = headers.get_all("X-CPTC-Token") or []
        # compare_digest() is built so its timing doesn't show how much of
        # the token matched. Bytes, because it raises an error on non-ASCII
        # text, which a header could contain.
        if len(given) != 1 or not secrets.compare_digest(given[0].encode("utf-8"),
                                                         token.encode("utf-8")):
            return refusal
    return None


def send_body(handler, status, content_type, body):
    """Send a response with the safety headers every response gets (Constraint 9)."""
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    # The browser must use the type above, not guess HTML from the content:
    # a log with "<script>" in it must never run as part of this page.
    handler.send_header("X-Content-Type-Options", "nosniff")
    # No other site may show the page inside a frame of its own.
    handler.send_header("X-Frame-Options", "DENY")
    # Deliberately no Access-Control-Allow-Origin (CORS) header, so other
    # sites' scripts can't read any response.
    handler.end_headers()
    # A HEAD response is headers only (HTTP says so); Content-Length still
    # gives the size the body would have, as the stdlib's own errors do.
    if handler.command != "HEAD":
        handler.wfile.write(body)


def send_text(handler, status, text):
    """Send a plain-text response: file and log content, and messages."""
    send_body(handler, status, "text/plain; charset=utf-8", text.encode("utf-8"))


def send_json(handler, status, data):
    """Send data (e.g. a file list) as JSON."""
    # ensure_ascii (the default) escapes non-ASCII text, so the body is plain ASCII.
    send_body(handler, status, "application/json", json.dumps(data).encode("ascii"))


def send_page(handler):
    """Send the app's one HTML page. Only "/" uses this; data is never HTML."""
    send_body(handler, 200, "text/html; charset=utf-8", APP_PAGE.encode("utf-8"))


# The app page: a left column (nav) and a main pane, both empty until the
# feature tasks add their parts. Inline CSS and JS only, no outside files
# (Constraint 1). Black on white, or white on black when the system is in
# dark mode; the button swaps them by hand. No styling beyond spacing.
APP_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>CPTC notebook</title>
<style>
:root { --text: black; --background: white; }
@media (prefers-color-scheme: dark) {
  :root { --text: white; --background: black; }
}
/* Set by the toggle button; these win over the system setting above. */
:root[data-theme="light"] { --text: black; --background: white; }
:root[data-theme="dark"] { --text: white; --background: black; }
body { margin: 0; color: var(--text); background: var(--background); font-family: sans-serif; }
.columns { display: flex; gap: 2rem; padding: 1rem; }
nav { width: 15rem; flex-shrink: 0; }
main { flex-grow: 1; }
</style>
</head>
<body>
<div class="columns">
<nav id="nav">
<button type="button" id="theme-toggle">Light / dark</button>
</nav>
<main id="main"></main>
</div>
<script>
/* Swap light and dark, starting from whatever is showing now. */
document.getElementById("theme-toggle").addEventListener("click", function () {
  var root = document.documentElement;
  var dark = root.dataset.theme
    ? root.dataset.theme === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches;
  root.dataset.theme = dark ? "light" : "dark";
});
</script>
</body>
</html>
"""

# The app's routes: path -> function(handler). The feature tasks add the rest.
# GET routes must never change anything (Constraint 8).
GET_ROUTES = {"/": send_page}
POST_ROUTES = {}


class NotebookHandler(BaseHTTPRequestHandler):
    """Answers each request; the server must have a `token` attribute."""

    def do_GET(self):
        self.answer("GET", GET_ROUTES)

    def do_POST(self):
        self.answer("POST", POST_ROUTES)

    def answer(self, method, routes):
        """Refuse a bad request before any route runs, else run its route."""
        # One request per connection, whatever protocol_version says. A refused
        # request's body is never read, so on a kept-open connection the
        # server would read it as a second request, which could pass the guard.
        self.close_connection = True
        port = self.server.server_address[1]
        refusal = request_refusal(method, self.headers, port, self.server.token)
        if refusal is not None:
            # Nothing has been read or changed yet, so a refused POST changes nothing.
            send_text(self, 403, refusal)
            return
        route = routes.get(self.path)
        if route is None:
            send_text(self, 404, "not found: " + self.path)
            return
        route(self)

    def send_error(self, code, message=None, explain=None):
        # The stdlib sends its own errors (e.g. 501 for a method other than
        # GET and POST, 431 for too many headers) as an HTML page without the
        # safety headers; send them as text instead.
        # Limit: for a request line it can't parse, the stdlib sends no status
        # line or headers at all (old HTTP/0.9 style), only this text.
        # Close the connection, as the stdlib's own version does: the body was
        # never read, and must not be read as a second request (see answer()).
        self.close_connection = True
        send_text(self, code, message or self.responses.get(code, ("error",))[0])

    def log_message(self, format, *args):
        """Don't print a line for every request; the terminal stays readable."""


def parse_args(argv=None):
    """Read the command-line options. argv=None means use sys.argv."""
    parser = argparse.ArgumentParser(
        description="A local notebook for checklists, field notes and templates.",
    )
    # Required, so every file the notebook makes lands in the right person's
    # field-notes/<name>/ folder instead of a guessed one. It is slugged like
    # a title, so it can only ever be one plain folder name.
    parser.add_argument("--name", required=True, type=name_option,
                        help="your name, e.g. alice")
    parser.add_argument(
        "--root",
        type=compile.expand_path,
        # The working copy, never the current folder, for the same reason as
        # compile.py: running from the repo clone must not write into it.
        default=Path("~/cptc-work").expanduser(),
        help="the working copy to work in (default: ~/cptc-work)",
    )
    parser.add_argument("--port", type=port_option, default=8765,
                        help="the port to listen on (default: 8765)")
    # There is deliberately no option for the address: the page is only ever
    # served on 127.0.0.1, so no setting can open it to the network.
    return parser.parse_args(argv)


def port_option(text):
    """Turn --port into a number from 1 to 65535, the range a port can be."""
    # isascii() too, because isdigit() also accepts other scripts' digits.
    if not (text.isascii() and text.isdigit()) or not 1 <= int(text) <= 65535:
        # argparse shows this message with its usage line, instead of a traceback.
        raise argparse.ArgumentTypeError("the port must be a number from 1 to 65535: " + repr(text))
    return int(text)


def log_dir():
    """Return the terminal log folder: $LOGDIR, or ~/cptc-logs if it isn't set."""
    # Same rule as scripts/logged-shell.sh (${LOGDIR:-$HOME/cptc-logs}), so the
    # notebook reads the folder the logs were written to; an empty value
    # counts as unset there too.
    return compile.expand_path(os.environ.get("LOGDIR") or "~/cptc-logs")


def load_settings(argv=None):
    """Return the startup settings as a dict, or raise compile.RootError.

    The keys are name, root (resolved), port and logdir.
    """
    args = parse_args(argv)
    return {
        "name": args.name,
        # Checked before the server exists, so a refused root (e.g. the git
        # clone) is never served from or written to.
        "root": compile.validate_root(args.root),
        "port": args.port,
        "logdir": log_dir(),
    }


def make_server(settings):
    """Return the server, listening on 127.0.0.1 only, with a new token for this run."""
    # The literal address, never "" or "0.0.0.0" (every network interface) or
    # "localhost" (a name the system looks up, which may not be 127.0.0.1), so
    # other boxes on the network can't reach the notebook (Constraint 2).
    server = HTTPServer(("127.0.0.1", settings["port"]), NotebookHandler)
    server.token = make_token()
    # For the routes the feature tasks add: they reach these as handler.server.settings.
    server.settings = settings
    return server


def main(argv=None):
    """Run from the command line and return the exit code."""
    try:
        settings = load_settings(argv)
    except compile.RootError as error:
        # A readable line instead of a traceback, with compile.py's exit code
        # for "couldn't run".
        print("notebook failed: " + str(error))
        return 2
    try:
        server = make_server(settings)
    except OSError as error:
        # Usually the port is already in use, e.g. by a second notebook.
        print("notebook failed: can't listen on 127.0.0.1:" + str(settings["port"])
              + ": " + str(error))
        return 2
    print("Notebook: http://127.0.0.1:" + str(server.server_address[1]))
    print("Local only: it listens on 127.0.0.1, so only this box can open it. Ctrl+C stops it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        # Ctrl+C is the normal way to stop it, so no traceback.
        print("Notebook stopped.")
    finally:
        server.server_close()
    return 0


# Only runs when started as `python3 tools/notebook.py`, never on import, so
# the tests can import this file without side effects.
if __name__ == "__main__":
    sys.exit(main())

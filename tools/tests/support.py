"""Shared helpers for the tools/ tests.

Test files start with `import support` so the code under test can be imported.
"""

import shutil
import sys
import tempfile
from pathlib import Path

# The tools live in tools/, one folder above this file. `unittest discover`
# only puts tools/tests/ on the import path, so without this line
# `import compile` would fail. Adding tools/ here means the tests need no
# tools/tests/__init__.py and no install step.
TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

# Tests write only here, never to /tmp or the OS temp folder, so nothing
# lands outside the repo. .gitignore excludes it, so nothing is committed.
TMP_DIR = Path(__file__).resolve().parent / ".tmp"


def make_worktree(test, files=None):
    """Create a fake working copy for one test and return its root folder.

    `files` maps a relative path (e.g. "findings/F-001-x.md") to its text.
    The folder is removed when the test finishes, pass or fail.
    """
    TMP_DIR.mkdir(exist_ok=True)
    # mkdtemp picks a fresh name, so two tests never share or clash on a folder.
    # It never creates a .git folder, so the root passes the tools' .git check.
    root = Path(tempfile.mkdtemp(prefix="worktree-", dir=str(TMP_DIR)))
    test.addCleanup(remove_worktree, root)
    for relative_path, text in (files or {}).items():
        write_fake_file(root, relative_path, text)
    return root


def write_fake_file(root, relative_path, text):
    """Write one fake file under root, creating its folders."""
    path = (root / relative_path).resolve()
    # A typo such as "../x" must not let a test write outside its own folder.
    if root.resolve() not in path.parents:
        raise ValueError("fake file escapes the worktree: " + relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# templates/finding.md filled in by hand, so tests have one finding that should
# pass every check. Same sections and labels as the template, every marker
# replaced and every NOTE deleted. The Attack chain section is removed, as the
# template says to for a standalone finding: one default finding has no
# neighbours to link, and a chain naming made-up IDs would make the duplicate
# and index checks report findings that don't exist.
# Only {finding_id} and {title} are filled by .format(), so any literal brace
# added later must be doubled.
COMPLETE_FINDING = """\
### {finding_id}: {title}

- **Severity:** Critical
- **CVSS 3.1:** `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H` (9.8)
- **Why this severity:** We logged in to the admin portal over the network with the vendor default password and could change any account.
- **Likelihood:** Anyone on the guest network can reach the login page, and the default password is published in the vendor manual.
- **Affected assets:** web01 (10.0.0.1), http://10.0.0.1/login, admin
- **Discovered by / when:** alice, 2026-11-07 10:15
- **Status:** Exploited
- **References:** CWE-1392, ATT&CK T1078.001, https://example.invalid/advisories/default-credentials

#### Summary
The client-example admin portal still accepts the password it shipped with. Anyone who knows that password can take full control of the portal and every account in it.

#### Business impact
An outsider on the guest network could lock staff out of the portal, change prices and read customer details.

#### Technical detail
The portal's built-in admin account was never given a new password after installation, and the login page allows unlimited attempts.

#### Reproduction steps
Starting position: Unauthenticated, on the client-example guest network, with no credentials.

1. `curl -i http://10.0.0.1/login`
   Expected: HTTP/1.1 200 OK and the admin portal login form
2. `curl -i -c cookies.txt -d 'user=admin&pass=admin' http://10.0.0.1/login`
   Expected: HTTP/1.1 302 Found redirecting to /admin, with a session cookie saved
3. `curl -i -b cookies.txt http://10.0.0.1/admin`
   Expected: HTTP/1.1 200 OK and the admin dashboard listing all accounts

#### Evidence
- `evidence/{finding_id}-01.png`: the admin dashboard after logging in as admin
- Log excerpt (timestamps included):

```
2026-11-07 10:14:52 POST /login user=admin -> 302 Found
2026-11-07 10:14:53 GET /admin -> 200 OK
```

#### Remediation
- **Immediate:** Set a new, unique password on the admin account.
- **Longer term:** Require every installed product's default passwords to be changed before it goes live.
- **How to verify the fix:** Repeat step 2 and confirm the login is refused.
"""


def make_complete_finding(finding_id="F-001", title="Default admin password on web01"):
    """Return the text of a fully filled-in fake finding."""
    return COMPLETE_FINDING.format(finding_id=finding_id, title=title)


def remove_worktree(root):
    """Delete one test's folder, and refuse anything else.

    Deleting is allowed only for the tests' own folders inside .tmp/, so check
    the folder really sits directly in .tmp/ before removing it.
    """
    if root.resolve().parent != TMP_DIR.resolve():
        raise ValueError("refusing to delete a folder outside tests/.tmp: " + str(root))
    # rmtree removes a symlink itself and never follows it, so a test link
    # such as incoming/alice -> another folder can't make cleanup delete
    # anything outside this folder.
    shutil.rmtree(str(root))

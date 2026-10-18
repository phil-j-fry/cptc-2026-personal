# CPTC Team Repo

Pre-staged templates, checklists, and scripts for the Collegiate Penetration Testing Competition (CPTC12, Regionals).

## Rules that govern this repo (from the official rulebook, Oct 2025 revision)

- **This repo is public.** Other teams and the internet can read it. Never put credentials, client data, or anything from the competition environment in here, during or after the event (rule R3).
- **Request deadline:** the repo must be requested at least **14 days before** the event. The request comes from a school email and includes the school name and every member's account name.
- **Freeze:** no commits during the **7 days before** the event. During competition hours, changes may be made only from inside the competition environment.
- **Be ready to explain anything in `scripts/`.** Operations may ask you to demonstrate it.
- **No coach commits.**
- **No outside collaboration tools** (Google Docs, M365, Dropbox) unless officials provide them. The templates here are Markdown so they work in whatever environment we're given.
- **Printed checklists are allowed.** Print everything in `checklists/` before the event.

Re-check the current rulebook (https://cp.tc/docs/cptc-rules.pdf) before the event in case these rules change.

## Layout

| Path | What it is |
|---|---|
| `CONVENTIONS.md` | **Team rules and naming conventions**, each linked to the document with the detail. Start here |
| `OPEN-ITEMS.md` | Open questions, and every unconfirmed assumption with the question that blocks it |
| `WORKFLOWS.md` | Step-by-step walkthroughs (tentative) for everyone and for the report writer: what to do, in what order, with which file |
| `templates/` | Report, finding, incident-report, status-update, inject-response, and presentation templates. **Start with `templates/README.md`**, which explains the `[[…]]` placeholder markers and which template to use when |
| `findings-library/` | 22 pre-written findings, written during study. Copy one into `findings/` on the day |
| `checklists/` | Printable run sheets: kickoff, AD, web, OT-safe, evidence, report QA, AI/LLM |
| `scripts/` | Small helpers we can explain line by line |
| `findings/` | One file per finding during the event (`F-001-short-name.md`). Used in the **working copy**, never committed (see below) |
| `evidence/` | Screenshots and logs, named to match the finding ID. Same rule |
| `tools/` | `compile.py` and `notebook.py` (planned; the build brief is `tools/BUILD-SPEC.md`) |
| `field-notes/`, `incoming/`, `build/` | Created in the working copy on the day, never committed: your own notes and reports; teammates' pulled files (read-only); `compile.py` output |

## What each file is for

**Start with `CONVENTIONS.md`, then `WORKFLOWS.md`.** `CONVENTIONS.md` holds the team's rules (R1–R18), and the naming and format conventions. `OPEN-ITEMS.md` lists every open question and unconfirmed assumption. `WORKFLOWS.md` says what everyone and the report writer do, step by step (tentative). This README is the map and the rulebook summary.

| File | Use it for |
|---|---|
| `CONVENTIONS.md` | The rules and naming conventions |
| `OPEN-ITEMS.md` | Open questions and unconfirmed items, with what each one blocks. Take this to the team meeting |
| `WORKFLOWS.md` | Step-by-step walkthroughs per role, naming the file or command for each step |
| `templates/README.md` | The `[[…]]` marker key and which template to use when. Read before filling anything in |
| `templates/finding.md` | One finding (copied once per finding) |
| `templates/report.md` | The full report skeleton (copied once, to `~/cptc-work/report.md`) |
| `templates/severity-guide.md` | How to rate severity (CVSS 3.1 plus context) |
| `templates/incident-report.md`, `status-update.md`, `inject-response.md` | The three client-communication documents |
| `templates/presentation-outline.md` | Plan for the debrief slides after submission |
| `templates/tracker/` | Five CSV files (hosts, credentials, created accounts, attack path, findings index) and their README |
| `findings-library/README.md` | Index of the 22 pre-written findings (L01–L22) and how to use them |
| `checklists/00-kickoff.md` … `60-ai-llm.md` | Printable run sheets: kickoff, AD, web, OT-safe, evidence and logging, report QA, AI/LLM |
| `scripts/logged-shell.sh` | Records each terminal session; `logged-shell.md` explains it line by line |
| `tools/BUILD-SPEC.md` | The brief for building `compile.py` and `notebook.py` (planned) |
| `.gitignore` | Keeps event files (findings, evidence, scan output, credentials) out of git if anyone commits by mistake |

## Roles (fill in)

| Role | Person | Owns |
|---|---|---|
| Everyone | | Testing, notes, writing up their own findings |
| Report writer (tentative) | | Assembling and submitting the report |

All other roles and team jobs (severity calls, incident reports, client and Operations contact, status updates, injects, what the captain facilitates) are TBD; see "Roles, and who owns which team jobs?" in `OPEN-ITEMS.md`.

## The workflow on the day

1. Kickoff checklist: read the scope and ROE aloud, then write the out-of-scope list on the whiteboard.
2. Everyone starts a logged shell (`scripts/logged-shell.sh`).
3. Every finding gets an ID the moment it's found, before it gets exploited further. How IDs are allocated is **TBD** (R6: a shared doc, or per-person blocks such as Alice F-001 to F-020, Bob F-021 to F-040; blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`).
4. The finder fills in `templates/finding.md` (or a library entry) and hands it to the report writer. The author keeps editing their own file until the finding is pasted into `report.md`; after that, changes are made in `report.md` (R18). Who makes the final severity call is TBD (R8).
5. If something breaks, stop and tell the team. An incident report follows (`templates/incident-report.md`; who files it and how fast are **TBD**, see the open questions).
6. Report assembly starts at the halfway point, not at the end. The report writer (see `WORKFLOWS.md`) copies `templates/report.md` to `~/cptc-work/report.md` and works there.
7. Before every submission, someone who didn't write it runs `checklists/50-report-qa.md`.

## Working copy and moving files on the day

**Work in a copy, not in the git clone.** At kickoff, each person runs:

```
[ -e ~/cptc-work ] && echo "~/cptc-work already exists: stop" || { cp -r <repo-clone> ~/cptc-work && rm -rf ~/cptc-work/.git && mkdir -p ~/cptc-work/field-notes/<yourname> ~/cptc-work/incoming; }
```

Replace `<repo-clone>` and `<yourname>` before running it (leaving `<yourname>` in makes the shell fail halfway, after the copy). That makes a plain copy with no `.git`, so nothing in it can be committed. It refuses to run if `~/cptc-work` already exists. (A plain `cp -r` into an existing folder would put the clone *inside* it with `.git` intact and the cleanup would silently do nothing.) Practice runs and tool tests should use a different folder; the tools take `--root`.

**Do this before starting any logged shell, and open every terminal in `~/cptc-work`.** The checklists write scan output to the current directory; inside the clone, one stray `git add` would publish it.

All event work happens inside `~/cptc-work`: `findings/`, `evidence/`, `field-notes/<yourname>/`, your tracker copy, and later `report.md`. Every path in the templates and checklists stays the same; you're simply working in the copy.

**Picking up a tool fix mid-event:** never re-run the copy command. Copy just the changed file from a fresh clone, for example `cp <repo-clone>/tools/compile.py ~/cptc-work/tools/`.

**Getting files to the report writer.** At kickoff, pick the first of these that works, in order:

1. **Shared storage provided by the officials.** It's explicitly allowed, so use it if it's offered.
2. **Report writer pulls over SSH** (`rsync` or `scp`) from each teammate's Kali box:
   ```
   mkdir -p ~/cptc-work/incoming/alice
   rsync -av --delete kali@<alice-kali-ip>:~/cptc-work/findings/ ~/cptc-work/incoming/alice/findings/
   rsync -av --delete kali@<alice-kali-ip>:~/cptc-work/evidence/ ~/cptc-work/incoming/alice/evidence/
   rsync -av --delete kali@<alice-kali-ip>:~/cptc-work/field-notes/ ~/cptc-work/incoming/alice/field-notes/
   rsync -av --delete kali@<alice-kali-ip>:~/cptc-work/tracker/ ~/cptc-work/incoming/alice/tracker/
   ```
   Each teammate must start `sshd` (`sudo systemctl start ssh`). **Change the default `kali` password first.** (**Unconfirmed:** `kali@` assumes every box uses the `kali` login; use the real username if not. Blocked by the open question "Did every box log in as the same user?" in `OPEN-ITEMS.md`.) The report writer merges teammates' tracker rows (from `incoming/<name>/tracker/`) by hand for the attack path and Appendix F.
3. **Exported bundle, moved by hand.** Each person makes one archive (the notebook's export zip, or `zip -r` by hand) and drops it on the report writer's machine any way that works (RDP drive mapping, `scp`). Unpack it fresh each time, so files the teammate deleted don't linger: `rm -rf ~/cptc-work/incoming/alice && unzip <file> -d ~/cptc-work/incoming/alice/`.

Whatever the method, incoming work lands in `~/cptc-work/incoming/<name>/` on the report writer's machine. Assembly tooling reads from there, so the method of transfer doesn't matter.

**`incoming/` is a read-only mirror. Nobody edits anything in it.** Every pull overwrites it (and `--delete` removes files the teammate has deleted). Changes to a finding are made by its author in their own `findings/`, and the next pull brings them across; once a finding is in `report.md`, changes are made there (rule R18 in `CONVENTIONS.md`).

**Rules check:** the rulebook bans *external* private storage and "peer to peer or distributed file sharing clients or servers". Our reading is that copying files between our own team's boxes inside the environment is fine, but **confirm with Operations** before relying on option 2 (**Unconfirmed:** blocked by the open question "How may teammates move files…?" in `OPEN-ITEMS.md`). Never move event data anywhere outside the competition environment.

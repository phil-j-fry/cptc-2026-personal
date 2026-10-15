# Kickoff Checklist (first 30 minutes)

- [ ] Read the **Scope of Work** and **Rules of Engagement** aloud to the whole team
- [ ] Write the **in-scope ranges** and the **explicit exclusions** on the whiteboard
- [ ] Note any ROE limits on: password spraying, poisoning/relay, DoS-prone tests, social engineering, OT/ride systems, data exfiltration
- [ ] Record the client contacts and how to reach the Operations Team
- [ ] Record the deliverable deadlines and set timers for each one
- [ ] Assign roles (see README) and the first-hour targets
- [ ] Everyone starts `scripts/logged-shell.sh`, and the system clock is checked
- [ ] Create `findings/` and `evidence/` with the naming convention
- [ ] Agree on the "stop and tell the lead" triggers: anything goes down, an account locks, an unexpected host shows up, or a sensitive system responds
- [ ] **If unsure whether a target is in scope, ask Operations before touching it.**

## Midpoint (halfway through the event)
- [ ] Lead starts assembling the report
- [ ] Executive summary draft v0
- [ ] Every finding so far has evidence and an owner
- [ ] Send a client status update (`templates/status-update.md`)

## Final 90 minutes
- [ ] No new exploitation. Writing only.
- [ ] Severity consistency pass
- [ ] Remediation steps are specific and testable
- [ ] Spell check, and check that IDs match evidence filenames
- [ ] Record cleanup status of anything left on systems

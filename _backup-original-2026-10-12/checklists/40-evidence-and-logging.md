# Evidence and Logging Sheet

The report is only as good as the evidence. Novices: **this sheet is your main job, and it's worth real points.**

## Every session
- [ ] Start `scripts/logged-shell.sh <yourname>`. Every command is captured with a timestamp in the prompt.
- [ ] Confirm the system clock is correct (`date`)

## Every finding
- [ ] Assign an ID immediately: `F-001`, `F-002`… (the lead keeps the master list)
- [ ] Create `findings/F-XXX-short-name.md` from `templates/finding.md`
- [ ] Screenshot showing: **the command, the output, the target IP/hostname, and the clock** in one frame
- [ ] Name screenshots `evidence/F-XXX-NN.png`
- [ ] Paste the relevant log lines (with timestamps) into the finding
- [ ] Write the reproduction steps **while you remember them**, not at the end

## Credentials
- [ ] Record where each credential came from, which finding it relates to, and where it was used
- [ ] Credentials stay in the competition environment only. Redact them in the report (show the first and last characters).

## Changes made to systems
- [ ] Log every account created, password changed, file dropped, or service touched, with a time and host, so it can be reported and cleaned up

## If something breaks
- [ ] Stop. Note the time. Tell the lead.
- [ ] Lead files `templates/incident-report.md` and notifies Operations

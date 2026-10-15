### [[FINDING_ID]]: SQL Injection in Web Application

[[NOTE: Library entry L15, to be written during study. Study day: replace every TODO marker with your own general text. Competition day: copy this file to findings/F-XXX-sql-injection.md, replace FINDING_ID, fill every other marker with real evidence, and delete the NOTE markers. Marker key: templates/README.md.]]

[[NOTE: Library text is general. Check each section against what you actually found, then delete this note.]]

- **Severity:** High [[NOTE: Library default. Set the final rating per templates/severity-guide.md.]]
- **CVSS 3.1:** `[[CVSS_VECTOR]]` ([[CVSS_SCORE]])
- **Why this severity:** [[SEVERITY_RATIONALE]]
- **Likelihood:** [[TODO: who could exploit this in general, from where, and what they need. Adjust it to the real situation on the day.]]
- **Affected assets:** [[HOST]] ([[HOST_IP]]), [[URL]], [[ACCOUNT]]
- **Discovered by / when:** [[TESTER]], [[DATE]] [[TIME]]
- **Status:** [[CHOOSE: Confirmed / Exploited / Suspected]]
- **References:** CWE-89, ATT&CK T1190, [[TODO: one vendor or standards link]]

#### Summary
[[TODO: Two or three plain-language sentences for a manager.]]

#### Business impact
[[TODO: The general business impact, in plain terms with no tool names.]] [[CLIENT_SPECIFIC_IMPACT]] [[NOTE: On the day, add one line in the client's own terms (rides, ticketing, guest data, payments).]]

#### Technical detail
[[TODO: Root cause and how the attack works, in your own words.]]

#### Reproduction steps
[[TODO: The general command sequence from your lab, in the format shown in templates/finding.md: numbered steps, each with the command in backticks and an "Expected:" line.]]

Starting position: [[STARTING_POSITION]]

[[REPRODUCTION_STEPS]]

#### Evidence
- `evidence/[[FINDING_ID]]-01.png`: [[WHAT_IT_SHOWS]]

#### Remediation
- **Immediate:** [[TODO: the specific setting or fix]]
- **Longer term:** [[TODO: the control that prevents this class of issue]]
- **How to verify the fix:** [[TODO: a command or check the client can run]]

#### Detection (for the client's defenders)
[[TODO: What log or event would show this being exploited (e.g. Windows event IDs).]]

#### Attack chain
[[PREVIOUS_FINDING_ID]] → this → [[NEXT_FINDING_ID]] [[NOTE: Delete this section if the finding stands alone.]]

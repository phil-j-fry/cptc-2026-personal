# Findings Library

Pre-written findings so we fill in specifics on the day instead of writing from scratch. **Each one is written the day you study the technique.** Writing the root cause, impact, and remediation is the test of whether you understood it.

On the day: copy the library file to `findings/F-XXX-<slug>.md`, replace every `<<…>>` placeholder with real evidence, and adjust the severity to context.

| ID | Finding | Default severity | ATT&CK | CWE | Written on | Status |
|---|---|---|---|---|---|---|
| L01 | [Anonymous SMB/LDAP Access Exposes Domain Information](L01-anonymous-smb-ldap-access.md) | Medium | T1087.002 | CWE-284 | Oct 12 | ☐ |
| L02 | [SNMP Uses Default Community String](L02-snmp-default-community.md) | Medium | T1602.001 | CWE-1392 | Oct 12 | ☐ |
| L03 | [SMB Signing Not Required Allows NTLM Relay](L03-smb-signing-not-required.md) | Medium | T1557.001 | CWE-294 | Oct 17 | ☐ |
| L04 | [Kerberoastable Service Account with Crackable Password](L04-kerberoastable-service-account.md) | High | T1558.003 | CWE-521 | Oct 13 | ☐ |
| L05 | [Account Does Not Require Kerberos Pre-Authentication](L05-asrep-roastable-account.md) | High | T1558.004 | CWE-287 | Oct 13 | ☐ |
| L06 | [Weak Domain Password Policy Permits Password Spraying](L06-weak-password-policy.md) | Medium | T1110.003 | CWE-521 | Oct 13 | ☐ |
| L07 | [Excessive Privileges Create a Path to Domain Admin](L07-excessive-privilege-attack-path.md) | High | T1069.002 | CWE-269 | Oct 14 | ☐ |
| L08 | [Dangerous Active Directory ACL Allows Account Takeover](L08-dangerous-ad-acl.md) | High | T1098 | CWE-732 | Oct 15 | ☐ |
| L09 | [MSSQL Misconfiguration Allows Command Execution](L09-mssql-misconfiguration.md) | High | T1505.001 | CWE-250 | Oct 15 | ☐ |
| L10 | [LLMNR/NBT-NS Enabled Allows Credential Capture](L10-llmnr-nbtns-poisoning.md) | Medium | T1557.001 | CWE-300 | Oct 17 | ☐ |
| L11 | [Shared Local Administrator Password Enables Lateral Movement](L11-local-admin-password-reuse.md) | High | T1550.002 | CWE-262 | Oct 19 | ☐ |
| L12 | [Vulnerable AD CS Certificate Template Allows Privilege Escalation](L12-adcs-vulnerable-template.md) | Critical | T1649 | CWE-295 | Oct 20 | ☐ |
| L13 | [Full Active Directory Domain Compromise](L13-domain-compromise.md) | Critical | T1003.006 | CWE-269 | Oct 21 | ☐ |
| L14 | [Local Privilege Escalation via Sudo/SUID Misconfiguration](L14-linux-privilege-escalation.md) | High | T1548.003 | CWE-250 | Oct 27 | ☐ |
| L15 | [SQL Injection in Web Application](L15-sql-injection.md) | High | T1190 | CWE-89 | Oct 22 | ☐ |
| L16 | [Insecure Direct Object Reference Exposes Other Users' Data](L16-idor-broken-access-control.md) | High | T1190 | CWE-639 | Oct 22 | ☐ |
| L17 | [Weak Web Application Authentication Controls](L17-web-authentication-weakness.md) | Medium | T1110 | CWE-287 | Oct 22 | ☐ |
| L18 | [Ride Control Network Reachable from Corporate/Guest Networks](L18-ot-network-segmentation.md) | Critical | ICS T0846 | CWE-923 | Oct 27 | ☐ |
| L19 | [Industrial Protocol Accepts Unauthenticated Commands](L19-unauthenticated-industrial-protocol.md) | Critical | ICS T0855 | CWE-306 | Oct 27 | ☐ |
| L20 | [Default Credentials on Administrative Interface](L20-default-credentials.md) | High | T1078.001 | CWE-1392 | Oct 28 | ☐ |
| L21 | [Sensitive Services Use Cleartext Protocols](L21-cleartext-protocols.md) | Medium | T1040 | CWE-319 | Oct 28 | ☐ |
| L22 | [Outdated and Unsupported Software in Use](L22-outdated-software.md) | Medium | T1190 | CWE-1104 | Oct 28 | ☐ |

Statuses: ☐ not written, ◐ drafted, ☑ reviewed against a winning report.

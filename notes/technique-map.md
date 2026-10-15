# Technique Map

Study map for CPTC prep, organized by tracker week. Each technique links to:
- **ATT&CK ID**, which you'll also cite in the finding
- **Evidence**: how many of 9 public sources document it (8 winning or finalist team repos plus one competitor's packet)
- **Where to study it**: a specific file in a public team repo
- **Library finding**: the finding you write the day you learn the technique (see `findings-library/`)

> **How the evidence was measured:** a case-insensitive keyword count across each repo's notes, cheat sheets, and scripts, done on 2026-10-08. It shows what teams *wrote down*, not what they used or scored on. Generic words ("relay", "exchange") inflate a few counts. Treat it as a signal for prioritizing, not as ground truth.
>
> **Sources (9):** Stanford, UC Irvine (CPTC11 champion), Univ. of Florida, UMass Amherst, Cal Poly Pomona, Princess Sumaya Univ. (PSUT), UCF, CCSF (ours, last season), and `sears-s/cptc`. Team repos are at `github.com/nationalcptc-teamtools/<School-Name>`.
>
> **Safety:** read these repos, don't run them. Some contain precompiled payloads and root install scripts. Open anything executable only in a throwaway VM.

## Best study sources (start here)
| File | Why |
|---|---|
| `University-of-Massachusetts-Amherst/cheatsheets/CPTC Cheatsheet.md` | The densest single cheat sheet: AD, pivoting, and privilege escalation in one place |
| `Princess-Sumaya-University-for-Technology/notes/pivoting.md` | Focused pivoting notes |
| `University-of-Florida/notes/adam/AD.md` | AD workflow, MSSQL, and pivoting |
| `University-of-California-Irvine/notes/*.docx` | The champion's notes: AD, Linux, mail, MongoDB, pivoting, a website checklist |
| `Stanford-university/ad_notes.pdf` | AD notes |
| `Stanford-university/templates/findings/*.docx` | 25 pre-written findings, a model for our library |
| `globalcptc/report_examples/CPTC10/` | The most recent finalist reports and presentations |

---

## Week 1: AD fundamentals and enumeration
| Technique | ATT&CK | Tools | Sources | Library finding |
|---|---|---|---|---|
| Network service discovery | T1046 | nmap | 9/9 | (supports all) |
| SMB, LDAP, and RPC enumeration (null and guest sessions) | T1087.002, T1069.002 | nxc, smbclient, smbmap, enum4linux, ldapsearch, ldapdomaindump | 8/9 | `L01 anonymous-smb-ldap-access` |
| SNMP enumeration (default community strings) | T1602.001 | nmap scripts, snmpwalk, onesixtyone | 5/9 | `L02 snmp-default-community` |
| Mail service enumeration (SMTP user enumeration, open relay) | T1087 | nmap, swaks, smtp-user-enum | 7/9* | (note only) |
| Username enumeration via Kerberos | T1087.002 | kerbrute | 8/9 | (supports L04/L05) |
| Kerberoasting | T1558.003 | GetUserSPNs.py, nxc, hashcat -m 13100 | 8/9 | `L04 kerberoastable-service-account` |
| AS-REP roasting | T1558.004 | GetNPUsers.py, nxc, hashcat -m 18200 | 7/9 | `L05 asrep-roastable-account` |
| Password spraying (policy-aware) | T1110.003 | nxc, kerbrute | 6/9 | `L06 weak-password-policy` |
| BloodHound attack-path analysis | T1069.002, T1087.002 | bloodhound-python / SharpHound, BloodHound | 8/9 | `L07 excessive-privilege-attack-path` |
| ACL abuse (GenericAll, WriteDACL, ForceChangePassword) | T1098 | BloodHound, bloodyAD, dacledit.py | (in AD notes) | `L08 dangerous-ad-acl` |
| MSSQL abuse (xp_cmdshell, impersonation, linked servers) | T1505.001 | mssqlclient.py, nxc mssql | 5/9 | `L09 mssql-misconfiguration` |

\* The mail count is inflated by the word "exchange".

## Week 2: Lateral movement, escalation, and pivoting
| Technique | ATT&CK | Tools | Sources | Library finding |
|---|---|---|---|---|
| LLMNR/NBT-NS poisoning | T1557.001 | Responder (analyze mode first) | 7/9 | `L10 llmnr-nbtns-poisoning` |
| SMB relay (signing not required) | T1557.001 | nxc `--gen-relay-list`, ntlmrelayx.py | 8/9 | `L03 smb-signing-not-required` |
| Authentication coercion (PetitPotam etc.) | T1187 | PetitPotam, Coercer | 6/9 | (part of L03/L12) |
| Credential reuse / local admin reuse (no LAPS) | T1078.003, T1550.002 | nxc, secretsdump.py | 7/9 | `L11 local-admin-password-reuse` |
| Remote execution (WinRM, SMB, WMI) | T1021.006, T1021.002, T1047 | evil-winrm, wmiexec.py, psexec.py | 6/9 | (supports L11) |
| ADCS template abuse (ESC1, ESC8) | T1649 | certipy | 5/9 | `L12 adcs-vulnerable-template` |
| DCSync / domain compromise | T1003.006 | secretsdump.py | 4/9 | `L13 domain-compromise` |
| GPO abuse | T1484.001 | pyGPOAbuse | 4/9 | (note only) |
| Pivoting / tunneling | T1572, T1090 | ligolo-ng, chisel, proxychains, ssh -D/-L | 7/9 | (methodology, not a finding) |
| Web: SQL injection | T1190 | Burp, sqlmap (low risk/level) | 6/9 | `L15 sql-injection` |
| Web: IDOR / broken access control | T1190 | Burp | (in web checklists) | `L16 idor-broken-access-control` |
| Web: authentication weaknesses | T1110, T1078 | Burp, hydra (check the ROE) | 5/9 | `L17 web-authentication-weakness` |

## Week 3: Reporting depth, OT, and the remaining common findings
| Technique | ATT&CK | Tools | Sources | Library finding |
|---|---|---|---|---|
| Linux privilege escalation (sudo, SUID, cron, credentials in files) | T1548.003, T1548.001, T1552.001 | linpeas, pspy, GTFOBins | 8/9 | `L14 linux-privilege-escalation` |
| OT network reachability / segmentation | ICS T0846 | nmap -sT (slow, specific ports) | 3/9 | `L18 ot-network-segmentation` |
| Unauthenticated industrial protocols (Modbus, BACnet, S7) | ICS T0846; impact T0855 | nmap modbus-discover / bacnet-info (read-only) | 3/9 | `L19 unauthenticated-industrial-protocol` |
| Default credentials | T1078.001 | manual, vendor lists | (common) | `L20 default-credentials` |
| Cleartext protocols (HTTP, FTP, Telnet) | T1040 | nmap, Wireshark | (common) | `L21 cleartext-protocols` |
| Outdated or unsupported software | T1190 | nmap -sV, version research | (common) | `L22 outdated-software` |

## Additions from the CPTC10 finals report review (2026-10-14)
These are techniques that most CPTC10 finalists reported but that weren't on this map. The **Reports** column counts how many of the 12 published CPTC10 finals reports mention each one. That's keyword presence in the reports' text, so it's a prioritizing signal, not proof that each team found it. Whether AI and cloud targets recur at regionals is an inference; the finals environment had both.

| Technique | ATT&CK / ATLAS | Tools | Reports | Library finding |
|---|---|---|---|---|
| Kerberos delegation abuse (unconstrained, constrained, RBCD) | T1558 | BloodHound, findDelegation.py, getST.py, rbcd.py, nxc ldap `--trusted-for-delegation` | 11/12 (RBCD alone: 7/12) | (none yet, candidate) |
| Shadow credentials (KeyCredentialLink write) | T1098 | certipy shadow, pywhisker | 4/12 | (note only) |
| LLM jailbreak and prompt injection (chatbots, AI "password managers") | ATLAS AML.T0054, AML.T0051 | Manual prompts; Burp for the API calls | 8–9/12 | (none yet, candidate) |
| Cloud storage and identity enumeration (public blobs or buckets holding credentials) | T1530, T1580 | AzureHound, az cli, MicroBurst | 9/12 | (none yet, candidate) |
| Phishing with a macro document (only if in scope) | T1566.001 | Office macro plus an obfuscated payload | 11/12 | (note only) |
| AI-voice vishing of a helpdesk (only if in scope) | T1566.004 | The platform the client provides | 8/12 | (note only) |
| URL-fetch features abused for file read or SSRF (`file://` in an image URL) | T1190 | Burp | 8/12 | (covered by the web checklist) |

## Deliberately skipped (low value for this timeline)
C2 frameworks (Sliver: 3/9), AV-evasion loaders, custom collaboration web apps, and Zerologon/EternalBlue exploitation. These appear in older notes and are worth recognizing as findings, but don't spend practice time on them.

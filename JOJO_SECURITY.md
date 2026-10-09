# JoJo defensive security skills

JoJo now supports local defensive checks. It is not an antivirus replacement,
intrusion-prevention system, browser extension, or a guarantee against hacking.

## Commands and controls

- **“JoJo security check”**, **“device hack hua hai?”**: checks Windows Defender
  protection/status, active Defender threats, firewall profiles, encoded startup
  commands, startup entries in temporary/download folders, encoded PowerShell
  processes and current Wi-Fi authentication where Windows exposes it.
- **“link check https://example.com”**: inspects URL structure without visiting
  the site. Checks disguised user-info, active/non-web schemes, HTTP, Unicode or
  punycode hosts, shortened URLs, executable downloads and restricted sites.
- **“app check C:\path\installer.exe”**: reads SHA256 and Authenticode signature
  without running or uploading the file. A valid signature is not proof of safety;
  an unsigned file is not proof of malware. No cloud reputation check is performed.
- **“wifi security”**: defensive guidance for your own router. No password extraction,
  cracking, deauthentication, packet interception, exploitation or unauthorized
  network access is implemented.
- Desktop **Security check** button: on-demand read-only audit.
- Desktop **Defender quick scan** button: explicitly starts Windows Defender's
  QuickScan. Defender's existing protection/remediation policy applies. JoJo does
  not change exclusions, disable protection, delete suspected files or kill
  processes based on heuristics. Scan completion does not prove absence of malware.

## Warnings and protection

While the JoJo core is running, a local worker repeats the audit every five minutes.
High/critical changes show a native warning and a report in the desktop conversation.
Unchanged findings are quiet within the current desktop session. This is periodic
observation, not real-time detection of every attack. It stops when JoJo exits.
Set `JOJO_DISABLE_SECURITY_MONITOR=1` before starting JoJo to disable the watcher.

JoJo refuses obvious high-risk URLs in its own guarded action paths. This does not
intercept links that you click in other apps or protect an arbitrary browser outside
JoJo. Existing restricted-app checks remain enabled. Android action plans use the
same URL guard, but the Windows device audit describes the **laptop**, not the phone.
Android malware/package scanning is not implemented in this release.

The latest local report is `jojo_security_latest.json` (excluded from Git). Raw
process command lines, Wi-Fi passwords, URL credentials and query tokens are not
included in reports. No file or URL is uploaded by these inspection functions.
Calling inspection through the model tool loop can include the returned metadata
in the normal model conversation; direct security commands use the local route.

## Interpreting results

“No indicators found” means only that these checks did not flag a condition.
Unavailable or permission-denied checks are explicitly unknown. Historic remediated
Defender detections are distinguished from active threats. Encoded commands and
temporary startup paths are investigation hints, not automatic malware verdicts.

For an active Defender threat, follow **Windows Security → Protection history**.
If you suspect an ongoing compromise, avoid sensitive sign-ins, consider disconnecting
the affected device, and use a trusted device for account recovery. JoJo reports
remediation guidance rather than silently reconfiguring the firewall/router.

## Validation

Regression fixtures cover deceptive URLs, expected-domain boundaries, passive URL
inspection, file hashing/signature metadata, active versus historical threats,
unknown checks, Wi-Fi indicators and the action boundary. No test deliberately
infects the device, attacks Wi-Fi or changes Windows protection settings.

Implementation references: [Microsoft Defender PowerShell commands](https://learn.microsoft.com/en-us/powershell/module/defender/)
and [FTC home Wi-Fi security guidance](https://consumer.ftc.gov/articles/how-secure-your-home-wi-fi-network).

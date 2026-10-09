# Learning, locking and smart devices

These are source changes, not a new APK. APK generation is deferred until the user
explicitly requests a final build.

## Learning

Every terminal task records its outcome and result in a bounded local learning
store. Related successes/failures are retrieved for future tasks; duplicate journal
updates do not count as multiple experiences. The planner is told to inspect the
current situation and avoid blindly retrying previously failed actions.

Explicit owner corrections: “yaad rakho short answers dena” / “remember this …”.
“Learning status” shows stored correction and outcome counts. Clearing conversation
memory also clears this learning store. No weight training, unsupervised code edits,
new permissions, background web crawling or automatic execution of learned workflows
is implemented. Improvement in real-world task success still needs measurement.

## Lock / unlock

- “JoJo lock the phone”: verified mobile owner command → native Android lock
  action → fresh Keyguard state → session revoked. JoJo must already be running
  with microphone and accessibility permission. Background restrictions can stop it.
- “JoJo lock the laptop/PC/computer”: desktop uses Windows LockWorkStation.
  The verified phone command can explicitly request laptop locking on its paired
  backend too. A successful API call means a request was initiated, not a verified
  locked desktop. Laptop-to-phone remote locking is not implemented.
- Windows “Unlock …”: manual Windows Hello/PIN/password remains required.
  Android now has an optional local saved-PIN flow; see `JOJO_PIN_AND_SYNC.md`.
  It uses the normal supported PIN entry UI, never bypasses the OS/app lock or
  impersonates a fingerprint. It is disabled until configured locally.
- Android locked state is checked before screen capture/actions. Recognized app
  password/fingerprint prompts withhold their contents and request manual unlock.
  After authenticating, say “JoJo continue” while the clarification session is
  active, or repeat the task. JoJo gets a fresh observation. Expired sessions do
  not silently resume actions. Custom app locks may require manual identification.

Owner voice matching is not replay-proof and is not a replacement for the OS lock.
No real device was locked during automated testing.

## Smart devices

An optional Home Assistant REST adapter provides a common bridge. Devices must
first be paired to Home Assistant using their supported integrations. JoJo neither
scans nearby networks nor logs in/pairs with arbitrary devices automatically.

Set these locally in `.env` (never send the token in chat):

```
JOJO_HA_URL=http://192.168.1.10:8123
JOJO_HA_TOKEN=your-token
JOJO_HA_ENTITIES=light.bedroom,fan.study,switch.desk
```

Supported now: list observed device states and on/off for allowlisted lights,
switches, fans and media players. Door locks, security alarms, arbitrary services,
AC temperatures and brand-specific functions are not implemented. Do not allowlist
a switch powering equipment you do not want JoJo to operate.

Desktop planner tools: `list_smart_devices`, `control_smart_device`.
Exact voice commands on desktop/phone: “smart devices”, “smart light.bedroom on”.
Credentials and device IDs are still unconfigured; no real hardware test performed.
Responses are checked after control, and uncertain commands are never auto-retried.

Platform sources: [Android lock action](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService#GLOBAL_ACTION_LOCK_SCREEN),
[Windows lock semantics](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-lockworkstation),
[Home Assistant REST API](https://developers.home-assistant.io/docs/api/rest/).

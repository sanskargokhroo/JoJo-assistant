# JoJo native Android companion

Native Java/Canvas source targets Android 8.1+ (API 27). No browser/WebView. The companion uses
the laptop's AI service over a USB connection; standalone phone reasoning and
wireless deployment are not implemented.

Included feature: optional phone-local encrypted numeric PIN vault and
saved-PIN entry on supported normal authentication screens. See
`../JOJO_PIN_AND_SYNC.md` for opt-in setup, security tradeoffs, supported targets,
Firestore synchronization and remaining device tests. The local test APK built on 10 October 2026 includes this change; physical-device validation is pending.

## Current testing build

The 29 October 2026 testing build is **0.3.0-alpha.3**, version code 4, minimum
Android 8.1 (API 27). It includes the native dashboard, JoJo icon, masked pairing
field, connection diagnostics and selected laptop-voice playback. APK signing
and Java compilation passed; physical voice/action testing is still in progress.

Laptop **Deactivate** now stops laptop listening, speech and tasks only. The
shared backend remains available to the phone. Phone **Stop phone assistant**
affects the phone only. This remains a USB companion: powering off the laptop,
terminating the shared backend or disconnecting USB prevents full phone AI work.
Memory is shared; this change does not move model execution onto the phone.

Phone speech uses the laptop's selected Madhur voice/rate/pitch through an
authenticated audio endpoint. Temporary audio is deleted after playback; no default
Android/female voice fallback is used. If synthesis fails, the dashboard shows the
reply. Private sessions do not send text to this online voice service. Latest reply
and error display are process-local, not saved to phone preferences.

On Android 8.1, locking requires the physical power button. On-device speech for
local essentials requires Android 12+ and an available recognizer; typed commands
remain available. No automatic unlock or payment tests are part of this trial.

## Install

1. Start `start_jojo.bat` on the laptop. Enroll your voice in Settings.
2. Connect the phone by USB. Enable USB debugging yourself and approve the laptop
   on the phone. No permissions are enabled automatically.
3. Run `powershell -File android/install_on_phone.ps1` from the repository root.
   If multiple devices are connected, pass `-DeviceId SERIAL`.
4. Desktop Settings → **Pair native Android companion**. Enter that key in JoJo
   on the phone and save it. The key is stored locally, excluded from Git.
5. On the phone, enable **JoJo screen control** in Accessibility settings. Return
   to JoJo, tap **Start listening**, grant microphone permission, then tap Start
   again. Allow notifications to keep the Stop control easy to find.
6. Leave the setup screen and say **JoJo**. A verified wake starts the animated
   edge fog. The center animation is optional in the phone dashboard. Say a complete command, e.g. “JoJo calculator kholo”.

`adb reverse tcp:8000 tcp:8000` must be repeated after disconnect/reboot. No public
tunnel is required. The default API stays on laptop loopback. The companion only
allows cleartext to localhost, not arbitrary remote hosts.

## What this version does

- Captures speech into RAM, sends PCM16 audio to the paired laptop, verifies its
  owner profile and recognizes Hindi/Hinglish. Raw audio is not saved by JoJo.
- Captures visible accessibility text **after** wake and voice verification.
  Password fields are omitted. Image/canvas-only app content is not understood.
- Executes one observed node click, text entry, scroll, back or allowed installed
  app launch at a time, then sends a fresh screen/result for verification (up to
  24 actions / 5 minutes). Phone calls, SMS, WhatsApp and sharing use the app's own
  visible controls, with exact recipient/content from the user. Ambiguous contacts
  or unlabelled photos require a user selection; images are not visually classified.
- Opens Contacts, dialer, Messages, Gallery and specific Settings pages through
  native Android intents. OEM apps can lack these handlers or expose incomplete nodes.
- Opens/searches Amazon and Flipkart apps. For a missing app, resolves its package
  against the official Play Store, reads its real title, then asks the owner before
  installation. A verified “haan” is scoped to that phone/session/app for 90 seconds.
  The companion opens its exact Play Store details page and permits one unambiguous
  free Install click; downloads are observed, never treated as already successful.
  If the package is unknown, supply its Play Store link. Paid apps, account prompts,
  incompatible apps, network failures and extra install dialogs require manual help.
- Checks foreground package, target label and launch package against restricted
  names; blocks Paytm, Binance, Trust Wallet and known financial apps. Amazon is
  allowed under the updated policy. Checkout/Pay/Buy now/Place order targets stop
  automation. Recognized payment/credential screens are withheld from the backend,
  with “Ab aap kijiye…” handoff. These are text/package heuristics, not an OS sandbox.
- Binds phone sessions to a locally generated installation ID. A different phone
  cannot reuse the session or installation approval. Phone control has no laptop fallback.
- Saves completed/partial conversations and task steps in the laptop journal.
- Shows a native, touch-through accessibility overlay with the same continuous
  cyan/violet/pink fog field and status speeds as the laptop, plus a persistent microphone
  notification. Stop from the notification or app to release the microphone.

## Limits and validation

### Inbox conversation

- Say “JoJo WhatsApp par kiski chats unread hain, messages padh kar batao”. JoJo
  navigates the requested app's visible unread list/chats and reads observed sender
  names and text. Opening a chat may mark it read. It reports the inspected view;
  bounded scans, truncated text, hidden/locked chats and image/voice messages are not
  a complete inbox audit. It does not monitor/announce incoming notifications in the background.
- Say “JoJo kiska call aaya?” for the default dialer's recent/missed calls screen,
  or ask specifically for WhatsApp calls. “Kiska SMS/message aaya?” uses the default
  SMS app. JoJo reads visible status/time when exposed; it never calls back during reading.
- After reading messages: “Sir, koi reply karna hai kya?” → “haan” → recipient
  selection if needed → “kya reply karna hai?” → dictated text. “Usko ye reply kr …”
  also supplies a direct reply when a single recipient is in context.
- “Na/nahi” leaves that app for Home. It does not force-stop WhatsApp or turn off
  its notifications. Owner verification and the same phone/session are required
  for every follow-up; sleep, expiry or failed owner match revoke pending context.
- The native service checks chat heading and exact draft before sending, reserves
  one send attempt, then looks for the text outside the editor in that chat. It
  reports uncertainty rather than retrying a send. This does not prove delivery/read.
  Apps with inaccessible headings/composers require manual help.

The 0.2.0-alpha.2 local test APK includes these inbox changes.
Java-only validation: `python android/check_java.py --sdk PATH_TO_ANDROID_SDK`.
This compiles classes and parses the manifest without packaging/signing an APK.

Default-app identification uses Android's
[SMS package API](https://developer.android.com/reference/android/provider/Telephony.Sms)
and [dialer package API](https://developer.android.com/reference/android/telecom/TelecomManager).
No SMS database or call-log permissions are requested. Notification-listener access is optional and must be enabled manually for notification summaries.

APK compilation, signing and alignment verification passed on 10 October 2026 for version 0.2.0-alpha.2 (version code 2). Physical phone
installation, microphone quality, manufacturer battery restrictions and actual
accessibility behavior still require a connected phone test. Apps can refuse
accessibility actions. Saved-PIN entry is opt-in and limited to supported authentication screens; first unlock after reboot remains manual. Payment automation is blocked by policy.

The laptop now uses a trained local WeSpeaker neural speaker embedding model.
Re-enroll your voice for 9 seconds in desktop Settings after this upgrade. It does
not provide liveness detection and may reject the owner across microphones or accept
a replayed voice. Owner/other-speaker recordings on the actual devices are still
needed to calibrate and validate exclusive-owner behavior. Recognition/reasoning
need internet. Voice matching runs locally on the paired laptop.
The app deny-list is defense in depth, not an OS-enforced security boundary or a
complete catalog of all finance apps.

## Build

With Android SDK platform/build-tools 35 and a JDK installed:

```powershell
python android/build_local.py
```

This offline builder uses aapt2, javac, D8, zipalign and apksigner, then verifies the
APK. Output: `app/build/local/JoJo-debug.apk`. A local debug signing key is generated
under the ignored build directory and reused on subsequent builds. This is a local
development build, not a Play Store release. Standard Gradle project files are
also included (AGP 8.13, Gradle 8.13+, compatible JDK).

Platform references: [Android intents](https://developer.android.com/guide/components/intents-filters),
[Play Store app links](https://developer.android.google.cn/distribute/marketing-tools/linking-to-google-play?hl=en),
[AccessibilityService](https://developer.android.com/reference/android/accessibilityservice/AccessibilityService),
[Android Gradle plugin 8.13](https://developer.android.com/build/releases/agp-8-13-0-release-notes).

## Stop and uninstall

New source controls include **Local essentials — without laptop** and opt-in
**Notification summaries**. See [commands, permissions and limitations](../JOJO_WORKSPACE.md#android-source-additions).
These additions have Java/manifest validation but still need physical-phone testing.

The native dashboard now has **Stop JoJo** and **Uninstall JoJo**. Stop disables
listening/resume until Start is tapped. Uninstall opens Android's system removal
confirmation; it does not erase the laptop or Firestore. See
[removal scope](../JOJO_UNINSTALL.md). These controls are included in the 0.2.0-alpha.2 local test APK.


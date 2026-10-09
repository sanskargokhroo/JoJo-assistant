# JoJo native Android companion

Native Java/Canvas app for Android 11+. No browser/WebView. The APK currently uses
the laptop's AI service over a USB connection; standalone phone reasoning and
wireless deployment are not implemented.

Latest source-only feature: optional phone-local encrypted numeric PIN vault and
saved-PIN entry on supported normal authentication screens. See
`../JOJO_PIN_AND_SYNC.md` for opt-in setup, security tradeoffs, supported targets,
Firestore synchronization and remaining device tests. The existing APK does not
include this change; the user deferred APK generation until the final build.

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
   edge lights and center orb. Say a complete command, e.g. “JoJo calculator kholo”.

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

### Inbox conversation (source changes after the last APK)

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

No new APK has been generated for this inbox change, per the user's instruction.
Java-only validation: `python android/check_java.py --sdk PATH_TO_ANDROID_SDK`.
This compiles classes and parses the manifest without packaging/signing an APK.

Default-app identification uses Android's
[SMS package API](https://developer.android.com/reference/android/provider/Telephony.Sms)
and [dialer package API](https://developer.android.com/reference/android/telecom/TelecomManager).
No SMS database/call-log permissions or notification-listener access are requested.

APK compilation and signing verification passed on 8 October 2026. Physical phone
installation, microphone quality, manufacturer battery restrictions and actual
accessibility behavior still require a connected phone test. Apps can refuse
accessibility actions. No lock-screen unlocking or payment automation is included.

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

## Stop and uninstall (source only)

New source controls include **Local essentials — without laptop** and opt-in
**Notification summaries**. See [commands, permissions and limitations](../JOJO_WORKSPACE.md#android-source-additions).
These additions have Java/manifest validation but still need physical-phone testing.

The native dashboard now has **Stop JoJo** and **Uninstall JoJo**. Stop disables
listening/resume until Start is tapped. Uninstall opens Android's system removal
confirmation; it does not erase the laptop or Firestore. See
[removal scope](../JOJO_UNINSTALL.md). No APK has been generated for these changes.


# Saved PINs and shared memory — source changes, no new APK

## What is implemented

The Android app now has **Local encrypted PIN vault** in its native setup screen.
Authenticate with the phone's existing lock first. Select this phone or a specific
installed, non-financial app and enter its numeric PIN (4–16 digits). Saving enables
automatic use for that target during an owner-verified JoJo task. Delete disables it.
Screen capture is blocked for the editor, listening stops during setup, autofill and
keyboard learning are disabled for the PIN input, and saved PINs cannot be revealed
or exported through JoJo APIs. Do not dictate or paste PINs into chat/voice commands:
speech recognition uses an online service. Use the local editor only.

PIN ciphertext uses AES-256-GCM with a random IV and Android Keystore key; scope and
installed signing certificate are authenticated as associated data. The encryption
key is non-exportable through the normal app API. Hardware backing depends on the
device. Android backup is disabled. PIN values never go to the laptop, model prompt,
task journal, logs or Firestore through this vault flow. This is encryption at rest;
the native input path briefly needs plaintext in memory to submit it to the OS/app.

The key intentionally does not require a fresh biometric for every decrypt, because
that would prevent unattended saved-PIN entry while locked. This trades away some
protection of manual PIN entry. Existing speaker matching is **not replay-proof**;
a convincing replay, compromised/rooted device or compromised trusted backend is
outside the protection this feature can promise. It is opt-in, per target, not a
guarantee that nobody else can ever unlock the device.

## Unlock behavior and limits

- “JoJo unlock phone”: after voice verification the native app requests the normal
  system authentication screen, then attempts the saved PIN on a recognized System
  UI PIN field or keypad. It verifies Keyguard state afterwards. OS background
  launch/wake limits or inaccessible OEM controls may prevent this; manual unlock
  is then required. First unlock after reboot must be manual.
- “JoJo unlock WhatsApp”: opens the configured app's normal screen and uses an
  accessible PIN entry if the installed app actually provides one. “Unlock app”
  refers to the foreground app. A saved app lock encountered during another verified
  task can be unlocked before the original task resumes with a fresh observation.
- A fingerprint-only screen is not a PIN screen. No fingerprint simulation, app
  lock bypass, recovery-code use or WhatsApp two-step-verification reset is provided.
  Third-party/OEM app-lock packages need their own explicit compatible target setup;
  a WhatsApp entry does not authorize entering its PIN into another package.
- Each grant is short-lived and tied to the paired phone's owner session. It is
  emitted by the verified backend branch, not by model tool output. A partial,
  wrong or uncertain PIN attempt is not retried automatically. Authenticate manually
  and re-save the entry locally to re-enable that target after an unresolved attempt.
- Numeric PINs only in this version. General app passwords, Windows secure-desktop
  login and laptop-to-phone unlock dispatch are not implemented. Mobile and laptop
  tasks keep their own source; no silent substitution of one device for the other.

## Firestore: actual architecture

Both devices use the **same laptop backend** and shared local SQLite journal.
The phone is still a USB-connected companion, not a standalone Firestore client.
Previous Firebase profile/reminder/conversation code did not synchronize the entire
new native journal. A persistent outbox now synchronizes new journal turns, saved
workflow instructions and owner corrections for both sources to:

`jojo_memory/{JOJO_MEMORY_NAMESPACE}/turns|workflows|corrections/{stable-id}`

Default namespace: `primary`. Firestore uses the existing laptop service credential;
no service-account key is bundled into Android. Mobile records include source and
device ID, with shared memory separate from target selection. Offline writes queue
locally and retry idempotently. `/api/memory/sync` exposes pending count, last success
and error type. Local memory clear queues deletion of corresponding cloud documents.
PIN vault data, audio and credentials are excluded. Cloud copies of ordinary
conversation text are not end-to-end encrypted by this feature.

Read-only connectivity on 8 October 2026 succeeded for `your-configured-project`. Outbox
writes/deletes are tested using fixtures; live writes have not been exercised.
Restart the backend to start the worker. Existing historical journal/vector data
is not automatically backfilled, and remote Firestore restore/multi-backend merge
is not implemented. Shared recall works through the common laptop database.

No APK was generated for these changes. Java compilation and mocked backend tests
do not establish real-phone unlock reliability or replay resistance. Physical-device
tests are still required before relying on this feature.

Sources: [Android Keystore parameters](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec),
[key use while locked](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec.Builder),
[Keyguard authentication UI](https://developer.android.com/reference/android/app/KeyguardManager),
[Firestore writes](https://firebase.google.com/docs/firestore/manage-data/add-data).

# One-time startup and background listening

## Windows

Run `python jojo_start.py` or double-click `start_jojo.bat` once. This installs a
current-user Startup entry and launches the native desktop. Re-running is safe:
the same entry is updated and the desktop/core instance locks prevent duplicates.
The installed entry uses this Python installation and this project directory;
run setup again if you move the folder or replace Python.

At Windows sign-in JoJo starts hidden and waits for the verified owner's “JoJo”.
If voice enrollment is missing, the setup window opens. Closing the dashboard
keeps it running. Settings → Quit stops it until the next login/manual launch.
`python jojo_start.py --disable-autostart` removes future login startup without killing
an active assistant. `--install-only` registers startup without launching it.
Startup happens **after sign-in**, not at the Windows password screen. A powered
off, sleeping or hibernating laptop cannot hear this assistant; resume the device
normally. No reboot/login was performed during validation.

## Android — source changes, no new APK

After installing a future updated APK, pair it and enable microphone, notifications
and accessibility, then tap **Start listening** once. Listening is a visible
foreground service: closing the screen or removing the app from Recents does not
intentionally stop it. A timed, renewed partial wake lock keeps listening work
running with the display off; this uses battery. Android can restart the sticky
service after reclaiming its process, but OEM battery management can still stop it.
Use the app's battery-settings button to review system restrictions if necessary.

On reboot or app update, opted-in users receive **Resume JoJo listening**. Tap it
and unlock the phone normally to resume the microphone. Modern Android forbids
starting this microphone foreground service directly from boot. If notifications
are denied, reopen JoJo. Force-stop also requires reopening; JoJo does not defeat
an explicit OS stop. Stop listening (in app or notification) disables automatic
resume on reopening and the reboot reminder until you tap Start again. Opening
the PIN vault also stops/disables listening; restart it manually after editing.

The phone still needs the running laptop backend and USB connection. Laptop
startup now restores `adb reverse tcp:8000 tcp:8000` every 15 seconds if missing,
only on already USB-authorized devices with the JoJo package installed. ADB must
be installed in the standard Android SDK location, ANDROID_HOME, or PATH.
It never accepts a USB-debugging authorization prompt for you. Set
`JOJO_DISABLE_USB_RECONNECT=1` to disable the helper. No USB bridge is started for
non-default test ports. Independent phone operation while the laptop is off is
not implemented. Wake recognition/AI still require internet.

Validation: startup-file idempotence/path tests, USB restoration/skip tests,
Java compilation and backend startup smoke test. Actual reboot, screen-off voice,
OEM process termination and phone reconnect need physical-device testing. No APK
was generated.

Android reference: [microphone foreground service restrictions](https://developer.android.com/develop/background-work/services/fgs/service-types#microphone).

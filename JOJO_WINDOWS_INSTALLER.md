# JoJo Windows installer and controls

JoJo-Setup.exe is an unsigned x64 Windows setup/launcher. It bundles an audited
source snapshot and a CPython runtime (with its license). It does not bundle accounts,
voice profiles, conversations, site-packages or the developer's Firebase project.

1. Run the installer and select **Install / update**. No administrator access is requested.
2. In setup, install dependencies and the local voice model (internet required).
3. Configure your own provider/model/API key and optional Firebase service account.
4. Open JoJo, enroll your voice, and select microphone and skills in the dashboard.

Installs to %LOCALAPPDATA%/Programs/JoJo. Start menu > JoJo opens the dashboard.
JoJo.exe --cli opens interactive terminal setup. JoJo-Setup.exe --verify
checks the embedded payload. Installation does not enable login startup by itself;
the setup launch step can enable it unless previously disabled.

Controls:
- **Ctrl+Alt+J**: Windows Start menu launch shortcut. Starts JoJo even after
  deactivation, without re-enabling login startup. Say JoJo after it starts;
  this shortcut does not bypass the wake word or owner verification.
- **Ctrl+Shift+J**: stop current and queued laptop tasks and speech, hide overlay,
  return to JoJo wake-word mode. Already executed actions are not undone.
- **Ctrl+Shift+Q**: deactivate, stop the app, remove JoJo's login startup entry.
  Account data stays. Open the app manually when wanted.
- **Settings > Show center orb and status**: off by default; edge fog remains.
- No inactivity timer cancels tasks.
- **Stop JoJo** exits for this session. **Deactivate** also disables login startup.
- **Uninstall JoJo** is a separate destructive workflow with confirmation.

Stop/deactivate shortcuts require the dashboard process to be running. The launch
shortcut is handled by Windows Explorer while signed in. If Windows reports a
shortcut conflict, use the dashboard buttons. Shortcuts do not operate on the Windows
secure desktop. The emergency exit scopes process termination to this installation's
backend and its child processes; it does not terminate unrelated Python programs.

The initial dependencies/model download is not an offline installation. This is an
alpha, unsigned installer, not a Microsoft Store or signed production release.
Bundled-runtime extraction, fresh venv creation, full dependency/model installation,
model checksum, pip dependency consistency and isolated no-voice/no-cloud backend
startup/API/shutdown passed on October 15 using the published installer;
installation on an independent clean Windows PC is still needed.

Build: python jojo_build_windows.py using an installed CPython 3.14 Windows x64
runtime and .NET Framework C# compiler. Output: jojo_release/windows/JoJo-Setup.exe.
The existing APK remains Android 11+. Updated Android source targets 8.1+, but
a new APK and physical-phone tests are deferred. The Windows installer does not
install the phone companion.

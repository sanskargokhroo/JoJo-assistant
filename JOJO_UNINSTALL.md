# Stop and uninstall controls

## Stop JoJo

The desktop dashboard now has **Stop JoJo**, separate from **Stop task**.
Stop JoJo bypasses the command queue, disables automatic core launch in this
dashboard, cancels active and queued tasks, stops speech, closes the microphone
and requests backend shutdown. The desktop closes after confirmation. A failed
request is reported as unconfirmed, not as a successful stop. OS actions already
started cannot be undone. Login startup remains installed; a future Windows login
or manual launch starts JoJo again. Disable login startup separately if desired.

Android **Stop JoJo** immediately revokes the local running loop, interrupts
recording/network work and TTS, hides the overlay and stops the foreground service.
It also disables saved startup/resume preference. Tap Start listening to resume.
Stop affects the device where the button was pressed; it is not a remote global
kill switch for every paired device.

## Uninstall JoJo

This is an explicit native UI operation, never an AI tool or chat command.

On Windows the dialog shows the resolved install folder (currently `C:\JoJo`).
Type **DELETE** and press Permanently uninstall to remove that entire folder,
including source and Git history, APK builds, local memory, voice profiles,
credentials, caches and logs, plus the current user's JoJo startup entry.
A detached PowerShell helper validates paths before removal, refuses linked
files/directories, and stops only recognized JoJo Python entrypoints from that
folder. The standard `%LOCALAPPDATA%/JoJo` private directory is also shown and
removed for new installs. A custom external JOJO_DATA_DIR is refused instead of
recursively deleting an unrelated location.

An optional checkbox also deletes shared Firestore memory in the configured
jojo_memory namespace and the explicitly listed legacy JoJo collections:
user_profile, learned_skills, conversations, notes, reminders and
jojo_remote_commands. It affects shared data used by both devices. It does not
delete the Firebase project, other namespaces or provider backups/retention data.
Cloud cleanup failure aborts local folder removal so credentials/code remain for
retry; some cloud records may already have been removed. Startup is disabled.
Other JoJo backends must be stopped to prevent repopulating shared cloud data.

Android opens the OS uninstall confirmation for this app after stopping JoJo and
disabling its accessibility service. Confirm there, without choosing Keep app
data if offered, to remove the app and its private data/PIN vault. Cancelling
leaves the app installed but stopped; accessibility may need re-enabling.
Phone uninstall does not remove laptop files or cloud memory; use the laptop
dialog for those. Each device must be uninstalled separately.

No app can truthfully promise to erase all traces everywhere. Shared Python,
Android SDK/JDK, downloaded APK copies outside the install folder, backups,
other Windows users' installations and OS history are not automatically removed.
The temporary uninstall helper/result report remains under the user's Temp
folder (`JoJo-uninstall-*`) for troubleshooting. Deleting files is not forensic
secure erasure. The helper reports errors/partial removal instead of claiming
success if any installation files remain.

Validation is non-destructive: unit tests use temporary marker files and mocked
Firestore/process interfaces; PowerShell syntax is parsed and Android Java is
compiled. No live uninstall or cloud deletion was performed. No APK generated.

# Your data belongs to your installation

Private-session scope, notification previews and new workspace storage are explained
in [the workspace privacy section](JOJO_WORKSPACE.md#private-session). Workspace
memory/indexes and conversation handoffs are local; they are not automatically synced
to Firestore. Knowledge excerpts can reach your chosen model when requested as context.

JoJo is a bring-your-own-account application. No developer API keys, Firebase
service account, owner voice embedding, memory database or chat history belong in
the source distribution. Run `jojo_release.py --check` before publishing.

New Windows installs store private settings and memory in `%LOCALAPPDATA%/JoJo`.
Existing installations retain their existing local data directory. API keys and
the optional Firebase service-account JSON entered in setup are encrypted with
Windows current-user DPAPI. Other programs running as that Windows user may still
be able to decrypt them. Do not upload or share your private data directory.

Firebase is optional. For cloud sync, select **your own** Firebase service-account
JSON from your project settings; a Firebase web API key is not a substitute for a
server credential. It stays on your laptop, never inside the Android APK. Use a
dedicated Firebase project, restrict its IAM permissions and monitor usage.
Local-only setup does not initialize a developer's Firebase account.

Private does not mean offline: recognition currently uses Google's online speech
recognition service, model requests go to the provider you select, and online TTS
may be used. Screen text/images and relevant owner/memory context can be sent for
your requests. Firebase sync copies conversation/workflow data to your own project
when configured. Ordinary cloud memories are not end-to-end encrypted by JoJo.

The neural owner voice profile remains local. It can falsely accept or reject
speakers and has no proven liveness/replay protection. Read-aloud enrollment is
a guided recording, not proof against cloned or replayed voices. Local typed
dashboard commands remain available to the logged-in Windows user.

If any credential was ever committed, deleting the latest file is insufficient:
rotate/revoke it, remove sensitive Git history before public distribution, and
check branches/tags/releases/artifacts. The release exporter creates a clean
source-only snapshot without Git history. It does not rewrite a remote repository
or revoke credentials automatically. Do not make an old repository public until
its history has been audited and cleaned.

# JoJo naming

The main launcher is `jojo_start.py`; `start_jojo.bat` calls it. The existing
`start.py` remains a thin compatibility entrypoint. Windows login startup still
launches `jojo_desktop.py`, so the registered startup entry remains valid.

31 first-party Python modules/helpers/launchers were renamed with JoJo names,
including the research/tool suite and modules under jojo_agi and jojo_skills.
Imports, scripts, tests and documentation were updated together. Research prompts,
tool descriptions and overlay comments now use JoJo branding. Future generated
skill filenames use the jojo_ prefix; executable skill generation remains subject
to the existing restrictions.

Framework conventions such as __init__.py, AndroidManifest.xml, build.gradle,
README.md and requirements.txt stay valid. Generic Android component names are
stable to preserve installed activity/accessibility-service identities. Actual
dependency/model names, browser profiles, credentials, saved conversation content,
Git history and existing APK/build artifacts are not rebranded. Original source
attribution is retained in JOJO_THIRD_PARTY_NOTICES.md; it is not assistant branding.

No APK was built. Restart the desktop backend to load the renamed source modules.

# JoJo workspace and reliability upgrade

These are experimental source features, with
automated fixtures rather than a claim of universal app control or AGI.

## Native desktop controls

Open **Workspace** beside Owner setup in the native dashboard.

- **Memory cards:** add, edit and remove preferences, corrections and project notes.
  Cards are local and included as untrusted context in relevant model requests.
  This editor manages workspace cards, not every older semantic/profile database.
- **Knowledge:** select individual TXT, Markdown or text-based PDF files. Search
  returns excerpts with file/page citations. No folder crawl or automatic upload
  occurs. A model can request indexed excerpts when answering your document question.
  Reindex after edits; scanned PDFs need external OCR. Limits: 20 MB, 300 PDF pages,
  2 million extracted characters per file. The index is local plaintext SQLite.
- **Routines:** create a draft, or select a past task and choose Make routine draft.
  The model's `draft_workflow` tool can also propose instructions. Review and enable
  before Run. Editing revokes approval and removes its schedule. This is instruction
  reuse, not recording mouse gestures or installing generated executable code.
- **Schedules:** explicitly approve recurring runs every 5–120 minutes. Runs happen
  only while the desktop core is running. Restart resets the next due time; missed
  runs and failed submissions are skipped, not caught up. A pending run does not
  overlap the next run of the same routine. Disable stops future scheduled runs;
  use Stop task to cancel work already queued or running. Scheduling can incur model
  API charges and performs the approved routine without another voice prompt.
- **Tasks & recovery:** inspect saved action observations, rate results, save an
  owner correction, or Continue / correct a terminal unfinished task. JoJo starts a
  new task with prior evidence and fresh observations. It never automatically resumes
  after a crash. Unknown-result sends, calls, installs or destructive actions must
  be inspected or clarified, not blindly repeated. This is replanning, not exact
  instruction-pointer restoration.
- **Handoffs:** transfer conversation context between laptop and phone. On the phone,
  say `JoJo continue on laptop`; review and accept in the desktop Handoffs tab. From
  a laptop history row choose Continue on phone, then say `JoJo continue laptop task`
  in the verified paired phone session. Handoffs expire after 30 minutes and are
  consumed once. If several phone handoffs exist, discard extras on the dashboard.
  Documents/attachments are **not** transferred; the destination asks for missing files.
- **Permissions:** temporarily allow or block a capability for 15 minutes. The saved
  setting resumes at expiry or restart. Individual tool switches remain in Skills &
  plugins. These are JoJo capability checks, not OS sandbox permissions.
- **Undo files:** restore an original from an eligible JoJo text edit. Originals use
  Windows current-user DPAPI and are capped at 30 entries. Supported existing files:
  TXT/MD/JSON/CSV, at most 2 MB. Private mode creates no backup. Undo refuses modified,
  moved or linked targets and verifies restored bytes. It does not undo GUI actions,
  messages, installs, new files or arbitrary changes by other programs.
- **Reliability:** view recorded outcomes, frequent failing tools and owner-rated
  success. Model completion status is not independent proof of success. Corrections
  influence later context; the assistant does not retrain or rewrite its own model.

## Execution changes

The tool loop publishes a remaining-step plan, journals action intent before the
call, and records returned observations afterward. Known file writes require a
read observation; GUI changes require a fresh screen observation; smart-home changes
require another device-state read before finish. Repeated identical mutation calls
are blocked until a new observation. Model connection retries do not replay actions.
These checks improve observability but do not prove that every user requirement was
met or that a screenshot was interpreted correctly.

Task progress is saved during work, not only when it ends. Privacy tasks suppress
this persistence. Device-scoped conversation recall reduces phone/laptop confusion.
Owner corrections and ambiguous references reach the planner, which must clarify
uncertain recipients before messaging.

Desktop Settings includes **Headphone interruption**. When enabled, say JoJo while
it speaks; the owner voice check still applies before following a command. This is
an opt-in microphone path, not acoustic echo cancellation. Use headphones. It needs
real microphone testing and does not add simultaneous listening to Android TTS.

## Private session

Turn on Private session in Workspace, or say `privacy on` / `private mode on`.
`privacy off` restores normal behavior. New private tasks do not persist their
conversation, learning records or action traces, even if privacy is switched off
before that task finishes. Workspace memory/index/routine writes are refused and
saved conversation/knowledge recall is suppressed. Desktop private speech uses the
offline voice fallback instead of saved MP3 cache; HTTP cached TTS is disabled.
Scheduled work is skipped while privacy is on.

This is **not** a guarantee of zero disk traces or offline execution. Existing data,
explicit file/reminder actions, application/OS logs, external providers and third-party
app histories are outside that promise. Phone recognition and full AI tasks still
use the paired backend and online services. Previously queued Firebase sync can still
finish. Workspace cards, indexes, undo originals, schedules and handoffs are local;
they are not added to the existing Firestore conversation/workflow sync.

Clearing conversation history also clears action traces, outcome feedback and pending
handoffs, plus legacy QA/episode/behavior caches. Explicit cards, knowledge files,
routine definitions and file-undo backups are separate controls. SQLite deletion is
logical deletion, not certified secure erasure; previous backups may retain data.

## Android source additions

**Notification summaries** are off by default. Select a package allowlist and enable
JoJo notification access in Android settings. New allowed notifications are kept in a
bounded, deduplicated RAM buffer while listening is enabled and the phone is unlocked.
Say `JoJo notifications` or `JoJo notifications batao` in an owner-verified session.
Only then are previews sent to the backend for a deterministic summary. The buffer
is not the complete inbox; sensitive-text filtering is heuristic. No automatic
notification reply or background spoken announcement is enabled. Existing observed
WhatsApp reply flows remain separate. Stop clears the notification buffer.

**Local essentials — without laptop** uses Android device authentication, then typed
commands or optional on-device tap-to-talk. Supported commands: `time`, `date`,
`battery`, `lock phone`, `open <exact installed app name>`, `timer <1–180 minutes>`.
Recognized speech is a draft: tap Run after reviewing it. Speech needs Android 12+
and an available installed on-device recognizer/language; otherwise type. No cloud
speech fallback is used in this mode. It stops the paired background listener and
does not implement autonomous offline wake-word or speaker-embedding authentication.
Leaving the activity ends local authentication. Restricted apps remain blocked.

No APK was generated for these changes. Java compile and manifest checks do not
replace phone tests. Full standalone Android reasoning, offline background wake,
file transfer, Android voice barge-in, universal smart-device support and automatic
self-training are **not** implemented by this upgrade.

Platform references: [on-device speech](https://developer.android.com/reference/android/speech/SpeechRecognizer),
[notification access](https://developer.android.com/reference/android/service/notification/NotificationListenerService),
[device authentication](https://developer.android.com/reference/android/app/KeyguardManager),
[timer intents](https://developer.android.com/reference/android/provider/AlarmClock).

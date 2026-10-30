# JoJo native control center

The desktop uses a compact sidebar and conversation workspace. Settings are grouped into Voice & appearance, Connections, and Privacy & security. Existing owner enrollment, model/Firebase setup, skills, workspace, security checks and lifecycle controls remain reachable.

Android uses Home, Connect, Skills and Settings tabs with an always-visible phone Stop control. It identifies the current phone from the device model. Redmi 12 5G is the intended primary device; the connected vivo is a trial device. Redmi hardware behavior has not yet been tested.

Saved pairing keys are not prefilled or displayed. Change pairing opens an empty password field; Remove pairing stops this phone and removes its saved key. Android settings windows prevent screenshots. Desktop pairing is masked by default with an explicit reveal control.

The paired phone can update shared skill categories, the task-memory switch and encrypted model credentials. Model changes require a backend restart; environment settings still override saved account settings. Firebase credentials, detailed tool switches, voice enrollment and full memory review/deletion remain available in the PC controls. Phone AI still requires the paired laptop backend and USB transport.

Each mobile voice command already passes the enrolled-speaker check. Voice embeddings are not replay-proof authentication. Task memory stores outcomes for relevant retrieval, not executable action recordings; a disabled memory switch or private session skips new outcomes. Credential-bearing requests/replies are excluded. Previously stored data is not automatically removed by turning memory off.

## Brand asset

`assets/jojo_jj_hd.png` is the generated high-resolution double-J master, also used by the desktop and Android icon. Built-in image generation was used with this prompt:

> Create a polished square high definition app icon for JoJo personal assistant. Exact monogram JJ, two clearly distinguishable uppercase J letters side by side, custom geometric rounded lettering in luminous cyan and soft lavender, deep midnight navy background, subtle restrained edge glow, premium minimal professional technology identity. Center the mark with generous icon safe margins. Flat front view, crisp shapes, no mockup, no additional text, no phone, no busy patterns.

Validation: Android local build/signature checks; 242 regression tests; desktop preview; vivo dashboard launch and visible navigation labels. No Redmi live or voice-spoof resistance test has been performed.

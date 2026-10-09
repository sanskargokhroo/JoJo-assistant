# Contributing to JoJo

Start with a small reproducible issue. Include OS, Python version, selected
provider/model and sanitized logs. Never attach API keys, service-account JSON,
voice recordings, personal screenshots or memory databases.

For changes: run `python -m unittest discover -s tests`,
`python tests/smoke_local_server.py` and `python jojo_release.py --check`.
Android contributors can run `python android/check_java.py --sdk YOUR_SDK`;
this does not generate an APK. State which behavior was tested on real hardware.

Preserve payment handoffs, device scoping, cancellation and tool permission checks.
Add a regression test when changing those boundaries. Do not describe heuristic
controls as guaranteed security or this assistant as verified AGI.

Useful contributions: native accessibility compatibility, speech robustness,
provider integration fixtures, setup accessibility, translations and documentation.
Stars and sharing are welcome if JoJo is useful; no fake metrics or star exchanges.

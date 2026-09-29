# GitHub-hosted runners

*[Auf Deutsch](hosted-runners.de.md)*

`.github/workflows/hosted-runner-check.yml` is a hand-triggered check, one
matrix leg per candidate runner. It runs `abgal setup`, `doctor`, `create`,
`start` and `status`, holds the guest for 15 minutes under load, and on
`self-hosted` also starts and probes the web UI, since only that runner
sits on a reachable network. See #94.

`ubuntu-slim` was tried and dropped: its container has a fixed single CPU
core, below what the emulator requires. No arm64 leg is listed, the
`android` CLI has no arm64 build upstream, a dead end tracked in #113.

## Result

| Runner | doctor | Guest boots | 15 minute hold | Result |
|---|---|---|---|---|
| `ubuntu-latest` | passed | yes | passed | Runs the full cycle, web UI not reachable from this runner, skipped by design |
| `ubuntu-26.04` | passed | yes | passed | Runs the full cycle, web UI not reachable from this runner, skipped by design |
| `self-hosted` | passed | yes | passed | Runs the full cycle, web UI started, reachable and controllable |

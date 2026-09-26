# The AbGal guide

Start with the [quick start](../README.md#quick-start). It takes you from a
fresh clone to a running guest in four steps. The pages here are for what
comes after.

| Page | Read it when |
|---|---|
| [Templates](templates.md) | you want another screen, Android version or memory size |
| [How it works](how-it-works.md) | a command did something you did not expect |
| [Troubleshooting](troubleshooting.md) | a command ended with `ERROR` |
| [View and control from a browser](view-service.md) | you want to use or understand the web UI as it works today |
| [Dashboard design](dashboard-design.md) | you want to know the web UI's target layout |

## A guest's life

Every command moves a guest from one state to another, drawn in the root
README's [Lifecycle](../README.md#lifecycle).

A template is a line of text. A guest is a folder under `avd/` with a disk of
its own, made from that line. A running guest is an emulator process with a
serial like `emulator-5554`, which `adb` and every test tool can talk to.

## A day with AbGal

Two guests for a test run, then gone again:

```bash
./abgal create phone-1080x2400-480-api35-x86_64 --as ci --count 2
./abgal start -n ci-01 -n ci-02
./abgal status
./abgal stop -n ci-01 -n ci-02
./abgal delete -n ci-01 --yes
./abgal delete -n ci-02 --yes
```

`start` boots them one after another and checks the memory before each one.
`status` lists the serial of each guest, which is what the test tool needs.
`delete` takes one guest per call.

A guest can also keep its disk between runs. `abgal start -n dev --wipe`
boots it as if it were new, without creating it again.

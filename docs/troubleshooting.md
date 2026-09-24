# Troubleshooting

Each section starts with what AbGal prints. Search this page for the first
words of your error.

## The SDK is missing

```text
ERROR: the Android SDK is not under .../abgal/sdk.
       Both platform-tools/adb and emulator/emulator have to be there.
```

`./abgal setup` has not run, or the SDK was put into another folder. `sdk/`
has to sit next to the `abgal` file. `./abgal doctor` names each part that is
missing.

```text
ERROR: avdmanager or android is not under .../sdk/cmdline-tools/latest/bin.
       The command line tools 23.0 or newer belong in sdk/cmdline-tools/latest.
```

Either the command line tools are older than 23.0, which have no `android`
command, or a zip unpacked by hand went one level too deep. The folder has to
be `sdk/cmdline-tools/latest/bin`, not `sdk/cmdline-tools/cmdline-tools/bin`.

## Setup did not finish

```text
ERROR: nothing fetched, there is nobody to ask.
```

`setup` ran without a terminal, as in a CI job, and could not ask about the
license. Read it at the address `setup` printed, then run
`./abgal setup --accept-licenses`.

```text
ERROR: sdk/cmdline-tools/latest has 19.0, and AbGal needs 23.0 or newer.
```

A part is older than the minimum in `versions.conf`. `setup` does not replace
a folder it did not make. Move it aside, for example to
`sdk/cmdline-tools-19.0`, and run `setup` again.

```text
ERROR: the download has sha1 ..., versions.conf expects ....
```

The zip is not the one `versions.conf` names. Nothing was unpacked and the
download is deleted. Run `setup` again. If the checksum stays wrong, Google
has replaced the file under the same address, and `versions.conf` needs a new
line.

## The device is not listed

```text
ERROR: device phone-1080x2400-480 is not listed in devices.xml.
```

`avdmanager` reads screen descriptions only from `~/.android/devices.xml`.
`create` links that path to the file in the clone, but only when nothing is
there yet. Android Studio writes its own file to the same place. See what is
there:

```bash
ls -l ~/.android/devices.xml
```

If it is a file and not a link into the clone, either copy the `<d:device>`
block from the clone's `devices.xml` into it, or move it aside and run
`create` again, which then links the clone's file.

## Not enough memory

```text
ERROR: dev needs about 2436 MB, 2100 MB are free, and 1024 MB stay reserved for
       the machine. Stop a guest first, or insist with --force.
```

The check counts the guest's `hw.ramSize`, 900 MB on top and 1024 MB for the
machine. Stop a guest, give the template less `ram`, or start with `--force`
and watch `abgal status`. Below 1536 MB a guest swaps.

## The guest did not come up

```text
ERROR: dev did not come up. Last lines of the log:
```

Either the emulator process ended within the first seconds, or it still runs
but its console did not answer within `--timeout`. The lines below the
message come from `logs/<guest>/emulator.log`. In the second case the guest
keeps running and a new `start` reports it as running, so end it with
`abgal stop -n <guest>` first. The most common cause is KVM.
Check that the device exists and that your user is in the group:

```bash
ls -l /dev/kvm
getent group kvm
```

`/dev/kvm` missing means virtualization is off in the firmware or the
`kvm_intel` or `kvm_amd` module is not loaded. Your user missing from the
`kvm` line means the `usermod` from the quick start has not run. A session
opened before the `usermod` is handled by `abgal start` itself.

```text
ERROR: dev is running on emulator-5554 but did not report a completed boot in 300 s.
```

The guest runs but Android has not finished booting. On a slow machine with
`--gpu software` the first boot can take longer. Give it more time with
`--timeout 600`, or look at the guest with
`sdk/platform-tools/adb -s emulator-5554 logcat`.

## The temperature watch did not start

```text
ERROR: ABGAL_TEMP_STOP=9x is not a whole number.
```

One of the `ABGAL_TEMP_*` variables holds something other than digits. No
guest was started. Fix or unset the variable and start again.

```text
ERROR: no processor temperature measurable, so no guest could be watched.
```

Neither the `x86_pkg_temp` zone nor `sensors` gave a value, and no guest was
started. Both readings come from Intel drivers: the zone from the kernel
module `x86_pkg_temp_thermal`, and the line `Package id 0` that the watch
looks for in `sensors` from `coretemp`. On Debian `sensors` comes from the
`lm-sensors` package. An AMD processor has neither, so there the watch cannot
run yet. `--no-watch` starts the guest without it, and then nothing stops it
when the processor gets too hot.

```text
ERROR: the temperature watch for dev ended at once with exit code 1.
```

The guest runs, but nothing protects it from overheating. The message names
the watch's log, and its last line says why, unless the log itself could not
be written, as with an `ABGAL_TEMP_LOG` in a folder you cannot write to. In a
batch no further guest is started. Stop the guest with `abgal stop -n dev`
before you fix it.

## A guest stopped by itself

Look at the temperature watch:

```bash
cat logs/<guest>/watch.log
```

A line `ABORT at 96 C` means the watch stopped it because the processor got
too hot. [How it works](how-it-works.md#temperature-watch) has the thresholds
and how to change them. A guest that stops without such a line ended on its
own; its last start is in `logs/<guest>/emulator.log`.

## Files in your home folder

AbGal keeps the SDK, the guests and the logs in the clone. The SDK tools
write a few things to your home folder anyway. These are the ones seen on the
machine AbGal is developed on:

| Path | Written by | What it is |
|---|---|---|
| `~/.android/bin/`, `~/.android/cli/` | the Android CLI | the CLI itself with its own Java runtime, about 250 MB |
| `~/.android/adbkey`, `~/.android/adbkey.pub` | adb | the key adb uses to talk to devices |
| `~/.android/adb.5037` | adb | which adb program runs the server on port 5037 |
| `~/.android/devices.xml` | `abgal create` | a link to the clone's screen descriptions |
| `~/.android/modem-nv-ram-<port>` | the emulator | modem state, one file per port |
| `~/.android/emu-*`, `~/.android/cache/` | the emulator and the SDK tools | feature flags, update checks, repository lists |
| `~/.android/userid`, `~/.android/analytics.settings` | the SDK tools | an id and the usage data setting |
| `~/.emulator_console_auth_token` | the emulator | the token for the emulator console |

The tools write them again when they are missing. Leave the adb key alone
if you also use a phone over USB: a new key means the phone has to allow this
computer again. Keeping all of it in the clone is planned in
[#32](https://github.com/mohamadmussa/abgal/issues/32).

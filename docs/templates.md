# Templates

A template is one line in `devices.conf`. It describes a class of device, and
every guest created from it gets the same screen, Android version, system image
and memory. This page explains the line, what `create` makes of it, and how to
add one.

## The line

```text
# template                               | device              | api | tag                   | abi    | ram  | note
phone-1080x2400-480-api35-x86_64         | phone-1080x2400-480 | 35  | google_apis           | x86_64 | 1536 | Phone class screen at 480 dpi, Google services without a store
```

| Column | Meaning |
|---|---|
| `template` | The name you pass to `abgal create` |
| `device` | The `<d:id>` of a screen in `devices.xml` |
| `api` | Android API level, 35 is Android 15 |
| `tag` | `google_apis`, `google_apis_playstore` or `default` |
| `abi` | `x86_64` or `arm64-v8a`, spelled as in the system image path |
| `ram` | Memory of the guest in MB. It decides how many guests fit at once |
| `note` | What the template is for, shown by `abgal list` |

The name repeats screen, density, API level and instruction set on purpose, so
it can be read without the table. There is no port column: a port belongs to a
running guest, and the emulator picks a free one at start.

The system image of a template is `system-images;android-<api>;<tag>;<abi>`.
All guests of one template share it on disk.

## What create sets

`avdmanager` creates a guest from the screen in `devices.xml` and the system
image. It drops or overrides several values without a message, so `create`
sets these afterwards in `avd/<guest>.avd/config.ini`:

| Value | After avdmanager | Set to | Why |
|---|---|---|---|
| `PlayStore.enabled` | `no` | `yes` | only for the `google_apis_playstore` tag |
| `hw.ramSize` | `2G` | the `ram` column | `devices.xml` cannot carry it |
| `hw.camera.front` | `none` | `emulated` | the screen description has one |
| `firstboot.bootFromDownloadableSnapshot` | `yes` | `no` | would fetch state from the network |
| `firstboot.bootFromLocalSnapshot` | `yes` | `no` | a run must not depend on the one before |
| `firstboot.saveToLocalSnapshot` | `yes` | `no` | the same in the other direction |

Then it reads the file back and checks thirteen lines: the six above, plus
`abi.type`, `hw.device.name`, `hw.lcd.density`, `hw.lcd.height`,
`hw.lcd.width`, `image.sysdir.1` and `tag.id`. Screen size and density are
taken from `devices.xml`, not from a fixed number, so a tablet is checked
against its own screen. If one line differs, `create` names it and ends with
exit code 1.

## Add a template

A template needs a screen in `devices.xml` and a line in `devices.conf`. If
the screen is already there, skip to step 3.

### 1. Find the system image

List the images for one API level:

```bash
sdk/cmdline-tools/latest/bin/android --no-metrics sdk list --all 'system-images/android-34/*'
```

Each row reads `system-images/android-<api>/<tag>/<abi>`. The three parts go
into the `api`, `tag` and `abi` columns as they are written there. Pick a
`tag` of `google_apis`, `google_apis_playstore` or `default`, and on an x86
machine an `x86_64` abi. An `arm64-v8a` image runs through translation and is
far too slow for a suite.

### 2. Describe the screen

Copy the `<d:device>` block in `devices.xml` and change these values. The
example is a phone with 720 x 1600 pixels at 320 dpi and a 6.5 inch display:

| Value | Example | How to get it |
|---|---|---|
| `d:name` | `Phone 720x1600 320dpi` | free text |
| `d:id` | `phone-720x1600-320` | width, height and dpi, as the existing one |
| `d:x-dimension`, `d:y-dimension` | `720`, `1600` | `adb shell wm size` on the handset |
| `d:pixel-density` | `xhdpi` | `adb shell wm density`, as a name: 160 `mdpi`, 240 `hdpi`, 320 `xhdpi`, 480 `xxhdpi`, 640 `xxxhdpi`. Other values are written as `420dpi` |
| `d:diagonal-length` | `6.5` | the display size in inches |
| `d:xdpi`, `d:ydpi` | `269.93` | sqrt(720^2 + 1600^2) / 6.5 |
| `d:screen-size` | `normal` | width / (dpi / 160) = 360 dp, a phone is `normal` |

The block also names one `d:api-level` and one set of `d:abis`. Keep them in
line with the templates that use this screen. Check that the SDK sees the new
screen:

```bash
sdk/cmdline-tools/latest/bin/avdmanager list device -c
```

If the id is missing, see [The device is not listed](troubleshooting.md#the-device-is-not-listed).

### 3. Add the line

```text
phone-720x1600-320-api35-x86_64 | phone-720x1600-320 | 35 | google_apis | x86_64 | 1536 | Small phone at 320 dpi
```

Keep `ram` at 1536 or above. Below that a guest swaps and app cold starts
take twice as long. Each step up costs room for other guests, see the `ram`
entry in the column list at the top of `devices.conf`.

### 4. Create a guest

```bash
./abgal list
./abgal create phone-720x1600-320-api35-x86_64 --as small
```

`create` fetches the system image the first time a template needs it. For
API 35 on x86_64 that is about 3.5 GB. It ends with the thirteen checks from
[What create sets](#what-create-sets).

The density is the value to get right. An app ships its images as one split
per density, and a guest at 420 dpi loads other images than one at 480, even
at the same resolution.

### Keep your template across updates

`devices.conf` and `devices.xml` are tracked by git, so a `git pull` can
meet your own lines. Either keep them on a branch of your own and merge
`main` into it, or put them aside first:

```bash
git stash
git pull
git stash pop
```

If both sides changed the same lines, git marks the conflict in the file.
Keep both lines, delete the markers, and run `./abgal list` to see that
every template is read. If others need the screen too, send it as a pull
request, see [CONTRIBUTING.md](../CONTRIBUTING.md).

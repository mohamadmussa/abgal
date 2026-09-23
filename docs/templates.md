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

1. If the screen is new, add a `<d:device>` block to `devices.xml`. Copy the
   existing one and change `d:name`, `d:id`, `d:pixel-density`,
   `d:x-dimension`, `d:y-dimension` and `d:diagonal-length`.
2. Add a line to `devices.conf`.
3. Create a guest from it and read the check at the end:

```bash
./abgal list
./abgal create <template> --as <name>
```

`create` fetches the system image the first time a template needs it. For
API 35 on x86_64 that is about 3.5 GB.

The density is the value to get right. An app ships its images as one split
per density, and a guest at 420 dpi loads other images than one at 480, even
at the same resolution.

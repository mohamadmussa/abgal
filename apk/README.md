# apk

*[Auf Deutsch](README.de.md)*

The app packages a run installs. Everything in here is ignored by git, this
file is the one exception.

A modern Android app does not ship as a single file. It arrives as a base
package plus one split per screen density, per architecture and per language,
and the emulator needs the ones that match it. `bin/fetch-app.sh` pulls that
set off a device or emulator that already has the app, and
`bin/install-app.sh` puts it on another one.

## Layout

    apk/
      splits-v<version>-<arch>/
        base.apk
        split_config.<density>.apk
        split_config.<arch>.apk
        split_config.<language>.apk
        PROVENANCE.txt

`PROVENANCE.txt` records where the set came from and when. Without it a set is
just files, and nobody can say later which build was tested.

## Why the files are not committed

Three reasons. They are large, they are binaries that no diff can show, and
they belong to whoever published the app, not to this repository. A run pins
the version in `app.conf` and fetches the files, it does not carry them.

# Fehlerbehebung

*[In English](troubleshooting.md)*

Jeder Abschnitt beginnt mit dem, was AbGal ausgibt. Such auf dieser Seite nach
den ersten Wörtern deines Fehlers.

## Das SDK fehlt

```text
ERROR: the Android SDK is not under .../abgal/sdk.
       Both platform-tools/adb and emulator/emulator have to be there.
```

`./abgal setup` ist nicht gelaufen, oder das SDK liegt in einem anderen Ordner.
`sdk/` muss neben der Datei `abgal` liegen. `./abgal doctor` nennt jeden Teil,
der fehlt.

```text
ERROR: avdmanager or android is not under .../sdk/cmdline-tools/latest/bin.
       The command line tools 23.0 or newer belong in sdk/cmdline-tools/latest.
```

Entweder sind die Kommandozeilenwerkzeuge älter als 23.0 und haben keinen Befehl
`android`, oder ein von Hand entpacktes Zip liegt eine Ebene zu tief. Der Ordner
muss `sdk/cmdline-tools/latest/bin` heißen, nicht
`sdk/cmdline-tools/cmdline-tools/bin`.

## Setup ist nicht fertig geworden

```text
ERROR: nothing fetched, there is nobody to ask.
```

`setup` lief ohne Terminal, etwa in einem CI Job, und konnte nicht nach der
Lizenz fragen. Lies sie unter der Adresse, die `setup` ausgegeben hat, und ruf
dann `./abgal setup --accept-licenses` auf.

```text
ERROR: nothing fetched, the license was not accepted.
```

Die Antwort auf die Lizenzfrage war nicht `y`. Nichts wurde geladen. Ruf
`setup` noch einmal auf, sobald du die Lizenz gelesen hast.

```text
ERROR: sdk/cmdline-tools/latest has 19.0, and AbGal needs 23.0 or newer.
```

Ein Teil ist älter als das Minimum in `versions.conf`. `setup` ersetzt keinen
Ordner, den es nicht selbst angelegt hat. Schieb ihn beiseite, etwa nach
`sdk/cmdline-tools-19.0`, und ruf `setup` noch einmal auf.

```text
ERROR: the download has sha1 ..., versions.conf expects ....
```

Das Zip ist nicht das, das `versions.conf` nennt. Nichts wurde entpackt, und der
Download ist gelöscht. Ruf `setup` noch einmal auf. Bleibt die Prüfsumme falsch,
hat Google die Datei unter derselben Adresse ersetzt, und `versions.conf` braucht
eine neue Zeile.

```text
ERROR: could not fetch https://dl.google.com/android/repository/...:
```

Die Zeile darunter ist der Grund aus dem Netz. Hinter einem Proxy setz
`https_proxy` in der Shell, die `setup` aufruft. Es bleibt nichts liegen, also
ruf `setup` noch einmal auf, sobald sich die Adresse in einem Browser auf
demselben Rechner öffnet.

```text
ERROR: could not unpack into sdk/cmdline-tools/latest:
```

Meist gibt es den Ordner schon von einem früheren Versuch, aber ohne die
`source.properties`, die einen fertigen Teil kennzeichnet. Schieb ihn beiseite
und ruf `setup` noch einmal auf. Download und halb entpackte Kopie werden
gelöscht.

```text
ERROR: .../sdk/cmdline-tools/latest/bin/android is missing, so platform-tools, emulator cannot be installed.
```

Platform Tools und Emulator kommen über die Android CLI, und die gehört zu den
Kommandozeilenwerkzeugen. Im Ordner `sdk/cmdline-tools/latest` liegen Werkzeuge
ohne sie. Schieb den Ordner beiseite und ruf `setup` noch einmal auf.

```text
ERROR: the Android CLI did not install emulator.
```

Die CLI ist fertig, aber der Ordner dieses Teils liegt nicht unter `sdk/`. Die
CLI sagt nicht immer, warum. Ruf `setup` noch einmal auf, und scheitert es ein
zweites Mal, ruf die Zeile von Hand auf, um die Ausgabe der CLI selbst zu sehen:

```bash
source bin/env.sh
sdk/cmdline-tools/latest/bin/android --no-metrics --sdk="$PWD/sdk" sdk install emulator
```

## Das Gerät ist nicht gelistet

```text
ERROR: device phone-1080x2400-480 is not listed in devices.xml.
```

`avdmanager` liest Bildschirmbeschreibungen nur aus `android-home/devices.xml`.
`create` verlinkt diesen Pfad auf die Datei im Klon, aber nur, wenn dort noch
nichts liegt. Sieh nach, was dort liegt:

```bash
ls -l android-home/devices.xml
```

Ist es eine Datei und kein Link in den Klon, kopier entweder den `<d:device>`
Block aus der `devices.xml` des Klons hinein, oder leg sie beiseite und ruf
`create` noch einmal auf, das dann die Datei des Klons verlinkt.

## Nicht genug Speicher

```text
ERROR: dev needs about 2436 MB, 2100 MB are free, and 1024 MB stay reserved for
       the machine. Stop a guest first, or insist with --force.
```

Die Prüfung zählt `hw.ramSize` des Android Virtual Device (AVD), 900 MB
obendrauf und 1024 MB für den Rechner. Stopp ein AVD, gib der Vorlage weniger
`ram`, oder starte mit `--force` und beobachte `abgal status`. Unter 1536 MB
lagert ein AVD aus.

```text
Note: dev has 4096 MB in its config.ini, its template
      phone-1080x2400-480-api35-x86_64 says 1536 MB.
      It starts with 4096 MB. To bring it in line, keeping its disk:
      abgal create phone-1080x2400-480-api35-x86_64 --as dev
```

Das ist kein Fehler, das AVD startet trotzdem mit dem Wert, den es schon
hat. Es bedeutet, dass das AVD vor der Änderung von `ram` in
`devices.conf` angelegt wurde und noch die alte Zahl trägt. Der genannte
Befehl `abgal create` schreibt `hw.ramSize` aus der Vorlage neu, ohne die
Platte zu verlieren.

## Das AVD kam nicht hoch

```text
ERROR: dev did not come up. Last lines of the log:
```

Entweder hat der Emulator Prozess in den ersten Sekunden geendet, oder er
läuft noch, aber seine Konsole hat innerhalb von `--timeout` nicht geantwortet.
Die Zeilen unter der Meldung stammen aus `logs/<guest>/emulator.log`. Im
zweiten Fall läuft das AVD weiter, und ein neues `start` meldet es als
laufend, also beende es zuerst mit `abgal stop -n <guest>`. Die häufigste
Ursache ist KVM.
Prüf, ob das Gerät existiert und ob dein Benutzer in der Gruppe ist:

```bash
ls -l /dev/kvm
getent group kvm
```

Fehlt `/dev/kvm`, ist die Virtualisierung in der Firmware aus oder das Modul
`kvm_intel` beziehungsweise `kvm_amd` nicht geladen. Fehlt dein Benutzer in der
Zeile `kvm`, ist das `usermod` aus dem Schnellstart nicht gelaufen. Eine
Sitzung, die vor dem `usermod` geöffnet wurde, behandelt `abgal start` selbst.

```text
ERROR: dev is running on emulator-5554 but did not report a completed boot in 300 s.
```

Das AVD läuft, aber Android ist mit dem Booten nicht fertig geworden. Auf
einem langsamen Rechner mit `--gpu software` kann der erste Start länger
dauern. Gib ihm mit `--timeout 600` mehr Zeit, oder sieh dir das AVD mit
`sdk/platform-tools/adb -s emulator-5554 logcat` an.

## Die Temperaturwache ist nicht angelaufen

```text
ERROR: ABGAL_TEMP_STOP=9x is not a whole number.
```

Eine der Variablen `ABGAL_TEMP_*` enthält etwas anderes als Ziffern. Kein AVD
wurde gestartet. Berichtige die Variable oder entferne sie, und starte neu.

```text
ERROR: no processor temperature measurable, so no guest could be watched.
```

Weder die Zone `x86_pkg_temp` noch `sensors` lieferte einen Wert, und kein AVD
wurde gestartet. Beide Werte kommen von Intel Treibern: die Zone vom
Kernelmodul `x86_pkg_temp_thermal`, und die Zeile `Package id 0`, nach der die
Wache in `sensors` sucht, von `coretemp`. Unter Debian kommt `sensors` aus dem
Paket `lm-sensors`. Ein AMD Prozessor hat beides nicht, dort kann die Wache
also noch nicht laufen. `--no-watch` startet das AVD ohne sie, und dann hält
es nichts an, wenn der Prozessor zu heiß wird.

```text
ERROR: the temperature watch for dev ended at once with exit code 1.
```

Das AVD läuft, aber nichts schützt es vor Überhitzung. Die Meldung nennt das
Protokoll der Wache, und dessen letzte Zeile sagt, warum, außer das Protokoll
selbst ließ sich nicht schreiben, etwa bei einem `ABGAL_TEMP_LOG` in einem
Ordner ohne Schreibrecht. In einem Stapel startet kein weiteres AVD. Stopp das
AVD mit `abgal stop -n dev`, bevor du es behebst.

## Ein AVD hat von selbst gestoppt

Sieh in die Temperaturwache:

```bash
cat logs/<guest>/watch.log
```

Eine Zeile `ABORT at 96 C` heißt, die Wache hat es gestoppt, weil der
Prozessor zu heiß wurde. [Wie es funktioniert](how-it-works.md#temperature-watch)
nennt die Schwellen und wie man sie ändert. Ein AVD, das ohne eine solche Zeile
stoppt, hat von selbst geendet. Sein letzter Start steht in
`logs/<guest>/emulator.log`.

## Dateien in deinem Home Ordner

AbGal hält SDK, AVDs, Protokolle und die eigenen Nutzerdateien der SDK
Werkzeuge im Klon, unter `sdk/`, `avd/`, `logs/` und `android-home/`. Nur adb
schreibt noch in deinen Home Ordner, weil es für seinen eigenen Ordner keine
Variable liest, dazu eine Datei für die Emulator Konsole:

| Pfad | Geschrieben von | Was es ist |
|---|---|---|
| `~/.android/adbkey` | adb | der private Schlüssel, mit dem adb mit Geräten spricht |
| `~/.android/adbkey.pub` | adb | der dazugehörige öffentliche Schlüssel |
| `~/.android/adb.<port>` | adb | welches adb Programm den Dienst auf diesem Port fährt |
| `~/.emulator_console_auth_token` | dem Emulator | das Token für die Emulator Konsole |

Alles andere, was die SDK Werkzeuge schreiben, landet in `android-home/` im
Klon.

Lief AbGal schon vor `android-home/` auf diesem Rechner, kann `~/.android/`
noch alte Dateien enthalten: `bin/`, `cli/`, `devices.xml`, `emu-*`,
`modem-nv-ram-*`, `userid` und `cache/`. AbGal nutzt sie nicht mehr, und sie
können gelöscht werden, wenn kein anderes Android Werkzeug, etwa Android
Studio, `~/.android` nutzt. Den adb Schlüssel nie löschen.

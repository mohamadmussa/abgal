# AbGal

*[In English](README.md)*

[![Build status](https://github.com/mohamadmussa/abgal/actions/workflows/checks.yml/badge.svg)](https://github.com/mohamadmussa/abgal/actions/workflows/checks.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)

**Android Batch Guests, Accelerated and Local.** AbGal legt Android Emulatoren
aus einer kurzen Liste von Vorlagen an und fährt mehrere davon nebeneinander auf
einem Linux Rechner, ohne Docker und ohne Android Studio. Vor jedem Start prüft
es den Speicher, und es stoppt ein Android Virtual Device (AVD), bevor der
Prozessor überhitzt.

Eine *Vorlage* beschreibt eine Klasse von Gerät: Bildschirm, Dichte, Android
Version, Systemabbild und Speicher. Ein *AVD* ist ein Emulator aus einer
Vorlage, mit eigenem Namen und eigener Platte. Zehn AVDs aus einer Vorlage
teilen sich ein Systemabbild.

## Lebenszyklus

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/lifecycle-dark.svg">
  <img src="docs/img/lifecycle-light.svg" alt="A guest's life from template to deleted. template becomes stopped through abgal create. stopped becomes booting through abgal start, with a note that abgal start refuses and leaves it stopped when memory is too low. booting becomes running once boot completes, or falls back to stopped if the guest did not come up. running returns to stopped through abgal stop or the temperature watch at 96 C. stopped becomes deleted through abgal delete.">
</picture>

`abgal start` weist ein AVD schon vor dem Booten ab, wenn der freie Speicher
unter das fallen würde, was der Rechner für sich behält. Ein AVD wächst nach
dem Booten noch minutenlang, deshalb zählt die Prüfung seine eingeschwungene
Größe und nicht die beim Booten. `--force` startet es trotzdem.

## Schnellstart

AbGal läuft auf **Linux auf x86_64 mit KVM**. macOS und Windows sind in
[#13](https://github.com/mohamadmussa/abgal/issues/13) geplant. Du brauchst
Python 3, getestet mit 3.11. AbGal selbst nutzt nur die Standardbibliothek von
Python.

**1. Klonen und KVM erlauben.**

```bash
git clone https://github.com/mohamadmussa/abgal.git
cd abgal
sudo usermod -aG kvm "$USER"
```

Eine Sitzung, die schon vor dem `usermod` offen war, kennt die Gruppe noch
nicht. `abgal start` merkt das und startet für dich über `sg kvm`.

**2. Das Android SDK nach `sdk/` holen.**

```bash
./abgal setup
```

`setup` nennt die Lizenz des Android SDK und fragt, bevor es etwas holt.
`--accept-licenses` antwortet für einen CI Job. Dann lädt es die
Kommandozeilenwerkzeuge, die in `versions.conf` stehen, prüft ihre sha1 und
installiert Platform Tools und Emulator mit der Android CLI und
`--no-metrics`. Alles landet in `sdk/`, das git ignoriert. Der erste Aufruf der
CLI legt die CLI selbst nach `android-home/` im Klon, siehe
[Was AbGal nicht ist](#was-abgal-nicht-ist). Am Ende ruft `setup` `abgal doctor`
auf. Das prüft KVM, die Versionen des SDK, die Systemabbilder und den Speicher
und sagt zu jeder Zeile, die nicht ok ist, wie man sie behebt.

Das Systemabbild einer Vorlage wird beim ersten `create` geholt, das es
braucht, auf demselben Weg und mit `--no-metrics`. Auf dem Rechner, auf dem
AbGal entwickelt wird, brauchte `setup` anderthalb Minuten und das erste
`create` knapp vier (24.09.2026).

**3. Ein AVD anlegen und starten.**

```bash
./abgal list
./abgal create phone-1080x2400-480-api35-x86_64 --as dev
./abgal start -n dev
./abgal status
```

Auf dem Rechner, auf dem AbGal entwickelt wird, dauerte der Start 50 Sekunden,
bis das AVD bereit war (23.09.2026). `status` zeigt es danach als live, dazu
das Gerät, über das adb es erreicht hat:

```text
NAME                   ID        STATE     DEVICE         ADB          MEM    CPU    UPTIME    TEMPLATE
dev                    19c95791  live      emulator-5554  device       612    3.2    00:00:12  phone-1080x2400-480-api35-x86_64

Memory available: 9211 MB. A guest needs its own size plus about 900 MB.
```

Ab da ist es ein gewöhnlicher Emulator:

```bash
sdk/platform-tools/adb -s emulator-5554 install app.apk
```

**4. Wieder stoppen.**

```bash
./abgal stop -n dev
```

## Befehle

Aus dem Klon als `./abgal` aufrufen, oder den Klon in den `PATH` legen.

| Befehl | Was er tut |
|---|---|
| `abgal setup` | Holt die Teile des SDK aus `versions.conf` nach `sdk/`, nach der Frage zur Lizenz |
| `abgal doctor` | Prüft KVM, die Versionen des SDK, die Systemabbilder und den Speicher und nennt zu jedem Problem die Abhilfe |
| `abgal list` | Zeigt die Vorlagen in `devices.conf` und die AVDs auf der Platte |
| `abgal create <template>` | Legt ein AVD an, benannt nach der Vorlage |
| `abgal create <template> --as ci --count 4` | Legt `ci-01` bis `ci-04` an |
| `abgal create <template> --as dev --recreate` | Löscht zuerst `dev` und legt es dann neu an. Fragt zuerst, `--yes` überspringt die Frage |
| `abgal start -n <guest>` | Startet ein AVD und wartet, bis es gebootet hat |
| `abgal start -n a -n b -n c` | Startet mehrere nacheinander, jeden mit eigener Speicherprüfung |
| `abgal start -n <guest> --locale ar-SA --timezone Asia/Riyadh` | Setzt Sprache und Zeitzone. Ohne sie bekommt ein AVD `en-US` und `Europe/Berlin`, nicht die Werte des Rechners |
| `abgal start -n <guest> --gpu host` | Rechnet die Grafik auf der Grafikkarte statt in Software |
| `abgal start -n <guest> --wipe` | Bootet wie neu, die Nutzerdaten werden gelöscht |
| `abgal start -n <guest> --dry-run` | Zeigt die Befehlszeile und die Prüfungen, startet nichts |
| `abgal status` | Was auf der Platte liegt, was läuft und wie viel Speicher frei ist |
| `abgal stop -n <guest>` | Stoppt ein AVD, erst geordnet, nach `--grace` Sekunden per Signal |
| `abgal delete -n <guest>` | Löscht ein AVD samt Platte, nach Rückfrage |
| `abgal watch -n <guest>` | Die Temperaturwache. `start` startet sie selbst, von Hand also nur nach `--no-watch` |

Jeder Befehl kennt `--help`. Ein AVD lässt sich über seinen Namen oder über
seine achtstellige Kennung ansprechen. Der [Guide](docs/README.de.md) behandelt
Vorlagen, das Innenleben und jede Fehlermeldung.

### Vorlagen

`devices.conf` hat eine Zeile je Vorlage, `devices.xml` beschreibt die
Bildschirme. Sechs Vorlagen liefert AbGal mit, alle ein Telefonbildschirm mit
1080 x 2400 bei 480 dpi: API 35, 36 und 37 ohne Store, API 35 mit dem Play
Store, und API 35 mit 4096 oder 5120 MB. Der Kommentar oben in
`devices.conf` erklärt jede Spalte und wie man eine Vorlage hinzufügt.

### Wie viele AVDs passen

Die Spalte `ram` entscheidet. Gemessen am 23.09.2026 auf einem Rechner mit
16 GB: ein AVD mit 1536 MB pendelt sich bei etwa 2400 MB ein, und vier passen
gleichzeitig. Ein AVD mit 2048 MB landet bei etwa 2900 MB, und drei passen.
Unter 1536 MB lagert das AVD aus, und eine App braucht doppelt so lange zum
Start.

## Was AbGal nicht ist

- **Kein Container.** AVDs laufen als gewöhnliche Prozesse auf dem Host. Es
  gibt kein Abbild zu bauen und keinen Docker Dienst.
- **Keine Gerätefarm.** `view/view-service.py` zeigt die AVDs eines
  Rechners im Browser, man kann sie antippen, darin tippen, sie starten und
  stoppen, siehe
  [Ansicht und Steuerung aus dem Browser](docs/view-service.de.md).
  `abgal webui` öffnet es ins Netzwerk, und wer es erreicht, steuert jedes
  AVD. Es gibt keine Benutzer, keine Warteschlange und keinen zweiten
  Rechner.
- **Kein Testwerkzeug.** AbGal macht AVDs bereit. Getestet wird dann mit
  Maestro, Espresso, Appium oder schlicht `adb`.
- **Nicht für echte Geräte.** Es legt nur Emulatoren an und fährt sie.
- **Noch nicht ganz in sich geschlossen.** SDK, AVDs, Protokolle und die
  eigenen Nutzerdateien der SDK Werkzeuge liegen im Klon, das meiste davon in
  `android-home/`: die Android CLI, etwa 250 MB samt eigener Java Laufzeit,
  `devices.xml` als Link, und der Rest ihres Zustands. Zwei Dinge bleiben im
  Home Ordner, geschrieben von zwei verschiedenen Werkzeugen: die eigenen
  Dateien von adb in `~/.android/` (`adbkey`, `adbkey.pub` und ein
  `adb.<port>`), weil adb für seinen Ordner keine Variable liest, und
  `~/.emulator_console_auth_token`, geschrieben vom Emulator. Ein neuer
  Schlüssel dort würde ein Handy an USB erneut nach der Erlaubnis für diesen
  Rechner fragen.

## Warum es neben dem Vorhandenen existiert

| Projekt | Was es tut | Worin AbGal sich unterscheidet |
|---|---|---|
| [budtmo/docker-android](https://github.com/budtmo/docker-android) | Ein Emulator je Docker Container, mit Browseransicht über noVNC | Braucht Docker. AbGal fährt mehrere AVDs auf dem Host und prüft den Speicher zwischen den Starts |
| [google/android-emulator-container-scripts](https://github.com/google/android-emulator-container-scripts) | Skripte, die den Emulator in ein Container Abbild packen | Nur Container. AbGal braucht kein Abbild und keinen Bauschritt |
| [DeviceFarmer/stf](https://github.com/DeviceFarmer/stf) | Steuert schon verbundene Geräte aus dem Browser | STF startet keinen Emulator. AbGal startet sie und könnte unter STF liegen |
| Android Studio Device Manager | Legt Emulatoren von Hand an und startet sie | Einer nach dem anderen, in einem Desktopprogramm. AbGal macht es stapelweise aus einer Shell |
| `avdmanager` und `emulator` | Die SDK Werkzeuge selbst | AbGal ruft sie auf. Es ergänzt Vorlagen, Stapel, Speicherprüfung und Temperaturwache und setzt die Werte fest, die `avdmanager` still fallen lässt |

Wer einen Emulator in einem Container will, nimmt docker-android. Wer ein
Gerätelabor im Browser will, nimmt STF. AbGal ist für den Fall dazwischen: ein
Linux Rechner, mehrere Emulatoren gleichzeitig, nachbaubar aus einer Textdatei.

## Stand

AbGal ist jung und läuft täglich auf einem Rechner. Die offene Arbeit steht in
[den Issues](https://github.com/mohamadmussa/abgal/issues).

## Mitarbeit

Erst ein Issue, dann ein Pull Request. [CONTRIBUTING.de.md](CONTRIBUTING.de.md) hat
die Hausregeln.

## Lizenz

[Apache 2.0](LICENSE). Copyright 2026 Mohamad Mussa.

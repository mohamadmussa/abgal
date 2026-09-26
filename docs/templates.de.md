# Vorlagen

*[In English](templates.md)*

Eine Vorlage ist eine Zeile in `devices.conf`. Sie beschreibt eine Klasse von
Gerät, und jedes Android Virtual Device (AVD) daraus bekommt denselben
Bildschirm, dieselbe Android Version, dasselbe Systemabbild und denselben
Speicher. Diese Seite erklärt die Zeile, was `create` daraus macht und wie man
eine hinzufügt.

## Die Zeile

```text
# template                               | device              | api | tag                   | abi    | ram  | note
phone-1080x2400-480-api35-x86_64         | phone-1080x2400-480 | 35  | google_apis           | x86_64 | 1536 | Phone class screen at 480 dpi, Google services without a store
```

| Spalte | Bedeutung |
|---|---|
| `template` | Der Name, den du `abgal create` gibst |
| `device` | Die `<d:id>` eines Bildschirms in `devices.xml` |
| `api` | Android API Stufe, 35 ist Android 15 |
| `tag` | `google_apis`, `google_apis_playstore` oder `default` |
| `abi` | `x86_64` oder `arm64-v8a`, geschrieben wie im Pfad des Systemabbilds |
| `ram` | Speicher des AVD in MB. Er entscheidet, wie viele AVDs gleichzeitig passen |
| `note` | Wofür die Vorlage da ist, gezeigt von `abgal list` |

Der Name wiederholt Bildschirm, Dichte, API Stufe und Befehlssatz mit Absicht,
damit er sich ohne die Tabelle lesen lässt. Eine Spalte für den Port gibt es
nicht: ein Port gehört zu einem laufenden AVD, und der Emulator sucht sich beim
Start einen freien.

Das Systemabbild einer Vorlage ist `system-images;android-<api>;<tag>;<abi>`.
Alle AVDs einer Vorlage teilen es sich auf der Platte.

## Was create setzt

`avdmanager` legt ein AVD aus dem Bildschirm in `devices.xml` und dem
Systemabbild an. Mehrere Werte lässt es dabei ohne Meldung fallen oder
überschreibt sie, deshalb setzt `create` diese danach in
`avd/<guest>.avd/config.ini`:

| Wert | Nach avdmanager | Gesetzt auf | Warum |
|---|---|---|---|
| `PlayStore.enabled` | `no` | `yes` | nur für den Tag `google_apis_playstore` |
| `hw.ramSize` | `2G` | die Spalte `ram` | `devices.xml` kann ihn nicht tragen |
| `hw.camera.front` | `none` | `emulated` | die Bildschirmbeschreibung hat eine |
| `firstboot.bootFromDownloadableSnapshot` | `yes` | `no` | würde Zustand aus dem Netz holen |
| `firstboot.bootFromLocalSnapshot` | `yes` | `no` | ein Lauf darf nicht vom vorigen abhängen |
| `firstboot.saveToLocalSnapshot` | `yes` | `no` | dasselbe in die andere Richtung |

Dann liest es die Datei zurück und prüft dreizehn Zeilen: die sechs oben, dazu
`abi.type`, `hw.device.name`, `hw.lcd.density`, `hw.lcd.height`,
`hw.lcd.width`, `image.sysdir.1` und `tag.id`. Bildschirmgröße und Dichte kommen
aus `devices.xml` und nicht aus einer festen Zahl, damit ein Tablet gegen seinen
eigenen Bildschirm geprüft wird. Weicht eine Zeile ab, nennt `create` sie und
endet mit Exit Code 1.

## Eine Vorlage hinzufügen

Eine Vorlage braucht einen Bildschirm in `devices.xml` und eine Zeile in
`devices.conf`. Gibt es den Bildschirm schon, geht es gleich mit Schritt 3
weiter.

### 1. Das Systemabbild finden

Die Abbilder für eine API Stufe auflisten:

```bash
source bin/env.sh
sdk/cmdline-tools/latest/bin/android --no-metrics sdk list --all 'system-images/android-34/*'
```

Jede Zeile liest sich als `system-images/android-<api>/<tag>/<abi>`. Die drei
Teile kommen unverändert in die Spalten `api`, `tag` und `abi`. Einen `tag`
von `google_apis`, `google_apis_playstore` oder `default` wählen, dazu auf
einem x86 Rechner ein `x86_64` abi. Ein `arm64-v8a` Abbild läuft durch
Übersetzung und ist für eine Suite viel zu langsam.

### 2. Den Bildschirm beschreiben

Den `<d:device>` Block in `devices.xml` kopieren und diese Werte ändern. Das
Beispiel ist ein Handy mit 720 x 1600 Pixeln bei 320 dpi und einem 6,5 Zoll
Bildschirm:

| Wert | Beispiel | Wie man ihn bekommt |
|---|---|---|
| `d:name` | `Phone 720x1600 320dpi` | freier Text |
| `d:id` | `phone-720x1600-320` | Breite, Höhe und dpi, wie beim vorhandenen |
| `d:x-dimension`, `d:y-dimension` | `720`, `1600` | `adb shell wm size` auf dem Gerät |
| `d:pixel-density` | `xhdpi` | `adb shell wm density`, als Name: 160 `mdpi`, 240 `hdpi`, 320 `xhdpi`, 480 `xxhdpi`, 640 `xxxhdpi`. Andere Werte werden als `420dpi` geschrieben |
| `d:diagonal-length` | `6.5` | die Bildschirmgröße in Zoll |
| `d:xdpi`, `d:ydpi` | `269.93` | sqrt(720^2 + 1600^2) / 6.5 |
| `d:screen-size` | `normal` | Breite / (dpi / 160) = 360 dp, ein Handy ist `normal` |

Der Block nennt auch ein `d:api-level` und einen Satz `d:abis`. Diese mit den
Vorlagen abstimmen, die diesen Bildschirm verwenden. Prüfen, dass das SDK den
neuen Bildschirm sieht:

```bash
source bin/env.sh
sdk/cmdline-tools/latest/bin/avdmanager list device -c
```

Fehlt die Id, siehe [Das Gerät ist nicht gelistet](troubleshooting.md#the-device-is-not-listed).

### 3. Die Zeile eintragen

```text
phone-720x1600-320-api35-x86_64 | phone-720x1600-320 | 35 | google_apis | x86_64 | 1536 | Small phone at 320 dpi
```

`ram` bei 1536 oder darüber halten. Darunter lagert ein AVD aus, und App
Kaltstarts brauchen doppelt so lange. Jede Stufe nach oben kostet Platz für
andere AVDs, siehe den Eintrag `ram` in der Spaltenliste oben in `devices.conf`.

### 4. Ein AVD anlegen

```bash
./abgal list
./abgal create phone-720x1600-320-api35-x86_64 --as small
```

`create` holt das Systemabbild, wenn eine Vorlage es zum ersten Mal braucht.
Für API 35 auf x86_64 sind das etwa 3,5 GB. Es endet mit den dreizehn
Prüfungen aus [Was create setzt](#what-create-sets).

Die Dichte ist der Wert, der stimmen muss. Eine App liefert ihre Bilder als
ein Split je Dichte aus, und ein AVD mit 420 dpi lädt andere Bilder als
eines mit 480, selbst bei gleicher Auflösung.

### Die eigene Vorlage über Updates behalten

`devices.conf` und `devices.xml` werden von git verfolgt, darum kann ein
`git pull` auf die eigenen Zeilen treffen. Entweder auf einem eigenen Branch
behalten und `main` hinein mergen, oder erst beiseite legen:

```bash
git stash
git pull
git stash pop
```

Haben beide Seiten dieselben Zeilen geändert, markiert git den Konflikt in
der Datei. Beide Zeilen behalten, die Marker löschen und `./abgal list`
laufen lassen, um zu sehen, dass jede Vorlage gelesen wird. Braucht sonst
noch jemand den Bildschirm, ihn als Pull Request schicken, siehe
[CONTRIBUTING.md](../CONTRIBUTING.md).

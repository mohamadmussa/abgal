# Ansicht und Steuerung aus dem Browser

`view/view-service.py` zeigt jedes Android Virtual Device (AVD), das
`abgal` kennt, im Browser, erlaubt einem Betrachter zu wechseln, welches
AVD gerade zu sehen ist, es mit Maus und Tastatur zu steuern, und es zu
starten, zu stoppen oder neu zu starten, ohne ein Terminal zu berühren.

## Starten

```bash
python3 view/view-service.py
```

| Option | Standard | Was sie tut |
|---|---|---|
| `--guest <name>` | keiner | Wählt ein AVD vor, das schon läuft. Ohne sie öffnet die Seite ohne Auswahl |
| `--address` | `127.0.0.1` | Die Schnittstelle, an die gebunden wird. Standardmäßig nur Loopback, für Zugriff von einem anderen Rechner mitgeben |
| `--port` | `8099` | Der Port, auf dem gehorcht wird |
| `--step` | `2` | Die Standard-Verkleinerung des Bildschirms, 1 ist volle Größe, höher ist kleiner und schneller |

`http://127.0.0.1:8099/` (oder die gewählte Adresse und der gewählte Port)
im Browser öffnen. Der Dienst gibt seine eigene URL beim Start aus.

## Die Seite

Drei Spalten: eine AVD-Liste links, das Live-Bild in der Mitte, ein
Bedienfeld rechts. Beide Seitenspalten lassen sich durch Ziehen an der
schmalen Leiste daneben in der Breite ändern. Die linke Spalte selbst
teilt sich in die AVD-Liste oben und ein DEBUG-Feld unten, in der Höhe
verschiebbar über die gleiche Art Leiste dazwischen.

### AVD-Liste

Eine Zeile je AVD, alle paar Sekunden neu geladen. Der Knopf der Zeile
zeigt die Seriennummer, sobald das AVD läuft, sonst seinen Namen, daneben
eine Status-Pille:

| Pille | Bedeutung |
|---|---|
| Grün, `running` | `adb` meldet den Zustand `device`, die Zeile lässt sich auswählen |
| Amber, `booting` | Das AVD hat einen Prozess, aber `adb` hat es noch nicht erreicht |
| Rot, `unknown` | `adb` meldet `unauthorized` |
| Rot, `stopped` | Kein Prozess, das AVD läuft nicht |

Nur eine laufende Zeile lässt sich anklicken, um sie auszuwählen. Ein Klick
auf den kleinen Pfeil am rechten Rand der Zeile klappt sie auf und zeigt
Name, Vorlage, Id, `adb`-Zustand, Speicher und CPU des AVD, dazu drei
Knöpfe:

| Knopf | Aktiv, wenn | Tut |
|---|---|---|
| Start | das AVD keinen Prozess hat | `abgal start` |
| Stopp | das AVD einen Prozess hat | `abgal stop` |
| Neustart | das AVD einen Prozess hat | `abgal stop`, danach `abgal start` |

Ein Start kann im schlechtesten Fall bis zu zehn Minuten dauern, `abgal`
wartet bis zu fünf Minuten auf die Konsole und danach noch einmal bis zu
fünf Minuten auf den Boot, eins nach dem anderen. Ein Stopp oder die
Stopp-Hälfte eines Neustarts dauert höchstens etwa eine Minute. Während
eine dieser Aktionen läuft, zeigt die Zeile statt der Knöpfe den Namen der
Aktion. Hat das AVD, das ein Betrachter gerade sah, gerade gestoppt oder
ist neu gestartet, fällt der Bildschirm auf den Platzhalter zurück, statt
eine Seriennummer abzufragen, die es nicht mehr gibt.

### Das Bild

Die Auswahl eines laufenden AVD startet den Bildabruf dafür. Ein Klick
ohne Mausbewegung tippt diesen Punkt an, ein Klick mit Ziehen wischt
zwischen den beiden Punkten. Beides sendet den Bruchteil des Bilds, an dem
geklickt wurde, keine Pixelposition, das funktioniert also bei jeder
Verkleinerung.

### Das Bedienfeld

**SCREEN** hat automatisches Neuladen und drei Verkleinerungsknöpfe, FULL,
HALF und SMALL, dazu NOW für einen einzelnen Abruf außerhalb der
Neulade-Schleife. Die Kopfzeile über der Seite zeigt die Abrufzeit des
letzten Bilds und den freien Speicher des Hosts.

**KEYS** hat je einen Knopf für BACK, HOME, APP_SWITCH, ENTER, DEL, TAB,
SEARCH, VOLUME_UP und VOLUME_DOWN. Die Menge ist bewusst fest, damit die
Seite nicht mitten im Test POWER oder SLEEP schicken kann.

**SWIPE** schickt einen Wisch von der Bildschirmmitte zu einem Rand.

**TEXT** tippt eine Zeile in das, was auf dem AVD gerade den Fokus hat, bis
zu 200 Zeichen, bei Enter.

Ein DEBUG-Feld, standardmäßig eingeklappt, kann jede Anfrage der Seite und
ihre Antwort zeigen, hilfreich wenn etwas auf dem Bildschirm nicht zu dem
passt, was angeklickt wurde.

## Was es braucht

`abgal` selbst, als Subprozess für die AVD-Liste und für Start, Stopp und
Neustart aufgerufen, und `adb` für alles, was den Bildschirm oder die
Eingabe eines ausgewählten AVD berührt. Der Dienst hält selbst keinen
AVD-Zustand außer dem, welches gerade ausgewählt ist, `abgal status
--json` wird bei jeder Aktualisierung der AVD-Liste erneut gefragt.

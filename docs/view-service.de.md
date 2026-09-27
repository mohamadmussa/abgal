# Ansicht und Steuerung aus dem Browser

*[In English](view-service.md)*

`view/view-service.py` zeigt jedes Android Virtual Device (AVD), das
`abgal` kennt, im Browser, erlaubt einem Betrachter zu wechseln, welches
AVD gerade zu sehen ist, es mit Maus und Tastatur zu steuern, und es zu
starten, zu stoppen oder neu zu starten, ohne ein Terminal zu berühren.

## Starten

```bash
./abgal webui
```

`abgal webui` startet `view/view-service.py` und reicht `--address`,
`--port`, `--guest` und `--allow-host` durch. Es lauscht auf `0.0.0.0`,
also auf jeder Schnittstelle, damit die Seite auch von einem anderen
Rechner im Netzwerk aufgeht, und sagt das bei jedem Start als Warnung,
siehe [Sicherheit](#sicherheit). `./abgal webui --address 127.0.0.1` hält
es auf diesem Rechner.

Das Skript lässt sich auch direkt starten und lauscht dann auf Loopback:

```bash
python3 view/view-service.py
```

| Option | Standard | Was sie tut |
|---|---|---|
| `--guest <name>` | keiner | Wählt ein AVD vor, das schon läuft. Ohne sie öffnet die Seite ohne Auswahl |
| `--address` | `127.0.0.1` | Die Schnittstelle, an die gebunden wird. Standardmäßig nur Loopback, für Zugriff von einem anderen Rechner mitgeben |
| `--port` | `8099` | Der Port, auf dem gehorcht wird |
| `--step` | `2` | Die Standard-Verkleinerung des Bildschirms, 1 ist volle Größe, höher ist kleiner und schneller |
| `--allow-host <name>` | keiner | Ein zusätzlicher Host-Name, den der Dienst im Host-Header annimmt, wiederholbar. Nur nötig, wenn die Seite über einen DNS-Namen statt localhost erreicht wird, eine literale IP-Adresse wird immer angenommen |

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

## Sicherheit

Jede Anfrage außer dem Laden der Seite selbst braucht ein Token. Der
Dienst erzeugt bei jedem Start ein frisches Token und legt es in die
Seite, die Seite schickt dieses Token bei jeder Anfrage in einem Header.

Eine fremde Webseite kann diesen Header nicht setzen, ohne dass der
Browser vorher den Dienst um Erlaubnis fragt, und der Dienst erteilt diese
Erlaubnis nie, nur die Seite selbst kann also eine Anfrage mit diesem
Header erzeugen.

Der Host-Header jeder Anfrage muss localhost sein, eine literale
IP-Adresse, oder ein mit `--allow-host` angegebener Name. Das verhindert
DNS Rebinding, denn eine literale Adresse lässt sich nicht umleiten und
ein Name muss eigens erlaubt werden. Ein Origin-Header muss, wenn er
gesendet wird, zum Host-Header passen.

POST-Körper müssen `application/json` sein. Text aus TEXT erreicht das
AVD als ein einziges zitiertes Wort, Steuerzeichen werden abgelehnt.
Unerwartete Fehler erreichen die Seite nur als allgemeine Meldung, die
Einzelheiten stehen in der eigenen Log-Ausgabe des Dienstes. Lehnt
`abgal` einen Start, Stopp oder Neustart ab, etwa wegen zu wenig
Speicher, zeigt die Seite `abgal`s eigenen Grund mit 409. Je AVD läuft
nur ein Start, Stopp oder Neustart gleichzeitig, ein zweiter bekommt 409.

Jede Ablehnung mit 403 sagt, was zu tun ist. Ein Tab, der über einen
Neustart des Dienstes offen blieb, hat ein altes Token und bekommt
„reload the page“, also die Seite neu laden. Wer die Seite über einen
Rechnernamen öffnet, bekommt den passenden `--allow-host`-Aufruf genannt.
Rechnernamen werden ohne Rücksicht auf Groß- und Kleinschreibung
verglichen.

Das schützt nicht gegen alles. Wer die Seite öffnen kann, kann sie
benutzen, das Token ist kein Login und es gibt kein Benutzerkonto. Der
Datenverkehr läuft als reines HTTP ohne Verschlüsselung, ein anderer
Rechner auf dem Weg im selben Netzwerk kann ihn mitlesen, das Token
eingeschlossen. Eine Bindung an eine andere Schnittstelle mit `--address`
gibt daher jedem, der diese Adresse erreichen kann, die volle Kontrolle
über jedes AVD. `abgal webui` tut genau das von sich aus.

`abgal webui` in einem Netzwerk benutzen, in dem jeder, der den Rechner
erreicht, dessen AVDs steuern darf. Überall sonst `--address 127.0.0.1`
mitgeben, oder das Skript direkt starten, und den Dienst über einen
SSH-Tunnel erreichen.

## Was es braucht

`abgal` selbst, als Subprozess für die AVD-Liste und für Start, Stopp und
Neustart aufgerufen, und `adb` für alles, was den Bildschirm oder die
Eingabe eines ausgewählten AVD berührt. Der Dienst hält selbst keinen
AVD-Zustand außer dem, welches gerade ausgewählt ist, `abgal status
--json` wird bei jeder Aktualisierung der AVD-Liste erneut gefragt.

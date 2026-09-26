# Dashboard Design

`view/view-service.py` liefert heute eine schlichte dreispaltige Seite aus:
eine Liste der Android Virtual Devices (AVDs), einen Live-Bildschirm und ein
Bedienfeld. Diese Seite beschreibt das Ziellayout für diese Seite, ein
vollständiges Dashboard, vereinbart als das Bild, auf das hin gebaut wird. Es
ist kein Plan für einen einzelnen Pull Request. Funktionen kommen nach und
nach hinzu, jede über ein eigenes Issue verfolgt, und eine Steuerung ohne
eigenes Backend erscheint als sichtbarer, aber deaktivierter Platzhalter,
statt darauf zu warten, dass alle Teile auf einmal fertig sind.

Bisher verfolgt: Lebenszyklus-Steuerung eines AVD, Start, Stopp, Neustart,
Anlegen, Löschen
([#69](https://github.com/mohamadmussa/abgal/issues/69)), eine
Terminal-Sitzung zum Host oder zu einem AVD
([#70](https://github.com/mohamadmussa/abgal/issues/70)), und die
Gesamtform, während die Seite wächst
([#71](https://github.com/mohamadmussa/abgal/issues/71)).

## Wo die Referenz liegt

Ein hochauflösender, klickbarer Prototyp mit simulierten Daten zeigt jeden
Bildschirm und jede Interaktion. Er bleibt lokal, nicht in diesem Repository
getrackt, und wird nicht so ausgeliefert: die echte Seite bleibt reines
HTML, CSS und JS ohne Build-Schritt, ausgeliefert vom bestehenden
`Handler`, genau wie `view-service.py` heute schon arbeitet.

## Layout

Ein CSS-Grid füllt das Browserfenster, vier Zeilen: Kopfzeile, Hauptbereich,
Terminal, Statuszeile. Die Hauptzeile hat drei Spalten, die AVD-Liste, die
Mitte, und ein rechtes Panel mit Reitern.

| Bereich | Inhalt |
|---|---|
| Kopfzeile | Titel und Hostname, ein Breadcrumb, ein Befehlssuchfeld, APK installieren, Host-Terminal, neues AVD, Einstellungen |
| AVD-Liste | Eine Zeile je AVD: ein Status-Punkt, der Name, eine Shell-Verknüpfung, Seriennummer oder Id, Speicher, CPU. Ein Fortschrittsbalken während ein AVD stoppt oder seine Platte entfernt wird |
| Mitte, AVD-Ansicht | Name, Status, Lebenszyklus-Knöpfe (Start, Stopp, Neustart), eine Shell-Verknüpfung, Löschen, eine Werkzeugleiste (Layout, Bildqualität, automatisches Aktualisieren, Screenshot, Aufnahme), der Live-Bildschirm |
| Mitte, Leerzustand | Kein AVD gewählt oder keins vorhanden: eine Erklärung und die Aktionen AVD anlegen und Host-Terminal öffnen |
| Rechtes Panel | Reiter: Steuerung (Tasten, Wischen, Text eingeben, Zwischenablage), Details (ein CPU-Verlauf, Speicher, AVD-Angaben), Protokoll |
| Terminal | Einklappbar, Reiter für Host- und AVD-Sitzungen, geöffnet über eine Tastenkombination oder aus der Statuszeile |
| Statuszeile | Terminal-Tastenkombination, letzte Meldung, weitere Hinweise auf Tastenkombinationen |

AVDs lassen sich auch als Gitter kleiner Live-Kacheln gleichzeitig anzeigen,
sobald mehr als eines läuft.

## Was jeder Teil vom Backend braucht

| Teil | Backend |
|---|---|
| AVD-Liste | `GET /guests`, existiert schon |
| Ein AVD wählen | `POST /switch`, existiert schon |
| Tippen, Taste, Wischen, Text | existieren schon |
| Live-Bildschirm | `GET /frame.png`, existiert schon |
| Start, Stopp, Neustart, Löschen | neue Routen, rufen `abgal start`, `stop`, `delete` |
| Anlegen | neue Route, ruft `abgal create`. `--ram`, `--cores` und `--dry-run` gibt es in der CLI noch nicht |
| Vorlagen für den Anlegen-Dialog | neue Route, liest `devices.conf` |
| Terminal | ein neuer Sitzungskanal, zum Host oder zu `adb shell` auf einem AVD. Der Dienst ist heute nur lokal erreichbar, ein Terminal braucht dieselbe Sorgfalt |
| APK installieren | neue Route, ruft `adb install` |
| Zwischenablage | neue Route, über `adb shell cmd clipboard` oder einen Helfer |
| Screenshot, Aufnahme | neue Routen, speichern in einen Ordner auf dem Host |
| Temperatur | die bestehende Wache, als Wert ausgegeben |

## Einstellungen

Eine eigene Seite, Änderungen werden vorgemerkt und erst beim Speichern
angewendet, mit einer Warnung, wenn der Browser-Tab vorher schließt.
Aktualisierungsintervall des Bildschirms und Standard-Bildqualität,
Aufnahmeordner auf dem Host, und Erscheinungsbild: vier fertige Farbthemen
plus ein eigenes, zur Laufzeit über CSS-Variablen geändert.

## Optik

Zwei Schriftarten, eine serifenlose für die Oberfläche und eine
dicktengleiche für Ids, Seriennummern, Befehle und Zahlen. Eine dunkle,
kontrastarme Palette als Standard, mit Statusfarben, Grün für ein laufendes
AVD, Amber für eine Warnung oder einen laufenden Schritt, Rot für ein
Problem, getrennt von der Akzentfarbe für Knöpfe und Fokus. Jedes Thema ist
ein kleiner Satz an Variablen, sodass ein eigenes Thema nur diese ändert,
nicht die Seite selbst.

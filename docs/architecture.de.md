# Architektur

[README.md](../README.md) bringt ein Android Virtual Device (AVD) in vier
Befehlen von einem frischen Klon zu einem laufenden Emulator. [Wie es
funktioniert](how-it-works.md) verfolgt ein AVD durch die Datei oder
Funktion, die jeden Schritt ausführt.
Keines von beiden zeigt die ganze Form auf einmal: welche Teile auf welche
warten, in welcher Reihenfolge, und wie ein Warten neben einem Schritt
aussieht, der einfach nur läuft. Diese Seite zeigt genau das, mit denselben
erzeugten Diagrammen, die [CONTRIBUTING.md](../CONTRIBUTING.md) überall dort
verlangt, wo ein Ablauf von Warten, Abfragen oder mehr als einem Akteur
gleichzeitig abhängt.

Drei Leser könnten diese Seite öffnen. Jemand, der AbGal betreibt und sehen
will, warum ein Start so lange dauert, wie er dauert, oder wie ein Fehlschlag
auf dem Weg dorthin tatsächlich aussah. Jemand, der einen Pull Request
schicken will und wissen muss, zu welcher Datei eine Änderung gehört, bevor
er sie schreibt. Jemand, der entscheidet, ob er AbGal überhaupt einsetzt, und
die Form der Sache sehen will, bevor er eine Zeile Python liest.

## Die ganze Form

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/pieces-topology-dark.svg">
  <img src="img/pieces-topology-light.svg" alt="A hub and spoke diagram. abgal sits in the center. It reads devices.conf and versions.conf, links devices.xml, creates avd/, writes logs/, and fetches into sdk/ and android-home/. bin/env.sh sits apart, unconnected, labeled not read by abgal.">
</picture>

`abgal` ist die eine Datei, die alles andere im Klon berührt. Sie liest
`devices.conf` und `versions.conf`, verlinkt `devices.xml` an ihren Platz,
legt `avd/` an, schreibt `logs/` und lädt das SDK nach `sdk/` und
`android-home/`. `bin/env.sh` ist die eine bewusste Ausnahme: sie setzt die
SDK Pfade für eine eigene Shell, und `abgal` liest sie nie, weil `abgal`
seine eigene Umgebung intern setzt. Der Rest dieser Seite folgt dem, was
innerhalb dieser einen Datei geschieht, einen Befehl nach dem anderen.

## Der Lebenszyklus eines AVD

Jeder Befehl bewegt ein AVD zwischen derselben kleinen Menge von Zuständen,
von einer Zeile in `devices.conf` über
`create`, `start`, laufend, und wieder zurück zu gestoppt, entweder durch
`abgal stop` oder durch die Temperaturüberwachung bei 96 C. README.md
zeichnet das schon als Zustandsdiagramm, siehe
[Lebenszyklus](../README.md#lifecycle), deshalb wird es hier nicht wiederholt.
`docs/README.md` trägt eine zweite, leicht abweichende Kopie desselben
Diagramms, der die Speicherverweigerung und die genaue Temperatur fehlen.
Das ist eine kleine, bereits bestehende Unstimmigkeit zwischen zwei
Dateien, die diese Seite nicht anfasst, festgehalten in Issue #39, hier
nicht behoben.

## Ein AVD erstellen

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/create-flow-dark.svg">
  <img src="img/create-flow-light.svg" alt="Nine steps in a column for abgal create: refuse an invalid name; check the screen is listed by avdmanager; fetch the system image if missing; refuse a running guest; delete and recreate, or keep the disk; create avd/ and call avdmanager create avd; write abgal-template; pin five values in config.ini, a sixth for the store template; read config.ini back and compare thirteen values against what was asked for.">
</picture>

`abgal create` durchläuft neun Schritte für jedes AVD und endet damit, dass
`create` `config.ini` zurückliest und dreizehn Werte gegen das prüft, was es
von `avdmanager` verlangt hatte, weil `avdmanager` mehrere davon ohne eine
Meldung verwirft oder überschreibt. Siehe [Templates](templates.md), welche
die dreizehn Werte sind und wie eine eigene Vorlage hinzugefügt wird. Das
Diagramm ist statisch, nicht animiert, weil `create_one()` an keiner Stelle
ein gemessenes Warten enthält: jeder Schritt ist eine Prüfung, ein
Dateischreibvorgang oder ein Aufruf von `avdmanager`, keiner davon ist eine
Abfrage oder ein Schlaf, also gibt es nichts, das als Verstreichen gezeigt
werden könnte.

## Ein AVD starten

`abgal start` ist der eine Ablauf in AbGal, der es am meisten wert ist, aus
mehr als einem Blickwinkel gesehen zu werden, weil es die eine Stelle ist,
an der mehrere Dinge aufeinander warten: der Emulatorprozess selbst, adb,
das seine console abfragt, ein Unterprozess für die Temperaturüberwachung,
und eine zweite Abfrage, bis der Boot fertig ist. Drei Diagramme zeigen
denselben realen Ablauf auf drei verschiedene Arten.

Der Schaltplan zeigt die reale Verdrahtung: `abgal` und die vier Dinge, mit
denen es spricht, der Kernel, der Emulator, adb und die
Temperaturüberwachung, eine Leitung pro Paar. Ein kleiner Impuls leuchtet
auf jeder Leitung genau in dem Moment auf, in dem dieser Kanal benutzt wird,
sodass ein Kanal, der zweimal benutzt wird, adb für die console und erneut
für den Boot, eine Leitung ist, die sichtbar zweimal pulsiert, nicht zwei
getrennte Leitungen.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/start-circuit-dark.svg">
  <img src="img/start-circuit-light.svg" alt="abgal and four actors it talks to, kernel, emulator, adb and the temperature watch, wired with one line each. A small dot on each wire lights up at the real moment that channel is used, twice on the adb wire, once for the console and once for the boot, and twice on the watch wire, starting it and then checking it is alive.">
</picture>

Die Bahnendarstellung legt dieselbe reale Abfolge entlang einer gemeinsamen
Zeitachse aus, eine Spalte pro Akteur, sodass die beiden adb Momente zu zwei
getrennten Zeilen werden statt zu zwei Impulsen auf einer gemeinsamen
Leitung.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/start-swimlane-dark.svg">
  <img src="img/start-swimlane-light.svg" alt="Five columns, abgal start, kernel, emulator, adb and the temperature watch, with abgal start's own steps running down its own column and a line crossing to whichever lane that step talks to, in real order from top to bottom.">
</picture>

Der Zustandsautomat zeigt, wo der Ablauf enden kann: bereit, oder einer von
drei unterschiedlichen Fehlerabschlüssen, die console hat nie geantwortet,
die Temperaturüberwachung ist sofort gestorben, oder das AVD ist nie fertig
gebootet, jeder davon mit der echten Meldung, die `start` für diesen Fall
ausgibt.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/start-states-dark.svg">
  <img src="img/start-states-light.svg" alt="A column of states for abgal start: the memory and running checks, launching the emulator, polling adb for the console up to the timeout, starting the temperature watch and checking it survived two seconds, polling adb for the completed boot, and four terminals, ready or one of three distinct failures.">
</picture>

## Ports, und wie viele AVDs gleichzeitig laufen

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/ports-scale-dark.svg">
  <img src="img/ports-scale-light.svg" alt="A row of the sixteen emulator ports from 5554 to 5584. Below it, an illustrative example: thirteen already busy, a guest's automatic pick taking the first free port, an explicit --port claiming one directly, a second automatic pick taking what is left, and a further guest's automatic pick finding nothing free.">
</picture>

`abgal` selbst führt keine Aufzeichnung darüber, welchen Port ein AVD
benutzt. Ohne `--port` ist die Wahl ganz allein die eigene Logik der
Emulator Binärdatei, sie sucht aufwärts ab 5554 nach einem freien Paar und
nimmt es, und `abgal` gibt für diesen Fall nur "vom Emulator gewählt" aus,
siehe [Ports](how-it-works.md#ports). Ein ausdrücklicher `--port` muss
gerade sein, von 5554 bis 5584, sechzehn Werte insgesamt, `abgal`s eigener
Kommentar zur Zählung nennt denselben Bereich "die sechzehn Ports, die adb
anbietet", weil aus genau diesem Bereich die adb Seriennummer eines AVD,
`emulator-<port>`, wieder herausgelesen wird. Ein Port außerhalb davon ist
einer, den adb für ein AVD tatsächlich nicht finden kann. Die sechzehn
Plätze im Diagramm sind diese reale Regel. Die Füllreihenfolge darunter ist
veranschaulichend, kein gemessener Lauf: welcher der sechzehn Ports gerade
in einem Moment belegt ist, ist Laufzeitzustand, kein Wert, den `abgal`
irgendwo festhält.

Mehr als sechzehn gleichzeitig laufende AVDs haben heute keine Lösung in
AbGal. `start` kennt kein stillschweigendes "alle AVDs", also müsste eine so
große Zahl ohnehin einzeln angefordert werden, und wenn das geschieht,
findet die automatische Wahl eines siebzehnten AVD nichts Freies mehr:
`abgal` hat für diesen Fall keinen Codepfad, und der Emulatorprozess selbst
würde einfach nicht starten, mit welcher generischen Fehlermeldung auch
immer er für einen Start ohne verfügbaren Port ausgibt. Das ist eine bewusst
offene Frage, für ein späteres Issue vorgemerkt, nicht Teil dieses
Dokuments.

## Ein AVD stoppen

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/stop-ladder-dark.svg">
  <img src="img/stop-ladder-light.svg" alt="An escalation ladder for abgal stop: adb emu kill, then a poll for up to the --grace default of 20 seconds, then, if still running, SIGTERM and a fixed 10 second wait, then SIGKILL and another fixed 10 second wait, ending in stopped or, if nothing worked, still running.">
</picture>

`abgal stop` versucht zuerst den geordneten Weg, weil ein harter Kill die
Festplatte eines AVD beschädigen kann. Es sendet `adb emu kill` und fragt
einmal pro Sekunde ab, bis zu dem `--grace` Standardwert von 20 Sekunden.
Läuft das AVD noch, sendet es `SIGTERM` und wartet fest 10 Sekunden, nicht
skaliert durch `--grace`, und prüft dann erneut. Läuft es danach immer
noch, `SIGKILL` und noch einmal ein festes Warten von 10 Sekunden. Übersteht
das AVD sogar das, sagt `stop` das und endet mit Exitcode 1: es gibt nichts
weiter, das das Programm tun kann.

## Temperaturüberwachung

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="img/watch-states-dark.svg">
  <img src="img/watch-states-light.svg" alt="A column of states for abgal watch: an initial temperature reading that must succeed once, a warmup poll for a guest to appear, then an unbounded main poll. Four terminals: no temperature measurable at all, no guest appeared during warmup, no guests left to watch, or the temperature reaching the stop threshold, which hands off to the same stop cascade abgal stop uses. An unreadable sensor during the main loop retries, stated on the diagram as eventually aborting after four misses running.">
</picture>

Das ist die ausführlichere, animierte Fassung des Flowcharts, das schon in
[Temperaturüberwachung](how-it-works.md#temperature-watch) steht, kein
Widerspruch dazu: dieselbe Warnung bei 88 C und derselbe Abbruch bei 96 C,
hier zusammen mit dem Aufwärm-Warten und dem eigenen fehlenden Limit der
Hauptabfrage gezeichnet. Das Diagramm zeigt vier unterschiedliche Enden.
Zwei sind saubere Abschlüsse, kein AVD ist während der Aufwärmphase
erschienen, oder es sind keine AVDs mehr zu überwachen übrig. Eines ist ein
harter Fehlschlag ganz am Anfang, wenn weder die Thermozone noch `sensors`
überhaupt etwas messen können. Dass die Temperatur die Stoppschwelle
erreicht, wird nicht ein zweites Mal als eigene Kaskade gezeichnet, sondern
übergibt an dieselbe `stop_one()` Eskalation, die das
Eskalationsleiter-Diagramm oben schon vollständig zeigt. Ein Sensor, der
während der Hauptschleife unlesbar bleibt, bricht ebenfalls ab, nach vier
Fehlversuchen in Folge, im Diagramm als die echte Konsequenz an genau
diesem Schritt dargestellt, nicht als fünftes, eigenständiges Ende.

## Für Mitwirkende

Jeder Kasten in den Diagrammen dieser Seite ist eine echte Datei oder eine
echte Funktion, keine bloße Illustration davon, außer wo ein Diagramm auf
seiner eigenen Fläche etwas anderes sagt. `abgal` ist die eine Python Datei
hinter jedem einzelnen von ihnen; `devices.conf`, `devices.xml` und
`versions.conf` sind die Dateien, die das Diagramm der ganzen Form oben
nennt; ein neuer Bildschirm oder eine neue Vorlage gehört in
[Templates](templates.md), was diese Seite nicht wiederholt. Die Diagramme
selbst werden von `tools/gen-architecture-diagrams.py` erzeugt, nicht von
Hand gezeichnet, sodass eine Änderung an `abgal`, die einen dieser Abläufe
ändert, bedeutet, dieses Skript zu aktualisieren und die SVGs unter
`docs/img/` neu zu erzeugen, nicht ein Bild direkt zu bearbeiten. Die
Hausregeln für Branches, Commits und den Datenschutz Gate stehen in
[CONTRIBUTING.md](../CONTRIBUTING.md), was diese Seite ebenfalls nicht
wiederholt.

## Für die Entscheidung, es einzusetzen

AbGal ist eine einzige Python Datei, die nur die Standardbibliothek
benutzt. Es gibt nichts zu installieren und nichts zu paketieren, die Datei
ist das Programm. Jedes AVD stammt aus einer Zeile in `devices.conf`, also
ist die Flotte, die ein Team betreibt, eine Textdatei, die in git
eingecheckt ist, keine Ansammlung von Klicks, die sich eine Person in einem
Geräte Manager merkt, und eine zweite Maschine erreicht dieselbe Flotte aus
demselben Klon. Genau das zeigen die Diagramme dieser Seite auf der
Mechanik Ebene: AbGal einzusetzen bedeutet, eine Textdatei als Quelle der
Wahrheit für die Emulatoren zu übernehmen, die ein Projekt betreibt,
reproduzierbar auf jeder Maschine, die sie klont.

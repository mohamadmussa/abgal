# Der AbGal Guide

*[In English](README.md)*

Fang mit dem [Schnellstart](../README.md#quick-start) an. Er bringt dich in vier
Schritten von einem frischen Klon zu einem laufenden Android Virtual Device
(AVD). Die Seiten hier sind für das, was danach kommt.

| Seite | Lies sie, wenn |
|---|---|
| [Vorlagen](templates.md) | du einen anderen Bildschirm, eine andere Android Version oder Speichergröße willst |
| [Wie es funktioniert](how-it-works.md) | ein Befehl etwas getan hat, das du nicht erwartet hast |
| [Fehlerbehebung](troubleshooting.md) | ein Befehl mit `ERROR` geendet hat |
| [Ansicht und Steuerung aus dem Browser](view-service.de.md) | du die Web-Oberfläche nutzen oder verstehen willst, wie sie heute funktioniert |
| [Dashboard Design](dashboard-design.de.md) | du das Ziellayout der Web-Oberfläche kennen willst |

## Das Leben eines AVD

Jeder Befehl bringt ein AVD von einem Zustand in einen anderen, gezeichnet im
Lebenslauf des Root READMEs, [Lifecycle](../README.md#lifecycle).

Eine Vorlage ist eine Zeile Text. Ein AVD ist ein Ordner unter `avd/` mit
eigener Platte, gemacht aus dieser Zeile. Ein laufendes AVD ist ein Emulator
Prozess mit einem Serial wie `emulator-5554`, mit dem `adb` und jedes
Testwerkzeug sprechen kann.

## Ein Tag mit AbGal

Zwei AVDs für einen Testlauf, danach wieder weg:

```bash
./abgal create phone-1080x2400-480-api35-x86_64 --as ci --count 2
./abgal start -n ci-01 -n ci-02
./abgal status
./abgal stop -n ci-01 -n ci-02
./abgal delete -n ci-01 --yes
./abgal delete -n ci-02 --yes
```

`start` bootet sie nacheinander und prüft vor jedem den Speicher. `status`
zeigt das Serial jedes AVD, und das braucht das Testwerkzeug. `delete` nimmt
ein AVD je Aufruf.

Ein AVD kann seine Platte auch zwischen den Läufen behalten.
`abgal start -n dev --wipe` bootet es wie neu, ohne es neu anzulegen.

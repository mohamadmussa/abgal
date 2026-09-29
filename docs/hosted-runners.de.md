# GitHub-gehostete Runner

*[In English](hosted-runners.md)*

`.github/workflows/hosted-runner-check.yml` ist eine von Hand ausgelöste
Prüfung, ein Matrix-Zweig je Kandidat-Runner. Sie führt `abgal setup`,
`doctor`, `create`, `start` und `status` aus, hält das AVD 15 Minuten unter
Last, und startet und prüft auf `self-hosted` zusätzlich die
Web-Oberfläche, weil nur dieser Runner in einem erreichbaren Netzwerk
sitzt. Siehe #94.

`ubuntu-slim` wurde ausprobiert und verworfen: sein Container hat einen
festen, einzelnen CPU-Kern, weniger als der Emulator braucht. Kein
arm64-Zweig ist gelistet, die `android` CLI hat kein arm64-Build vorgelagert,
eine Sackgasse, verfolgt in #113.

## Ergebnis

| Runner | doctor | AVD startet | 15-Minuten-Halt | Ergebnis |
|---|---|---|---|---|
| `ubuntu-latest` | bestanden | ja | bestanden | Läuft den vollen Zyklus, Web-Oberfläche von diesem Runner nicht erreichbar, absichtlich übersprungen |
| `ubuntu-26.04` | bestanden | ja | bestanden | Läuft den vollen Zyklus, Web-Oberfläche von diesem Runner nicht erreichbar, absichtlich übersprungen |
| `self-hosted` | bestanden | ja | bestanden | Läuft den vollen Zyklus, Web-Oberfläche gestartet, erreichbar und steuerbar |

# GitHub Actions Runner

*[In English](github-runner.md)*

`abgal github-runner` registriert einen selbst gehosteten GitHub Actions
Runner auf dieser Maschine, entweder als systemd Dienst (Host-Backend)
oder als Docker- oder Podman-Container (Container-Backend), sodass ein
Runner mit derselben Disziplin kommt und geht wie ein AVD. Beide Backends
reichen `/dev/kvm` an den Runner durch, für Jobs, die selbst ein AbGal AVD
starten.

## Befehle

| Befehl | Was er tut |
|---|---|
| `abgal github-runner create -n <name>` | Registriert und startet einen Runner, liest Repo, Labels und Backend aus `runner.conf` |
| `abgal github-runner create -n <name> --repo o/r --backend container` | Überschreibt `runner.conf`, oder definiert einen Runner, der dort gar nicht steht |
| `abgal github-runner status` | Lokale Erreichbarkeit jedes Runners, den diese Maschine verwaltet |
| `abgal github-runner status -n <name> --wait 60` | Wiederholt die Prüfung bis zu 60 Sekunden lang, nützlich direkt nach `create` |
| `abgal github-runner log -n <name>` | Das eigene Log des Runners, genug Zeilen, um eine erfolgreiche Verbindung zu erkennen |
| `abgal github-runner remove -n <name>` | Stoppt den Runner, meldet ihn bei GitHub ab, löscht seinen lokalen Zustand |

Jeder Unterbefehl nimmt `--help`.

## runner.conf

`runner.conf.example` nach `runner.conf` kopieren und pro Runner eine Zeile
eintragen:

```text
name    | repo                  | labels          | backend
ci-01   | myorg/myrepo          | linux,x64       | host
```

`runner.conf` steht in der `.gitignore`, sie nennt eigene Repositories, was
eine Eigenschaft der Maschine ist, die den Runner hostet, nicht des
Projekts. Jede Spalte lässt sich auch auf der Kommandozeile setzen, auch
für einen Runner, der gar nicht in der Datei steht.

## Die zwei Backends

**Host.** `create` lädt den festgelegten Runner-Build aus
`runner-versions.conf`, packt ihn unter `runners/<name>` aus, führt dessen
eigenes `config.sh` zur Registrierung aus, dann `svc.sh install` und
`svc.sh start`. `remove` führt genauso `svc.sh stop`, `svc.sh uninstall`
und `config.sh remove` aus. `status` liest `svc.sh status` direkt, ohne
GitHub Abfrage.

**Container.** `create` verweigert den Start, wenn abgal selbst schon in
einem Container läuft, verschachtelte Container werden nicht unterstützt.
Es zieht das Runner-Image von GHCR, oder baut es aus `docker/runner`, wenn
das Ziehen fehlschlägt und dieser Ordner vorhanden ist. Das festgelegte
Tarball aus `runner-versions.conf` wird als Bind Mount unter `/runner` in
den Container eingehängt, sodass nicht das Container-Image über die
Runner-Version entscheidet, sondern weiterhin `runner-versions.conf`. Der
Container bekommt `/dev/kvm` per `--device` durchgereicht, dazu die
`kvm`-Gruppe des Hosts, damit der Container-Nutzer es öffnen kann.
`remove` führt `config.sh remove` im Container über `docker exec` oder
`podman exec` aus, dann wird der Container entfernt. `status` liest den
eigenen Zustand des Containers über `inspect`.

Beide Backends halten eine Zustandsdatei unter `runners/<name>.json` mit
Name, Backend, Repo, Labels und Version des Runners, beim Container-Backend
zusätzlich Engine und Container-Name. `status` und `remove` lesen zuerst
diese Datei, `--backend` bei `remove` zählt nur, wenn die Datei schon
fehlt.

## Registrierungs- und Entfernungs-Token

Standardmäßig holen `create` und `remove` ein kurzlebiges Token über die
eigene `gh` Anmeldung des Aufrufers. `--key <token>` nutzt stattdessen ein
Personal Access Token, für eine Maschine ohne `gh` oder ohne API-Zugriff
darüber.

## runner-versions.conf

Eine Zeile pro getestetem Runner-Build, Architektur, Version,
Download-Adresse und sha256. `create` nimmt die neueste getestete Zeile
für die Architektur der Maschine, außer `--version` nennt eine ältere, die
noch aufgeführt ist. Eine Version, die hier nicht steht, wird nie
installiert. Der Kommentar am Anfang der Datei erklärt, wie eine neu
getestete Zeile hinzukommt.

## Kompatibilität

Wird gefüllt, sobald eine Kombination geprüft und funktionsfähig ist,
siehe die offenen Punkte in Issue #98.

| Runner Version | Backend | Container Engine | Host OS | Ergebnis |
|---|---|---|---|---|
| noch nicht geprüft | | | | |

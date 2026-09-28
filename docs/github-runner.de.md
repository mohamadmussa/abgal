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
und `config.sh remove` aus. `status` liest `svc.sh status`, ohne GitHub
Abfrage. `config.sh` läuft als der Nutzer, unter dem abgal selbst läuft, und
verweigert Root. `svc.sh` ist der eigene systemd-Wrapper des Runners und
verweigert für jeden seiner Befehle, auch `status`, jeden anderen Nutzer als
Root. abgal führt `svc.sh` deshalb immer über `sudo` aus, unabhängig davon
wie abgal selbst gestartet wurde, sodass create, remove und jede
status-Abfrage nach einem sudo-Passwort fragen können, außer das Konto hat
passwortloses sudo dafür eingerichtet.

**Container.** `create` verweigert den Start, wenn abgal selbst schon in
einem Container läuft, verschachtelte Container werden nicht unterstützt.
Es zieht das Runner-Image mit dem Tag der festgelegten Runner-Version aus
`runner-versions.conf` (zum Beispiel
`ghcr.io/mohamadmussa/abgal-runner:2.337.0`), oder baut denselben Tag aus
`docker/runner`, wenn das Ziehen fehlschlägt und dieser Ordner vorhanden
ist. `ABGAL_RUNNER_IMAGE` überschreibt den Image-Namen für einen Fork mit
eigenem Image, Standard ist `ghcr.io/mohamadmussa/abgal-runner`. Das
festgelegte Tarball aus `runner-versions.conf` wird als Bind Mount unter
`/runner` in den Container eingehängt, sodass nicht das Container-Image
über die Runner-Version entscheidet, sondern weiterhin
`runner-versions.conf`. Der Container läuft unter der eigenen UID des
Aufrufers, nicht als root, der Runner verweigert die Registrierung als
root, und root würde auch Dateien unter `runners/<name>` hinterlassen, die
abgal selbst nicht mehr aufräumen könnte. Er bekommt `/dev/kvm` per
`--device` durchgereicht, dazu die `kvm`-Gruppe des Hosts, damit er es
trotzdem öffnen kann. `remove` führt `config.sh remove` im Container über
`docker exec` oder `podman exec` aus, dann wird der Container entfernt.
`status` liest den eigenen Zustand des Containers über `inspect`.

Läuft abgal selbst als root, gibt `create` einen Hinweis aus, dass der
Container das übernimmt und der Runner die Registrierung dann verweigert;
abgal stattdessen als normaler Nutzer ausführen.

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
| 2.337.0 | container | Docker 20.10.24 | Debian 12 (bookworm) | Registriert sich, zeigt "Listening for Jobs", meldet sich bei remove sauber ab und räumt auf |
| 2.337.0 | host | entfällt | Debian 12 (bookworm) | Registriert sich, zeigt "Listening for Jobs", meldet sich bei remove sauber ab und räumt auf, sudo nötig für create und remove |

# apk

*[In English](README.md)*

Die App Pakete, die ein Lauf installiert. Alles hier drin ist per git
ignoriert, diese Datei ist die eine Ausnahme.

Eine moderne Android App kommt nicht als einzelne Datei. Sie besteht aus
einem Basispaket plus je einem Split für Bildschirmdichte, Architektur und
Sprache, und der Emulator braucht die passenden davon. `bin/fetch-app.sh`
holt diesen Satz von einem Gerät oder Emulator, auf dem die App schon
installiert ist, `bin/install-app.sh` spielt ihn auf ein anderes.

## Aufbau

    apk/
      splits-v<version>-<arch>/
        base.apk
        split_config.<density>.apk
        split_config.<arch>.apk
        split_config.<language>.apk
        PROVENANCE.txt

`PROVENANCE.txt` hält fest, woher der Satz stammt und von wann. Ohne das
sind es nur Dateien, und niemand kann später sagen, welcher Build getestet
wurde.

## Warum die Dateien nicht eingecheckt sind

Drei Gründe. Sie sind groß, sie sind Binärdateien, die kein Diff zeigen
kann, und sie gehören dem, der die App veröffentlicht hat, nicht diesem
Repository. Ein Lauf legt die Version in `app.conf` fest und holt die
Dateien, er trägt sie nicht mit sich.

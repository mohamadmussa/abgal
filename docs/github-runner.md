# GitHub Actions runners

*[Auf Deutsch](github-runner.de.md)*

`abgal github-runner` registers a self hosted GitHub Actions runner on this
machine, either as a systemd service (the host backend) or as a Docker or
Podman container (the container backend), so a runner comes and goes with
the same discipline as a guest. Both backends pass `/dev/kvm` through to
the runner, for jobs that boot an AbGal guest themselves.

## Commands

| Command | What it does |
|---|---|
| `abgal github-runner create -n <name>` | Registers and starts a runner, reading `runner.conf` for its repo, labels and backend |
| `abgal github-runner create -n <name> --repo o/r --backend container` | Overrides `runner.conf`, or defines a runner not listed there at all |
| `abgal github-runner status` | Local liveness of every runner this machine manages |
| `abgal github-runner status -n <name> --wait 60` | Repeats the check for up to 60 seconds, useful right after `create` |
| `abgal github-runner log -n <name>` | The runner's own log, enough lines to catch a successful connection |
| `abgal github-runner remove -n <name>` | Stops the runner, deregisters it from GitHub, deletes its local state |

Every subcommand takes `--help`.

## runner.conf

Copy `runner.conf.example` to `runner.conf` and add a line per runner:

```text
name    | repo                  | labels          | backend
ci-01   | myorg/myrepo          | linux,x64       | host
```

`runner.conf` is gitignored, it names your own repositories, which is a
property of the machine that hosts the runner, not of this project. Any
column can also be set on the command line, for a runner not listed in the
file at all.

## The two backends

**Host.** `create` fetches the pinned runner build from
`runner-versions.conf`, unpacks it under `runners/<name>`, runs its own
`config.sh` to register, then `svc.sh install` and `svc.sh start`. `remove`
runs `svc.sh stop`, `svc.sh uninstall` and `config.sh remove` the same way.
`status` reads `svc.sh status`, no GitHub query involved. `config.sh` runs
as whichever user abgal itself runs as, and refuses to run as root; `svc.sh`
is the runner's own systemd wrapper and refuses to run as anyone but root,
for every one of its own commands including `status`. abgal therefore always
runs `svc.sh` through `sudo`, regardless of how abgal itself was started, so
create, remove and every status check may prompt for a sudo password unless
the account has passwordless sudo set up for it.

**Container.** `create` refuses to run when abgal itself is already inside
a container, nested containers are not supported. It pulls the runner
image tagged with the pinned runner version from `runner-versions.conf`
(`ghcr.io/mohamadmussa/abgal-runner:2.337.0`, for example), or builds that
same tag from `docker/runner` when the pull fails and that folder is
present. `ABGAL_RUNNER_IMAGE` overrides the image name for a fork building
its own, `ghcr.io/mohamadmussa/abgal-runner` by default. The pinned
tarball from `runner-versions.conf` is bind mounted into the container at
`/runner`, so the container image never decides the runner's version,
`runner-versions.conf` still does. The container runs as the calling
user's own uid, not root, the runner refuses to register as root and root
would also leave files under `runners/<name>` that abgal itself could not
clean up again. It gets `/dev/kvm` passed through with `--device`, plus
the host's `kvm` group so it can open it despite not being root. `remove`
runs `config.sh remove` inside the container through `docker exec` or
`podman exec`, then removes the container. `status` reads the container's
own state through `inspect`.

If abgal itself runs as root, `create` prints a note that the container
will inherit that and the runner will then refuse to register; run abgal
as a normal user instead.

Either backend keeps a state file at `runners/<name>.json` with the
runner's name, backend, repo, labels, version, and for the container
backend its engine and container name. `status` and `remove` read this
file first, `--backend` on `remove` only matters when the file is
already gone.

## Registration and removal tokens

By default `create` and `remove` fetch a short lived token through the
caller's own `gh` login. `--key <token>` uses a personal access token
instead, for a machine without `gh` or without API access through it.

## runner-versions.conf

One line per tested runner build, architecture, version, download url and
sha256. `create` takes the newest tested line for the machine's
architecture unless `--version` names an older one still listed. A version
not listed here is never installed. See the comment at the top of the file
for how to add a newly tested line.

## Compatibility

Filled in as a combination is verified working, see the open items in
issue #98.

| Runner version | Backend | Container engine | Host OS | Result |
|---|---|---|---|---|
| 2.337.0 | container | Docker 20.10.24 | Debian 12 (bookworm) | Registers, shows "Listening for Jobs", deregisters and cleans up on remove |
| 2.337.0 | host | not applicable | Debian 12 (bookworm) | Registers, shows "Listening for Jobs", deregisters and cleans up on remove, sudo required for create and remove |

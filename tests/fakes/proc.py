"""A fake /proc tree, written under a temporary folder.

abgal reads processes and memory through its PROC constant. Point that at
FakeProc.root and every reader sees only what a test put there.
"""

import shutil

import abgal

# Fields after the closing ")" of /proc/<pid>/stat. Index 0 is the state,
# abgal reads utime, stime and starttime at 11, 12 and 19.
STAT_FIELDS = 50


class FakeProc:

    def __init__(self, root, uptime=1000.0, available_kb=8 * 1024 * 1024):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.set_uptime(uptime)
        self.set_available(available_kb)

    def set_uptime(self, seconds):
        (self.root / "uptime").write_text("%.2f 0.00\n" % seconds)

    def set_available(self, available_kb):
        """None leaves the MemAvailable line out, as on an old kernel."""
        lines = ["MemTotal:       16384000 kB", "MemFree:         1024000 kB"]
        if available_kb is not None:
            lines.append("MemAvailable:   %8d kB" % available_kb)
        (self.root / "meminfo").write_text("\n".join(lines) + "\n")

    def add_process(self, pid, comm, args, rss_kb=0, utime=0, stime=0,
                    starttime=0):
        folder = self.root / str(pid)
        folder.mkdir()
        (folder / "comm").write_text(comm + "\n")
        (folder / "cmdline").write_bytes(
            b"".join(a.encode() + b"\0" for a in args))
        (folder / "status").write_text(
            "Name:\t%s\nState:\tS (sleeping)\nVmRSS:\t%d kB\n" % (comm, rss_kb))
        fields = ["0"] * STAT_FIELDS
        fields[0] = "S"
        fields[11], fields[12], fields[19] = str(utime), str(stime), str(starttime)
        (folder / "stat").write_text("%d (%s) %s\n" % (pid, comm, " ".join(fields)))

    def add_emulator(self, pid, name, **stats):
        """One emulator process, with the command line abgal starts it with."""
        args = [str(abgal.SDK / "emulator" / "qemu" / "linux-x86_64" / "qemu-system-x86_64"),
                "-avd", name, "-no-window"]
        self.add_process(pid, abgal.QEMU, args, **stats)

    def add_watch(self, pid, name=None, **stats):
        """One temperature watch process, with the command line start detaches."""
        args = ["python3", str(abgal.Path(abgal.__file__).resolve()), "watch"]
        if name:
            args += ["-n", name]
        self.add_process(pid, "python3", args, **stats)

    def remove(self, pid):
        shutil.rmtree(self.root / str(pid), ignore_errors=True)

    def pids(self):
        return sorted(int(p.name) for p in self.root.iterdir() if p.name.isdigit())

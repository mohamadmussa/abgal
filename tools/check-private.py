#!/usr/bin/env python3
"""Refuse to publish anything private.

Reads what git is about to record rather than what happens to lie in the
working tree, because only the first of those ever reaches a remote. Reports
how often a pattern matched and in which file, never the matched value, so the
report itself stays safe to paste anywhere.

    tools/check-private.py              the staged content, what a commit would record
    tools/check-private.py --all        every tracked file
    tools/check-private.py --tree       every file on disk, works before git init

Exit code 0 means clean, 1 means findings, 2 means the scan could not run.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORDS = os.path.join(ROOT, ".private-words")

# Directories the --tree walk stays out of. They mirror .gitignore, because
# before git init there is no index to ask.
SKIP_DIRS = {".git", "sdk", "avd", "experiments", "runs", "results", "apk",
             "__pycache__", "node_modules", "logs", "android-home"}
# Also from .gitignore, but by path rather than by name: tools/local/ is
# ignored by its path, and .private-words holds the deny list itself, so it
# always matches its own patterns.
SKIP_PATHS = {"tools/local", ".private-words"}
SKIP_SUFFIX = (".de.md", ".log", ".pyc", ".png", ".jpg", ".zip", ".apk")
# Anything carrying .local. is ignored by git and can never be committed, so
# scanning it only produces noise. A directory named *.local is skipped whole.
SKIP_MARK = ".local."

# Label of the umlaut pattern below, named so the .de.md exemption in main()
# can skip it by identity instead of by a duplicated string literal.
UMLAUT_LABEL = "non English letter"

# Committed German mirrors, exempt from UMLAUT_LABEL by exact path, not by
# suffix. Every other .de.md file stays local per .gitignore and is never
# staged, so widening this to every *.de.md path would only ever weaken the
# check for a file that should not exist in a commit in the first place.
UMLAUT_EXEMPT_PATHS = {
    "docs/architecture.de.md",
    "docs/README.de.md",
    "docs/templates.de.md",
    "docs/how-it-works.de.md",
    "docs/troubleshooting.de.md",
    "docs/dashboard-design.de.md",
}

# Structural patterns. These describe a shape, not a value, so the list is
# safe to publish. Anything that is a literal belongs in .private-words.
PATTERNS = [
    ("private IPv4 address",
     rb"\b(?:192\.168|10\.|172\.(?:1[6-9]|2[0-9]|3[01]))\.[0-9]{1,3}\.[0-9]{1,3}\b"),
    ("mail address",
     rb"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("phone number with country code",
     rb"\+[0-9]{1,3}[ .-]?[0-9]{6,}"),
    ("device serial number",
     rb"\bR[0-9A-Z]{10}\b"),
    ("absolute home directory",
     rb"/(?:home|Users)/[a-z][a-z0-9._-]*"),
    # A spelled out path only. "$HOME/.kube/" and "~/.kube/" name no user and
    # are the documented default everywhere, so they run through.
    ("kubeconfig path",
     rb"(?<!\$HOME/)(?<!\$\{HOME\}/)(?<!~/)\.kube/"),
    ("home network host name",
     rb"\b[a-z0-9][a-z0-9-]*\.(?:fritz\.box|lan|home\.arpa|internal)\b"),
    ("long digit run",
     rb"\b[0-9]{9,}\b"),
    (UMLAUT_LABEL,
     "[äöüßÄÖÜàáâçéèêëíìîïñóòôõúùûý]".encode()),
]


def run(args):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True)
    except OSError as err:
        fail("could not run '%s': %s" % (" ".join(args), err))


def fail(message):
    """Stop because the scan could not run. That is exit code 2, not a finding."""
    print(message, file=sys.stderr)
    sys.exit(2)


def load_extra():
    """Read the local deny list. Absent is allowed, empty is not a finding."""
    out = []
    if not os.path.exists(WORDS):
        return out
    try:
        with open(WORDS, encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                if "=" not in line:
                    fail("%s line %d: expected 'label = regex'" % (WORDS, n))
                label, expr = (s.strip() for s in line.split("=", 1))
                try:
                    out.append((label, re.compile(expr.encode(), re.IGNORECASE)))
                except re.error as err:
                    fail("%s line %d: %s" % (WORDS, n, err))
    except OSError as err:
        fail("%s: %s" % (WORDS, err))
    return out


def in_repo():
    return run(["git", "rev-parse", "--git-dir"]).returncode == 0


def staged():
    """Path and staged bytes for everything a commit would record."""
    if run(["git", "rev-parse", "--verify", "HEAD"]).returncode == 0:
        names = run(["git", "diff", "--cached", "--name-only",
                     "--diff-filter=ACMR"])
        if names.returncode != 0:
            fail("git diff failed: " + names.stderr.decode().strip())
    else:
        names = run(["git", "ls-files", "--cached"])
        if names.returncode != 0:
            fail("git ls-files failed: " + names.stderr.decode().strip())
    for path in names.stdout.decode().splitlines():
        blob = run(["git", "show", ":" + path])
        if blob.returncode != 0:
            fail("git show failed: " + blob.stderr.decode().strip())
        yield path, blob.stdout


def tracked():
    names = run(["git", "ls-files", "--cached"])
    if names.returncode != 0:
        fail("git ls-files failed: " + names.stderr.decode().strip())
    for path in names.stdout.decode().splitlines():
        full = os.path.join(ROOT, path)
        if os.path.isfile(full):
            with open(full, "rb") as fh:
                yield path, fh.read()


def on_disk():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs
                   if d not in SKIP_DIRS and not d.endswith(".local")
                   and os.path.relpath(os.path.join(base, d), ROOT) not in SKIP_PATHS]
        for name in sorted(files):
            full = os.path.join(base, name)
            rel = os.path.relpath(full, ROOT)
            if name.endswith(SKIP_SUFFIX) or SKIP_MARK in name or rel in SKIP_PATHS:
                continue
            # A dangling symlink is not an error, there is simply nothing there
            # to scan.
            if not os.path.isfile(full):
                continue
            with open(full, "rb") as fh:
                yield rel, fh.read()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--staged"
    if mode not in ("--staged", "--all", "--tree"):
        fail(__doc__)
    if mode in ("--staged", "--all") and not in_repo():
        fail("not a git repository, use --tree")

    checks = [(label, re.compile(expr)) for label, expr in PATTERNS]
    checks += load_extra()
    source = {"--staged": staged, "--all": tracked, "--tree": on_disk}[mode]

    me = os.path.relpath(os.path.abspath(__file__), ROOT)
    findings = {}
    scanned = skipped = 0
    # A file that vanishes or turns unreadable mid walk is not a finding, it
    # is a reason the scan itself could not finish.
    try:
        for path, data in source():
            if path == me:
                # The scanner describes the patterns it hunts, so it would always
                # report itself. Everything else is scanned without exception.
                continue
            if b"\0" in data[:8192]:
                skipped += 1
                continue
            scanned += 1
            for label, rx in checks:
                # German prose in a committed mirror legitimately carries
                # umlauts. Every other pattern still runs, a mirror can leak
                # an address or a phone number exactly like any other file.
                if label == UMLAUT_LABEL and path in UMLAUT_EXEMPT_PATHS:
                    continue
                n = len(rx.findall(data))
                if n:
                    findings.setdefault(label, {})[path] = n
    except OSError as err:
        fail(str(err))

    print("AbGal commit gate, mode %s" % mode[2:])
    print("Scanned %d text files, skipped %d binary." % (scanned, skipped))
    if not os.path.exists(WORDS):
        print("No .private-words present, structural patterns only.")
    print()
    total = 0
    for label, _ in checks:
        hits = findings.get(label, {})
        count = sum(hits.values())
        total += count
        print("  %-34s %4d" % (label, count))
        for path, n in sorted(hits.items()):
            print("      %-56s %d" % (path, n))
    print()
    if total:
        print("REFUSED: %d match(es). Nothing was committed." % total)
        print("Open the files named above. The value is not printed here on")
        print("purpose, so that this report stays safe to share.")
        return 1
    print("CLEAR: no match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""The machine the e2e tests run on is ready for guests.

Runs abgal doctor the way a user does, as its own process. It only reads,
so it changes nothing on the runner. The first test to fail here explains
every other e2e failure after it.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_doctor_reports_the_machine_ready():
    done = subprocess.run([sys.executable, str(ROOT / "abgal"), "doctor"],
                          capture_output=True, text=True, timeout=120)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready." in done.stdout

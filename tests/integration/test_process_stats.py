"""Per process memory and CPU, read straight from /proc."""

import os
import subprocess

import abgal


def test_process_stats_of_the_running_test_process():
    stats = abgal.process_stats(os.getpid())

    assert stats is not None
    assert stats["mem_mb"] > 0
    assert stats["cpu_percent"] >= 0


def test_process_stats_of_a_gone_process_is_none():
    child = subprocess.Popen(["true"])
    child.wait()

    assert abgal.process_stats(child.pid) is None

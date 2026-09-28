"""What abgal reads from /proc, against a fake tree instead of the real one."""

import os

import abgal


def test_available_memory_comes_from_mem_available(fake_proc):
    fake_proc.set_available(3 * 1024 * 1024)

    assert abgal.available_mb() == 3072


def test_available_memory_is_none_without_mem_available(fake_proc):
    fake_proc.set_available(None)

    assert abgal.available_mb() is None


def test_only_emulator_processes_are_listed(fake_proc):
    fake_proc.add_emulator(4100, "pixel")
    fake_proc.add_process(4200, "bash", ["/bin/bash", "-avd", "pixel"])

    found = list(abgal.qemu_processes())

    assert [pid for pid, _ in found] == [4100]
    assert "pixel" in found[0][1]


def test_running_pid_matches_the_whole_name(fake_proc):
    fake_proc.add_emulator(4100, "pixel2")

    assert abgal.running_pid("pixel2") == 4100
    assert abgal.running_pid("pixel") is None


def test_running_pid_is_none_when_nothing_runs(fake_proc):
    assert abgal.running_pid("pixel") is None


def test_process_stats_reads_memory_and_average_cpu(fake_proc):
    tick = os.sysconf("SC_CLK_TCK")
    fake_proc.set_uptime(1000.0)
    # Started 100 seconds ago, 50 seconds of CPU time since, so 50 percent.
    fake_proc.add_emulator(4100, "pixel", rss_kb=2048 * 1024,
                           utime=30 * tick, stime=20 * tick, starttime=900 * tick)

    assert abgal.process_stats(4100) == {"mem_mb": 2048, "cpu_percent": 50.0}


def test_process_stats_survives_a_name_with_parentheses(fake_proc):
    tick = os.sysconf("SC_CLK_TCK")
    fake_proc.set_uptime(1000.0)
    fake_proc.add_process(4300, "odd) (name", ["odd"], rss_kb=1024,
                          utime=10 * tick, stime=0, starttime=990 * tick)

    assert abgal.process_stats(4300) == {"mem_mb": 1, "cpu_percent": 100.0}


def test_process_stats_is_none_for_a_process_that_is_gone(fake_proc):
    assert abgal.process_stats(4999) is None

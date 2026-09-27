"""runner-versions.conf: parsing and picking the tested build to install.

abgal.HOME is monkeypatched to a temp folder so this never reads the real
runner-versions.conf, and platform.machine() is monkeypatched so the test
does not depend on which architecture runs the suite.
"""

import pytest

import abgal


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "HOME", tmp_path)
    return tmp_path


def write_conf(home, text):
    (home / "runner-versions.conf").write_text(text)


def test_runner_version_rows_without_the_file_is_empty(home):
    assert abgal.runner_version_rows() == []


def test_runner_version_row_parses_the_four_columns(home):
    assert abgal.runner_version_row("linux-x64 | 2.337.0 | url | sha") == {
        "arch": "linux-x64", "version": "2.337.0", "url": "url", "sha256": "sha"}


def test_runner_version_rows_skips_comments_and_blank_lines(home):
    write_conf(home, "# a comment\n\nlinux-x64 | 2.337.0 | url | sha\n")

    assert abgal.runner_version_rows() == [
        {"arch": "linux-x64", "version": "2.337.0", "url": "url", "sha256": "sha"}]


def test_pick_runner_version_takes_the_newest_row_for_this_arch(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    write_conf(home, "\n".join([
        "linux-x64 | 2.336.0 | url-old | sha-old",
        "linux-arm64 | 2.337.0 | url-arm | sha-arm",
        "linux-x64 | 2.337.0 | url-new | sha-new",
    ]))

    row = abgal.pick_runner_version()

    assert row == {"arch": "linux-x64", "version": "2.337.0", "url": "url-new", "sha256": "sha-new"}


def test_pick_runner_version_with_a_version_takes_that_row(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    write_conf(home, "\n".join([
        "linux-x64 | 2.336.0 | url-old | sha-old",
        "linux-x64 | 2.337.0 | url-new | sha-new",
    ]))

    row = abgal.pick_runner_version("2.336.0")

    assert row["url"] == "url-old"


def test_pick_runner_version_with_an_unlisted_version_is_none(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    write_conf(home, "linux-x64 | 2.337.0 | url | sha\n")

    assert abgal.pick_runner_version("9.9.9") is None


def test_pick_runner_version_with_an_unsupported_arch_is_none(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "riscv64")
    write_conf(home, "linux-x64 | 2.337.0 | url | sha\n")

    assert abgal.pick_runner_version() is None


class FakeReleaseResponse:
    def __init__(self, data):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._data


def test_latest_runner_release_strips_the_leading_v(monkeypatch):
    monkeypatch.setattr(abgal.urllib.request, "urlopen",
                        lambda url, timeout: FakeReleaseResponse(b'{"tag_name": "v2.338.0"}'))

    assert abgal.latest_runner_release() == "2.338.0"


def test_latest_runner_release_without_network_is_none(monkeypatch):
    def raises(url, timeout):
        raise OSError("no network")
    monkeypatch.setattr(abgal.urllib.request, "urlopen", raises)

    assert abgal.latest_runner_release() is None


def test_doctor_checks_when_the_pinned_version_is_the_newest(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    write_conf(home, "linux-x64 | 2.337.0 | url | sha\n")
    monkeypatch.setattr(abgal, "latest_runner_release", lambda: "2.337.0")
    monkeypatch.setattr(abgal, "version_rows", lambda: [])
    monkeypatch.setattr(abgal, "template_rows", lambda: [])

    checks = abgal.doctor_checks()

    runner_check = next(c for c in checks if c[1] == "GitHub Actions runner")
    assert runner_check[0] == "ok"
    assert "newest release" in runner_check[2]


def test_doctor_checks_when_a_newer_version_is_out(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    write_conf(home, "linux-x64 | 2.337.0 | url | sha\n")
    monkeypatch.setattr(abgal, "latest_runner_release", lambda: "2.338.0")
    monkeypatch.setattr(abgal, "version_rows", lambda: [])
    monkeypatch.setattr(abgal, "template_rows", lambda: [])

    checks = abgal.doctor_checks()

    runner_check = next(c for c in checks if c[1] == "GitHub Actions runner")
    assert runner_check[0] == "later"
    assert "2.337.0 pinned, 2.338.0 is out" in runner_check[2]


def test_doctor_checks_without_network_stays_ok(home, monkeypatch):
    monkeypatch.setattr(abgal.platform, "machine", lambda: "x86_64")
    write_conf(home, "linux-x64 | 2.337.0 | url | sha\n")
    monkeypatch.setattr(abgal, "latest_runner_release", lambda: None)
    monkeypatch.setattr(abgal, "version_rows", lambda: [])
    monkeypatch.setattr(abgal, "template_rows", lambda: [])

    checks = abgal.doctor_checks()

    runner_check = next(c for c in checks if c[1] == "GitHub Actions runner")
    assert runner_check[0] == "ok"
    assert "could not reach GitHub" in runner_check[2]

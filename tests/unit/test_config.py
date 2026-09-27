"""config_lines, set_value and verify against a sample config.ini."""

import abgal

SAMPLE = """\
avd.ini.encoding=UTF-8
abi.type=x86_64
hw.device.name=pixel_6
hw.ramSize=2G
tag.id=google_apis
"""


def test_config_lines_normalizes_spacing(tmp_path):
    config = tmp_path / "config.ini"
    config.write_text("hw.ramSize = 2G\nabi.type=x86_64\n")

    lines = abgal.config_lines(config)

    assert "hw.ramSize=2G" in lines
    assert "abi.type=x86_64" in lines


def test_set_value_adds_a_missing_key():
    lines = ["abi.type=x86_64"]

    abgal.set_value(lines, "hw.camera.front", "emulated")

    assert "hw.camera.front=emulated" in lines


def test_set_value_overwrites_an_existing_key():
    lines = ["hw.ramSize=2G", "abi.type=x86_64"]

    abgal.set_value(lines, "hw.ramSize", "1536")

    assert "hw.ramSize=1536" in lines
    assert "hw.ramSize=2G" not in lines


def test_set_value_leaves_a_matching_key_untouched():
    lines = ["hw.ramSize=1536"]

    abgal.set_value(lines, "hw.ramSize", "1536")

    assert lines == ["hw.ramSize=1536"]


def row(**overrides):
    base = {"name": "phone", "device": "pixel_6", "api": "35", "tag": "google_apis",
            "abi": "x86_64", "ram": "1536", "note": ""}
    base.update(overrides)
    return base


def test_verify_passes_when_every_value_matches(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "device_value",
                        lambda device, name: {"pixel-density": "480", "y-dimension": "2400",
                                              "x-dimension": "1080"}[name])
    config = tmp_path / "config.ini"
    config.write_text("\n".join([
        "abi.type=x86_64",
        "PlayStore.enabled=no",
        "firstboot.bootFromDownloadableSnapshot=no",
        "firstboot.bootFromLocalSnapshot=no",
        "firstboot.saveToLocalSnapshot=no",
        "hw.camera.front=emulated",
        "hw.device.name=pixel_6",
        "hw.lcd.density=480",
        "hw.lcd.height=2400",
        "hw.lcd.width=1080",
        "hw.ramSize=1536",
        "image.sysdir.1=system-images/android-35/google_apis/x86_64/",
        "tag.id=google_apis",
    ]))

    assert abgal.verify(config, row(), "dev") is True


def test_verify_fails_when_avdmanager_dropped_a_value(tmp_path, monkeypatch):
    """The case that motivated verify(): avdmanager silently drops a value."""
    monkeypatch.setattr(abgal, "device_value",
                        lambda device, name: {"pixel-density": "480", "y-dimension": "2400",
                                              "x-dimension": "1080"}[name])
    config = tmp_path / "config.ini"
    config.write_text("\n".join([
        "abi.type=x86_64",
        "PlayStore.enabled=no",
        "firstboot.bootFromDownloadableSnapshot=no",
        "firstboot.bootFromLocalSnapshot=no",
        "firstboot.saveToLocalSnapshot=no",
        # hw.camera.front is missing here, the way avdmanager dropped it.
        "hw.device.name=pixel_6",
        "hw.lcd.density=480",
        "hw.lcd.height=2400",
        "hw.lcd.width=1080",
        "hw.ramSize=1536",
        "image.sysdir.1=system-images/android-35/google_apis/x86_64/",
        "tag.id=google_apis",
    ]))

    assert abgal.verify(config, row(), "dev") is False

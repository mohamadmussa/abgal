"""How abgal finds its guests through adb, against a fake adb."""

import abgal


def test_attached_lists_only_emulators_with_their_state(fake_adb):
    fake_adb.attach("emulator-5554", "pixel")
    fake_adb.attach("emulator-5556", "tablet", state="offline")
    fake_adb.attach("usb-test-phone", "phone")

    assert abgal.attached() == {"emulator-5554": "device",
                                "emulator-5556": "offline"}


def test_attached_is_empty_when_adb_fails(fake_adb):
    fake_adb.attach("emulator-5554", "pixel")
    fake_adb.devices_fails = True

    assert abgal.attached() == {}


def test_running_serials_maps_each_name_to_its_serial(fake_adb):
    fake_adb.attach("emulator-5554", "pixel")
    fake_adb.attach("emulator-5556", "tablet", state="offline")

    assert abgal.running_serials() == {"pixel": "emulator-5554",
                                       "tablet": "emulator-5556"}


def test_running_serials_never_asks_an_unauthorized_console(fake_adb):
    fake_adb.attach("emulator-5554", "pixel")
    fake_adb.attach("emulator-5556", "tablet", state="unauthorized")

    assert abgal.running_serials() == {"pixel": "emulator-5554"}
    assert fake_adb.serials_called("emu", "avd", "name") == ["emulator-5554"]


def test_serial_of_finds_a_guest_by_name(fake_adb):
    fake_adb.attach("emulator-5554", "pixel")
    fake_adb.attach("emulator-5556", "tablet")

    assert abgal.serial_of("tablet") == "emulator-5556"
    assert abgal.serial_of("watch") is None


def test_serial_name_is_none_when_the_console_does_not_answer(fake_adb):
    assert abgal.serial_name("emulator-5554") is None


def test_port_comes_from_the_serial():
    assert abgal.port_of("emulator-5556") == 5556
    assert abgal.port_of("usb-test-phone") == 0

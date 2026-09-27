"""Guest names: accepted and refused. Ids: created once, never changed."""

import abgal


def test_guest_name_accepts_letters_digits_dot_underscore_dash():
    for name in ("dev", "dev-01", "dev.01", "dev_01", "Dev123"):
        assert abgal.GUEST_NAME.match(name), name


def test_guest_name_refuses_anything_else():
    for name in ("dev 01", "dev/01", "dev:01", "", "dev*", "dev,01"):
        assert not abgal.GUEST_NAME.match(name), name


def test_guest_id_is_created_once(tmp_path):
    folder = tmp_path / "dev.avd"
    folder.mkdir()

    first = abgal.guest_id(folder)
    second = abgal.guest_id(folder)

    assert first != "unknown"
    assert first == second


def test_guest_id_two_readers_see_the_same_id(tmp_path):
    folder = tmp_path / "dev.avd"
    folder.mkdir()

    first_reader = abgal.guest_id(folder)
    # A second, independent read of the same folder, as another process would do.
    second_reader = abgal.guest_id(folder)

    assert first_reader == second_reader
    assert (folder / "abgal-id").read_text().strip() == first_reader

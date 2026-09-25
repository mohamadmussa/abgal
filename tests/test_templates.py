"""devices.conf parsing and the image name built from a row."""

import abgal

DEVICES_CONF = """\
# comment, ignored
phone-1080x2400-480-api35-x86_64|pixel_6|35|google_apis|x86_64|1536|phone
store-1080x2400-480-api35-x86_64|pixel_6|35|google_apis_playstore|x86_64|2048|with Play Store

"""


def test_template_rows_parses_every_column(tmp_path, monkeypatch):
    (tmp_path / "devices.conf").write_text(DEVICES_CONF)
    monkeypatch.setattr(abgal, "HOME", tmp_path)

    rows = abgal.template_rows()

    assert len(rows) == 2
    first = rows[0]
    assert first["name"] == "phone-1080x2400-480-api35-x86_64"
    assert first["device"] == "pixel_6"
    assert first["api"] == "35"
    assert first["tag"] == "google_apis"
    assert first["abi"] == "x86_64"
    assert first["ram"] == "1536"
    assert first["note"] == "phone"


def test_template_rows_builds_the_image_name(tmp_path, monkeypatch):
    (tmp_path / "devices.conf").write_text(DEVICES_CONF)
    monkeypatch.setattr(abgal, "HOME", tmp_path)

    rows = abgal.template_rows()

    assert rows[0]["image"] == "system-images;android-35;google_apis;x86_64"
    assert rows[1]["image"] == "system-images;android-35;google_apis_playstore;x86_64"


def test_template_rows_skips_comments_and_blank_lines(tmp_path, monkeypatch):
    (tmp_path / "devices.conf").write_text(DEVICES_CONF)
    monkeypatch.setattr(abgal, "HOME", tmp_path)

    rows = abgal.template_rows()

    assert all(not r["name"].startswith("#") for r in rows)


def test_template_rows_missing_file_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(abgal, "HOME", tmp_path)

    assert abgal.template_rows() == []

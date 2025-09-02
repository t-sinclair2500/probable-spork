# tests/test_media_utils.py
import time

from pathlib import Path

from bin.utils.media import find_voiceover_for_slug, sanitize_text_for_pillow


def test_vo_discovery_prefers_exact(tmp_path, monkeypatch):
    vd = tmp_path / "voiceovers"
    vd.mkdir()
    # create files
    (vd / "2024-08-21_my-slug.mp3").write_bytes(b"")
    time.sleep(0.01)
    (vd / "my-slug_v2.wav").write_bytes(b"")
    time.sleep(0.01)
    (vd / "my-slug.mp3").write_bytes(b"")  # exact
    # redirect search dir
    slug = "my-slug"
    assert find_voiceover_for_slug(slug, search_dirs=[str(vd)]).name == "my-slug.mp3"


def test_vo_discovery_falls_back_newest_reasonable(tmp_path):
    vd = tmp_path / "voiceovers"
    vd.mkdir()
    (vd / "x-my-slug-y.mp3").write_bytes(b"")
    time.sleep(0.01)
    (vd / "z_my-slug_1.m4a").write_bytes(b"")
    path = find_voiceover_for_slug("my-slug", search_dirs=[str(vd)])
    assert path is not None and path.suffix in {".mp3", ".m4a"}


def test_metadata_resolution_order(tmp_path, monkeypatch):
    s = tmp_path / "scripts"
    v = tmp_path / "videos"
    s.mkdir()
    v.mkdir()
    (v / "my-slug.metadata.json").write_text("{}", encoding="utf-8")
    (s / "my-slug.metadata.json").write_text('{"from":"scripts"}', encoding="utf-8")
    # monkeypatch working dir
    cwd = Path.cwd()
    try:
        import os

        os.chdir(tmp_path)
        from bin.utils.media import resolve_metadata_for_slug

        p = resolve_metadata_for_slug("my-slug")
        assert p and p.parent.name == "scripts"
    finally:
        os.chdir(cwd)


def test_sanitize_ellipsis():
    assert sanitize_text_for_pillow("Hello… world") == "Hello... world"
    assert sanitize_text_for_pillow("No ellipsis") == "No ellipsis"

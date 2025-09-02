from bin.packaging.seo_packager import _ensure_coverage, _format_chapters


def test_chapter_formatting():
    sm = [
        {"start_s": 0, "title": "Intro"},
        {"start_s": 12, "title": "Step 1"},
        {"start_s": 33, "title": "Step 2"},
    ]
    ch = _format_chapters(sm, {"merge_below_s": 6, "max_first_chapter_start_s": 5})
    assert ch[0][0] == "00:00" and len(ch) >= 2


def test_ensure_coverage():
    txt = "Hello world"
    kk = ["ai", "automation", "growth"]
    out = _ensure_coverage(txt, kk)
    assert "Keywords:" in out

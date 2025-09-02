from bin.ui.run_helpers import discover_slugs, health_check


def test_health_check_does_not_crash():
    hc = health_check()
    assert "ffmpeg" in hc and "ffprobe" in hc and "videotoolbox" in hc


def test_discover_slugs_does_not_crash():
    slugs = discover_slugs()
    assert isinstance(slugs, list)




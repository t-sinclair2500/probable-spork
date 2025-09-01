from bin.contracts.paths import artifact_paths, ensure_dirs_for_slug


def test_paths_and_dirs(tmp_path, monkeypatch):
    slug = "demo"
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        ensure_dirs_for_slug(slug)
        ap = artifact_paths(slug)
        assert ap["animatics_dir"].exists()
    finally:
        os.chdir(cwd)


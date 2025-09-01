from bin.orchestrator.state import StateMachine, Step


def test_sm_idempotence(monkeypatch, tmp_path):
    ran = []

    def runner(name, cmd):
        ran.append(name)
        return "OK"

    s1 = Step("a", ["echo", "a"], idempotent_outputs=[str(tmp_path / "out.txt")])
    s2 = Step("b", ["echo", "b"]) 
    (tmp_path / "out.txt").write_text("x", encoding="utf-8")
    sm = StateMachine([s1, s2], runner)
    # change CWD so path check is relative
    import os
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        status = sm.run(force=False)
        assert status in ("OK", "PARTIAL")  # skip counts as partial in minimal SM
        assert ran == ["b"]  # a was skipped
    finally:
        os.chdir(cwd)


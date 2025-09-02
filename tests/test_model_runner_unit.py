# tests/test_model_runner_unit.py
from unittest.mock import patch

from bin.model_runner import ModelRunner


# Helpers to simulate Ollama
def _resp(status=200, json=None):
    class R:
        def __init__(self, status, data):
            self.status_code = status
            self._data = data or {}
            self.content = b"{}"

        def json(self):
            return self._data

        def raise_for_status(self):
            if self.status_code >= 400:
                raise Exception(f"HTTP {self.status_code}")

    return R(status, json or {})


def _sequence_responses(seq):
    # yields one response per call
    it = iter(seq)

    def _request(method, url, **kwargs):
        try:
            return next(it)
        except StopIteration:
            return _resp(200, {})

    return _request


@patch("requests.Session.request")
def test_ensure_model_pulls_when_missing(mock_req):
    # 1) /api/tags returns empty -> triggers pull
    # 2) /api/pull ok
    # 3) /api/chat ok
    mock_req.side_effect = _sequence_responses(
        [
            _resp(200, {"models": []}),  # tags
            _resp(200, {}),  # pull
            _resp(200, {"message": {"content": "ok"}}),  # chat
        ]
    )
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=5)
    out = mr.chat([{"role": "user", "content": "hi"}], model="llama3.2:3b")
    assert "message" in out


@patch("requests.Session.request")
def test_no_pull_when_present(mock_req):
    # 1) tags include model -> no pull
    # 2) chat ok
    mock_req.side_effect = _sequence_responses(
        [
            _resp(200, {"models": [{"model": "llama3.2:3b"}]}),  # tags
            _resp(200, {"message": {"content": "ok"}}),  # chat
        ]
    )
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=3)
    out = mr.chat([{"role": "user", "content": "hello"}], model="llama3.2:3b")
    assert out["message"]["content"] == "ok"


@patch("requests.Session.request")
def test_timeout_propagation(mock_req):
    # ensure request called with timeout we set
    captured = {}

    def _spy(method, url, **kwargs):
        captured["timeout"] = kwargs.get("timeout")
        return _resp(200, {"models": [{"model": "llama3.2:3b"}]})

    mock_req.side_effect = _spy
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=7)
    mr.list_tags()
    assert captured["timeout"] == 7


@patch("requests.Session.request")
def test_option_mapping(mock_req):
    # tags + generate; check that options are passed
    calls = []

    def _spy(method, url, **kwargs):
        calls.append((method, url, kwargs.get("json")))
        # First call: tags; Second: generate
        if url.endswith("/api/tags"):
            return _resp(200, {"models": [{"model": "llama3.2:3b"}]})
        return _resp(200, {"response": "ok"})

    mock_req.side_effect = _spy
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=7)
    mr.options.update({"num_ctx": 1024, "temperature": 0.1})
    mr.generate("test", model="llama3.2:3b")
    # find generate call
    gen_call = [c for c in calls if c[1].endswith("/api/generate")][0]
    assert "options" in gen_call[2]
    assert gen_call[2]["options"]["num_ctx"] == 1024
    assert gen_call[2]["options"]["temperature"] == 0.1


@patch("requests.Session.request")
def test_embeddings_with_options(mock_req):
    # Test embeddings endpoint with options
    mock_req.side_effect = _sequence_responses(
        [
            _resp(200, {"models": [{"model": "nomic-embed-text"}]}),  # tags
            _resp(200, {"embeddings": [[0.1, 0.2, 0.3]]}),  # embeddings
        ]
    )
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=5)
    result = mr.embeddings(["test text"], model="nomic-embed-text")
    assert "embeddings" in result


@patch("requests.Session.request")
def test_default_model_fallback(mock_req):
    # Test that defaults are used when no model specified
    mock_req.side_effect = _sequence_responses(
        [
            _resp(200, {"models": [{"model": "llama3.2:3b"}]}),  # tags
            _resp(200, {"message": {"content": "default response"}}),  # chat
        ]
    )
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=5)
    # Set a default chat model
    mr.defaults["chat_model"] = "llama3.2:3b"
    out = mr.chat([{"role": "user", "content": "hi"}])
    assert out["message"]["content"] == "default response"


@patch("requests.Session.request")
def test_error_handling(mock_req):
    # Test that HTTP errors are properly raised
    mock_req.return_value = _resp(500, {"error": "Internal server error"})
    mr = ModelRunner(base_url="http://localhost:11434", timeout_sec=5)
    try:
        mr.list_tags()
        assert False, "Should have raised an exception"
    except Exception as e:
        assert "HTTP 500" in str(e)


@patch("requests.Session.request")
def test_legacy_model_session_compatibility(mock_req):
    # Test that legacy ModelSession still works
    from bin.model_runner import ModelSession

    mock_req.side_effect = _sequence_responses(
        [
            _resp(200, {"models": [{"model": "llama3.2:3b"}]}),  # tags
            _resp(200, {"message": {"content": "legacy response"}}),  # chat
        ]
    )

    with ModelSession("llama3.2:3b", "http://localhost:11434") as session:
        result = session.chat("You are helpful", "Hello")
        assert result == "legacy response"

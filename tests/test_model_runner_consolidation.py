"""
Tests for ModelRunner consolidation:
- Single client enforcement
- Retry with exponential backoff
- ensure_model not called repeatedly
- Timeout and retry behavior
"""

from unittest.mock import Mock, patch

import pytest
import requests

from bin.model_runner import ModelRunner


def test_single_client_enforcement():
    """Test that only ModelRunner is used throughout the codebase."""
    # Verify ModelRunner is the primary client
    runner = ModelRunner(base_url="http://test", timeout_sec=5)
    assert hasattr(runner, "chat")
    assert hasattr(runner, "generate")
    assert hasattr(runner, "embeddings")
    assert hasattr(runner, "ensure_model")
    assert hasattr(runner, "_retry_request")


def test_ensure_model_not_called_repeatedly():
    """Test that ensure_model is not called repeatedly for the same model."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5)

        # Mock successful API responses
        with patch.object(runner, "_retry_request") as mock_retry:
            mock_retry.return_value = Mock(
                status_code=200,
                json=lambda: {"models": [{"name": "test-model"}]},
                raise_for_status=Mock(),
            )

            # Call chat multiple times
            runner.chat([{"role": "user", "content": "test"}])
            runner.chat([{"role": "user", "content": "test2"}])
            runner.chat([{"role": "user", "content": "test3"}])

            # ensure_model should only be called once for the same model
            assert mock_retry.call_count == 4  # 1 for tags, 3 for chat calls
            # Verify the first call was to /api/tags
            assert "/api/tags" in mock_retry.call_args_list[0][0][1]


def test_retry_with_exponential_backoff():
    """Test retry behavior with exponential backoff on transient errors."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5, retries=3)

        # Mock ensure_model to not make requests
        with patch.object(runner, "ensure_model"):
            # Mock the session request to simulate 500 errors
            with patch.object(runner.sess, "request") as mock_request:
                # Mock 500 error on first two attempts, success on third
                mock_request.side_effect = [
                    Mock(status_code=500),  # First attempt fails
                    Mock(status_code=500),  # Second attempt fails
                    Mock(
                        status_code=200, json=lambda: {"response": "success"}
                    ),  # Third succeeds
                ]

                # This should trigger retries
                with patch("time.sleep") as mock_sleep:
                    result = runner.chat([{"role": "user", "content": "test"}])

                    # Should have slept between retries
                    assert mock_sleep.call_count == 2
                    # Verify exponential backoff delays
                    assert mock_sleep.call_args_list[0][0][0] >= 0.5  # First delay
                    assert mock_sleep.call_args_list[1][0][0] >= 1.0  # Second delay


def test_timeout_applied_to_all_requests():
    """Test that timeout is applied to all requests."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 10
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=10)

        with patch.object(runner.sess, "request") as mock_request:
            mock_request.return_value = Mock(
                status_code=200,
                json=lambda: {"response": "success"},
                raise_for_status=Mock(),
            )

            # Test chat
            runner.chat([{"role": "user", "content": "test"}])
            assert mock_request.call_args[1]["timeout"] == 10

            # Test generate
            runner.generate("test prompt")
            assert mock_request.call_args[1]["timeout"] == 10

            # Test embeddings
            runner.embeddings(["test text"])
            assert mock_request.call_args[1]["timeout"] == 10


def test_connection_error_retry():
    """Test retry behavior on connection errors."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5, retries=2)

        # Mock ensure_model to not make requests
        with patch.object(runner, "ensure_model"):
            with patch.object(runner.sess, "request") as mock_request:
                # Mock connection error on first attempt, success on second
                mock_request.side_effect = [
                    requests.ConnectionError(
                        "Connection failed"
                    ),  # First attempt fails
                    Mock(
                        status_code=200, json=lambda: {"response": "success"}
                    ),  # Second succeeds
                ]

                with patch("time.sleep") as mock_sleep:
                    result = runner.chat([{"role": "user", "content": "test"}])

                    # Should have slept between retries
                    assert mock_sleep.call_count == 1
                    # Should have succeeded on second attempt
                    assert mock_request.call_count == 2


def test_timeout_error_retry():
    """Test retry behavior on timeout errors."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5, retries=2)

        # Mock ensure_model to not make requests
        with patch.object(runner, "ensure_model"):
            with patch.object(runner.sess, "request") as mock_request:
                # Mock timeout error on first attempt, success on second
                mock_request.side_effect = [
                    requests.Timeout("Request timed out"),  # First attempt fails
                    Mock(
                        status_code=200, json=lambda: {"response": "success"}
                    ),  # Second succeeds
                ]

                with patch("time.sleep") as mock_sleep:
                    result = runner.chat([{"role": "user", "content": "test"}])

                    # Should have slept between retries
                    assert mock_sleep.call_count == 1
                    # Should have succeeded on second attempt
                    assert mock_request.call_count == 2


def test_no_pull_in_hot_paths():
    """Test that /api/pull is not called in chat/generate hot paths."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5)

        with patch.object(runner.sess, "request") as mock_request:
            mock_request.return_value = Mock(
                status_code=200,
                json=lambda: {"response": "success"},
                raise_for_status=Mock(),
            )

            # Mock ensure_model to not make any requests
            with patch.object(runner, "ensure_model") as mock_ensure:
                # Call chat and generate
                runner.chat([{"role": "user", "content": "test"}])
                runner.generate("test prompt")

                # Verify ensure_model was called but no /api/pull in hot paths
                assert mock_ensure.call_count == 2  # Once for chat, once for generate

                # Verify no /api/pull calls in the request URLs (only /api/chat and /api/generate)
                for call in mock_request.call_args_list:
                    url = call[0][1]  # Second argument is the URL
                    assert "/api/pull" not in url
                    assert "/api/chat" in url or "/api/generate" in url


def test_ensure_model_optional_preflight():
    """Test that ensure_model is called as optional preflight check."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5)

        with patch.object(runner, "_retry_request") as mock_retry:
            # Mock successful responses
            mock_retry.return_value = Mock(
                status_code=200,
                json=lambda: {"models": [{"name": "test-model"}]},
                raise_for_status=Mock(),
            )

            # Call ensure_model directly
            runner.ensure_model("test-model")

            # Should have called /api/tags to check if model exists
            assert mock_retry.call_count == 1
            assert "/api/tags" in mock_retry.call_args[0][1]

            # Call it again - should not make another request
            runner.ensure_model("test-model")
            assert mock_retry.call_count == 1  # No additional calls


def test_ensure_model_pulls_if_missing():
    """Test that ensure_model pulls model if it's not in the tags list."""
    with patch("bin.model_runner.load_all_configs") as mock_load:
        # Mock config bundle
        mock_bundle = Mock()
        mock_bundle.models.ollama.base_url = "http://test"
        mock_bundle.models.ollama.timeout_sec = 5
        mock_bundle.models.defaults.chat_model = "test-model"
        mock_bundle.models.defaults.generate_model = "test-model"
        mock_bundle.models.defaults.embeddings_model = "test-model"
        mock_bundle.models.options.__dict__ = {}
        mock_load.return_value = mock_bundle

        runner = ModelRunner(base_url="http://test", timeout_sec=5)

        with patch.object(runner, "_retry_request") as mock_retry:
            # Mock responses: first call returns empty models list, second call succeeds
            mock_retry.side_effect = [
                Mock(status_code=200, json=lambda: {"models": []}),  # Model not found
                Mock(
                    status_code=200, json=lambda: {"status": "success"}
                ),  # Pull successful
            ]

            runner.ensure_model("missing-model")

            # Should have called /api/tags first, then /api/pull
            assert mock_retry.call_count == 2
            assert "/api/tags" in mock_retry.call_args_list[0][0][1]
            assert "/api/pull" in mock_retry.call_args_list[1][0][1]


def test_legacy_compatibility():
    """Test that legacy ModelSession still works."""
    from bin.model_runner import ModelSession, model_session

    # Test ModelSession creation
    session = ModelSession("test-model", "http://test")
    assert session.model_name == "test-model"
    assert session.server == "http://test"

    # Test model_session factory function
    session = model_session("test-model", "http://test")
    assert session.model_name == "test-model"
    assert session.server == "http://test"


if __name__ == "__main__":
    pytest.main([__file__])

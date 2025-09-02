#!/usr/bin/env python3
"""
Tests for model_runner module.

Tests the context manager behavior and ensures models are properly unloaded.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.model_runner import ModelSession, env_guard, model_session


class TestModelSession:
    """Test the ModelSession context manager."""

    @patch("bin.model_runner.requests.Session")
    @patch("bin.model_runner.subprocess.run")
    def test_context_manager_enter_exit(self, mock_subprocess, mock_session_class):
        """Test that context manager properly enters and exits."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock successful model unload
        mock_subprocess.return_value.returncode = 0

        with model_session("test-model") as session:
            assert isinstance(session, ModelSession)
            assert session.model_name == "test-model"
            assert session._model_loaded is False

        # Verify session was closed
        mock_session.close.assert_called_once()

        # Verify model was not unloaded (since it was never loaded)
        mock_subprocess.assert_not_called()

    @patch("bin.model_runner.requests.Session")
    @patch("bin.model_runner.subprocess.run")
    def test_model_loading_and_unloading(self, mock_subprocess, mock_session_class):
        """Test that models are loaded on first use and unloaded on exit."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock successful model unload
        mock_subprocess.return_value.returncode = 0

        # Mock API responses for model loading check and chat
        mock_ps_response = MagicMock()
        mock_ps_response.status_code = 200
        mock_ps_response.json.return_value = {"models": []}

        mock_chat_response = MagicMock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {"message": {"content": "test response"}}

        mock_session.get.return_value = mock_ps_response
        mock_session.post.return_value = mock_chat_response

        with model_session("test-model") as session:
            # First use should load the model
            session.chat("system", "user")
            assert session._model_loaded is True

        # Verify model was unloaded
        mock_subprocess.assert_called_once_with(
            ["ollama", "stop", "test-model"], capture_output=True, text=True, timeout=30
        )

    @patch("bin.model_runner.requests.Session")
    @patch("bin.model_runner.subprocess.run")
    def test_model_unload_failure_handling(self, mock_subprocess, mock_session_class):
        """Test graceful handling of model unload failures."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock API responses
        mock_ps_response = MagicMock()
        mock_ps_response.status_code = 200
        mock_ps_response.json.return_value = {"models": []}

        mock_chat_response = MagicMock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {"message": {"content": "test response"}}

        mock_session.get.return_value = mock_ps_response
        mock_session.post.return_value = mock_chat_response

        # Mock model unload failure
        mock_subprocess.side_effect = FileNotFoundError("ollama not found")

        with model_session("test-model") as session:
            session.chat("system", "user")
            assert session._model_loaded is True

        # Verify unload was attempted but failure was handled gracefully
        mock_subprocess.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("bin.model_runner.requests.Session")
    def test_chat_method(self, mock_session_class):
        """Test the chat method functionality."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "test response"}}
        mock_session.post.return_value = mock_response

        # Mock model loading response
        mock_ps_response = MagicMock()
        mock_ps_response.status_code = 200
        mock_ps_response.json.return_value = {"models": []}
        mock_session.get.return_value = mock_ps_response

        with model_session("test-model") as session:
            response = session.chat("system", "user")
            assert response == "test response"
            assert session._model_loaded is True

    @patch("bin.model_runner.requests.Session")
    def test_generate_method(self, mock_session_class):
        """Test the generate method functionality."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "generated text"}
        mock_session.post.return_value = mock_response

        # Mock model loading response
        mock_ps_response = MagicMock()
        mock_ps_response.status_code = 200
        mock_ps_response.json.return_value = {"models": []}
        mock_session.get.return_value = mock_ps_response

        with model_session("test-model") as session:
            response = session.generate("test prompt")
            assert response == "generated text"
            assert session._model_loaded is True

    @patch("bin.model_runner.requests.Session")
    def test_model_already_loaded(self, mock_session_class):
        """Test that already loaded models are not reloaded."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock that model is already loaded
        mock_ps_response = MagicMock()
        mock_ps_response.status_code = 200
        mock_ps_response.json.return_value = {"models": [{"name": "test-model"}]}
        mock_session.get.return_value = mock_ps_response

        # Mock successful API response
        mock_chat_response = MagicMock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {"message": {"content": "test response"}}
        mock_session.post.return_value = mock_chat_response

        with model_session("test-model") as session:
            response = session.chat("system", "user")
            assert response == "test response"
            assert session._model_loaded is True

        # Verify that no pull request was made since model was already loaded
        mock_session.post.assert_called_once()  # Only the chat call, not pull


class TestEnvGuard:
    """Test the environment guard functionality."""

    @patch.dict(os.environ, {}, clear=True)
    def test_env_guard_sets_variables(self):
        """Test that env_guard sets the required environment variables."""
        env_guard()

        assert os.environ["OLLAMA_NUM_PARALLEL"] == "1"
        assert os.environ["OLLAMA_TIMEOUT"] == "120"

    @patch.dict(os.environ, {"OLLAMA_TIMEOUT": "60"}, clear=True)
    def test_env_guard_preserves_existing_timeout(self):
        """Test that env_guard doesn't override existing OLLAMA_TIMEOUT."""
        env_guard()

        assert os.environ["OLLAMA_NUM_PARALLEL"] == "1"
        assert os.environ["OLLAMA_TIMEOUT"] == "60"  # Preserved existing value


class TestModelSessionIntegration:
    """Integration tests for ModelSession."""

    @patch("bin.model_runner.requests.Session")
    @patch("bin.model_runner.subprocess.run")
    def test_multiple_operations_same_session(
        self, mock_subprocess, mock_session_class
    ):
        """Test that multiple operations in the same session work correctly."""
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session

        # Mock successful model unload
        mock_subprocess.return_value.returncode = 0

        # Mock API responses
        mock_ps_response = MagicMock()
        mock_ps_response.status_code = 200
        mock_ps_response.json.return_value = {"models": []}

        mock_pull_response = MagicMock()
        mock_pull_response.status_code = 200
        mock_pull_response.json.return_value = {}

        mock_chat_response = MagicMock()
        mock_chat_response.status_code = 200
        mock_chat_response.json.return_value = {"message": {"content": "test response"}}

        mock_generate_response = MagicMock()
        mock_generate_response.status_code = 200
        mock_generate_response.json.return_value = {"response": "generated text"}

        mock_session.get.return_value = mock_ps_response
        # Fix the side effect to return the correct responses in order:
        # 1. /api/pull (model loading)
        # 2. /api/chat (chat request)
        # 3. /api/generate (generate request)
        mock_session.post.side_effect = [
            mock_pull_response,  # First call: model pull
            mock_chat_response,  # Second call: chat
            mock_generate_response,  # Third call: generate
        ]

        with model_session("test-model") as session:
            # Multiple operations should only load the model once
            chat_response = session.chat("system", "user")
            generate_response = session.generate("test prompt")

            assert chat_response == "test response"
            assert generate_response == "generated text"
            assert session._model_loaded is True

        # Verify model was unloaded only once
        mock_subprocess.assert_called_once_with(
            ["ollama", "stop", "test-model"], capture_output=True, text=True, timeout=30
        )


if __name__ == "__main__":
    pytest.main([__file__])

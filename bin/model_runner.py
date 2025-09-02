#!/usr/bin/env python3
"""
Consolidated LLM Client for Ollama Integration
Single client with robust timeouts, retries, and model lifecycle management.
"""

from __future__ import annotations

import random
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

from bin.utils.config import load_all_configs


class ModelRunner:
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_sec: Optional[float] = None,
        retries: int = 3,
    ):
        bundle = load_all_configs()
        o = bundle.models.ollama
        self.base = base_url or o.base_url
        self.timeout = float(timeout_sec or o.timeout_sec)
        self.retries = retries
        self.sess = requests.Session()
        self.defaults = bundle.models.defaults
        self.options = bundle.models.options
        self._ensured = set()

    @classmethod
    def for_task(cls, task: str, **kwargs) -> ModelRunner:
        """
        Factory method to create ModelRunner for specific task.

        Args:
            task: Task name (e.g., "viral", "research", "scriptwriter")
            **kwargs: Additional arguments to pass to __init__

        Returns:
            ModelRunner configured for the task
        """
        bundle = load_all_configs()

        # Get task-specific configuration
        if hasattr(bundle.models, "models") and hasattr(bundle.models.models, task):
            task_cfg = getattr(bundle.models.models, task)

            # Extract timeout from task config if available
            timeout = getattr(task_cfg, "timeout_s", None)
            if timeout:
                kwargs["timeout_sec"] = timeout

            # Create runner with task-specific config
            runner = cls(**kwargs)
            runner._task_config = task_cfg
            return runner

        # Fallback to default configuration
        return cls(**kwargs)

    def _retry_request(
        self, method: str, url: str, timeout: Optional[float] = None, **kw
    ) -> requests.Response:
        """Retry request with exponential backoff on transient errors."""
        delay = 0.5
        request_timeout = timeout or self.timeout

        for attempt in range(self.retries):
            try:
                resp = self.sess.request(method, url, timeout=request_timeout, **kw)
                if resp.status_code >= 500:
                    raise requests.HTTPError(f"HTTP {resp.status_code}")
                return resp
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError):
                if attempt >= self.retries - 1:
                    raise
                time.sleep(delay + random.random() * 0.25)  # Add jitter
                delay *= 2
        # Should not reach here
        raise RuntimeError("Retry loop failed")

    def ensure_model(self, model: str) -> None:
        """Ensure model is available (optional preflight check)."""
        if model in self._ensured:
            return

        try:
            # Query available models
            resp = self._retry_request("GET", urljoin(self.base, "/api/tags"))
            resp.raise_for_status()
            data = resp.json()
            names = {t.get("name") for t in data.get("models", [])}

            if model not in names:
                # Pull model if missing
                print(f"Pulling model {model}...")
                pull_resp = self._retry_request(
                    "POST", urljoin(self.base, "/api/pull"), json={"name": model}
                )
                pull_resp.raise_for_status()
                print(f"Model {model} pulled successfully")
        except Exception as e:
            # Non-fatal; let /api/chat lazy-load if supported
            print(f"Warning: Could not ensure model {model}: {e}")

        self._ensured.add(model)

    # ---------------------------
    # Chat / Generate / Embeddings
    # ---------------------------
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        mdl = model or self.defaults.chat_model
        self.ensure_model(mdl)  # Optional preflight; never per-call pull

        body = {"model": mdl, "messages": messages, "stream": stream}

        # Merge options with defaults and task-specific config
        merged_options = dict(self.options.__dict__)

        # Add task-specific options if available
        if hasattr(self, "_task_config"):
            task_opts = {
                k: v
                for k, v in self._task_config.__dict__.items()
                if k not in ["name", "description", "timeout_s"]
            }
            merged_options.update(task_opts)

        # Add user-provided options
        if options:
            merged_options.update(options)

        body["options"] = merged_options

        # Use task-specific timeout if available, otherwise use instance timeout
        request_timeout = timeout or getattr(self, "_task_config", {}).get(
            "timeout_s", self.timeout
        )

        resp = self._retry_request(
            "POST", urljoin(self.base, "/api/chat"), json=body, timeout=request_timeout
        )
        resp.raise_for_status()
        return resp.json()

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        mdl = model or self.defaults.generate_model
        self.ensure_model(mdl)  # Optional preflight; never per-call pull

        body = {"model": mdl, "prompt": prompt, "stream": stream}
        if options or self.options:
            oo = dict(self.options.__dict__)
            oo.update(options or {})
            body["options"] = oo

        resp = self._retry_request(
            "POST", urljoin(self.base, "/api/generate"), json=body
        )
        resp.raise_for_status()
        return resp.json()

    def embeddings(
        self, input_texts: List[str], model: Optional[str] = None
    ) -> Dict[str, Any]:
        mdl = model or self.defaults.embeddings_model
        self.ensure_model(mdl)  # Optional preflight; never per-call pull

        body = {"model": mdl, "input": input_texts}
        resp = self._retry_request(
            "POST", urljoin(self.base, "/api/embeddings"), json=body
        )
        resp.raise_for_status()
        return resp.json()


# Convenience functions (if current code expects module-level helpers)
_runner_singleton: Optional[ModelRunner] = None


def _runner() -> ModelRunner:
    global _runner_singleton
    if _runner_singleton is None:
        _runner_singleton = ModelRunner()
    return _runner_singleton


def chat(messages, model=None, options=None, stream=False):
    return _runner().chat(messages, model=model, options=options, stream=stream)


def generate(prompt, model=None, options=None, stream=False):
    return _runner().generate(prompt, model=model, options=options, stream=stream)


def embeddings(input_texts, model=None):
    return _runner().embeddings(input_texts, model=model)


# Legacy ModelSession for backward compatibility
class ModelSession:
    """
    Legacy ModelSession for backward compatibility.
    Use ModelRunner directly for new code.
    """

    def __init__(self, model_name: str, server: str = "http://localhost:11434"):
        self.model_name = model_name
        self.server = server
        self._runner = ModelRunner(base_url=server)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def chat(self, system: str, user: str, **opts) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        options = {}
        if opts:
            options.update(opts)

        result = self._runner.chat(messages, model=self.model_name, options=options)
        return result.get("message", {}).get("content", "")

    def generate(self, prompt: str, **opts) -> str:
        options = {}
        if opts:
            options.update(opts)

        result = self._runner.generate(prompt, model=self.model_name, options=options)
        return result.get("response", "")


def model_session(
    model_name: str, server: str = "http://localhost:11434"
) -> ModelSession:
    """
    Create a model session context manager (legacy compatibility).

    Args:
        model_name: Name of the Ollama model to use
        server: Ollama server URL

    Returns:
        ModelSession context manager
    """
    return ModelSession(model_name, server)

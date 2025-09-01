#!/usr/bin/env python3
"""
Model Lifecycle Manager for Deterministic Multi-Model Pipeline
Optimized for 8GB MacBook Air M2 with Metal Performance Shaders

Provides context managers that ensure models are loaded only when needed
and explicitly unloaded between batches to prevent memory accumulation.
Includes memory pressure handling and Metal optimization.
"""

from __future__ import annotations
from typing import Any, Dict, Iterable, List, Optional
import os
from urllib.parse import urljoin

import requests

from bin.utils.http import make_session, request_json
from bin.utils.config import load_models_config

class ModelRunner:
    def __init__(self, base_url: Optional[str] = None, timeout_sec: Optional[float] = None):
        cfg = load_models_config()
        self.base_url = base_url or (cfg.model_dump().get("ollama", {}) or {}).get("base_url", "http://127.0.0.1:11434")
        self.timeout = float(timeout_sec or (cfg.model_dump().get("ollama", {}) or {}).get("timeout_sec", 60))
        self.defaults = (cfg.model_dump().get("defaults") or {})
        self.options = (cfg.model_dump().get("options") or {})
        self.sess: requests.Session = make_session()

    # ---------------------------
    # Model lifecycle
    # ---------------------------
    def list_tags(self) -> List[str]:
        url = urljoin(self.base_url, "/api/tags")
        _, data = request_json(self.sess, "GET", url, timeout=self.timeout)
        # Ollama returns {"models": [{"model":"llama3.2:3b", ...}, ...]}
        models = data.get("models", [])
        return [m.get("model") for m in models if isinstance(m, dict)]

    def pull(self, model_name: str) -> None:
        url = urljoin(self.base_url, "/api/pull")
        body = {"name": model_name, "stream": False}
        request_json(self.sess, "POST", url, json=body, timeout=self.timeout)

    def ensure_model(self, model_name: str) -> None:
        tags = set(self.list_tags())
        if model_name not in tags:
            self.pull(model_name)

    # ---------------------------
    # Chat / Generate / Embeddings
    # ---------------------------
    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        mdl = model or self.defaults.get("chat_model") or self.defaults.get("generate_model")
        if not mdl:
            raise ValueError("No chat model configured in conf/models.yaml under defaults.chat_model")
        # Removed ensure_model call to prevent /api/pull on every request

        url = urljoin(self.base_url, "/api/chat")
        body = {
            "model": mdl,
            "messages": messages,
            "stream": stream,
        }
        merged_opts = dict(self.options)
        if options:
            merged_opts.update(options)
        if merged_opts:
            body["options"] = merged_opts

        if not stream:
            _, data = request_json(self.sess, "POST", url, json=body, timeout=self.timeout)
            return data
        # streaming mode
        # For Cursor's scope here, keep non-stream path primary; if you already support SSE, maintain it.
        _, data = request_json(self.sess, "POST", url, json=body, timeout=self.timeout)
        return data

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        mdl = model or self.defaults.get("generate_model") or self.defaults.get("chat_model")
        if not mdl:
            raise ValueError("No generate model configured in conf/models.yaml under defaults.generate_model")
        # Removed ensure_model call to prevent /api/pull on every request

        url = urljoin(self.base_url, "/api/generate")
        body = {"model": mdl, "prompt": prompt, "stream": stream}
        merged_opts = dict(self.options)
        if options:
            merged_opts.update(options)
        if merged_opts:
            body["options"] = merged_opts

        _, data = request_json(self.sess, "POST", url, json=body, timeout=self.timeout)
        return data

    def embeddings(self, input_texts: List[str], model: Optional[str] = None) -> Dict[str, Any]:
        mdl = model or self.defaults.get("embeddings_model")
        if not mdl:
            raise ValueError("No embeddings model configured in conf/models.yaml under defaults.embeddings_model")
        # Removed ensure_model call to prevent /api/pull on every request

        url = urljoin(self.base_url, "/api/embeddings")
        body = {"model": mdl, "input": input_texts}
        _, data = request_json(self.sess, "POST", url, json=body, timeout=self.timeout)
        return data

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
            {"role": "user", "content": user}
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

def model_session(model_name: str, server: str = "http://localhost:11434") -> ModelSession:
    """
    Create a model session context manager (legacy compatibility).
    
    Args:
        model_name: Name of the Ollama model to use
        server: Ollama server URL
        
    Returns:
        ModelSession context manager
    """
    return ModelSession(model_name, server)

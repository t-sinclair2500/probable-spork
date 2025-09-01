#!/usr/bin/env python3
"""
Reusable Ollama Client for Multi-Model Pipeline

DEPRECATED: This module is deprecated. Use bin.model_runner instead.
"""

import warnings
from bin import model_runner as _mr

warnings.warn(
    "bin/llm_client.py is deprecated; use bin.model_runner instead.",
    DeprecationWarning,
    stacklevel=2,
)

ModelRunner = _mr.ModelRunner
chat = _mr.chat
generate = _mr.generate
embeddings = _mr.embeddings
model_session = _mr.model_session

# Legacy compatibility functions
def run_cluster(tasks, model_name=None):
    """Legacy cluster function - use ModelRunner directly."""
    warnings.warn("run_cluster is deprecated; use ModelRunner.chat() directly", DeprecationWarning)
    messages = [
        {"role": "system", "content": "You are a helpful assistant that clusters topics."},
        {"role": "user", "content": f"Cluster these tasks: {tasks}"}
    ]
    return _mr.chat(messages, model=model_name)

def run_outline(topic, model_name=None):
    """Legacy outline function - use ModelRunner directly."""
    warnings.warn("run_outline is deprecated; use ModelRunner.chat() directly", DeprecationWarning)
    messages = [
        {"role": "system", "content": "You are a helpful assistant that creates outlines."},
        {"role": "user", "content": f"Create an outline for: {topic}"}
    ]
    return _mr.chat(messages, model=model_name)

def ollama_chat(model_type, system, user, **kwargs):
    """Legacy chat function - use ModelRunner.chat() directly."""
    warnings.warn("ollama_chat is deprecated; use ModelRunner.chat() directly", DeprecationWarning)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user}
    ]
    return _mr.chat(messages, **kwargs)

def ollama_embed(text, model_type='embed'):
    """Legacy embed function - use ModelRunner.embeddings() directly."""
    warnings.warn("ollama_embed is deprecated; use ModelRunner.embeddings() directly", DeprecationWarning)
    return _mr.embeddings([text], model=model_type)

#!/usr/bin/env python3
"""
Thin re-export of ModelRunner for backward compatibility.
DEPRECATED: Use bin.model_runner directly.
"""

import warnings

from bin.model_runner import chat, embeddings

warnings.warn(
    "bin/llm_client.py is deprecated; use bin.model_runner directly.",
    DeprecationWarning,
    stacklevel=2,
)


# Legacy compatibility functions
def run_cluster(tasks, model_name=None):
    """Legacy cluster function - use ModelRunner directly."""
    warnings.warn(
        "run_cluster is deprecated; use ModelRunner.chat() directly", DeprecationWarning
    )
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that clusters topics.",
        },
        {"role": "user", "content": f"Cluster these tasks: {tasks}"},
    ]
    return chat(messages, model=model_name)


def run_outline(topic, model_name=None):
    """Legacy outline function - use ModelRunner directly."""
    warnings.warn(
        "run_outline is deprecated; use ModelRunner.chat() directly", DeprecationWarning
    )
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that creates outlines.",
        },
        {"role": "user", "content": f"Create an outline for: {topic}"},
    ]
    return chat(messages, model=model_name)


def ollama_chat(model_type, system, user, **kwargs):
    """Legacy chat function - use ModelRunner.chat() directly."""
    warnings.warn(
        "ollama_chat is deprecated; use ModelRunner.chat() directly", DeprecationWarning
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    return chat(messages, **kwargs)


def ollama_embed(text, model_type="embed"):
    """Legacy embed function - use ModelRunner.embeddings() directly."""
    warnings.warn(
        "ollama_embed is deprecated; use ModelRunner.embeddings() directly",
        DeprecationWarning,
    )
    return embeddings([text], model=model_type)

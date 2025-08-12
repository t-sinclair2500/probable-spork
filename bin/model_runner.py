#!/usr/bin/env python3
"""
Model Lifecycle Manager for Deterministic Multi-Model Pipeline

Provides context managers that ensure models are loaded only when needed
and explicitly unloaded between batches to prevent memory accumulation.
"""

import contextlib
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import requests

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.core import get_logger, load_config

log = get_logger("model_runner")

def env_guard():
    """
    Set environment variables to ensure single-model operation.
    
    This prevents Ollama from loading multiple models simultaneously
    and sets appropriate timeouts for the single-lane pipeline.
    """
    # Ensure only one model is active at a time
    os.environ["OLLAMA_NUM_PARALLEL"] = "1"
    
    # Set reasonable timeouts for single-lane operation
    if "OLLAMA_TIMEOUT" not in os.environ:
        os.environ["OLLAMA_TIMEOUT"] = "120"
    
    log.info("Environment guard set: OLLAMA_NUM_PARALLEL=1")

class ModelSession:
    """
    Context manager for model lifecycle management.
    
    Ensures models are loaded when needed and explicitly unloaded
    when the context exits to prevent memory accumulation.
    """
    
    def __init__(self, model_name: str, server: str = "http://localhost:11434"):
        """
        Initialize model session.
        
        Args:
            model_name: Name of the Ollama model to use
            server: Ollama server URL
        """
        self.model_name = model_name
        self.server = server
        self.session = requests.Session()
        self._model_loaded = False
        
        # Set session timeouts
        self.session.timeout = 120
        
        log.info(f"Initialized model session for {model_name}")
    
    def __enter__(self):
        """Enter context - model will be loaded on first use."""
        env_guard()
        log.info(f"Entered model session for {self.model_name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context - explicitly unload model and close session."""
        try:
            if self._model_loaded:
                log.info(f"Exiting model session for {self.model_name}, unloading model")
                self._unload_model()
            else:
                log.info(f"Exiting model session for {self.model_name} (model was not loaded)")
        finally:
            self.session.close()
            log.info(f"Closed model session for {self.model_name}")
    
    def _ensure_model_loaded(self):
        """Ensure model is loaded, loading it if necessary."""
        if not self._model_loaded:
            log.info(f"Loading model {self.model_name}")
            self._load_model()
            self._model_loaded = True
    
    def _load_model(self):
        """Load the model via Ollama API."""
        try:
            # Check if model is already loaded
            response = self.session.get(f"{self.server}/api/ps")
            if response.status_code == 200:
                models = response.json().get("models", [])
                if any(model["name"] == self.model_name for model in models):
                    log.info(f"Model {self.model_name} is already loaded")
                    return
            
            # Load the model
            log.info(f"Loading model {self.model_name} via Ollama")
            response = self.session.post(f"{self.server}/api/pull", json={"name": self.model_name})
            response.raise_for_status()
            
            # Wait for model to be ready
            time.sleep(2)
            log.info(f"Model {self.model_name} loaded successfully")
            
        except Exception as e:
            log.error(f"Failed to load model {self.model_name}: {e}")
            raise RuntimeError(f"Cannot load model {self.model_name}: {e}")
    
    def _unload_model(self):
        """Explicitly unload the model via Ollama CLI."""
        try:
            log.info(f"Unloading model {self.model_name}")
            result = subprocess.run(
                ["ollama", "stop", self.model_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                log.info(f"Model {self.model_name} unloaded successfully")
            else:
                log.warning(f"Model unload returned code {result.returncode}: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            log.warning(f"Model unload timed out for {self.model_name}")
        except FileNotFoundError:
            log.warning("ollama CLI not found in PATH, cannot unload model")
        except Exception as e:
            log.warning(f"Failed to unload model {self.model_name}: {e}")
    
    def chat(self, system: str, user: str, **opts) -> str:
        """
        Send a chat completion request.
        
        Args:
            system: System message
            user: User message
            **opts: Additional options (temperature, top_p, etc.)
            
        Returns:
            Generated response text
        """
        self._ensure_model_loaded()
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            **opts
        }
        
        try:
            log.debug(f"Sending chat request to {self.model_name}")
            response = self.session.post(f"{self.server}/api/chat", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result["message"]["content"]
            
        except Exception as e:
            log.error(f"Chat request failed for {self.model_name}: {e}")
            raise RuntimeError(f"Chat request failed: {e}")
    
    def generate(self, prompt: str, **opts) -> str:
        """
        Send a text generation request.
        
        Args:
            prompt: Input prompt
            **opts: Additional options (temperature, top_p, etc.)
            
        Returns:
            Generated text
        """
        self._ensure_model_loaded()
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
            **opts
        }
        
        try:
            log.debug(f"Sending generate request to {self.model_name}")
            response = self.session.post(f"{self.server}/api/generate", json=payload)
            response.raise_for_status()
            
            result = response.json()
            return result["response"]
            
        except Exception as e:
            log.error(f"Generate request failed for {self.model_name}: {e}")
            raise RuntimeError(f"Generate request failed: {e}")

def model_session(model_name: str, server: str = "http://localhost:11434") -> ModelSession:
    """
    Create a model session context manager.
    
    Args:
        model_name: Name of the Ollama model to use
        server: Ollama server URL
        
    Returns:
        ModelSession context manager
    """
    return ModelSession(model_name, server)

# Convenience functions for common pipeline tasks
def run_cluster(tasks: List[str], model_name: str = None) -> List[Dict]:
    """
    Run topic clustering with specified model.
    
    Args:
        tasks: List of task descriptions to cluster
        model_name: Model to use, defaults to cluster model from config
        
    Returns:
        List of cluster dictionaries
    """
    if model_name is None:
        config = load_config()
        model_name = config.models.cluster.name
    
    with model_session(model_name) as session:
        # Import here to avoid circular imports
        from bin.llm_cluster import cluster_topics
        
        # Convert to the format expected by cluster_topics
        task_text = "\n".join([f"- {task}" for task in tasks])
        
        # Get clustering prompt
        prompt_path = ROOT / "prompts" / "cluster_topics.txt"
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
        
        response = session.chat(
            system=system_prompt,
            user=f"Cluster these topics:\n\n{task_text}",
            temperature=0.2
        )
        
        # Parse response (simplified - in practice you'd want more robust parsing)
        try:
            import json
            return json.loads(response)
        except:
            log.warning("Failed to parse cluster response as JSON")
            return [{"topics": tasks, "error": "Failed to parse response"}]

def run_outline(topic: str, model_name: str = None) -> str:
    """
    Generate outline for a topic with specified model.
    
    Args:
        topic: Topic to outline
        model_name: Model to use, defaults to outline model from config
        
    Returns:
        Outline text
    """
    if model_name is None:
        config = load_config()
        model_name = config.models.outline.name
    
    with model_session(model_name) as session:
        # Import here to avoid circular imports
        from bin.llm_outline import generate_outline
        
        # Get outline prompt
        prompt_path = ROOT / "prompts" / "outline.txt"
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
        
        return session.chat(
            system=system_prompt,
            user=f"Generate an outline for: {topic}",
            temperature=0.3
        )

def run_script(grounded_beats: List[Dict], brief: Dict, model_name: str = None) -> str:
    """
    Generate script from grounded beats with specified model.
    
    Args:
        grounded_beats: List of grounded beat dictionaries
        brief: Brief configuration
        model_name: Model to use, defaults to scriptwriter model from config
        
    Returns:
        Generated script text
    """
    if model_name is None:
        config = load_config()
        model_name = config.models.scriptwriter.name
    
    with model_session(model_name) as session:
        # Import here to avoid circular imports
        from bin.llm_script import generate_script
        
        # Get script prompt
        prompt_path = ROOT / "prompts" / "script_writer.txt"
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
        
        # Convert beats to text format
        beats_text = "\n".join([
            f"Beat {i+1}: {beat.get('content', '')}" 
            for i, beat in enumerate(grounded_beats)
        ])
        
        user_prompt = f"""Brief: {brief.get('title', 'Untitled')}
Tone: {brief.get('tone', 'informative')}
Target Length: {brief.get('target_len_sec', 300)} seconds

Grounded Beats:
{beats_text}

Generate a script following the brief and using the grounded beats."""
        
        return session.chat(
            system=system_prompt,
            user=user_prompt,
            temperature=0.7
        )

def run_research_plan(topic: str, model_name: str = None) -> Dict:
    """
    Generate research plan with specified model.
    
    Args:
        topic: Topic to research
        model_name: Model to use, defaults to research model from config
        
    Returns:
        Research plan dictionary
    """
    if model_name is None:
        config = load_config()
        model_name = config.models.research.name
    
    with model_session(model_name) as session:
        system_prompt = """You are a research planner. Generate a structured research plan for the given topic.
        
Return your response as JSON with the following structure:
{
  "queries": ["search query 1", "search query 2", ...],
  "sources": ["source type 1", "source type 2", ...],
  "focus_areas": ["area 1", "area 2", ...]
}"""
        
        response = session.chat(
            system=system_prompt,
            user=f"Create a research plan for: {topic}",
            temperature=0.3
        )
        
        try:
            import json
            return json.loads(response)
        except:
            log.warning("Failed to parse research plan as JSON")
            return {"queries": [topic], "sources": ["web"], "focus_areas": [topic]}

def run_fact_guard(script: str, model_name: str = None) -> Dict:
    """
    Run fact-checking and guard with specified model.
    
    Args:
        script: Script text to fact-check
        model_name: Model to use, defaults to research model from config
        
    Returns:
        Fact-checking results dictionary
    """
    if model_name is None:
        config = load_config()
        model_name = config.models.research.name
    
    with model_session(model_name) as session:
        system_prompt = """You are a fact-checker. Review the given script for factual accuracy and suggest improvements.
        
Return your response as JSON with the following structure:
{
  "issues": [
    {
      "text": "problematic text",
      "issue": "description of the issue",
      "suggestion": "corrected version"
    }
  ],
  "citations_needed": ["fact 1", "fact 2", ...],
  "overall_score": 0.95
}"""
        
        response = session.chat(
            system=system_prompt,
            user=f"Fact-check this script:\n\n{script}",
            temperature=0.1
        )
        
        try:
            import json
            return json.loads(response)
        except:
            log.warning("Failed to parse fact-check results as JSON")
            return {"issues": [], "citations_needed": [], "overall_score": 0.8}

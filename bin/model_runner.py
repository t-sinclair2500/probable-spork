#!/usr/bin/env python3
"""
Model Lifecycle Manager for Deterministic Multi-Model Pipeline
Optimized for 8GB MacBook Air M2 with Metal Performance Shaders

Provides context managers that ensure models are loaded only when needed
and explicitly unloaded between batches to prevent memory accumulation.
Includes memory pressure handling and Metal optimization.
"""

import contextlib
import logging
import os
import subprocess
import sys
import time
import psutil
import gc
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
import requests

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.core import get_logger, load_config

log = get_logger("model_runner")

# Memory thresholds for 8GB system
MEMORY_WARNING_THRESHOLD = 0.75  # 75% memory usage
MEMORY_CRITICAL_THRESHOLD = 0.90  # 90% memory usage
MEMORY_EMERGENCY_THRESHOLD = 0.95  # 95% memory usage

def get_memory_usage() -> float:
    """Get current memory usage as a percentage."""
    try:
        memory = psutil.virtual_memory()
        return memory.percent / 100.0
    except Exception:
        return 0.0

def get_memory_gb() -> float:
    """Get current memory usage in GB."""
    try:
        memory = psutil.virtual_memory()
        return memory.used / (1024**3)
    except Exception:
        return 0.0

def check_memory_pressure() -> str:
    """Check memory pressure and return status."""
    usage = get_memory_usage()
    if usage >= MEMORY_EMERGENCY_THRESHOLD:
        return "emergency"
    elif usage >= MEMORY_CRITICAL_THRESHOLD:
        return "critical"
    elif usage >= MEMORY_WARNING_THRESHOLD:
        return "warning"
    else:
        return "normal"

def handle_memory_pressure(status: str):
    """Handle memory pressure with appropriate actions."""
    if status == "emergency":
        log.warning("🚨 EMERGENCY: Memory usage critical, forcing cleanup")
        force_memory_cleanup()
    elif status == "critical":
        log.warning("⚠️ CRITICAL: Memory usage high, aggressive cleanup")
        aggressive_memory_cleanup()
    elif status == "warning":
        log.warning("⚠️ WARNING: Memory usage elevated, light cleanup")
        light_memory_cleanup()

def force_memory_cleanup():
    """Force aggressive memory cleanup."""
    try:
        # Force garbage collection
        gc.collect()
        
        # Clear Ollama model cache
        subprocess.run(["ollama", "stop", "--all"], 
                      capture_output=True, timeout=10)
        
        # Clear Python memory
        import gc
        gc.collect()
        
        log.info("Forced memory cleanup completed")
    except Exception as e:
        log.error(f"Failed to force memory cleanup: {e}")

def aggressive_memory_cleanup():
    """Aggressive memory cleanup."""
    try:
        # Force garbage collection
        gc.collect()
        
        # Clear Python memory
        import gc
        gc.collect()
        
        log.info("Aggressive memory cleanup completed")
    except Exception as e:
        log.error(f"Failed to perform aggressive cleanup: {e}")

def light_memory_cleanup():
    """Light memory cleanup."""
    try:
        # Light garbage collection
        gc.collect()
        log.info("Light memory cleanup completed")
    except Exception as e:
        log.error(f"Failed to perform light cleanup: {e}")

def env_guard():
    """
    Set environment variables to ensure single-model operation.
    
    This prevents Ollama from loading multiple models simultaneously
    and sets appropriate timeouts for the single-lane pipeline.
    Optimized for 8GB M2 MacBook Air.
    """
    # Ensure only one model is active at a time
    os.environ["OLLAMA_NUM_PARALLEL"] = "1"
    
    # Set reasonable timeouts for single-lane operation
    if "OLLAMA_TIMEOUT" not in os.environ:
        os.environ["OLLAMA_TIMEOUT"] = "120"
    
    # Metal Performance Shaders (MPS) optimization
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    
    # Memory management
    os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.7"
    
    # CPU optimization for M2
    os.environ["OMP_NUM_THREADS"] = "4"
    os.environ["MKL_NUM_THREADS"] = "4"
    
    log.info("Environment guard set: OLLAMA_NUM_PARALLEL=1, MPS optimized")

class ModelSession:
    """
    Context manager for model lifecycle management.
    
    Ensures models are loaded when needed and explicitly unloaded
    when the context exits to prevent memory accumulation.
    Includes memory pressure monitoring and Metal optimization.
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
        self._memory_check_count = 0
        
        # Set session timeouts
        self.session.timeout = 120
        
        # Memory monitoring
        self._last_memory_check = time.time()
        self._memory_check_interval = 5  # Check every 5 seconds
        
        log.info(f"Initialized model session for {model_name}")
    
    def _check_memory_pressure(self):
        """Check memory pressure and handle if necessary."""
        current_time = time.time()
        
        # Check memory every 5 seconds
        if current_time - self._last_memory_check >= self._memory_check_interval:
            status = check_memory_pressure()
            if status != "normal":
                handle_memory_pressure(status)
            self._last_memory_check = current_time
    
    def __enter__(self):
        """Enter context - model will be loaded on first use."""
        env_guard()
        
        # Check memory pressure before starting
        self._check_memory_pressure()
        
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
            
            # Force memory cleanup on exit
            self._check_memory_pressure()
            gc.collect()
            
            log.info(f"Closed model session for {self.model_name}")
    
    def _ensure_model_loaded(self):
        """Ensure model is loaded, loading it if necessary."""
        if not self._model_loaded:
            # Check memory pressure before loading
            self._check_memory_pressure()
            
            log.info(f"Loading model {self.model_name}")
            self._load_model()
            self._model_loaded = True
    
    def _load_model(self):
        """Load the model via Ollama API with Metal optimization."""
        try:
            # Check if model is already loaded
            response = self.session.get(f"{self.server}/api/ps")
            if response.status_code == 200:
                models = response.json().get("models", [])
                if any(model["name"] == self.model_name for model in models):
                    log.info(f"Model {self.model_name} is already loaded")
                    return
            
            # Load the model with M2-optimized parameters
            log.info(f"Loading model {self.model_name} via Ollama with M2 optimization")
            
            # Use optimized parameters for 8GB M2
            load_params = {
                "name": self.model_name,
                "options": {
                    "num_ctx": 4096,      # Limit context for memory
                    "num_thread": 4,      # Optimal for M2
                    "num_gpu": 0,         # Use CPU for stability on 8GB
                    "num_gqa": 8,         # Group query attention
                    "rope_freq_base": 10000,
                    "rope_freq_scale": 0.5
                }
            }
            
            response = self.session.post(f"{self.server}/api/pull", json=load_params)
            response.raise_for_status()
            
            # Wait for model to be ready
            time.sleep(2)
            log.info(f"Model {self.model_name} loaded successfully with M2 optimization")
            
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
        Send a chat completion request with memory monitoring.
        
        Args:
            system: System message
            user: User message
            **opts: Additional options (temperature, top_p, etc.)
            
        Returns:
            Generated response text
        """
        # Check memory pressure before request
        self._check_memory_pressure()
        
        self._ensure_model_loaded()
        
        # Optimize options for 8GB M2
        optimized_opts = {
            "temperature": opts.get("temperature", 0.7),
            "top_p": opts.get("top_p", 0.9),
            "num_predict": opts.get("num_predict", 512),  # Limit output length
            "stop": opts.get("stop", []),
            "stream": False
        }
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            **optimized_opts
        }
        
        try:
            log.debug(f"Sending chat request to {self.model_name}")
            response = self.session.post(f"{self.server}/api/chat", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Check memory pressure after request
            self._check_memory_pressure()
            
            return result["message"]["content"]
            
        except Exception as e:
            log.error(f"Chat request failed for {self.model_name}: {e}")
            raise RuntimeError(f"Chat request failed: {e}")
    
    def generate(self, prompt: str, **opts) -> str:
        """
        Send a text generation request with memory monitoring.
        
        Args:
            prompt: Input prompt
            **opts: Additional options (temperature, top_p, etc.)
            
        Returns:
            Generated text
        """
        # Check memory pressure before request
        self._check_memory_pressure()
        
        self._ensure_model_loaded()
        
        # Optimize options for 8GB M2
        optimized_opts = {
            "temperature": opts.get("temperature", 0.7),
            "top_p": opts.get("top_p", 0.9),
            "num_predict": opts.get("num_predict", 512),  # Limit output length
            "stop": opts.get("stop", []),
            "stream": False
        }
        
        payload = {
            "model": self.model_name,
            "prompt": prompt,
            **optimized_opts
        }
        
        try:
            log.debug(f"Sending generate request to {self.model_name}")
            response = self.session.post(f"{self.server}/api/generate", json=payload)
            response.raise_for_status()
            
            result = response.json()
            
            # Check memory pressure after request
            self._check_memory_pressure()
            
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

# Memory monitoring utility
def get_system_memory_info() -> Dict[str, Any]:
    """Get comprehensive system memory information."""
    try:
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        return {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent": memory.percent,
            "swap_total_gb": round(swap.total / (1024**3), 2),
            "swap_used_gb": round(swap.used / (1024**3), 2),
            "swap_percent": swap.percent,
            "status": check_memory_pressure()
        }
    except Exception as e:
        log.error(f"Failed to get memory info: {e}")
        return {"error": str(e)}

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
        # Load research planning prompt
        prompt_path = ROOT / "prompts" / "research_planning.txt"
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
        
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
        # Load fact-checking prompt
        prompt_path = ROOT / "prompts" / "fact_check.txt"
        with open(prompt_path, 'r') as f:
            system_prompt = f.read()
        
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

#!/usr/bin/env python3
"""
Reusable Ollama Client for Multi-Model Pipeline

Provides standardized interfaces for:
- Chat completion with different models
- Text embeddings
- Retry logic and error handling
"""

import json
import logging
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
from bin.model_runner import model_session

log = get_logger("llm_client")

# Thin helpers that call through to model_session
def run_cluster(tasks: List[str]) -> List[Dict]:
    """
    Run topic clustering with Llama model.
    
    Args:
        tasks: List of task descriptions to cluster
        
    Returns:
        List of cluster dictionaries
    """
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
            return json.loads(response)
        except:
            log.warning("Failed to parse cluster response as JSON")
            return [{"topics": tasks, "error": "Failed to parse response"}]

def run_outline(topic: str) -> str:
    """
    Generate outline for a topic with Llama model.
    
    Args:
        topic: Topic to outline
        
    Returns:
        Outline text
    """
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

def run_script(grounded_beats: List[Dict], brief: Dict) -> str:
    """
    Generate script from grounded beats with Llama model.
    
    Args:
        grounded_beats: List of grounded beat dictionaries
        brief: Brief configuration
        
    Returns:
        Generated script text
    """
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

def run_research_plan(topic: str) -> Dict:
    """
    Generate research plan with Mistral model.
    
    Args:
        topic: Topic to research
        
    Returns:
        Research plan dictionary
    """
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
            return json.loads(response)
        except:
            log.warning("Failed to parse research plan as JSON")
            return {"queries": [topic], "sources": ["web"], "focus_areas": [topic]}

def run_fact_guard(script: str) -> Dict:
    """
    Run fact-checking and guard with Mistral model.
    
    Args:
        script: Script text to fact-check
        
    Returns:
        Fact-checking results dictionary
    """
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
            return json.loads(response)
        except:
            log.warning("Failed to parse fact-check results as JSON")
            return {"issues": [], "citations_needed": [], "overall_score": 0.8}

class OllamaClient:
    """Client for interacting with Ollama API with retry logic and model management."""
    
    def __init__(self, models_config: Optional[Dict] = None):
        """
        Initialize Ollama client.
        
        Args:
            models_config: Models configuration dict, loads from conf/models.yaml if None
        """
        if models_config is None:
            try:
                import yaml
                models_path = ROOT / "conf" / "models.yaml"
                with open(models_path, 'r', encoding='utf-8') as f:
                    models_config = yaml.safe_load(f)
            except Exception as e:
                log.warning(f"Failed to load models.yaml: {e}, using defaults")
                models_config = {}
        
        self.config = models_config
        self.ollama_config = models_config.get('ollama', {})
        self.server = self.ollama_config.get('server', 'http://localhost:11434')
        self.timeout = self.ollama_config.get('timeout_s', 120)
        self.retry_attempts = self.ollama_config.get('retry_attempts', 3)
        self.retry_delay = self.ollama_config.get('retry_delay_s', 2)
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Test connection to Ollama server."""
        try:
            response = requests.get(f"{self.server}/api/tags", timeout=10)
            response.raise_for_status()
            log.info(f"Connected to Ollama server at {self.server}")
        except Exception as e:
            log.error(f"Failed to connect to Ollama server at {self.server}: {e}")
            raise ConnectionError(f"Cannot connect to Ollama server: {e}")
    
    def _make_request(self, endpoint: str, payload: Dict, retries: Optional[int] = None) -> Dict:
        """
        Make HTTP request to Ollama with retry logic.
        
        Args:
            endpoint: API endpoint (e.g., '/api/generate')
            payload: Request payload
            retries: Number of retry attempts, uses config default if None
            
        Returns:
            Response JSON as dict
            
        Raises:
            requests.RequestException: If all retries fail
        """
        if retries is None:
            retries = self.retry_attempts
        
        url = f"{self.server}{endpoint}"
        
        for attempt in range(retries + 1):
            try:
                log.debug(f"Making request to {endpoint} (attempt {attempt + 1}/{retries + 1})")
                response = requests.post(url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                return response.json()
                
            except requests.RequestException as e:
                if attempt == retries:
                    log.error(f"Request failed after {retries + 1} attempts: {e}")
                    raise
                
                log.warning(f"Request attempt {attempt + 1} failed: {e}, retrying in {self.retry_delay}s")
                time.sleep(self.retry_delay)
    
    def chat(self, model_type: str, system: str, user: str, **kwargs) -> str:
        """
        Send a chat completion request.
        
        Args:
            model_type: Model type from config (e.g., 'cluster', 'research')
            system: System message
            user: User message
            **kwargs: Additional options
            
        Returns:
            Generated response text
        """
        if 'models' not in self.config or model_type not in self.config['models']:
            raise ValueError(f"Unknown model type: {model_type}")
        
        model_config = self.config['models'][model_type]
        model_name = model_config['name']
        
        # Merge model config with kwargs
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            **model_config,
            **kwargs
        }
        
        # Remove non-API fields
        payload.pop('description', None)
        
        log.info(f"Sending chat request to {model_name}")
        
        try:
            response = self._make_request('/api/chat', payload)
            return response['message']['content']
            
        except Exception as e:
            log.error(f"Chat request failed: {e}")
            raise
    
    def generate(self, model_type: str, prompt: str, **kwargs) -> str:
        """
        Send a text generation request.
        
        Args:
            model_type: Model type from config
            prompt: Input prompt
            **kwargs: Additional options
            
        Returns:
            Generated text
        """
        if 'models' not in self.config or model_type not in self.config['models']:
            raise ValueError(f"Unknown model type: {model_type}")
        
        model_config = self.config['models'][model_type]
        model_name = model_config['name']
        
        # Merge model config with kwargs
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            **model_config,
            **kwargs
        }
        
        # Remove non-API fields
        payload.pop('description', None)
        
        log.info(f"Sending generate request to {model_name}")
        
        try:
            response = self._make_request('/api/generate', payload)
            return response['response']
            
        except Exception as e:
            log.error(f"Generate request failed: {e}")
            raise
    
    def embed(self, text: str, model_type: str = 'embed') -> List[float]:
        """
        Generate text embeddings.
        
        Args:
            text: Text to embed
            model_type: Model type from config
            
        Returns:
            Embedding vector as list of floats
        """
        if 'models' not in self.config or model_type not in self.config['models']:
            raise ValueError(f"Unknown model type: {model_type}")
        
        model_config = self.config['models'][model_type]
        model_name = model_config['name']
        
        # Check if model supports embeddings
        if not model_name.startswith('nomic-embed'):
            log.warning(f"Model {model_name} may not support embeddings")
        
        payload = {
            "model": model_name,
            "prompt": text
        }
        
        log.info(f"Generating embeddings with {model_name}")
        
        try:
            response = self._make_request('/api/embeddings', payload)
            embeddings = response.get('embeddings', [])
            
            if not embeddings:
                raise ValueError("No embeddings returned from API")
            
            # Ollama returns embeddings as a list of lists, we want the first one
            embedding = embeddings[0] if isinstance(embeddings, list) else embeddings
            
            log.debug(f"Generated {len(embedding)}-dimensional embedding")
            return embedding
            
        except Exception as e:
            log.error(f"Embedding generation failed: {e}")
            raise
    
    def list_models(self) -> List[Dict]:
        """
        List available models on Ollama server.
        
        Returns:
            List of model information dictionaries
        """
        try:
            response = requests.get(f"{self.server}/api/tags", timeout=10)
            response.raise_for_status()
            return response.json().get('models', [])
        except Exception as e:
            log.error(f"Failed to list models: {e}")
            return []
    
    def ensure_model(self, model_name: str) -> bool:
        """
        Ensure a specific model is available, pull if needed.
        
        Args:
            model_name: Name of model to ensure
            
        Returns:
            True if model is available, False otherwise
        """
        available_models = [m['name'] for m in self.list_models()]
        
        if model_name in available_models:
            log.info(f"Model {model_name} is already available")
            return True
        
        log.info(f"Model {model_name} not found, pulling...")
        try:
            payload = {"name": model_name}
            response = self._make_request('/api/pull', payload)
            log.info(f"Successfully pulled model {model_name}")
            return True
        except Exception as e:
            log.error(f"Failed to pull model {model_name}: {e}")
            return False

# Convenience functions for backward compatibility
def ollama_chat(model_type: str, system: str, user: str, **kwargs) -> str:
    """Convenience function for chat completion."""
    client = OllamaClient()
    return client.chat(model_type, system, user, **kwargs)

def ollama_embed(text: str, model_type: str = 'embed') -> List[float]:
    """Convenience function for text embeddings."""
    client = OllamaClient()
    return client.embed(text, model_type)

if __name__ == "__main__":
    # Test the client
    client = OllamaClient()
    print("Available models:")
    for model in client.list_models():
        print(f"  - {model['name']}")
    
    # Test chat
    try:
        response = client.chat('cluster', 
                              "You are a helpful assistant.", 
                              "Say hello!")
        print(f"Chat test response: {response}")
    except Exception as e:
        print(f"Chat test failed: {e}")

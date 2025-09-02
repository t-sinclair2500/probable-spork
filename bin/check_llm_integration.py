#!/usr/bin/env python3
"""
LLM Integration Checker

- Checks Ollama server connectivity
- Checks model availability (llama3.2:3b)
- Tests basic model response
- Validates configuration

Usage:
    python bin/check_llm_integration.py --server http://localhost:11434 --models llama3.2:3b
"""

import argparse
import sys

import requests
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.core import get_logger

log = get_logger("check_llm_integration")


def check_ollama_server(server_url: str) -> bool:
    """Check if Ollama server is running and accessible."""
    try:
        response = requests.get(f"{server_url}/api/tags", timeout=5)
        if response.status_code == 200:
            log.info(f"✅ Ollama server accessible at {server_url}")
            return True
        else:
            log.error(f"❌ Ollama server returned status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        log.error(f"❌ Cannot connect to Ollama server at {server_url}: {e}")
        return False


def check_model_availability(server_url: str, model_name: str) -> bool:
    """Check if specified model is available."""
    try:
        response = requests.get(f"{server_url}/api/tags", timeout=10)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name") for m in models]

            if model_name in model_names:
                log.info(f"✅ Model {model_name} is available")
                return True
            else:
                log.error(
                    f"❌ Model {model_name} not found. Available models: {model_names}"
                )
                return False
        else:
            log.error(f"❌ Failed to get model list: {response.status_code}")
            return False
    except Exception as e:
        log.error(f"❌ Error checking model availability: {e}")
        return False


def test_model_response(server_url: str, model_name: str) -> bool:
    """Test basic model response."""
    try:
        test_prompt = "Hello! Please respond with just 'OK' to confirm you're working."

        payload = {
            "model": model_name,
            "prompt": test_prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 10},
        }

        log.info(f"🧪 Testing model response with {model_name}...")
        response = requests.post(f"{server_url}/api/generate", json=payload, timeout=30)

        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "").strip()
            log.info(f"✅ Model response: {response_text}")
            return True
        else:
            log.error(f"❌ Model test failed: {response.status_code}")
            return False

    except Exception as e:
        log.error(f"❌ Error testing model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Check LLM integration")
    parser.add_argument(
        "--server", default="http://localhost:11434", help="Ollama server URL"
    )
    parser.add_argument(
        "--models", default="llama3.2:3b", help="Comma-separated model names to check"
    )

    args = parser.parse_args()

    print(f"🔍 Checking LLM integration with server: {args.server}")
    print(f"📋 Models to check: {args.models}")
    print()

    # Check server connectivity
    if not check_ollama_server(args.server):
        print("❌ Ollama server check failed")
        sys.exit(1)

    # Check each model
    model_list = [m.strip() for m in args.models.split(",")]
    all_models_ok = True

    for model in model_list:
        print(f"\n🔍 Checking model: {model}")

        if not check_model_availability(args.server, model):
            all_models_ok = False
            continue

        if not test_model_response(args.server, model):
            all_models_ok = False
            continue

    print("\n" + "=" * 50)
    if all_models_ok:
        print("✅ All LLM integration checks passed!")
        print("🚀 Your pipeline should be ready to run")
    else:
        print("❌ Some LLM integration checks failed")
        print("🔧 Please fix the issues above before running the pipeline")
        sys.exit(1)


if __name__ == "__main__":
    main()

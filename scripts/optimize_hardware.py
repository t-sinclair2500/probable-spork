#!/usr/bin/env python3
"""
Hardware Optimization Script for Probable Spork
Automatically detects hardware and optimizes configuration for best performance.
"""

import platform
import subprocess

import psutil


def get_system_info():
    """Get detailed system information."""
    info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }

    # CPU Information
    try:
        info["cpu_count"] = psutil.cpu_count()
        info["cpu_count_logical"] = psutil.cpu_count(logical=True)
        info["cpu_freq"] = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
    except Exception as e:
        info["cpu_error"] = str(e)

    # Memory Information
    try:
        memory = psutil.virtual_memory()
        info["memory"] = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent": memory.percent,
        }
    except Exception as e:
        info["memory_error"] = str(e)

    # GPU Information (Windows-specific)
    if platform.system() == "Windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                shell=True,
            )
            gpu_lines = [
                line.strip()
                for line in result.stdout.split("\n")
                if line.strip() and "Name" not in line
            ]
            info["gpu"] = gpu_lines
        except Exception as e:
            info["gpu_error"] = str(e)

    return info


def detect_hardware_tier(system_info):
    """Detect hardware tier and recommend optimizations."""
    memory_gb = system_info.get("memory", {}).get("total_gb", 0)
    cpu_count = system_info.get("cpu_count", 0)
    gpu_info = system_info.get("gpu", [])

    # Check for high-end GPU (RTX 3080, 3090, 4080, 4090, etc.)
    has_high_end_gpu = any(
        "RTX 3080" in gpu
        or "RTX 3090" in gpu
        or "RTX 4080" in gpu
        or "RTX 4090" in gpu
        or "RTX 4070" in gpu
        for gpu in gpu_info
    )

    # High performance: 32GB+ RAM, 8+ cores, OR high-end GPU with 16GB+ RAM
    if (memory_gb >= 31.5 and cpu_count >= 8) or (
        has_high_end_gpu and memory_gb >= 16 and cpu_count >= 8
    ):
        return "high_performance"
    elif memory_gb >= 16 and cpu_count >= 4:
        return "mid_range"
    else:
        return "basic"


def optimize_ollama_config(hardware_tier):
    """Optimize Ollama configuration based on hardware tier."""
    config = {}

    if hardware_tier == "high_performance":
        config.update(
            {
                "OLLAMA_NUM_PARALLEL": "3",
                "OLLAMA_TIMEOUT": "60",
                "OLLAMA_GPU_LAYERS": "35",
                "OLLAMA_CPU_LAYERS": "5",
            }
        )
    elif hardware_tier == "mid_range":
        config.update(
            {
                "OLLAMA_NUM_PARALLEL": "2",
                "OLLAMA_TIMEOUT": "90",
                "OLLAMA_GPU_LAYERS": "20",
                "OLLAMA_CPU_LAYERS": "10",
            }
        )
    else:
        config.update(
            {
                "OLLAMA_NUM_PARALLEL": "1",
                "OLLAMA_TIMEOUT": "120",
                "OLLAMA_GPU_LAYERS": "10",
                "OLLAMA_CPU_LAYERS": "20",
            }
        )

    return config


def optimize_service_config(hardware_tier):
    """Optimize service configuration based on hardware tier."""
    config = {}

    if hardware_tier == "high_performance":
        config.update(
            {
                "WORKERS": "4",
                "MAX_REQUESTS": "1000",
                "TIMEOUT": "30",
                "UI_MAX_THREADS": "8",
                "UI_QUEUE_SIZE": "20",
            }
        )
    elif hardware_tier == "mid_range":
        config.update(
            {
                "WORKERS": "2",
                "MAX_REQUESTS": "500",
                "TIMEOUT": "45",
                "UI_MAX_THREADS": "4",
                "UI_QUEUE_SIZE": "10",
            }
        )
    else:
        config.update(
            {
                "WORKERS": "1",
                "MAX_REQUESTS": "100",
                "TIMEOUT": "60",
                "UI_MAX_THREADS": "2",
                "UI_QUEUE_SIZE": "5",
            }
        )

    return config


def create_optimized_env_file(config, output_path=".env.optimized"):
    """Create an optimized .env file."""
    env_content = f"""# Hardware-Optimized Environment Configuration
# Generated automatically by optimize_hardware.py

# =============================================================================
# HARDWARE OPTIMIZATION SETTINGS
# =============================================================================

# Ollama Configuration
OLLAMA_NUM_PARALLEL={config.get('OLLAMA_NUM_PARALLEL', '1')}
OLLAMA_TIMEOUT={config.get('OLLAMA_TIMEOUT', '120')}
OLLAMA_GPU_LAYERS={config.get('OLLAMA_GPU_LAYERS', '10')}
OLLAMA_CPU_LAYERS={config.get('OLLAMA_CPU_LAYERS', '20')}

# Service Configuration
PORT=8008
HOST=127.0.0.1
WORKERS={config.get('WORKERS', '1')}
LOG_LEVEL=info
MAX_REQUESTS={config.get('MAX_REQUESTS', '100')}
TIMEOUT={config.get('TIMEOUT', '60')}

# Gradio UI Configuration
UI_PORT=7860
UI_SHARE=false
UI_DEBUG=false
UI_MAX_THREADS={config.get('UI_MAX_THREADS', '2')}
UI_QUEUE_SIZE={config.get('UI_QUEUE_SIZE', '5')}

# Authentication
ADMIN_TOKEN=default-admin-token-change-me

# Database & Storage
DATABASE_URL=sqlite:///./data/dev.db
STORAGE_PATH=./data
CACHE_PATH=./data/cache

# Performance Monitoring
ENABLE_METRICS=true
PERFORMANCE_TRACKING=true
"""

    with open(output_path, "w") as f:
        f.write(env_content)

    return output_path


def install_gpu_dependencies():
    """Install GPU-accelerated dependencies if available."""
    try:
        # Check if CUDA is available
        result = subprocess.run(["nvidia-smi"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ NVIDIA GPU detected, installing CUDA dependencies...")

            # Install PyTorch with CUDA support
            subprocess.run(
                [
                    "pip",
                    "install",
                    "torch",
                    "torchvision",
                    "torchaudio",
                    "--index-url",
                    "https://download.pytorch.org/whl/cu118",
                ],
                check=True,
            )

            print("✅ CUDA dependencies installed successfully")
            return True
        else:
            print("⚠️  NVIDIA GPU not detected, skipping CUDA dependencies")
            return False
    except Exception as e:
        print(f"⚠️  Could not install GPU dependencies: {e}")
        return False


def main():
    """Main optimization function."""
    print("🚀 Probable Spork - Hardware Optimization")
    print("=" * 50)

    # Get system information
    print("🔍 Detecting hardware...")
    system_info = get_system_info()

    print(f"Platform: {system_info['platform']}")
    print(
        f"CPU: {system_info['cpu_count']} cores ({system_info['cpu_count_logical']} logical)"
    )
    if system_info.get("memory"):
        print(f"Memory: {system_info['memory']['total_gb']}GB total")
    if system_info.get("gpu"):
        print(f"GPU: {', '.join(system_info['gpu'])}")

    # Detect hardware tier
    hardware_tier = detect_hardware_tier(system_info)
    print(f"Hardware Tier: {hardware_tier.replace('_', ' ').title()}")

    # Generate optimizations
    print("\n⚙️  Generating optimizations...")
    ollama_config = optimize_ollama_config(hardware_tier)
    service_config = optimize_service_config(hardware_tier)

    # Merge configurations
    config = {**ollama_config, **service_config}

    # Create optimized environment file
    env_file = create_optimized_env_file(config)
    print(f"✅ Created optimized configuration: {env_file}")

    # Install GPU dependencies if available
    if hardware_tier == "high_performance":
        print("\n🎮 Installing GPU optimizations...")
        install_gpu_dependencies()

    # Recommendations
    print("\n📋 Optimization Recommendations:")
    if hardware_tier == "high_performance":
        print("  • Use multiple Ollama models simultaneously")
        print("  • Enable GPU acceleration for video processing")
        print("  • Run multiple FastAPI workers")
        print("  • Increase batch processing sizes")
    elif hardware_tier == "mid_range":
        print("  • Use 2 Ollama models simultaneously")
        print("  • Moderate GPU acceleration")
        print("  • Run 2 FastAPI workers")
    else:
        print("  • Use single Ollama model")
        print("  • CPU-only processing")
        print("  • Single FastAPI worker")

    print("\n💡 To use optimized settings:")
    print(f"  copy {env_file} .env")
    print("  make start")

    return config


if __name__ == "__main__":
    main()

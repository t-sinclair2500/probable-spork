#!/usr/bin/env python3
"""
Memory Monitor for 8GB MacBook Air M2
Monitors system memory usage and provides alerts for the pipeline.
"""

import json
import subprocess
import sys
import time
from typing import Any, Dict, List

import psutil
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bin.core import get_logger

log = get_logger("memory_monitor")

# Memory thresholds for 8GB system
MEMORY_WARNING_THRESHOLD = 0.75  # 75% memory usage
MEMORY_CRITICAL_THRESHOLD = 0.90  # 90% memory usage
MEMORY_EMERGENCY_THRESHOLD = 0.95  # 95% memory usage


class MemoryMonitor:
    """Monitor system memory and provide alerts."""

    def __init__(self, check_interval: int = 5):
        """
        Initialize memory monitor.

        Args:
            check_interval: Seconds between memory checks
        """
        self.check_interval = check_interval
        self.last_check = 0
        self.alert_history = []

    def get_memory_info(self) -> Dict[str, Any]:
        """Get comprehensive memory information."""
        try:
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # Get Ollama process info
            ollama_memory = self._get_ollama_memory()

            return {
                "timestamp": time.time(),
                "system": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "percent": memory.percent,
                    "swap_total_gb": round(swap.total / (1024**3), 2),
                    "swap_used_gb": round(swap.used / (1024**3), 2),
                    "swap_percent": swap.percent,
                },
                "ollama": ollama_memory,
                "status": self._get_memory_status(memory.percent / 100.0),
            }
        except Exception as e:
            log.error(f"Failed to get memory info: {e}")
            return {"error": str(e)}

    def _get_ollama_memory(self) -> Dict[str, Any]:
        """Get Ollama process memory usage."""
        try:
            ollama_processes = []
            total_memory = 0

            for proc in psutil.process_iter(["pid", "name", "memory_info"]):
                try:
                    if "ollama" in proc.info["name"].lower():
                        memory_mb = proc.info["memory_info"].rss / (1024**2)
                        ollama_processes.append(
                            {"pid": proc.info["pid"], "memory_mb": round(memory_mb, 2)}
                        )
                        total_memory += memory_mb
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                "processes": ollama_processes,
                "total_memory_mb": round(total_memory, 2),
                "total_memory_gb": round(total_memory / 1024, 3),
            }
        except Exception as e:
            log.error(f"Failed to get Ollama memory info: {e}")
            return {"error": str(e)}

    def _get_memory_status(self, usage: float) -> str:
        """Get memory status based on usage."""
        if usage >= MEMORY_EMERGENCY_THRESHOLD:
            return "emergency"
        elif usage >= MEMORY_CRITICAL_THRESHOLD:
            return "critical"
        elif usage >= MEMORY_WARNING_THRESHOLD:
            return "warning"
        else:
            return "normal"

    def check_memory_pressure(self) -> Dict[str, Any]:
        """Check current memory pressure and return status."""
        memory_info = self.get_memory_info()

        if "error" in memory_info:
            return memory_info

        status = memory_info["status"]
        current_time = time.time()

        # Only check at specified intervals
        if current_time - self.last_check < self.check_interval:
            return memory_info

        self.last_check = current_time

        # Handle memory pressure
        if status == "emergency":
            self._handle_emergency_memory()
        elif status == "critical":
            self._handle_critical_memory()
        elif status == "warning":
            self._handle_warning_memory()

        # Log status
        self._log_memory_status(memory_info)

        return memory_info

    def _handle_emergency_memory(self):
        """Handle emergency memory situation."""
        log.warning("🚨 EMERGENCY: Memory usage critical!")

        # Force cleanup
        self._force_memory_cleanup()

        # Alert history
        self.alert_history.append(
            {"timestamp": time.time(), "level": "emergency", "action": "forced_cleanup"}
        )

    def _handle_critical_memory(self):
        """Handle critical memory situation."""
        log.warning("⚠️ CRITICAL: Memory usage high!")

        # Aggressive cleanup
        self._aggressive_memory_cleanup()

        # Alert history
        self.alert_history.append(
            {
                "timestamp": time.time(),
                "level": "critical",
                "action": "aggressive_cleanup",
            }
        )

    def _handle_warning_memory(self):
        """Handle warning memory situation."""
        log.warning("⚠️ WARNING: Memory usage elevated!")

        # Light cleanup
        self._light_memory_cleanup()

        # Alert history
        self.alert_history.append(
            {"timestamp": time.time(), "level": "warning", "action": "light_cleanup"}
        )

    def _force_memory_cleanup(self):
        """Force aggressive memory cleanup."""
        try:
            log.info("Performing forced memory cleanup...")

            # Stop all Ollama models
            subprocess.run(["ollama", "stop", "--all"], capture_output=True, timeout=10)

            # Force Python garbage collection
            import gc

            gc.collect()

            log.info("Forced memory cleanup completed")
        except Exception as e:
            log.error(f"Failed to perform forced cleanup: {e}")

    def _aggressive_memory_cleanup(self):
        """Perform aggressive memory cleanup."""
        try:
            log.info("Performing aggressive memory cleanup...")

            # Force Python garbage collection
            import gc

            gc.collect()

            log.info("Aggressive memory cleanup completed")
        except Exception as e:
            log.error(f"Failed to perform aggressive cleanup: {e}")

    def _light_memory_cleanup(self):
        """Perform light memory cleanup."""
        try:
            log.info("Performing light memory cleanup...")

            # Light garbage collection
            import gc

            gc.collect()

            log.info("Light memory cleanup completed")
        except Exception as e:
            log.error(f"Failed to perform light cleanup: {e}")

    def _log_memory_status(self, memory_info: Dict[str, Any]):
        """Log current memory status."""
        system = memory_info["system"]
        ollama = memory_info["ollama"]
        status = memory_info["status"]

        log.info(f"Memory Status: {status.upper()}")
        log.info(
            f"  System: {system['used_gb']:.2f}GB / {system['total_gb']:.2f}GB ({system['percent']:.1f}%)"
        )
        log.info(
            f"  Swap: {system['swap_used_gb']:.2f}GB / {system['swap_total_gb']:.2f}GB ({system['swap_percent']:.1f}%)"
        )

        if "error" not in ollama:
            log.info(
                f"  Ollama: {ollama['total_memory_gb']:.3f}GB ({len(ollama['processes'])} processes)"
            )

    def get_alert_history(self) -> List[Dict[str, Any]]:
        """Get memory alert history."""
        return self.alert_history

    def clear_alert_history(self):
        """Clear memory alert history."""
        self.alert_history.clear()

    def get_memory_summary(self) -> str:
        """Get a human-readable memory summary."""
        memory_info = self.get_memory_info()

        if "error" in memory_info:
            return f"Error: {memory_info['error']}"

        system = memory_info["system"]
        ollama = memory_info["ollama"]
        status = memory_info["status"]

        summary = f"""
Memory Status: {status.upper()}
System Memory: {system['used_gb']:.2f}GB / {system['total_gb']:.2f}GB ({system['percent']:.1f}%)
Swap Memory: {system['swap_used_gb']:.2f}GB / {system['swap_total_gb']:.2f}GB ({system['swap_percent']:.1f}%)
"""

        if "error" not in ollama:
            summary += f"Ollama Memory: {ollama['total_memory_gb']:.3f}GB ({len(ollama['processes'])} processes)\n"

        return summary.strip()


def main():
    """Main function for command-line usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Memory Monitor for 8GB M2 MacBook Air"
    )
    parser.add_argument(
        "--interval", type=int, default=5, help="Check interval in seconds"
    )
    parser.add_argument("--continuous", action="store_true", help="Run continuously")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    monitor = MemoryMonitor(check_interval=args.interval)

    if args.continuous:
        print("🔄 Running memory monitor continuously...")
        print("Press Ctrl+C to stop")

        try:
            while True:
                memory_info = monitor.check_memory_pressure()

                if args.json:
                    print(json.dumps(memory_info, indent=2))
                else:
                    print(monitor.get_memory_summary())

                print("-" * 50)
                time.sleep(args.interval)

        except KeyboardInterrupt:
            print("\n🛑 Memory monitor stopped")
    else:
        # Single check
        memory_info = monitor.check_memory_pressure()

        if args.json:
            print(json.dumps(memory_info, indent=2))
        else:
            print(monitor.get_memory_summary())


if __name__ == "__main__":
    main()

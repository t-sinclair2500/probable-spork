#!/usr/bin/env python3
"""
Analytics collector for pipeline performance monitoring.
Collects and aggregates metrics from logs, system resources, and pipeline state.
"""
import json
import os
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List

import psutil

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger

log = get_logger("analytics_collector")


class MetricsCollector:
    """Collects and processes pipeline metrics."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or os.path.join(BASE, "data", "analytics")
        self.ensure_data_dir()

        # In-memory storage for recent data
        self.recent_metrics = deque(maxlen=1000)  # Last 1000 data points
        self.step_performance = defaultdict(list)  # Performance by step
        self.error_patterns = defaultdict(int)  # Error frequency tracking

    def ensure_data_dir(self):
        """Ensure analytics data directory exists."""
        os.makedirs(self.data_dir, exist_ok=True)

        # Create subdirectories for different metric types
        for subdir in ["metrics", "trends", "alerts"]:
            os.makedirs(os.path.join(self.data_dir, subdir), exist_ok=True)

    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system resource metrics."""
        try:
            # CPU and memory
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(BASE)

            # Process-specific metrics for Python processes
            python_processes = []
            for proc in psutil.process_iter(
                ["pid", "name", "cpu_percent", "memory_percent"]
            ):
                try:
                    if "python" in proc.info["name"].lower():
                        python_processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            return {
                "timestamp": time.time(),
                "cpu": {"percent": cpu_percent, "count": psutil.cpu_count()},
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent,
                    "used": memory.used,
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "used": disk.used,
                    "percent": (disk.used / disk.total) * 100,
                },
                "python_processes": len(python_processes),
                "load_average": (
                    os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0]
                ),
            }
        except Exception as e:
            log.error(f"Failed to collect system metrics: {e}")
            return {"timestamp": time.time(), "error": str(e)}

    def parse_state_logs(self, hours: int = 24) -> Dict[str, Any]:
        """Parse recent state logs for pipeline metrics."""
        state_file = os.path.join(BASE, "jobs", "state.jsonl")
        if not os.path.exists(state_file):
            return {"steps": {}, "errors": [], "performance": {}}

        cutoff_time = time.time() - (hours * 3600)
        steps = defaultdict(
            lambda: {"count": 0, "statuses": defaultdict(int), "durations": []}
        )
        errors = []
        recent_activities = []

        try:
            with open(state_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)
                        entry_time = entry.get("ts", 0)

                        # Convert timestamp string to epoch if needed
                        if isinstance(entry_time, str):
                            try:
                                dt = datetime.fromisoformat(
                                    entry_time.replace("Z", "+00:00")
                                )
                                entry_time = dt.timestamp()
                            except ValueError:
                                continue

                        if entry_time < cutoff_time:
                            continue

                        step = entry.get("step", "unknown")
                        status = entry.get("status", "unknown")

                        steps[step]["count"] += 1
                        steps[step]["statuses"][status] += 1

                        # Track errors
                        if "error" in status.lower() or "fail" in status.lower():
                            errors.append(
                                {
                                    "step": step,
                                    "status": status,
                                    "timestamp": entry_time,
                                    "notes": entry.get("notes", ""),
                                }
                            )

                        recent_activities.append(entry)

                    except json.JSONDecodeError as e:
                        log.warning(f"Invalid JSON in state log: {e}")
                        continue

            # Calculate success rates and trends
            performance = {}
            for step, data in steps.items():
                total = data["count"]
                success = data["statuses"].get("OK", 0)
                success_rate = (success / total) * 100 if total > 0 else 0

                performance[step] = {
                    "total_runs": total,
                    "success_rate": round(success_rate, 2),
                    "success_count": success,
                    "error_count": total - success,
                    "statuses": dict(data["statuses"]),
                }

            return {
                "steps": dict(steps),
                "errors": errors[-50:],  # Last 50 errors
                "performance": performance,
                "recent_activity": recent_activities[-100:],  # Last 100 activities
            }

        except Exception as e:
            log.error(f"Failed to parse state logs: {e}")
            return {"steps": {}, "errors": [], "performance": {}}

    def analyze_content_quality(self) -> Dict[str, Any]:
        """Analyze content quality metrics from recent content."""
        metrics = {
            "posts_analyzed": 0,
            "avg_word_count": 0,
            "fact_check_issues": {
                "total": 0,
                "by_severity": {"error": 0, "warning": 0, "info": 0},
            },
            "validation_scores": [],
            "content_trends": {},
        }

        try:
            # Look for recent content metadata
            cache_dir = os.path.join(BASE, "data", "cache")
            meta_file = os.path.join(cache_dir, "post.meta.json")

            if os.path.exists(meta_file):
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)

                validation = meta.get("validation", {})
                fact_check = validation.get("fact_check")

                metrics["posts_analyzed"] = 1
                metrics["avg_word_count"] = validation.get("metrics", {}).get(
                    "word_count", 0
                )

                if fact_check:
                    fact_metrics = fact_check.get("metrics", {})
                    severity_counts = fact_metrics.get("severity_counts", {})

                    metrics["fact_check_issues"]["total"] = fact_metrics.get(
                        "total_issues", 0
                    )
                    metrics["fact_check_issues"]["by_severity"] = severity_counts

                # Extract validation metrics
                val_metrics = validation.get("metrics", {})
                if val_metrics:
                    metrics["validation_scores"] = [val_metrics]

        except Exception as e:
            log.error(f"Failed to analyze content quality: {e}")

        return metrics

    def collect_asset_metrics(self) -> Dict[str, Any]:
        """Collect metrics about asset usage and provider performance."""
        metrics = {
            "total_assets": 0,
            "by_provider": defaultdict(int),
            "by_type": defaultdict(int),
            "avg_file_size": 0,
            "license_compliance": {"with_license": 0, "total": 0},
            "quality_metrics": {
                "avg_overall_score": 0,
                "avg_relevance_score": 0,
                "total_quality_issues": 0,
                "assets_analyzed": 0,
            },
        }

        try:
            assets_dir = os.path.join(BASE, "assets")
            if not os.path.exists(assets_dir):
                return metrics

            total_size = 0
            file_count = 0

            for folder in os.listdir(assets_dir):
                folder_path = os.path.join(assets_dir, folder)
                if not os.path.isdir(folder_path):
                    continue

                # Check for license file
                license_file = os.path.join(folder_path, "license.json")
                if os.path.exists(license_file):
                    metrics["license_compliance"]["with_license"] += 1

                    try:
                        with open(license_file, "r", encoding="utf-8") as f:
                            license_data = json.load(f)

                        items = license_data.get("items", [])
                        quality_scores = []
                        relevance_scores = []
                        total_issues = 0

                        for item in items:
                            provider = item.get("provider", "unknown")
                            metrics["by_provider"][provider] += 1

                            # Extract quality metrics if available
                            quality_data = item.get("quality", {})
                            if quality_data:
                                overall_score = quality_data.get("overall_score", 0)
                                relevance_score = quality_data.get("relevance_score", 0)
                                issues = quality_data.get("quality_issues", [])

                                if overall_score > 0:
                                    quality_scores.append(overall_score)
                                if relevance_score > 0:
                                    relevance_scores.append(relevance_score)
                                total_issues += len(issues)

                        # Update quality metrics
                        if quality_scores:
                            metrics["quality_metrics"]["avg_overall_score"] = sum(
                                quality_scores
                            ) / len(quality_scores)
                            metrics["quality_metrics"]["assets_analyzed"] += len(
                                quality_scores
                            )

                        if relevance_scores:
                            metrics["quality_metrics"]["avg_relevance_score"] = sum(
                                relevance_scores
                            ) / len(relevance_scores)

                        metrics["quality_metrics"][
                            "total_quality_issues"
                        ] += total_issues

                    except Exception:
                        pass

                metrics["license_compliance"]["total"] += 1

                # Analyze files in folder
                for file in os.listdir(folder_path):
                    if file in ["license.json", "sources_used.txt"]:
                        continue

                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path):
                        file_size = os.path.getsize(file_path)
                        total_size += file_size
                        file_count += 1
                        metrics["total_assets"] += 1

                        # Categorize by type
                        ext = os.path.splitext(file)[1].lower()
                        if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                            metrics["by_type"]["image"] += 1
                        elif ext in [".mp4", ".avi", ".mov"]:
                            metrics["by_type"]["video"] += 1
                        else:
                            metrics["by_type"]["other"] += 1

            if file_count > 0:
                metrics["avg_file_size"] = total_size // file_count

        except Exception as e:
            log.error(f"Failed to collect asset metrics: {e}")

        return dict(metrics)

    def generate_alerts(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate alerts based on current metrics."""
        alerts = []
        timestamp = time.time()

        # System resource alerts
        system = metrics.get("system", {})

        if system.get("cpu", {}).get("percent", 0) > 80:
            alerts.append(
                {
                    "type": "warning",
                    "category": "system",
                    "message": f"High CPU usage: {system['cpu']['percent']:.1f}%",
                    "timestamp": timestamp,
                    "value": system["cpu"]["percent"],
                    "threshold": 80,
                }
            )

        if system.get("memory", {}).get("percent", 0) > 85:
            alerts.append(
                {
                    "type": "warning",
                    "category": "system",
                    "message": f"High memory usage: {system['memory']['percent']:.1f}%",
                    "timestamp": timestamp,
                    "value": system["memory"]["percent"],
                    "threshold": 85,
                }
            )

        if system.get("disk", {}).get("percent", 0) > 90:
            alerts.append(
                {
                    "type": "error",
                    "category": "system",
                    "message": f"Disk space critical: {system['disk']['percent']:.1f}% used",
                    "timestamp": timestamp,
                    "value": system["disk"]["percent"],
                    "threshold": 90,
                }
            )

        # Pipeline performance alerts
        pipeline = metrics.get("pipeline", {})
        performance = pipeline.get("performance", {})

        for step, perf in performance.items():
            success_rate = perf.get("success_rate", 100)
            if success_rate < 70:
                alerts.append(
                    {
                        "type": "warning",
                        "category": "pipeline",
                        "message": f"Low success rate for {step}: {success_rate:.1f}%",
                        "timestamp": timestamp,
                        "value": success_rate,
                        "threshold": 70,
                        "step": step,
                    }
                )

        # Content quality alerts
        content = metrics.get("content", {})
        fact_check = content.get("fact_check_issues", {})

        if fact_check.get("by_severity", {}).get("error", 0) > 0:
            error_count = fact_check["by_severity"]["error"]
            alerts.append(
                {
                    "type": "warning",
                    "category": "content",
                    "message": f"Fact-check errors found: {error_count} critical issues",
                    "timestamp": timestamp,
                    "value": error_count,
                    "threshold": 0,
                }
            )

        return alerts

    def collect_all_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive metrics from all sources."""
        log.info("Collecting comprehensive metrics...")

        metrics = {
            "timestamp": time.time(),
            "system": self.collect_system_metrics(),
            "pipeline": self.parse_state_logs(),
            "content": self.analyze_content_quality(),
            "assets": self.collect_asset_metrics(),
        }

        # Generate alerts based on collected metrics
        alerts = self.generate_alerts(metrics)
        metrics["alerts"] = alerts

        # Store metrics
        self.store_metrics(metrics)

        log.info(f"Metrics collection complete: {len(alerts)} alerts generated")
        return metrics

    def store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics to disk for historical analysis."""
        timestamp = metrics["timestamp"]
        date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")

        # Store daily metrics file
        daily_file = os.path.join(self.data_dir, "metrics", f"{date_str}.json")

        # Load existing daily data or create new
        daily_data = []
        if os.path.exists(daily_file):
            try:
                with open(daily_file, "r", encoding="utf-8") as f:
                    daily_data = json.load(f)
            except Exception:
                daily_data = []

        daily_data.append(metrics)

        # Keep only last 24 hours of data per file
        cutoff = timestamp - (24 * 3600)
        daily_data = [m for m in daily_data if m.get("timestamp", 0) > cutoff]

        # Save updated data
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(daily_data, f, indent=2)

    def get_trend_data(self, hours: int = 24) -> Dict[str, Any]:
        """Get trend data for the specified time range."""
        cutoff = time.time() - (hours * 3600)
        trend_data = {
            "timestamps": [],
            "cpu": [],
            "memory": [],
            "disk": [],
            "pipeline_success": [],
        }

        # Look for recent daily files
        for days_back in range(2):  # Check last 2 days
            date = datetime.now() - timedelta(days=days_back)
            date_str = date.strftime("%Y-%m-%d")
            daily_file = os.path.join(self.data_dir, "metrics", f"{date_str}.json")

            if not os.path.exists(daily_file):
                continue

            try:
                with open(daily_file, "r", encoding="utf-8") as f:
                    daily_data = json.load(f)

                for entry in daily_data:
                    if entry.get("timestamp", 0) < cutoff:
                        continue

                    trend_data["timestamps"].append(entry["timestamp"])

                    system = entry.get("system", {})
                    trend_data["cpu"].append(system.get("cpu", {}).get("percent", 0))
                    trend_data["memory"].append(
                        system.get("memory", {}).get("percent", 0)
                    )
                    trend_data["disk"].append(system.get("disk", {}).get("percent", 0))

                    # Calculate overall pipeline success rate
                    pipeline = entry.get("pipeline", {})
                    performance = pipeline.get("performance", {})

                    if performance:
                        success_rates = [
                            perf.get("success_rate", 0) for perf in performance.values()
                        ]
                        avg_success = (
                            sum(success_rates) / len(success_rates)
                            if success_rates
                            else 0
                        )
                        trend_data["pipeline_success"].append(avg_success)
                    else:
                        trend_data["pipeline_success"].append(0)

            except Exception as e:
                log.error(f"Failed to load trend data from {daily_file}: {e}")

        return trend_data


def main():
    """CLI interface for metrics collection."""
    import argparse

    parser = argparse.ArgumentParser(description="Collect pipeline analytics metrics")
    parser.add_argument("--output", help="Output file for metrics (JSON)")
    parser.add_argument("--trends", action="store_true", help="Include trend data")
    parser.add_argument(
        "--hours", type=int, default=24, help="Hours of data to analyze"
    )

    args = parser.parse_args()

    collector = MetricsCollector()

    print("Collecting metrics...")
    metrics = collector.collect_all_metrics()

    if args.trends:
        print("Collecting trend data...")
        trends = collector.get_trend_data(args.hours)
        metrics["trends"] = trends

    # Display summary
    print("\nMetrics Summary:")
    print(f"  System CPU: {metrics['system'].get('cpu', {}).get('percent', 0):.1f}%")
    print(f"  Memory: {metrics['system'].get('memory', {}).get('percent', 0):.1f}%")
    print(f"  Disk: {metrics['system'].get('disk', {}).get('percent', 0):.1f}%")
    print(f"  Pipeline steps: {len(metrics['pipeline'].get('performance', {}))}")
    print(f"  Recent errors: {len(metrics['pipeline'].get('errors', []))}")
    print(f"  Active alerts: {len(metrics.get('alerts', []))}")

    if metrics.get("alerts"):
        print("\nActive Alerts:")
        for alert in metrics["alerts"]:
            print(f"  [{alert['type'].upper()}] {alert['message']}")

    # Save to file if requested
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2)
        print(f"\nMetrics saved to {args.output}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Asset quality assessment module for intelligent asset selection.
Analyzes image and video quality, relevance scoring, and provider performance.
"""
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageStat

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import get_logger

log = get_logger("asset_quality")


@dataclass
class QualityMetrics:
    """Quality assessment metrics for an asset."""

    file_path: str
    file_type: str  # 'image' or 'video'
    file_size: int

    # Image-specific metrics
    resolution: Tuple[int, int]  # (width, height)
    aspect_ratio: float
    compression_quality: float  # 0-100 estimate
    brightness: float  # 0-255 average
    contrast: float  # 0-100 estimate
    sharpness: float  # 0-100 estimate

    # Video-specific metrics (if applicable)
    duration: float  # seconds
    framerate: Optional[float]
    bitrate: Optional[int]

    # Relevance metrics
    relevance_score: float  # 0-100 based on query matching
    semantic_keywords: List[str]

    # Overall quality score
    overall_score: float  # 0-100 composite score
    quality_issues: List[str]  # List of detected issues

    # Metadata
    analyzed_at: str
    analysis_version: str


class AssetQualityAnalyzer:
    """Analyzes asset quality and relevance for intelligent selection."""

    def __init__(self):
        self.analysis_version = "1.0.0"

        # Quality thresholds
        self.min_resolution = (640, 480)
        self.preferred_resolution = (1920, 1080)
        self.min_file_size = 10 * 1024  # 10KB
        self.max_file_size = 50 * 1024 * 1024  # 50MB
        self.preferred_aspect_ratios = [16 / 9, 4 / 3, 1 / 1]  # Common video ratios

        # Semantic keyword expansion
        self.keyword_synonyms = {
            "typing": ["keyboard", "writing", "coding", "programming", "computer"],
            "monitor": ["screen", "display", "computer", "desktop", "laptop"],
            "notebook": ["notes", "writing", "planning", "journal", "book"],
            "clock": ["time", "schedule", "deadline", "timer", "watch"],
            "workspace": ["office", "desk", "work", "computer", "setup"],
            "technology": ["tech", "digital", "computer", "software", "ai"],
        }

    def analyze_image_quality(self, image_path: str) -> Dict[str, Any]:
        """Analyze image quality metrics."""
        try:
            with Image.open(image_path) as img:
                # Basic properties
                width, height = img.size
                file_size = os.path.getsize(image_path)

                # Convert to RGB if needed for analysis
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # Brightness analysis
                stat = ImageStat.Stat(img)
                brightness = sum(stat.mean) / 3  # Average across RGB

                # Contrast estimation (standard deviation of pixel values)
                contrast = sum(stat.stddev) / 3

                # Sharpness estimation using edge detection
                sharpness = self._estimate_sharpness(img)

                # Compression quality estimation
                compression_quality = self._estimate_compression_quality(img, file_size)

                return {
                    "resolution": (width, height),
                    "aspect_ratio": width / height if height > 0 else 1.0,
                    "file_size": file_size,
                    "brightness": brightness,
                    "contrast": contrast,
                    "sharpness": sharpness,
                    "compression_quality": compression_quality,
                    "duration": 0.0,
                    "framerate": None,
                    "bitrate": None,
                }
        except Exception as e:
            log.error(f"Failed to analyze image {image_path}: {e}")
            return self._default_image_metrics(image_path)

    def analyze_video_quality(self, video_path: str) -> Dict[str, Any]:
        """Analyze video quality metrics using ffprobe."""
        try:
            # Use ffprobe to get video metadata
            cmd = [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                video_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                log.warning(f"ffprobe failed for {video_path}: {result.stderr}")
                return self._default_video_metrics(video_path)

            metadata = json.loads(result.stdout)

            # Extract video stream info
            video_stream = None
            for stream in metadata.get("streams", []):
                if stream.get("codec_type") == "video":
                    video_stream = stream
                    break

            if not video_stream:
                return self._default_video_metrics(video_path)

            # Extract metrics
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            duration = float(metadata.get("format", {}).get("duration", 0))

            # Parse frame rate
            r_frame_rate = video_stream.get("r_frame_rate", "0/1")
            framerate = None
            if "/" in r_frame_rate:
                num, den = r_frame_rate.split("/")
                if int(den) > 0:
                    framerate = int(num) / int(den)

            # Bitrate
            bitrate = int(metadata.get("format", {}).get("bit_rate", 0))
            file_size = os.path.getsize(video_path)

            # Quality estimates
            compression_quality = self._estimate_video_compression_quality(
                width, height, duration, file_size, bitrate
            )

            return {
                "resolution": (width, height),
                "aspect_ratio": width / height if height > 0 else 16 / 9,
                "file_size": file_size,
                "duration": duration,
                "framerate": framerate,
                "bitrate": bitrate,
                "compression_quality": compression_quality,
                "brightness": 128,  # Default for videos
                "contrast": 50,  # Default for videos
                "sharpness": 75,  # Default for videos
            }

        except Exception as e:
            log.error(f"Failed to analyze video {video_path}: {e}")
            return self._default_video_metrics(video_path)

    def _estimate_sharpness(self, img: Image.Image) -> float:
        """Estimate image sharpness using Laplacian variance."""
        try:
            # Convert to grayscale for edge detection
            gray = img.convert("L")

            # Resize for faster processing if large
            if gray.size[0] > 1000 or gray.size[1] > 1000:
                gray.thumbnail((1000, 1000), Image.Resampling.LANCZOS)

            # Simple edge detection approximation
            pixels = list(gray.getdata())
            width, height = gray.size

            # Calculate approximate Laplacian (edge detection)
            edge_sum = 0
            edge_count = 0

            for y in range(1, height - 1):
                for x in range(1, width - 1):
                    center = pixels[y * width + x]
                    neighbors = [
                        pixels[(y - 1) * width + x],  # top
                        pixels[(y + 1) * width + x],  # bottom
                        pixels[y * width + (x - 1)],  # left
                        pixels[y * width + (x + 1)],  # right
                    ]

                    laplacian = abs(4 * center - sum(neighbors))
                    edge_sum += laplacian
                    edge_count += 1

            if edge_count > 0:
                variance = edge_sum / edge_count
                # Normalize to 0-100 scale
                return min(100, variance / 10)

            return 50  # Default

        except Exception:
            return 50  # Default on error

    def _estimate_compression_quality(self, img: Image.Image, file_size: int) -> float:
        """Estimate compression quality based on file size and image properties."""
        try:
            width, height = img.size
            pixels = width * height

            # Expected file size for high quality (rough estimate)
            expected_size = pixels * 3 * 0.1  # ~10% of uncompressed RGB

            if file_size >= expected_size:
                return 90  # High quality
            elif file_size >= expected_size * 0.5:
                return 70  # Good quality
            elif file_size >= expected_size * 0.25:
                return 50  # Medium quality
            else:
                return 30  # Lower quality

        except Exception:
            return 50  # Default

    def _estimate_video_compression_quality(
        self, width: int, height: int, duration: float, file_size: int, bitrate: int
    ) -> float:
        """Estimate video compression quality."""
        try:
            pixels = width * height

            # Quality based on bitrate and resolution
            if bitrate > 0:
                bitrate_per_pixel = bitrate / pixels if pixels > 0 else 0

                if bitrate_per_pixel > 0.1:  # High bitrate
                    return 90
                elif bitrate_per_pixel > 0.05:
                    return 75
                elif bitrate_per_pixel > 0.02:
                    return 60
                else:
                    return 40

            # Fallback to file size analysis
            if duration > 0:
                size_per_second = file_size / duration
                if size_per_second > 1024 * 1024:  # >1MB/sec
                    return 85
                elif size_per_second > 512 * 1024:  # >512KB/sec
                    return 70
                else:
                    return 50

            return 50  # Default

        except Exception:
            return 50

    def calculate_relevance_score(
        self, file_path: str, query: str, provider_metadata: Dict[str, Any]
    ) -> Tuple[float, List[str]]:
        """Calculate relevance score based on filename, metadata, and query."""
        try:
            # Extract keywords from various sources
            all_keywords = []

            # From filename
            filename = os.path.basename(file_path).lower()
            filename_keywords = re.findall(r"[a-z]+", filename)
            all_keywords.extend(filename_keywords)

            # From provider metadata
            description = provider_metadata.get("description", "").lower()
            tags = provider_metadata.get("tags", [])
            if isinstance(tags, list):
                all_keywords.extend([tag.lower() for tag in tags])

            # From URL (if available)
            url = provider_metadata.get("url", "").lower()
            url_keywords = re.findall(r"[a-z]+", url)
            all_keywords.extend(url_keywords)

            # Clean and deduplicate
            keywords = list(set([kw for kw in all_keywords if len(kw) > 2]))

            # Calculate relevance
            query_words = set(re.findall(r"\b\w+\b", query.lower()))
            direct_matches = len(query_words.intersection(set(keywords)))

            # Expand with synonyms
            synonym_matches = 0
            expanded_keywords = keywords.copy()

            for query_word in query_words:
                if query_word in self.keyword_synonyms:
                    synonyms = self.keyword_synonyms[query_word]
                    synonym_matches += len(set(synonyms).intersection(set(keywords)))
                    expanded_keywords.extend(synonyms)

            # Score calculation
            total_matches = direct_matches + (synonym_matches * 0.5)
            max_possible = len(query_words)

            if max_possible > 0:
                base_score = (total_matches / max_possible) * 100
                relevance_score = min(100, base_score)
            else:
                relevance_score = 50  # Default when no query words

            # Boost for exact phrase matches
            if query.lower() in filename.lower() or query.lower() in description:
                relevance_score = min(100, relevance_score + 20)

            return relevance_score, expanded_keywords[:10]  # Limit keywords

        except Exception as e:
            log.error(f"Failed to calculate relevance for {file_path}: {e}")
            return 50.0, []

    def calculate_overall_score(
        self, quality_data: Dict[str, Any], relevance_score: float
    ) -> Tuple[float, List[str]]:
        """Calculate overall quality score and identify issues."""
        issues = []
        scores = []

        # Resolution score
        width, height = quality_data["resolution"]
        resolution_score = self._score_resolution(width, height)
        if resolution_score < 60:
            issues.append(f"Low resolution: {width}x{height}")
        scores.append(resolution_score * 0.2)  # 20% weight

        # File size score
        file_size = quality_data["file_size"]
        size_score = self._score_file_size(file_size)
        if size_score < 50:
            issues.append(f"File size issues: {file_size} bytes")
        scores.append(size_score * 0.1)  # 10% weight

        # Compression quality score
        compression_score = quality_data["compression_quality"]
        if compression_score < 50:
            issues.append("Poor compression quality")
        scores.append(compression_score * 0.2)  # 20% weight

        # Brightness/contrast score
        brightness_score = self._score_brightness_contrast(
            quality_data["brightness"], quality_data["contrast"]
        )
        if brightness_score < 60:
            issues.append("Poor brightness/contrast")
        scores.append(brightness_score * 0.1)  # 10% weight

        # Aspect ratio score
        aspect_ratio = quality_data["aspect_ratio"]
        aspect_score = self._score_aspect_ratio(aspect_ratio)
        scores.append(aspect_score * 0.1)  # 10% weight

        # Relevance score (most important)
        scores.append(relevance_score * 0.3)  # 30% weight

        # Calculate weighted average
        overall_score = sum(scores)

        return overall_score, issues

    def _score_resolution(self, width: int, height: int) -> float:
        """Score based on resolution quality."""
        pixels = width * height
        min_pixels = self.min_resolution[0] * self.min_resolution[1]
        preferred_pixels = self.preferred_resolution[0] * self.preferred_resolution[1]

        if pixels >= preferred_pixels:
            return 100
        elif pixels >= min_pixels:
            ratio = pixels / preferred_pixels
            return 60 + (40 * ratio)
        else:
            return max(0, (pixels / min_pixels) * 60)

    def _score_file_size(self, file_size: int) -> float:
        """Score based on file size appropriateness."""
        if file_size < self.min_file_size:
            return 20  # Too small
        elif file_size > self.max_file_size:
            return 40  # Too large
        else:
            # Optimal range
            return 80

    def _score_brightness_contrast(self, brightness: float, contrast: float) -> float:
        """Score based on brightness and contrast."""
        # Prefer moderate brightness (not too dark or bright)
        brightness_score = 100 - abs(brightness - 128) / 128 * 100

        # Prefer good contrast (not too flat)
        contrast_score = min(100, contrast * 2)

        return (brightness_score + contrast_score) / 2

    def _score_aspect_ratio(self, aspect_ratio: float) -> float:
        """Score based on how close to preferred aspect ratios."""
        best_match = min(
            self.preferred_aspect_ratios, key=lambda x: abs(x - aspect_ratio)
        )

        difference = abs(best_match - aspect_ratio)

        if difference < 0.1:
            return 100
        elif difference < 0.3:
            return 80
        else:
            return 60

    def _default_image_metrics(self, image_path: str) -> Dict[str, Any]:
        """Default metrics when image analysis fails."""
        file_size = os.path.getsize(image_path) if os.path.exists(image_path) else 0
        return {
            "resolution": (800, 600),
            "aspect_ratio": 4 / 3,
            "file_size": file_size,
            "brightness": 128,
            "contrast": 50,
            "sharpness": 50,
            "compression_quality": 50,
            "duration": 0.0,
            "framerate": None,
            "bitrate": None,
        }

    def _default_video_metrics(self, video_path: str) -> Dict[str, Any]:
        """Default metrics when video analysis fails."""
        file_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
        return {
            "resolution": (1280, 720),
            "aspect_ratio": 16 / 9,
            "file_size": file_size,
            "duration": 10.0,
            "framerate": 30.0,
            "bitrate": 1000000,
            "compression_quality": 60,
            "brightness": 128,
            "contrast": 50,
            "sharpness": 60,
        }

    def analyze_asset(
        self, file_path: str, query: str, provider_metadata: Dict[str, Any] = None
    ) -> QualityMetrics:
        """Comprehensive asset quality analysis."""
        if provider_metadata is None:
            provider_metadata = {}

        # Determine file type
        ext = os.path.splitext(file_path)[1].lower()
        is_video = ext in [".mp4", ".avi", ".mov", ".wmv", ".flv"]

        # Analyze quality based on type
        if is_video:
            quality_data = self.analyze_video_quality(file_path)
            file_type = "video"
        else:
            quality_data = self.analyze_image_quality(file_path)
            file_type = "image"

        # Calculate relevance
        relevance_score, keywords = self.calculate_relevance_score(
            file_path, query, provider_metadata
        )

        # Calculate overall score
        overall_score, issues = self.calculate_overall_score(
            quality_data, relevance_score
        )

        # Create metrics object
        metrics = QualityMetrics(
            file_path=file_path,
            file_type=file_type,
            file_size=quality_data["file_size"],
            resolution=quality_data["resolution"],
            aspect_ratio=quality_data["aspect_ratio"],
            compression_quality=quality_data["compression_quality"],
            brightness=quality_data["brightness"],
            contrast=quality_data["contrast"],
            sharpness=quality_data["sharpness"],
            duration=quality_data["duration"],
            framerate=quality_data["framerate"],
            bitrate=quality_data["bitrate"],
            relevance_score=relevance_score,
            semantic_keywords=keywords,
            overall_score=overall_score,
            quality_issues=issues,
            analyzed_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            analysis_version=self.analysis_version,
        )

        return metrics

    def rank_assets(
        self, asset_metrics: List[QualityMetrics], max_count: int = 10
    ) -> List[QualityMetrics]:
        """Rank assets by overall quality score with diversity."""
        # Sort by overall score
        sorted_assets = sorted(
            asset_metrics, key=lambda x: x.overall_score, reverse=True
        )

        # Apply diversity filter to avoid too many similar assets
        selected = []
        used_keywords = set()

        for asset in sorted_assets:
            if len(selected) >= max_count:
                break

            # Check for keyword diversity
            asset_keywords = set(asset.semantic_keywords)
            keyword_overlap = len(asset_keywords.intersection(used_keywords))

            # Allow asset if high quality or good diversity
            if asset.overall_score >= 70 or keyword_overlap < 3:
                selected.append(asset)
                used_keywords.update(asset_keywords)

        return selected


def main():
    """CLI interface for testing asset quality analysis."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze asset quality")
    parser.add_argument("file_path", help="Path to asset file")
    parser.add_argument("--query", default="", help="Search query for relevance")
    parser.add_argument("--output", help="Output JSON file")

    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"Error: File not found: {args.file_path}")
        return 1

    analyzer = AssetQualityAnalyzer()
    metrics = analyzer.analyze_asset(args.file_path, args.query)

    # Display results
    print(f"\nAsset Quality Analysis: {os.path.basename(args.file_path)}")
    print(f"  File Type: {metrics.file_type}")
    print(f"  Resolution: {metrics.resolution[0]}x{metrics.resolution[1]}")
    print(f"  File Size: {metrics.file_size:,} bytes")
    print(f"  Overall Score: {metrics.overall_score:.1f}/100")
    print(f"  Relevance Score: {metrics.relevance_score:.1f}/100")
    print(f"  Compression Quality: {metrics.compression_quality:.1f}/100")

    if metrics.file_type == "video":
        print(f"  Duration: {metrics.duration:.1f}s")
        if metrics.framerate:
            print(f"  Frame Rate: {metrics.framerate:.1f} fps")

    if metrics.quality_issues:
        print(f"  Issues: {', '.join(metrics.quality_issues)}")

    if metrics.semantic_keywords:
        print(f"  Keywords: {', '.join(metrics.semantic_keywords[:5])}")

    # Save detailed results
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(asdict(metrics), f, indent=2)
        print(f"\nDetailed results saved to {args.output}")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

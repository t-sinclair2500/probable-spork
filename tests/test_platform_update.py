#!/usr/bin/env python3
"""
Test Platform Update (Pi → Mac)

Verifies Mac-first posture with platform-aware behavior and profiles:
1. Thermal guard no-op on macOS, Pi-only via vcgencmd
2. Profile overlays work correctly (m2_8gb_optimized.yaml, pi_8gb.yaml)
3. Platform detection and recommended profiles
"""

import os

# Ensure repo root on path
import sys
from unittest.mock import patch

import pytest
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import maybe_defer_for_thermals
from bin.run_pipeline import load_with_profile
from bin.utils.platform import (
    get_platform_info,
    get_recommended_profile,
    has_vcgencmd,
    is_linux_arm,
    is_macos,
    read_pi_cpu_temp_celsius,
)


class TestPlatformDetection:
    """Test platform detection utilities."""

    def test_is_macos_detection(self):
        """Test macOS detection."""
        with patch("platform.system") as mock_system:
            mock_system.return_value = "Darwin"
            assert is_macos() is True

            mock_system.return_value = "Linux"
            assert is_macos() is False

            mock_system.return_value = "Windows"
            assert is_macos() is False

    def test_is_linux_arm_detection(self):
        """Test Linux ARM detection."""
        with (
            patch("platform.system") as mock_system,
            patch("platform.machine") as mock_machine,
        ):

            # Linux ARM
            mock_system.return_value = "Linux"
            mock_machine.return_value = "aarch64"
            assert is_linux_arm() is True

            # Linux x86_64
            mock_system.return_value = "Linux"
            mock_machine.return_value = "x86_64"
            assert is_linux_arm() is False

            # macOS (should be False regardless of machine)
            mock_system.return_value = "Darwin"
            mock_machine.return_value = "arm64"
            assert is_linux_arm() is False

    def test_has_vcgencmd_detection(self):
        """Test vcgencmd availability detection."""
        with patch("shutil.which") as mock_which:
            # vcgencmd available
            mock_which.return_value = "/usr/bin/vcgencmd"
            assert has_vcgencmd() is True

            # vcgencmd not available
            mock_which.return_value = None
            assert has_vcgencmd() is False

    def test_get_platform_info(self):
        """Test comprehensive platform info gathering."""
        with (
            patch("platform.system") as mock_system,
            patch("platform.machine") as mock_machine,
            patch("platform.processor") as mock_processor,
            patch("platform.python_version") as mock_py_ver,
            patch("shutil.which") as mock_which,
        ):

            mock_system.return_value = "Darwin"
            mock_machine.return_value = "arm64"
            mock_processor.return_value = "Apple M2"
            mock_py_ver.return_value = "3.11.5"
            mock_which.return_value = None

            info = get_platform_info()

            assert info["system"] == "Darwin"
            assert info["machine"] == "arm64"
            assert info["processor"] == "Apple M2"
            assert info["is_macos"] is True
            assert info["is_linux"] is False
            assert info["is_linux_arm"] is False
            assert info["has_vcgencmd"] is False
            assert info["python_version"] == "3.11.5"

    def test_get_recommended_profile(self):
        """Test recommended profile selection."""
        with (
            patch("bin.utils.platform.is_macos") as mock_macos,
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
        ):

            # macOS
            mock_macos.return_value = True
            mock_linux_arm.return_value = False
            assert get_recommended_profile() == "m2_8gb_optimized"

            # Linux ARM (Pi)
            mock_macos.return_value = False
            mock_linux_arm.return_value = True
            assert get_recommended_profile() == "pi_8gb"

            # Other platforms
            mock_macos.return_value = False
            mock_linux_arm.return_value = False
            assert get_recommended_profile() == "default"


class TestThermalGuard:
    """Test thermal guard behavior."""

    def test_thermal_guard_no_op_on_macos(self):
        """Test that thermal guard is no-op on macOS."""
        with (
            patch("bin.utils.platform.is_macos") as mock_macos,
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
            patch("bin.utils.platform.read_pi_cpu_temp_celsius") as mock_temp,
            patch("time.sleep") as mock_sleep,
        ):

            # macOS should skip thermal guard
            mock_macos.return_value = True
            mock_linux_arm.return_value = False

            # Should return immediately without checking temp or sleeping
            maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)

            # Should not have called temp reading or sleep
            mock_temp.assert_not_called()
            mock_sleep.assert_not_called()

    def test_thermal_guard_no_op_on_non_linux_arm(self):
        """Test that thermal guard is no-op on non-Linux ARM."""
        with (
            patch("bin.utils.platform.is_macos") as mock_macos,
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
            patch("bin.utils.platform.read_pi_cpu_temp_celsius") as mock_temp,
            patch("time.sleep") as mock_sleep,
        ):

            # Non-Linux ARM should skip thermal guard
            mock_macos.return_value = False
            mock_linux_arm.return_value = False

            # Should return immediately without checking temp or sleeping
            maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)

            # Should not have called temp reading or sleep
            mock_temp.assert_not_called()
            mock_sleep.assert_not_called()

    def test_thermal_guard_runs_on_linux_arm_below_threshold(self):
        """Test that thermal guard runs but doesn't sleep when temp is below threshold."""
        with (
            patch("bin.core.is_macos") as mock_macos,
            patch("bin.core.is_linux_arm") as mock_linux_arm,
            patch("bin.core.read_pi_cpu_temp_celsius") as mock_temp,
            patch("time.sleep") as mock_sleep,
        ):

            # Linux ARM should run thermal guard
            mock_macos.return_value = False
            mock_linux_arm.return_value = True
            mock_temp.return_value = 50.0  # Below threshold

            maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)

            # Should have called temp reading but not sleep
            mock_temp.assert_called_once()
            mock_sleep.assert_not_called()

    def test_thermal_guard_sleeps_on_linux_arm_above_threshold(self):
        """Test that thermal guard sleeps when temp is above threshold."""
        with (
            patch("bin.core.is_macos") as mock_macos,
            patch("bin.core.is_linux_arm") as mock_linux_arm,
            patch("bin.core.read_pi_cpu_temp_celsius") as mock_temp,
            patch("time.sleep") as mock_sleep,
        ):

            # Linux ARM should run thermal guard
            mock_macos.return_value = False
            mock_linux_arm.return_value = True
            mock_temp.return_value = 80.0  # Above threshold

            maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)

            # Should have called temp reading and sleep
            mock_temp.assert_called_once()
            mock_sleep.assert_called_once_with(30)

    def test_thermal_guard_handles_none_temp(self):
        """Test that thermal guard handles None temperature gracefully."""
        with (
            patch("bin.core.is_macos") as mock_macos,
            patch("bin.core.is_linux_arm") as mock_linux_arm,
            patch("bin.core.read_pi_cpu_temp_celsius") as mock_temp,
            patch("time.sleep") as mock_sleep,
        ):

            # Linux ARM should run thermal guard
            mock_macos.return_value = False
            mock_linux_arm.return_value = True
            mock_temp.return_value = None  # No temperature reading

            maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)

            # Should have called temp reading but not sleep (None handling)
            mock_temp.assert_called_once()
            mock_sleep.assert_not_called()


class TestPiTemperatureReading:
    """Test Pi temperature reading functionality."""

    def test_read_pi_cpu_temp_celsius_success(self):
        """Test successful temperature reading."""
        with (
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
            patch("bin.utils.platform.has_vcgencmd") as mock_has_vcgencmd,
            patch("subprocess.check_output") as mock_check_output,
        ):

            mock_linux_arm.return_value = True
            mock_has_vcgencmd.return_value = True
            mock_check_output.return_value = "temp=41.2'C"  # String, not bytes

            temp = read_pi_cpu_temp_celsius()

            assert temp == 41.2
            mock_check_output.assert_called_once_with(
                ["vcgencmd", "measure_temp"], text=True
            )

    def test_read_pi_cpu_temp_celsius_not_linux_arm(self):
        """Test temperature reading returns None on non-Linux ARM."""
        with patch("bin.utils.platform.is_linux_arm") as mock_linux_arm:
            mock_linux_arm.return_value = False

            temp = read_pi_cpu_temp_celsius()

            assert temp is None

    def test_read_pi_cpu_temp_celsius_no_vcgencmd(self):
        """Test temperature reading returns None when vcgencmd not available."""
        with (
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
            patch("bin.utils.platform.has_vcgencmd") as mock_has_vcgencmd,
        ):

            mock_linux_arm.return_value = True
            mock_has_vcgencmd.return_value = False

            temp = read_pi_cpu_temp_celsius()

            assert temp is None

    def test_read_pi_cpu_temp_celsius_subprocess_error(self):
        """Test temperature reading returns None on subprocess error."""
        with (
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
            patch("bin.utils.platform.has_vcgencmd") as mock_has_vcgencmd,
            patch("subprocess.check_output") as mock_check_output,
        ):

            mock_linux_arm.return_value = True
            mock_has_vcgencmd.return_value = True
            mock_check_output.side_effect = Exception("vcgencmd failed")

            temp = read_pi_cpu_temp_celsius()

            assert temp is None

    def test_read_pi_cpu_temp_celsius_invalid_output(self):
        """Test temperature reading returns None on invalid output format."""
        with (
            patch("bin.utils.platform.is_linux_arm") as mock_linux_arm,
            patch("bin.utils.platform.has_vcgencmd") as mock_has_vcgencmd,
            patch("subprocess.check_output") as mock_check_output,
        ):

            mock_linux_arm.return_value = True
            mock_has_vcgencmd.return_value = True
            mock_check_output.return_value = b"invalid output"

            temp = read_pi_cpu_temp_celsius()

            assert temp is None


class TestProfileOverlays:
    """Test profile overlay functionality."""

    def test_load_with_profile_none(self):
        """Test loading without profile returns base config unchanged."""
        base_cfg = {"test": "value", "nested": {"key": "value"}}

        result = load_with_profile(base_cfg, None)

        assert result == base_cfg

    def test_load_with_profile_m2_8gb_optimized(self):
        """Test loading m2_8gb_optimized profile."""
        base_cfg = {
            "performance": {"max_concurrent_renders": 1, "pacing_cooldown_seconds": 60}
        }

        # Mock the profile file existence and content
        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("bin.run_pipeline._read_yaml") as mock_read_yaml,
        ):

            mock_exists.return_value = True
            mock_read_yaml.return_value = {
                "performance": {
                    "max_concurrent_renders": 2,
                    "pacing_cooldown_seconds": 15,
                }
            }

            result = load_with_profile(base_cfg, "m2_8gb_optimized")

            # Should merge profile overlay
            assert result["performance"]["max_concurrent_renders"] == 2
            assert result["performance"]["pacing_cooldown_seconds"] == 15

    def test_load_with_profile_pi_8gb(self):
        """Test loading pi_8gb profile."""
        base_cfg = {
            "performance": {"max_concurrent_renders": 2, "pacing_cooldown_seconds": 15}
        }

        # Mock the profile file existence and content
        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("bin.run_pipeline._read_yaml") as mock_read_yaml,
        ):

            mock_exists.return_value = True
            mock_read_yaml.return_value = {
                "performance": {
                    "max_concurrent_renders": 1,
                    "pacing_cooldown_seconds": 60,
                }
            }

            result = load_with_profile(base_cfg, "pi_8gb")

            # Should merge profile overlay
            assert result["performance"]["max_concurrent_renders"] == 1
            assert result["performance"]["pacing_cooldown_seconds"] == 60

    def test_load_with_profile_file_not_found(self):
        """Test loading profile when file doesn't exist."""
        base_cfg = {"test": "value"}

        with patch("pathlib.Path.exists") as mock_exists:
            mock_exists.return_value = False

            result = load_with_profile(base_cfg, "m2_8gb_optimized")

            # Should return base config unchanged
            assert result == base_cfg

    def test_load_with_profile_invalid_profile(self):
        """Test loading invalid profile name."""
        base_cfg = {"test": "value"}

        result = load_with_profile(base_cfg, "invalid_profile")

        # Should return base config unchanged
        assert result == base_cfg

    def test_load_with_profile_yaml_error(self):
        """Test loading profile when YAML parsing fails."""
        base_cfg = {"test": "value"}

        with (
            patch("pathlib.Path.exists") as mock_exists,
            patch("bin.run_pipeline._read_yaml") as mock_read_yaml,
        ):

            mock_exists.return_value = True
            mock_read_yaml.side_effect = Exception("YAML parse error")

            result = load_with_profile(base_cfg, "m2_8gb_optimized")

            # Should return base config unchanged
            assert result == base_cfg


class TestProfileFileContents:
    """Test that profile files contain expected configurations."""

    def test_m2_8gb_optimized_profile_structure(self):
        """Test m2_8gb_optimized.yaml has expected structure."""
        profile_path = Path("conf/m2_8gb_optimized.yaml")

        assert profile_path.exists(), "m2_8gb_optimized.yaml should exist"

        # Load and verify structure
        with open(profile_path, "r") as f:
            import yaml

            config = yaml.safe_load(f)

        # Check required sections
        assert "platform" in config
        assert "performance" in config
        assert "llm" in config
        assert "guards" in config

        # Check platform info
        assert config["platform"]["target"] == "mac_m2_8gb"
        assert "mac_optimizations" in config

        # Check performance settings
        assert config["performance"]["max_concurrent_renders"] == 2
        assert config["performance"]["pacing_cooldown_seconds"] == 15

        # Check thermal guard setting
        assert config["guards"]["thermal"] == "platform_aware"

    def test_pi_8gb_profile_structure(self):
        """Test pi_8gb.yaml has expected structure."""
        profile_path = Path("conf/pi_8gb.yaml")

        assert profile_path.exists(), "pi_8gb.yaml should exist"

        # Load and verify structure
        with open(profile_path, "r") as f:
            import yaml

            config = yaml.safe_load(f)

        # Check required sections
        assert "platform" in config
        assert "performance" in config
        assert "llm" in config
        assert "guards" in config

        # Check platform info
        assert config["platform"]["target"] == "pi_5_8gb"
        assert "pi_optimizations" in config

        # Check performance settings
        assert config["performance"]["max_concurrent_renders"] == 1
        assert config["performance"]["pacing_cooldown_seconds"] == 60

        # Check thermal guard setting
        assert config["guards"]["thermal"] == "pi_only"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

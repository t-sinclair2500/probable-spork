#!/usr/bin/env python3
"""
Tests for platform helpers and profile functionality:
- Platform detection (macOS, Linux ARM)
- Thermal guard behavior
- Profile overlay loading and merging
- Configuration precedence
"""

import os
import sys
from unittest.mock import patch

# Ensure repo root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def test_platform_helpers_detect():
    """Test platform detection functions."""
    from bin.utils.platform import (
        get_platform_info,
        has_vcgencmd,
        is_linux,
        is_linux_arm,
        is_macos,
    )

    # Test platform info structure
    info = get_platform_info()
    assert isinstance(info, dict)
    assert "system" in info
    assert "is_macos" in info
    assert "is_linux" in info
    assert "is_linux_arm" in info
    assert "has_vcgencmd" in info

    # Test boolean functions
    assert isinstance(is_macos(), bool)
    assert isinstance(is_linux(), bool)
    assert isinstance(is_linux_arm(), bool)
    assert isinstance(has_vcgencmd(), bool)

    print("✅ Platform helpers detect correctly")


def test_platform_helpers_macos_simulation():
    """Test platform helpers with macOS simulation."""
    with patch("bin.utils.platform.platform.system", return_value="Darwin"):
        with patch("bin.utils.platform.platform.machine", return_value="arm64"):
            from bin.utils.platform import is_linux, is_linux_arm, is_macos

            assert is_macos() is True
            assert is_linux() is False
            assert is_linux_arm() is False

    print("✅ macOS simulation works correctly")


def test_platform_helpers_linux_arm_simulation():
    """Test platform helpers with Linux ARM simulation."""
    with patch("bin.utils.platform.platform.system", return_value="Linux"):
        with patch("bin.utils.platform.platform.machine", return_value="aarch64"):
            from bin.utils.platform import is_linux, is_linux_arm, is_macos

            assert is_macos() is False
            assert is_linux() is True
            assert is_linux_arm() is True

    print("✅ Linux ARM simulation works correctly")


def test_thermal_guard_noop_on_macos():
    """Test that thermal guard is no-op on macOS."""
    with patch("bin.utils.platform.is_macos", return_value=True):
        from bin.core import maybe_defer_for_thermals

        # Should return immediately without sleeping
        maybe_defer_for_thermals(threshold_c=0.1, sleep_seconds=999)
        # If we get here, no sleep occurred (good)

    print("✅ Thermal guard no-op on macOS")


def test_thermal_guard_pi_behavior():
    """Test thermal guard behavior on Pi."""
    # Import the function first
    from bin.core import maybe_defer_for_thermals

    with patch("bin.core.is_macos", return_value=False):
        with patch("bin.core.is_linux_arm", return_value=True):
            with patch("bin.core.read_pi_cpu_temp_celsius", return_value=80.0):
                with patch("bin.core.time.sleep") as mock_sleep:
                    # Should sleep when temp exceeds threshold
                    maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)
                    mock_sleep.assert_called_once_with(30)

    print("✅ Thermal guard sleeps on Pi when hot")


def test_thermal_guard_no_vcgencmd():
    """Test thermal guard when vcgencmd not available."""
    with patch("bin.utils.platform.is_macos", return_value=False):
        with patch("bin.utils.platform.is_linux_arm", return_value=True):
            with patch(
                "bin.utils.platform.read_pi_cpu_temp_celsius", return_value=None
            ):
                with patch("time.sleep") as mock_sleep:
                    from bin.core import maybe_defer_for_thermals

                    # Should not sleep when temp reading fails
                    maybe_defer_for_thermals(threshold_c=75.0, sleep_seconds=30)
                    mock_sleep.assert_not_called()

    print("✅ Thermal guard handles missing vcgencmd gracefully")


def test_deep_merge_functionality():
    """Test deep merge functionality."""
    from bin.run_pipeline import _deep_merge

    # Test basic merge
    a = {"a": 1, "b": 2}
    b = {"b": 3, "c": 4}
    result = _deep_merge(a, b)
    assert result == {"a": 1, "b": 3, "c": 4}

    # Test nested merge
    a = {"nested": {"a": 1, "b": 2}}
    b = {"nested": {"b": 3, "c": 4}}
    result = _deep_merge(a, b)
    assert result == {"nested": {"a": 1, "b": 3, "c": 4}}

    # Test with None
    result = _deep_merge(a, None)
    assert result == a

    print("✅ Deep merge works correctly")


def test_profile_overlay_loading():
    """Test profile overlay loading."""
    from bin.run_pipeline import load_with_profile

    # Test with no profile
    base_cfg = {"a": 1, "b": 2}
    result = load_with_profile(base_cfg, None)
    assert result == base_cfg

    # Test with invalid profile
    result = load_with_profile(base_cfg, "invalid_profile")
    assert result == base_cfg  # Should return base config unchanged

    print("✅ Profile overlay loading handles edge cases")


def test_profile_overlay_merge_with_real_files():
    """Test profile overlay with actual YAML files."""
    from bin.run_pipeline import load_with_profile

    base_cfg = {
        "performance": {"max_concurrent_renders": 1, "pacing_cooldown_seconds": 30}
    }

    # Test with m2_8gb_optimized profile
    result = load_with_profile(base_cfg, "m2_8gb_optimized")

    # Should have merged the profile settings
    assert "performance" in result
    assert result["performance"]["max_concurrent_renders"] == 2
    assert result["performance"]["pacing_cooldown_seconds"] == 15
    assert "platform" in result
    assert result["platform"]["target"] == "mac_m2_8gb"

    print("✅ Profile overlay merges real YAML files correctly")


def test_recommended_profile_detection():
    """Test recommended profile detection."""
    from bin.utils.platform import get_recommended_profile

    # Test macOS detection
    with patch("bin.utils.platform.is_macos", return_value=True):
        profile = get_recommended_profile()
        assert profile == "m2_8gb_optimized"

    # Test Pi detection
    with patch("bin.utils.platform.is_macos", return_value=False):
        with patch("bin.utils.platform.is_linux_arm", return_value=True):
            profile = get_recommended_profile()
            assert profile == "pi_8gb"

    # Test default fallback
    with patch("bin.utils.platform.is_macos", return_value=False):
        with patch("bin.utils.platform.is_linux_arm", return_value=False):
            profile = get_recommended_profile()
            assert profile == "default"

    print("✅ Recommended profile detection works")


def test_platform_info_comprehensive():
    """Test comprehensive platform info."""
    from bin.utils.platform import get_platform_info

    info = get_platform_info()

    # Check all required fields
    required_fields = [
        "system",
        "machine",
        "processor",
        "is_macos",
        "is_linux",
        "is_linux_arm",
        "has_vcgencmd",
        "python_version",
    ]

    for field in required_fields:
        assert field in info, f"Missing field: {field}"

    # Check data types
    assert isinstance(info["system"], str)
    assert isinstance(info["is_macos"], bool)
    assert isinstance(info["is_linux"], bool)
    assert isinstance(info["is_linux_arm"], bool)
    assert isinstance(info["has_vcgencmd"], bool)
    assert isinstance(info["python_version"], str)

    print("✅ Platform info is comprehensive and well-formed")


def test_vcgencmd_detection():
    """Test vcgencmd availability detection."""
    from bin.utils.platform import has_vcgencmd

    # Test with mock shutil.which
    with patch("bin.utils.platform.shutil.which") as mock_which:
        # Test when vcgencmd is available
        mock_which.return_value = "/usr/bin/vcgencmd"
        assert has_vcgencmd() is True

        # Test when vcgencmd is not available
        mock_which.return_value = None
        assert has_vcgencmd() is False

    print("✅ vcgencmd detection works correctly")


def run_all_tests():
    """Run all platform and profile tests."""
    tests = [
        test_platform_helpers_detect,
        test_platform_helpers_macos_simulation,
        test_platform_helpers_linux_arm_simulation,
        test_thermal_guard_noop_on_macos,
        test_thermal_guard_pi_behavior,
        test_thermal_guard_no_vcgencmd,
        test_deep_merge_functionality,
        test_profile_overlay_loading,
        test_profile_overlay_merge_with_real_files,
        test_recommended_profile_detection,
        test_platform_info_comprehensive,
        test_vcgencmd_detection,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1

    print(f"\n📊 Platform Profile Tests: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All platform profile tests passed!")
        return True
    else:
        print("⚠️  Some tests failed - please check platform implementation")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

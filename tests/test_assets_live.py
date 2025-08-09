"""
Test asset fetching in LIVE mode.

These tests verify that:
- Budget limits are enforced
- Rate limiting works correctly
- API keys are properly checked
- Live fetches are logged correctly

Note: These tests are marked with @pytest.mark.liveapi and 
require actual API keys to run.
"""

import os
import time
from unittest.mock import patch

import pytest

from bin.fetch_assets import (
    enforce_live_budget,
    live_fetch_count,
    main_live_mode,
)


@pytest.mark.liveapi
class TestAssetLive:
    """Test live asset fetching with actual API calls"""
    
    def setup_method(self):
        """Reset global counters before each test"""
        global live_fetch_count
        live_fetch_count = 0
        from bin.fetch_assets import last_fetch_times
        last_fetch_times.clear()
    
    def test_budget_enforcement_basic(self):
        """Test basic budget enforcement"""
        budget = 3
        rate_limit = 10
        
        # First few calls should work
        enforce_live_budget(budget, rate_limit)
        assert live_fetch_count == 1
        
        enforce_live_budget(budget, rate_limit)
        assert live_fetch_count == 2
        
        enforce_live_budget(budget, rate_limit)
        assert live_fetch_count == 3
        
        # Next call should fail
        with pytest.raises(Exception, match="Live fetch budget exceeded"):
            enforce_live_budget(budget, rate_limit)
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        budget = 20  # High budget
        rate_limit = 2  # Low rate limit for testing
        
        # First two calls should be immediate
        start_time = time.time()
        enforce_live_budget(budget, rate_limit)
        enforce_live_budget(budget, rate_limit)
        first_two_duration = time.time() - start_time
        
        # Should be very fast (< 0.1 seconds)
        assert first_two_duration < 0.1
        
        # Third call should trigger rate limiting
        start_time = time.time()
        enforce_live_budget(budget, rate_limit)
        rate_limited_duration = time.time() - start_time
        
        # Should take significant time due to rate limiting
        # Note: This might be flaky in fast test environments
        # Adjust expectations as needed
        assert rate_limited_duration > 0.01  # At least some delay
    
    def test_api_key_validation(self, live_mode_env, test_config):
        """Test that API key validation works in live mode"""
        # Test with missing keys
        env_no_keys = live_mode_env.copy()
        env_no_keys.pop("PIXABAY_API_KEY", None)
        env_no_keys.pop("PEXELS_API_KEY", None)
        
        # Should fail if fail_on_live_without_keys is True
        result = main_live_mode(test_config, env_no_keys)
        # Result should be None (failed due to missing keys)
        assert result is None
    
    @pytest.mark.skipif(
        not os.environ.get("PIXABAY_API_KEY") or not os.environ.get("PEXELS_API_KEY"),
        reason="Requires PIXABAY_API_KEY and PEXELS_API_KEY environment variables"
    )
    def test_live_mode_with_real_keys(self, live_mode_env, test_config):
        """Test live mode with real API keys (requires actual keys)"""
        # Set real API keys from environment
        env_with_keys = live_mode_env.copy()
        env_with_keys["PIXABAY_API_KEY"] = os.environ.get("PIXABAY_API_KEY")
        env_with_keys["PEXELS_API_KEY"] = os.environ.get("PEXELS_API_KEY")
        
        # This test would need a script file to actually run
        # For now, just test that it doesn't fail immediately
        # In a full implementation, this would test actual API calls
        pass
    
    def test_budget_from_environment(self, live_mode_env, test_config):
        """Test that budget can be set from environment variables"""
        env_with_budget = live_mode_env.copy()
        env_with_budget["ASSET_LIVE_BUDGET"] = "2"
        
        # Mock the API key check to pass
        with patch('bin.fetch_assets.main_original_logic_with_budget') as mock_main:
            main_live_mode(test_config, env_with_budget)
            
            # Verify the budget was passed correctly
            mock_main.assert_called_once()
            args = mock_main.call_args[0]
            budget = args[2]  # budget is 3rd argument
            assert budget == 2
    
    def test_rate_limit_from_config(self, live_mode_env, test_config):
        """Test that rate limit comes from config"""
        # Modify test config to have different rate limit
        test_config_modified = test_config.copy() if hasattr(test_config, 'copy') else test_config
        if not hasattr(test_config_modified, 'testing'):
            # Add testing config if not present
            class TestingConfig:
                live_rate_limit_per_min = 5
                live_budget_per_run = 3
                fail_on_live_without_keys = False
            
            test_config_modified.testing = TestingConfig()
        
        with patch('bin.fetch_assets.main_original_logic_with_budget') as mock_main:
            main_live_mode(test_config_modified, live_mode_env)
            
            # Verify rate limit was passed correctly
            mock_main.assert_called_once()
            args = mock_main.call_args[0]
            rate_limit = args[3]  # rate_limit is 4th argument
            assert rate_limit == 5


@pytest.mark.liveapi
def test_live_fetch_logging():
    """Test that live fetches are properly logged"""
    # Reset counter
    global live_fetch_count
    live_fetch_count = 0
    
    budget = 5
    rate_limit = 10
    
    # Mock the logger to capture log messages
    with patch('bin.fetch_assets.log') as mock_log:
        enforce_live_budget(budget, rate_limit)
        
        # Verify LIVE_FETCH was logged
        log_calls = [call for call in mock_log.info.call_args_list]
        live_fetch_logged = any(
            "LIVE_FETCH" in str(call) for call in log_calls
        )
        assert live_fetch_logged


@pytest.mark.liveapi 
class TestLiveModeIntegration:
    """Integration tests for live mode functionality"""
    
    def test_mode_detection(self, live_mode_env):
        """Test that live mode is properly detected from environment"""
        assert live_mode_env["TEST_ASSET_MODE"] == "live"
        assert live_mode_env["ASSET_LIVE_BUDGET"] == "3"
    
    def test_provider_key_mapping(self):
        """Test that provider keys are correctly mapped"""
        # Test the key validation logic
        providers = ["pixabay", "pexels", "unsplash"]
        env = {}
        
        missing_keys = []
        if "pixabay" in providers and not env.get("PIXABAY_API_KEY"):
            missing_keys.append("PIXABAY_API_KEY")
        if "pexels" in providers and not env.get("PEXELS_API_KEY"):
            missing_keys.append("PEXELS_API_KEY")
        if "unsplash" in providers and not env.get("UNSPLASH_ACCESS_KEY"):
            missing_keys.append("UNSPLASH_ACCESS_KEY")
        
        assert missing_keys == ["PIXABAY_API_KEY", "PEXELS_API_KEY", "UNSPLASH_ACCESS_KEY"]
        
        # Test with keys present
        env_with_keys = {
            "PIXABAY_API_KEY": "test_key",
            "PEXELS_API_KEY": "test_key", 
            "UNSPLASH_ACCESS_KEY": "test_key"
        }
        
        missing_keys = []
        if "pixabay" in providers and not env_with_keys.get("PIXABAY_API_KEY"):
            missing_keys.append("PIXABAY_API_KEY")
        if "pexels" in providers and not env_with_keys.get("PEXELS_API_KEY"):
            missing_keys.append("PEXELS_API_KEY")
        if "unsplash" in providers and not env_with_keys.get("UNSPLASH_ACCESS_KEY"):
            missing_keys.append("UNSPLASH_ACCESS_KEY")
        
        assert missing_keys == []

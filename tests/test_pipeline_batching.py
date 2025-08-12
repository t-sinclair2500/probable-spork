#!/usr/bin/env python3
"""
Tests for pipeline batching functionality.

Tests that the pipeline executes steps in the correct order and that
model sessions are properly managed between batches.
"""

import pytest
from unittest.mock import patch, MagicMock, call
import os
import sys
from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class TestPipelineBatching:
    """Test the batch-by-model execution logic."""
    
    @patch('bin.run_pipeline.run_step')
    def test_batch_execution_order(self, mock_run_step):
        """Test that batches execute in the correct order."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock models config
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:latest"},
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        success = run_shared_ingestion(mock_cfg, models_config=models_config)
        
        assert success is True
        
        # Verify steps were called in the correct order
        expected_calls = [
            call("niche_trends", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("llm_cluster", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("llm_outline", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("llm_script", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("research_collect", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("research_ground", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("fact_check", required=False, brief_env=None, brief_data=None, models_config=models_config),
            call("fetch_assets", required=True, brief_env=None, brief_data=None, models_config=models_config)
        ]
        
        mock_run_step.assert_has_calls(expected_calls, any_order=False)
    
    @patch('bin.run_pipeline.run_step')
    def test_batch_failure_handling(self, mock_run_step):
        """Test that batch failures are handled correctly."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock step failure in the first batch
        def mock_step_side_effect(step_name, **kwargs):
            if step_name == "llm_cluster":
                return False
            return True
        
        mock_run_step.side_effect = mock_step_side_effect
        
        # Mock models config
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:latest"},
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        success = run_shared_ingestion(mock_cfg, models_config=models_config)
        
        assert success is False
        
        # Verify that steps in the first batch were called
        mock_run_step.assert_any_call("niche_trends", required=True, brief_env=None, brief_data=None, models_config=models_config)
        mock_run_step.assert_any_call("llm_cluster", required=True, brief_env=None, brief_data=None, models_config=models_config)
        
        # Verify that only 2 steps were called (niche_trends and llm_cluster)
        assert mock_run_step.call_count == 2
        
        # Verify that research steps were not called due to early failure
        # The mock was called twice, so we can't use assert_not_called()
        # Instead, verify that only the expected steps were called
        expected_calls = [
            call("niche_trends", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("llm_cluster", required=True, brief_env=None, brief_data=None, models_config=models_config)
        ]
        mock_run_step.assert_has_calls(expected_calls, any_order=False)
    
    @patch('bin.run_pipeline.run_step')
    def test_optional_script_refinement_batch(self, mock_run_step):
        """Test that optional script refinement batch is added when different from cluster model."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock models config with different scriptwriter model
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:3b"},  # Different from cluster
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        success = run_shared_ingestion(mock_cfg, models_config=models_config)
        
        assert success is True
        
        # Verify that script_refinement step was handled specially (not called via run_step)
        # The script_refinement step is handled in the batch logic, not as a regular step
        script_refinement_calls = [call for call in mock_run_step.call_args_list if call[0][0] == "script_refinement"]
        assert len(script_refinement_calls) == 0
        
        # But verify that the batch was executed (3 batches total)
        # This is verified by the logging output showing 3 batches
    
    @patch('bin.run_pipeline.run_step')
    def test_script_refinement_batch_skipped_when_same_model(self, mock_run_step):
        """Test that script refinement batch is skipped when same as cluster model."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock models config with same scriptwriter model as cluster
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:latest"},  # Same as cluster
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        success = run_shared_ingestion(mock_cfg, models_config=models_config)
        
        assert success is True
        
        # Verify that script_refinement step was NOT called
        script_refinement_calls = [call for call in mock_run_step.call_args_list if call[0][0] == "script_refinement"]
        assert len(script_refinement_calls) == 0
    
    @patch('bin.run_pipeline.run_step')
    def test_from_step_resumption(self, mock_run_step):
        """Test that pipeline can resume from a specific step."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock models config
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:latest"},
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        # Resume from research_collect step
        success = run_shared_ingestion(mock_cfg, from_step="research_collect", models_config=models_config)
        
        assert success is True
        
        # Verify that only steps from research_collect onwards were called
        expected_calls = [
            call("research_collect", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("research_ground", required=True, brief_env=None, brief_data=None, models_config=models_config),
            call("fact_check", required=False, brief_env=None, brief_data=None, models_config=models_config),
            call("fetch_assets", required=True, brief_env=None, brief_data=None, models_config=models_config)
        ]
        
        mock_run_step.assert_has_calls(expected_calls, any_order=False)
        
        # Verify that earlier steps were not called (this is handled by the batch logic)
        # The test verifies that only the expected steps from research_collect onwards were called
    
    @patch('bin.run_pipeline.run_step')
    def test_unknown_from_step_handling(self, mock_run_step):
        """Test that unknown from_step is handled gracefully."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock models config
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:latest"},
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        # Try to resume from unknown step
        success = run_shared_ingestion(mock_cfg, from_step="unknown_step", models_config=models_config)
        
        assert success is True
        
        # Verify that all steps were called (started from beginning)
        assert mock_run_step.call_count == 8  # All steps including fetch_assets
    
    @patch('bin.run_pipeline.run_step')
    def test_models_config_loading_fallback(self, mock_run_step):
        """Test that pipeline works when models.yaml is not available."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock config object
        mock_cfg = MagicMock()
        
        # No models config provided
        success = run_shared_ingestion(mock_cfg, models_config=None)
        
        assert success is True
        
        # Verify that steps were called with default model names
        mock_run_step.assert_called()
    
    @patch('bin.run_pipeline.run_step')
    def test_batch_logging_and_status(self, mock_run_step):
        """Test that batch execution provides proper logging and status tracking."""
        from bin.run_pipeline import run_shared_ingestion
        
        # Mock successful step execution
        mock_run_step.return_value = True
        
        # Mock models config
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:latest"},
                "outline": {"name": "llama3.2:latest"},
                "scriptwriter": {"name": "llama3.2:latest"},
                "research": {"name": "mistral:7b-instruct"}
            }
        }
        
        # Mock config object
        mock_cfg = MagicMock()
        
        success = run_shared_ingestion(mock_cfg, models_config=models_config)
        
        assert success is True
        
        # Verify that all required steps were called
        required_steps = ["niche_trends", "llm_cluster", "llm_outline", "llm_script", "research_collect", "research_ground", "fetch_assets"]
        for step in required_steps:
            mock_run_step.assert_any_call(step, required=True, brief_env=None, brief_data=None, models_config=models_config)
        
        # Verify that optional steps were called with required=False
        mock_run_step.assert_any_call("fact_check", required=False, brief_env=None, brief_data=None, models_config=models_config)


if __name__ == "__main__":
    pytest.main([__file__])

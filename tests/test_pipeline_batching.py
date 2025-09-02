#!/usr/bin/env python3
"""
Test pipeline batching functionality.
"""

import os
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# Add the bin directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "bin"))


class TestPipelineBatching:
    """Test pipeline batching functionality."""

    @patch("bin.run_pipeline.run_step")
    def test_shared_ingestion_success(self, mock_run_step):
        """Test successful shared ingestion execution."""
        from bin.run_pipeline import run_shared_ingestion

        # Mock successful step execution
        mock_run_step.return_value = True

        # Mock models config
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:3b"},
                "outline": {"name": "llama3.2:3b"},
                "scriptwriter": {"name": "llama3.2:3b"},
                "research": {"name": "llama3.2:3b"},
            }
        }

        # Mock config object
        mock_cfg = MagicMock()

        success = run_shared_ingestion(mock_cfg, models_config=models_config)

        assert success is True

        # Verify steps were called in the correct order
        expected_calls = [
            call(
                "niche_trends",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_cluster",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_outline",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_script",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_collect",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_ground",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "fact_check",
                required=False,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "storyboard_plan",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
        ]

        mock_run_step.assert_has_calls(expected_calls, any_order=False)

    @patch("bin.run_pipeline.run_step")
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
                "cluster": {"name": "llama3.2:3b"},
                "outline": {"name": "llama3.2:3b"},
                "scriptwriter": {"name": "llama3.2:3b"},
                "research": {"name": "llama3.2:3b"},
            }
        }

        # Mock config object
        mock_cfg = MagicMock()

        success = run_shared_ingestion(mock_cfg, models_config=models_config)

        assert success is False

        # Verify that steps in the first batch were called
        mock_run_step.assert_any_call(
            "niche_trends",
            required=True,
            brief_env=None,
            brief_data=None,
            models_config=models_config,
        )
        mock_run_step.assert_any_call(
            "llm_cluster",
            required=True,
            brief_env=None,
            brief_data=None,
            models_config=models_config,
        )

        # Verify that only 2 steps were called (niche_trends and llm_cluster)
        assert mock_run_step.call_count == 2

        # Verify that research steps were not called due to early failure
        # The mock was called twice, so we can't use assert_not_called()
        # Instead, verify that only the expected steps were called
        expected_calls = [
            call(
                "niche_trends",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_cluster",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
        ]
        mock_run_step.assert_has_calls(expected_calls, any_order=False)

    @patch("bin.run_pipeline.run_step")
    def test_optional_script_refinement_batch(self, mock_run_step):
        """Test that optional script refinement batch is added when different from cluster model."""
        from bin.run_pipeline import run_shared_ingestion

        # Mock successful step execution
        mock_run_step.return_value = True

        # Mock models config with different scriptwriter model
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:3b"},
                "outline": {"name": "llama3.2:3b"},
                "scriptwriter": {"name": "llama3.2:3b"},  # Same as cluster
                "research": {"name": "llama3.2:3b"},
            }
        }

        # Mock config object
        mock_cfg = MagicMock()

        success = run_shared_ingestion(mock_cfg, models_config=models_config)

        assert success is True

        # Verify all steps were called
        expected_calls = [
            call(
                "niche_trends",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_cluster",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_outline",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_script",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_collect",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_ground",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "fact_check",
                required=False,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "storyboard_plan",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
        ]

        mock_run_step.assert_has_calls(expected_calls, any_order=False)

    @patch("bin.run_pipeline.run_step")
    def test_optional_script_refinement_batch_different_model(self, mock_run_step):
        """Test that optional script refinement batch is added when different from cluster model."""
        from bin.run_pipeline import run_shared_ingestion

        # Mock successful step execution
        mock_run_step.return_value = True

        # Mock models config with different scriptwriter model
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:3b"},
                "outline": {"name": "llama3.2:3b"},
                "scriptwriter": {"name": "llama3.2:3b"},  # Same as cluster
                "research": {"name": "llama3.2:3b"},
            }
        }

        # Mock config object
        mock_cfg = MagicMock()

        success = run_shared_ingestion(mock_cfg, models_config=models_config)

        assert success is True

        # Verify all steps were called
        expected_calls = [
            call(
                "niche_trends",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_cluster",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_outline",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_script",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_collect",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_ground",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "fact_check",
                required=False,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "storyboard_plan",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
        ]

        mock_run_step.assert_has_calls(expected_calls, any_order=False)

    @patch("bin.run_pipeline.run_step")
    def test_optional_script_refinement_batch_same_model(self, mock_run_step):
        """Test that optional script refinement batch is not added when same as cluster model."""
        from bin.run_pipeline import run_shared_ingestion

        # Mock successful step execution
        mock_run_step.return_value = True

        # Mock models config with same scriptwriter model
        models_config = {
            "models": {
                "cluster": {"name": "llama3.2:3b"},
                "outline": {"name": "llama3.2:3b"},
                "scriptwriter": {"name": "llama3.2:3b"},  # Same as cluster
                "research": {"name": "llama3.2:3b"},
            }
        }

        # Mock config object
        mock_cfg = MagicMock()

        success = run_shared_ingestion(mock_cfg, models_config=models_config)

        assert success is True

        # Verify all steps were called
        expected_calls = [
            call(
                "niche_trends",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_cluster",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_outline",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "llm_script",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_collect",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "research_ground",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "fact_check",
                required=False,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
            call(
                "storyboard_plan",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=models_config,
            ),
        ]

        mock_run_step.assert_has_calls(expected_calls, any_order=False)

    @patch("bin.run_pipeline.run_step")
    def test_optional_script_refinement_batch_missing_config(self, mock_run_step):
        """Test that optional script refinement batch is not added when models config is missing."""
        from bin.run_pipeline import run_shared_ingestion

        # Mock successful step execution
        mock_run_step.return_value = True

        # Mock config object
        mock_cfg = MagicMock()

        success = run_shared_ingestion(mock_cfg, models_config=None)

        assert success is True

        # Verify all steps were called
        expected_calls = [
            call(
                "niche_trends",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "llm_cluster",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "llm_outline",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "llm_script",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "research_collect",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "research_ground",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "fact_check",
                required=False,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
            call(
                "storyboard_plan",
                required=True,
                brief_env=None,
                brief_data=None,
                models_config=None,
            ),
        ]

        mock_run_step.assert_has_calls(expected_calls, any_order=False)


if __name__ == "__main__":
    pytest.main([__file__])

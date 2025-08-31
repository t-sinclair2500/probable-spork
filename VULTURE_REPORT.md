# Vulture Dead Code Report

## Overview
This report documents unused code found by vulture analysis of the probable-spork codebase. Vulture identifies dead code with confidence levels from 60-100%.

**Summary:**
- **High confidence issues (80-100%):** 58 items
- **Medium confidence issues (60-79%):** 241 items (299 total - 58 high confidence)
- **Total issues found:** 299 items
- **Syntax error fixed:** `scripts/backup_wp.py:50` - missing closing bracket

## High Confidence Issues (80-100%)

### Unused Imports (90% confidence)

#### bin/ directory
- `bin/assemble_video.py:41`: unused import 'vfx'
- `bin/asset_manifest.py:19`: unused import 'Set'

- `bin/core.py:81`: unused import 'platform'
- `bin/cutout/asset_loop.py:16`: unused import 'Set'
- `bin/cutout/qa_gates.py:9`: unused import 'colorsys'
- `bin/cutout/sdk.py:11`: unused import 'pathlib'
- `bin/cutout/svg_geom.py:27`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_geom.py:39`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_geom.py:51`: unused import 'SVGElementPath'
- `bin/cutout/svg_geom.py:60`: unused imports 'shapely', 'LineString', 'Point'
- `bin/cutout/svg_path_ops.py:31`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_path_ops.py:43`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_path_ops.py:56`: unused import 'SVGElementPath'
- `bin/cutout/svg_path_ops.py:65`: unused imports 'shapely', 'LineString', 'Point'
- `bin/cutout/texture_engine.py:34`: unused import 'opensimplex'
- `bin/cutout/texture_engine.py:41`: unused imports 'skimage', 'filters'
- `bin/legibility.py:18`: unused import 'colorsys'
- `bin/llm_client.py:45`: unused import 'cluster_topics'
- `bin/model_runner.py:11`: unused import 'contextlib'
- `bin/model_runner.py:436`: unused import 'cluster_topics'
- `bin/web_ui.py:10`: unused import 'abort'
- `bin/web_ui.py:11`: unused import 'disconnect'

#### fastapi_app/ directory
- `fastapi_app/events.py:16`: unused import 'EventStreamResponse'
- `fastapi_app/middleware.py:8`: unused import 'Response'
- `fastapi_app/models.py:3`: unused import 'Union'
- `fastapi_app/routes.py:13`: unused import 'JobUpdate'

#### scripts/ directory
- `scripts/launch_web.py:18`: unused import 'ui'
- `scripts/launch_web.py:30`: unused import 'run_server'
- `scripts/launch_web.py:56`: unused import 'run_tests'
- `scripts/run_tests.py:42`: unused import 'demo_svg_path_ops'
- `scripts/run_tests.py:55`: unused import 'demo_texture_effects'
- `scripts/serve_api.py:43`: unused import 'fastapi'
- `scripts/start_system.py:97`: unused import 'run_tests'

#### tests/ directory
- `tests/phases/test_phase3_visual_polish.py:89`: unused imports 'boolean_union', 'morph_paths'
- `tests/phases/test_phase4_research.py:24`: unused import 'BASE'
- `tests/phases/test_phase4_research.py:33`: unused import 'run_fact_guard_analysis'
- `tests/texture/test_texture_engine.py:122`: unused import 'check_texture_cache'
- `tests/texture/test_texture_engine_core.py:16`: unused import 'apply_textures_to_clip'

### Unused Variables (100% confidence)

#### bin/ directory
- `bin/asset_manifest.py:504`: unused variable 'filter_palette_only'

- `bin/cutout/sdk.py:89`: unused variable 'cls'
- `bin/cutout/sdk.py:107`: unused variable 'cls'
- `bin/cutout/sdk.py:129`: unused variable 'cls'
- `bin/cutout/sdk.py:147`: unused variable 'cls'
- `bin/cutout/sdk.py:162`: unused variable 'cls'
- `bin/model_runner.py:198`: unused variables 'exc_tb', 'exc_type', 'exc_val'

#### fastapi_app/ directory
- `fastapi_app/models.py:131`: unused variable 'cls'
- `fastapi_app/models.py:155`: unused variable 'cls'
- `fastapi_app/models.py:162`: unused variable 'cls'
- `fastapi_app/models.py:167`: unused variable 'cls'

#### tests/ directory
- `tests/conftest.py:55`: unused variable 'kwargs'
- `tests/conftest.py:64`: unused variable 'kwargs'
- `tests/test_pipeline_batching.py:63`: unused variable 'kwargs'

## Medium Confidence Issues (60-79%)

### Unused Functions and Methods

#### bin/ directory
- `bin/core.py:405`: unused function 'get_brief_intent_template'
- `bin/core.py:458`: unused function 'require_keys'
- `bin/core.py:525`: unused function 'paced_sleep'
- `bin/core.py:614`: unused function 'sha1_bytes'
- `bin/core.py:733`: unused function 'should_publish_youtube'

- `bin/core.py:745`: unused function 'get_publish_summary'
- `bin/cutout/anim_fx.py:94`: unused function '_seconds_to_ms'
- `bin/cutout/asset_loop.py:225`: unused method 'generate_variants'
- `bin/cutout/color_engine.py:164`: unused function 'assert_legible_text'
- `bin/cutout/color_engine.py:205`: unused function 'shade'
- `bin/cutout/color_engine.py:249`: unused function 'enforce_scene_palette'
- `bin/cutout/color_engine.py:297`: unused function 'validate_scene_colors'
- `bin/cutout/qa_gates.py:474`: unused function 'run_qa_suite'
- `bin/cutout/qa_gates.py:860`: unused function 'qa_result_to_json'
- `bin/cutout/sdk.py:88`: unused function 'validate_font_sizes'
- `bin/cutout/sdk.py:106`: unused function 'validate_opacity'
- `bin/cutout/sdk.py:128`: unused function 'validate_type'
- `bin/cutout/sdk.py:146`: unused function 'validate_duration'
- `bin/cutout/sdk.py:161`: unused function 'validate_fps'
- `bin/cutout/svg_geom.py:102`: unused method '_log_validation_error'
- `bin/cutout/svg_geom.py:114`: unused function 'load_svg_paths'
- `bin/cutout/svg_geom.py:156`: unused function 'boolean_union'
- `bin/cutout/svg_geom.py:310`: unused function 'morph_paths'
- `bin/cutout/svg_geom.py:515`: unused function 'validate_geometry'
- `bin/cutout/svg_geom.py:580`: unused function 'write_validation_report'
- `bin/cutout/svg_path_ops.py:243`: unused method 'morph_paths'
- `bin/cutout/texture_engine.py:71`: unused function '_hash_image'
- `bin/cutout/texture_engine.py:326`: unused function 'apply_textures_to_clip'
- `bin/cutout/texture_integration.py:105`: unused function 'check_texture_cache'
- `bin/design_loader.py:75`: unused method 'get_color'
- `bin/design_loader.py:95`: unused method 'get_font'
- `bin/fact_guard.py:32`: unused function 'load_fact_guard_prompt'
- `bin/health_server.py:13`: unused function 'health'
- `bin/intent_loader.py:268`: unused function 'get_intent_summary'
- `bin/llm_client.py:30`: unused function 'run_cluster'
- `bin/llm_client.py:157`: unused function 'run_research_plan'
- `bin/llm_client.py:195`: unused function 'run_fact_guard'
- `bin/llm_client.py:451`: unused method 'ensure_model'
- `bin/llm_client.py:478`: unused function 'ollama_chat'
- `bin/llm_client.py:483`: unused function 'ollama_embed'
- `bin/memory_monitor.py:235`: unused method 'get_alert_history'
- `bin/memory_monitor.py:239`: unused method 'clear_alert_history'
- `bin/model_runner.py:45`: unused function 'get_memory_gb'
- `bin/model_runner.py:398`: unused function 'get_system_memory_info'
- `bin/model_runner.py:419`: unused function 'run_cluster'
- `bin/model_runner.py:553`: unused function 'run_research_plan'
- `bin/model_runner.py:594`: unused function 'run_fact_guard'
- `bin/music_library.py:213`: unused method 'get_tracks_by_mood'
- `bin/music_library.py:218`: unused method 'get_tracks_by_bpm_range'
- `bin/music_mixer.py:257`: unused method 'normalize_audio'
- `bin/pacing_kpi.py:335`: unused function 'run_complete_pacing_analysis'
- `bin/run_pipeline.py:241`: unused function '_run_llm_step'
- `bin/util.py:43`: unused function 'paced_sleep'
- `bin/util.py:48`: unused function 'run_cmd'
- `bin/util.py:53`: unused function 'load_json'
- `bin/util.py:60`: unused function 'dump_json'

#### fastapi_app/ directory
- `fastapi_app/__init__.py:94`: unused function 'health_check'
- `fastapi_app/config.py:128`: unused method 'get_sanitized_config'
- `fastapi_app/config.py:142`: unused method 'validate_config'
- `fastapi_app/db.py:501`: unused method 'delete_job'
- `fastapi_app/events.py:54`: unused method 'ensure_heartbeat_started'
- `fastapi_app/events.py:514`: unused method 'artifact_created'
- `fastapi_app/middleware.py:60`: unused function 'rate_limit_middleware'
- `fastapi_app/middleware.py:99`: unused function 'security_headers_middleware'
- `fastapi_app/middleware.py:133`: unused function 'binding_restriction_middleware'
- `fastapi_app/orchestrator.py:772`: unused method 'record_event'
- `fastapi_app/orchestrator.py:1113`: unused method 'reject_gate'
- `fastapi_app/orchestrator.py:1156`: unused method 'cancel_job'
- `fastapi_app/orchestrator.py:1191`: unused method 'cleanup_completed_jobs'
- `fastapi_app/routes.py:59`: unused function 'get_operator_config'
- `fastapi_app/routes.py:111`: unused function 'validate_config'
- `fastapi_app/routes.py:261`: unused function 'compile_brief'
- `fastapi_app/routes.py:433`: unused function 'reject_gate'
- `fastapi_app/routes.py:505`: unused function 'resume_job'
- `fastapi_app/routes.py:721`: unused function 'cancel_job'
- `fastapi_app/routes.py:835`: unused function 'stream_job_events'
- `fastapi_app/routes.py:945`: unused function 'get_gate_decision'
- `fastapi_app/routes.py:981`: unused function 'list_gate_decisions'
- `fastapi_app/routes.py:1019`: unused function 'apply_patch_direct'
- `fastapi_app/routes.py:1065`: unused function 'get_gates_status'
- `fastapi_app/routes.py:1130`: unused function 'get_patch_types'
- `fastapi_app/routes.py:1194`: unused function 'health_check'
- `fastapi_app/security.py:28`: unused function 'redact_secrets'
- `fastapi_app/security.py:66`: unused function 'is_authenticated'
- `fastapi_app/storage.py:31`: unused method 'create_job_directory'
- `fastapi_app/storage.py:43`: unused method 'store_artifact'
- `fastapi_app/storage.py:92`: unused method 'get_artifact_path'
- `fastapi_app/storage.py:110`: unused method 'list_job_artifacts'
- `fastapi_app/storage.py:155`: unused method 'cleanup_job'

### Unused Classes

#### fastapi_app/ directory
- `fastapi_app/models.py:115`: unused class 'JobUpdate'
- `fastapi_app/models.py:175`: unused class 'Config'
- `fastapi_app/models.py:192`: unused class 'EventStreamResponse'
- `fastapi_app/models.py:200`: unused class 'JobEventsResponse'

### Unused Variables and Attributes

#### bin/ directory
- `bin/acceptance.py:1060`: unused variable 'date_prefix'
- `bin/analytics_collector.py:34`: unused attribute 'recent_metrics'
- `bin/analytics_collector.py:35`: unused attribute 'step_performance'
- `bin/analytics_collector.py:36`: unused attribute 'error_patterns'
- `bin/assemble_video.py:544`: unused variable 'xfade_this'
- `bin/assemble_video.py:546`: unused variable 'xfade_this'
- `bin/asset_quality.py:56`: unused variable 'analyzed_at'
- `bin/audio_validator.py:423`: unused variable 'temp_output'
- `bin/audio_validator.py:580`: unused variable 'temp_analysis'
- `bin/audio_validator.py:655`: unused variable 'temp_segment'
- `bin/core.py:53`: unused variable 'temperature'
- `bin/core.py:54`: unused variable 'max_tokens'
- `bin/core.py:64`: unused variable 'enable_thumbnails'
- `bin/core.py:74`: unused variable 'logs_dir'
- `bin/core.py:76`: unused variable 'jobs_dir'
- `bin/core.py:136`: unused variable 'max_per_section'
- `bin/core.py:163`: unused variable 'auto_upload'
- `bin/core.py:165`: unused variable 'schedule'
- `bin/core.py:169`: unused variable 'require_attribution'
- `bin/core.py:197`: unused variable 'density'
- `bin/core.py:200`: unused variable 'seed_variation'
- `bin/core.py:205`: unused variable 'posterization_levels'
- `bin/core.py:206`: unused variable 'edge_strength'
- `bin/core.py:211`: unused variable 'dot_size'
- `bin/core.py:212`: unused variable 'dot_spacing'
- `bin/core.py:220`: unused variable 'session_based'
- `bin/core.py:224`: unused variable 'color_preservation'
- `bin/core.py:225`: unused variable 'brand_palette_only'
- `bin/core.py:238`: unused variable 'licenses'
- `bin/cutout/anim_fx.py:259`: unused variable 'time_seconds'
- `bin/cutout/asset_loop.py:433`: unused variable 'generation_results'
- `bin/cutout/micro_animations.py:43`: unused attribute 'geometry_engine'
- `bin/cutout/micro_animations.py:53`: unused attribute 'collision_check'
- `bin/cutout/motif_generators.py:459`: unused variable 'prev_angle_rad'
- `bin/cutout/sdk.py:39`: unused variable 'SLOW_ZOOM'
- `bin/cutout/sdk.py:40`: unused variable 'SLOW_PAN'
- `bin/cutout/sdk.py:82`: unused variable 'corner_radius'
- `bin/cutout/sdk.py:84`: unused variable 'shadow'
- `bin/cutout/sdk.py:86`: unused variable 'icon_palette'
- `bin/cutout/sdk.py:142`: unused variable 'audio_cue'
- `bin/cutout/svg_geom.py:34`: unused variable 'QuadraticBezier'
- `bin/cutout/svg_geom.py:35`: unused variable 'Arc'
- `bin/cutout/svg_geom.py:46`: unused variable 'QuadraticBezier'
- `bin/cutout/svg_geom.py:56`: unused variable 'SVGElementPath'
- `bin/cutout/svg_geom.py:67`: unused variable 'Point'
- `bin/cutout/svg_geom.py:68`: unused variable 'LineString'
- `bin/cutout/svg_path_ops.py:38`: unused variable 'QuadraticBezier'
- `bin/cutout/svg_path_ops.py:39`: unused variable 'Arc'
- `bin/cutout/svg_path_ops.py:50`: unused variable 'QuadraticBezier'
- `bin/cutout/svg_path_ops.py:51`: unused variable 'Arc'
- `bin/cutout/svg_path_ops.py:61`: unused variable 'SVGElementPath'
- `bin/cutout/svg_path_ops.py:72`: unused variable 'Point'
- `bin/cutout/svg_path_ops.py:73`: unused variable 'LineString'
- `bin/cutout/svg_path_ops.py:347`: unused attribute 'design_constraints'
- `bin/cutout/svg_path_ops.py:350`: unused attribute 'design_constraints'
- `bin/cutout/texture_engine.py:35`: unused variable 'OPENIMPLEX_AVAILABLE'
- `bin/cutout/texture_engine.py:37`: unused variable 'OPENIMPLEX_AVAILABLE'
- `bin/generate_captions.py:112`: unused variable 'code'
- `bin/llm_outline.py:148`: unused variable 'intent_context'
- `bin/llm_outline.py:150`: unused variable 'intent_context'
- `bin/memory_monitor.py:166`: unused attribute '_memory_check_count'
- `bin/music_manager.py:56`: unused variable 'stats_parser'
- `bin/music_manager.py:59`: unused variable 'validate_parser'
- `bin/music_manager.py:79`: unused variable 'setup_parser'
- `bin/pacing_kpi.py:159`: unused variable 'srt_words'
- `bin/research_ground.py:50`: unused attribute 'citation_format'
- `bin/seo_enhancer.py:38`: unused variable 'language'
- `bin/storyboard_reflow.py:42`: unused attribute 'max_scale_reduction'
- `bin/storyboard_reflow.py:43`: unused attribute 'max_nudge_distance'
- `bin/storyboard_reflow.py:47`: unused attribute 'layout_engine'
- `bin/timing_utils.py:83`: unused variable 'direction'
- `bin/voice_cues.py:78`: unused variable 'number'
- `bin/web_ui.py:25`: unused attribute 'secret_key'
- `bin/web_ui.py:40`: unused variable 'broadcast_queue'

## Recommendations

### High Priority (90-100% confidence)
1. **Remove unused imports** - These are safe to remove and will reduce code size
2. **Remove unused variables** - Clean up variables that are assigned but never used
3. **Fix syntax error** - `scripts/backup_wp.py:50` has a parenthesis mismatch

### Medium Priority (60-79% confidence)
1. **Review unused functions** - These may be:
   - Legacy code that can be safely removed
   - Future-proofing code that should be kept
   - Code that's used dynamically (imports, decorators, etc.)
2. **Review unused classes** - Check if these are used in configuration or dynamic loading
3. **Review unused attributes** - These may be used in serialization or configuration

### Investigation Required
1. **Dynamic usage** - Some functions may be called via reflection, decorators, or configuration
2. **API endpoints** - FastAPI routes may be used but not detected by static analysis
3. **Test utilities** - Some functions may be used in tests but not detected
4. **Configuration-driven code** - Some classes may be instantiated via configuration

## Next Steps
1. Fix the syntax error in `scripts/backup_wp.py`
2. Remove high-confidence unused imports and variables
3. Investigate medium-confidence issues to determine if they're truly unused
4. Consider using `# noqa: F401` comments for imports that are intentionally unused
5. Set up vulture in CI/CD to prevent accumulation of dead code

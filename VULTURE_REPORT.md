# Vulture Dead Code Analysis Report

Generated on: $(date)

## Summary

Vulture analyzed the entire codebase and found **156 instances** of potentially dead code across **60+ files**. The analysis used a minimum confidence threshold of 60% to identify unused imports, variables, functions, and methods.

## High Confidence Findings (80%+ confidence)

### Unused Imports (90% confidence)
These imports are likely dead code and can be safely removed:

#### Core Pipeline Files
- `bin/assemble_video.py:41`: unused import 'vfx'
- `bin/legibility.py:18`: unused import 'colorsys'

#### Cutout Module
- `bin/cutout/qa_gates.py:9`: unused import 'colorsys'
- `bin/cutout/sdk.py:11`: unused import 'pathlib'
- `bin/cutout/svg_geom.py:27`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_geom.py:39`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_geom.py:51`: unused import 'SVGElementPath'
- `bin/cutout/svg_geom.py:60`: unused import 'shapely'
- `bin/cutout/svg_geom.py:61`: unused imports 'LineString', 'Point'
- `bin/cutout/svg_path_ops.py:31`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_path_ops.py:43`: unused imports 'Arc', 'QuadraticBezier'
- `bin/cutout/svg_path_ops.py:56`: unused import 'SVGElementPath'
- `bin/cutout/svg_path_ops.py:65`: unused import 'shapely'
- `bin/cutout/svg_path_ops.py:66`: unused imports 'LineString', 'Point'
- `bin/cutout/texture_engine.py:34`: unused import 'opensimplex'
- `bin/cutout/texture_engine.py:41`: unused import 'skimage'
- `bin/cutout/texture_engine.py:42`: unused import 'filters'

#### LLM and Model Files
- `bin/llm_client.py:45`: unused import 'cluster_topics'
- `bin/model_runner.py:11`: unused import 'contextlib'
- `bin/model_runner.py:436`: unused import 'cluster_topics'

#### FastAPI Application
- `fastapi_app/events.py:16`: unused import 'EventStreamResponse'
- `fastapi_app/middleware.py:8`: unused import 'Response'
- `fastapi_app/routes.py:13`: unused imports 'GateDecision', 'JobUpdate'

#### Scripts
- `scripts/launch_web.py:18`: unused import 'ui'
- `scripts/launch_web.py:30`: unused import 'run_server'
- `scripts/launch_web.py:56`: unused import 'run_tests'
- `scripts/run_tests.py:42`: unused import 'demo_svg_path_ops'
- `scripts/run_tests.py:55`: unused import 'demo_texture_effects'
- `scripts/serve_api.py:43`: unused import 'fastapi'
- `scripts/start_system.py:97`: unused import 'run_tests'

#### Tests
- `tests/phases/test_phase3_visual_polish.py:89`: unused import 'boolean_union'
- `tests/texture/test_texture_engine.py:122`: unused import 'check_texture_cache'
- `tests/texture/test_texture_engine_core.py:16`: unused import 'apply_textures_to_clip'

### Unused Variables (100% confidence)
These variables are definitely dead code:

- `bin/asset_manifest.py:504`: unused variable 'filter_palette_only'
- `bin/cutout/sdk.py:89`: unused variable 'cls'
- `bin/cutout/sdk.py:107`: unused variable 'cls'
- `bin/cutout/sdk.py:129`: unused variable 'cls'
- `bin/cutout/sdk.py:147`: unused variable 'cls'
- `bin/cutout/sdk.py:162`: unused variable 'cls'
- `bin/model_runner.py:198`: unused variables 'exc_tb', 'exc_type', 'exc_val'

## Medium Confidence Findings (60-79% confidence)

### Unused Functions and Methods
These functions appear to be unused but may have indirect usage:

#### Core Module
- `bin/core.py:398`: unused function 'get_brief_intent_template'
- `bin/core.py:422`: unused function 'filter_content_by_brief'
- `bin/core.py:451`: unused function 'require_keys'
- `bin/core.py:518`: unused function 'paced_sleep'
- `bin/core.py:600`: unused function 'sanitize_html'
- `bin/core.py:607`: unused function 'sha1_bytes'
- `bin/core.py:648`: unused function 'schema_article'
- `bin/core.py:697`: unused function 'should_publish_youtube'

#### Cutout Module
- `bin/cutout/anim_fx.py:94`: unused function '_seconds_to_ms'
- `bin/cutout/color_engine.py:164`: unused function 'assert_legible_text'
- `bin/cutout/color_engine.py:205`: unused function 'shade'
- `bin/cutout/color_engine.py:249`: unused function 'enforce_scene_palette'
- `bin/cutout/color_engine.py:297`: unused function 'validate_scene_colors'
- `bin/cutout/qa_gates.py:474`: unused function 'run_qa_suite'
- `bin/cutout/qa_gates.py:860`: unused function 'qa_result_to_json'
- `bin/cutout/svg_geom.py:114`: unused function 'load_svg_paths'
- `bin/cutout/svg_geom.py:156`: unused function 'boolean_union'
- `bin/cutout/svg_geom.py:515`: unused function 'validate_geometry'
- `bin/cutout/svg_geom.py:580`: unused function 'write_validation_report'
- `bin/cutout/texture_engine.py:71`: unused function '_hash_image'
- `bin/cutout/texture_engine.py:326`: unused function 'apply_textures_to_clip'
- `bin/cutout/texture_integration.py:105`: unused function 'check_texture_cache'

#### FastAPI Application
- `fastapi_app/__init__.py:94`: unused function 'health_check'
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
- `fastapi_app/middleware.py:60`: unused function 'rate_limit_middleware'
- `fastapi_app/middleware.py:99`: unused function 'security_headers_middleware'
- `fastapi_app/middleware.py:133`: unused function 'binding_restriction_middleware'

### Unused Variables and Attributes
- `bin/acceptance.py:1006`: unused variable 'date_prefix'
- `bin/analytics_collector.py:34`: unused attribute 'recent_metrics'
- `bin/analytics_collector.py:35`: unused attribute 'step_performance'
- `bin/analytics_collector.py:36`: unused attribute 'error_patterns'
- `bin/assemble_video.py:349`: unused method 'callback'
- `bin/assemble_video.py:544`: unused variable 'xfade_this'
- `bin/assemble_video.py:546`: unused variable 'xfade_this'
- `bin/asset_generator.py:266`: unused method '_validate_palette'
- `bin/asset_manifest.py:376`: unused method '_validate_palette_compliance'
- `bin/asset_quality.py:56`: unused variable 'analyzed_at'
- `bin/asset_quality.py:525`: unused method 'rank_assets'
- `bin/audio_validator.py:135`: unused method 'extract_audio_safely'
- `bin/audio_validator.py:423`: unused variable 'temp_output'
- `bin/audio_validator.py:580`: unused variable 'temp_analysis'
- `bin/audio_validator.py:655`: unused variable 'temp_segment'

## Recommendations

### Immediate Actions (High Confidence)
1. **Remove unused imports** - These are safe to delete and will reduce memory usage
2. **Remove unused variables** - Especially the 100% confidence ones
3. **Clean up cutout module** - Many unused imports and functions in SVG/geometry code

### Investigation Required (Medium Confidence)
1. **Review FastAPI routes** - Many unused functions may be API endpoints
2. **Check core utilities** - Functions like `paced_sleep`, `sanitize_html` may be used indirectly
3. **Verify test functions** - Some may be used by test frameworks

### Files with Most Dead Code
1. `bin/cutout/svg_geom.py` - 8 unused imports/functions
2. `bin/cutout/svg_path_ops.py` - 7 unused imports
3. `fastapi_app/routes.py` - 12 unused functions
4. `bin/core.py` - 8 unused functions

## Notes
- Vulture may have false positives for functions used via reflection or dynamic imports
- Some unused code may be kept for future features or debugging
- Consider using `# noqa: F401` comments for intentionally unused imports
- Run tests after removing dead code to ensure no functionality is broken

## Command Used
```bash
python -m vulture . --exclude="venv,__pycache__,*.pyc,*.pyo,*.pyd,.git,assets,data,logs,render_cache,temp_export,videos,voiceovers,models,results,runs,scenescripts,schema,services,ui,utils,vendors" --min-confidence=60
```


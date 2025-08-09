# Background Agent 2: WordPress & Content Generation Track

You are a senior full-stack developer working in an Ubuntu-based Cursor background agent environment. Your mission is to polish the blog publishing pipeline and enhance content quality controls for a Raspberry Pi automation system.

## Environment Context

You are working in a clean Ubuntu VM that has been set up with:
- Python 3.x with venv created at `.venv`
- System dependencies: ffmpeg, git, jq, sqlite3, build-essential, cmake  
- Python dependencies installed from `requirements.txt`

**Important**: You do NOT have access to:
- Live WordPress instance for testing
- Ollama service (LLM calls will fail)
- Real API keys for asset providers
- External services (OpenAI, Pexels, Pixabay)

**You CAN work on**: Code logic, validation, error handling, UI improvements, and dry-run functionality.

## Your Assigned Work Track

You are responsible for **Track B: WordPress & Content Generation** from the Status Board in `MASTER_TODO.md`. Your parallel work track includes:

**P0 (Critical - Ship v1):**
- **D2**: Blog generate acceptance checks (structure/word count)
- **D5**: WP inline image uploads (attach to content)
- **H9**: Blog DRY_RUN env control & media upload polish

**P1 (Polish):**
- **G1**: Web UI enhancements (logs tail, auth hardening)

**P2 (Nice-to-have):**
- **Unsplash**: Optional provider with attribution

## Key Files to Review

Start by reading these files to understand the current state:

1. **`MASTER_TODO.md`** - Your canonical task list with detailed acceptance criteria
2. **`bin/blog_generate_post.py`** - Content generation needing acceptance validation
3. **`bin/blog_post_wp.py`** - WordPress client needing inline image support
4. **`bin/web_ui.py`** - Flask UI needing log tailing and auth hardening
5. **`conf/blog.yaml`** - Blog-specific configuration
6. **`conf/blog.example.yaml`** - Configuration schema template
7. **`jobs/state.jsonl`** - Contains evidence of blog DRY_RUN posts
8. **`assets/2025-08-09_ai-tools/`** - Example asset directory with licensing

## Environment-Aware Implementation Strategy

### For D2 (Blog Generate Validation):
- Add validation logic to `bin/blog_generate_post.py`:
  - Word count checking (target ranges)
  - Structure validation (H2/H3 headings present)
  - Required elements (bullets, FAQ, CTA)
- **Note**: LLM calls may fail, so focus on validating existing generated content or mock data
- Test with existing blog posts in `data/cache/` if present

### For D5 (WordPress Inline Images):
- Extend `bin/blog_post_wp.py` to handle inline images:
  - Parse blog content for image references  
  - Upload images to WordPress `/wp-json/wp/v2/media` endpoint
  - Replace local paths with WordPress media URLs
  - Implement idempotent reuse by SHA1 hash
- **Note**: Test in DRY_RUN mode since you don't have live WordPress
- Use existing featured image upload pattern as reference

### For H9 (DRY_RUN Polish):
- Ensure `BLOG_DRY_RUN` environment variable controls all WordPress interactions
- Add retry/backoff logic for WordPress API calls
- Implement media SHA1 deduplication
- Add robust error handling for WordPress API responses
- **Note**: Focus on code structure and error handling since you can't test live

### For G1 (Web UI Enhancements):
- Add log tailing to Flask UI (`bin/web_ui.py`):
  - Real-time log streaming from `jobs/state.jsonl`
  - WebSocket or SSE for live updates
- Improve authentication:
  - Session management
  - CSRF protection
  - Rate limiting
- **Note**: UI will run on port 8099; test with `python bin/web_ui.py`

### For Unsplash Provider (P2):
- Add Unsplash support to `bin/fetch_assets.py`
- Implement proper attribution handling
- Add to provider configuration options
- **Note**: Won't be able to test actual API calls

## Testing Strategy in Constrained Environment

1. **Use the existing venv**: `. .venv/bin/activate` before running Python scripts
2. **Focus on DRY_RUN modes**: Test logic without external service calls
3. **Use existing data**: Leverage existing blog posts, assets, and logs for testing
4. **Mock external services**: Create mock functions for WordPress API calls
5. **Test web UI locally**: Run Flask app and verify UI changes
6. **Validate file operations**: Ensure scripts create expected outputs

## Sample Test Commands

```bash
# Activate environment
. .venv/bin/activate

# Test blog generation (may need existing data)
python bin/blog_generate_post.py

# Test WordPress posting in DRY_RUN mode
BLOG_DRY_RUN=true python bin/blog_post_wp.py

# Test web UI
python bin/web_ui.py &
curl http://localhost:8099

# Test validation logic
python -c "
import sys
sys.path.append('.')
from bin.blog_generate_post import validate_blog_post
# Add your validation tests here
"
```

## Acceptance Criteria

- **D2**: Blog posts validated for word count, H2/H3 structure, bullets, FAQ/CTA
- **D5**: Inline image upload logic implemented; DRY_RUN shows correct API calls  
- **H9**: `BLOG_DRY_RUN` environment variable fully controls behavior; retry logic added
- **G1**: Web UI shows real-time logs; authentication hardened
- **Unsplash**: Provider added with attribution handling

## Implementation Priority

1. **H9** (DRY_RUN Control) - Critical for production readiness
2. **D2** (Content Validation) - Quality assurance for outputs
3. **D5** (Inline Images) - Complete WordPress integration
4. **G1** (Web UI) - Operator experience improvements  
5. **Unsplash** (P2) - Additional asset provider

## WordPress Integration Notes

Current working features:
- Featured image upload via `/wp-json/wp/v2/media`
- DRY_RUN mode prints JSON payload instead of posting
- Authentication via Application Password (HTTPBasicAuth)
- Category and tag creation/assignment

Extend this pattern for inline images while maintaining the same error handling and DRY_RUN behavior.

## Success Evidence

For each completed task, provide:
- Code changes that handle missing external services gracefully
- DRY_RUN output showing correct API call structure
- Validation logic that works with sample data
- Web UI improvements visible at localhost:8099
- Error handling for constrained environment scenarios

**Begin with H9 (DRY_RUN control) as it's critical for testing other WordPress features. Focus on making the blog pipeline robust and testable without external dependencies.**

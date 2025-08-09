# Test Strategy: REUSE vs LIVE Asset Fetching

## Overview

The asset testing strategy provides two modes for testing asset fetching functionality:

- **REUSE mode** (default): Uses fixtures and synthetic assets, makes zero network calls
- **LIVE mode** (opt-in): Makes actual API calls with strict budget and rate limiting

This ensures fast, reliable tests by default while providing the ability to validate actual API integration when needed.

## Quick Start

```bash
# Default: Run all tests in REUSE mode (no network calls)
make test

# Run LIVE mode tests (requires API keys, consumes quota)
make test-live

# Run both modes
make test-all
```

## Configuration

### Global Configuration (`conf/global.yaml`)

```yaml
testing:
  asset_mode: "reuse"               # reuse | live (DEFAULT: reuse)
  fixture_dir: "assets/fixtures"    # where test fixtures are stored
  live_budget_per_run: 5            # hard cap on API calls in live mode
  live_rate_limit_per_min: 10       # API calls per minute limit
  fail_on_live_without_keys: true   # fail live tests if API keys missing
```

### Environment Variables

```bash
# Override asset mode for specific runs
export TEST_ASSET_MODE=reuse    # or "live"

# Override live mode budget
export ASSET_LIVE_BUDGET=3

# API keys (required for live mode)
export PIXABAY_API_KEY=your_key_here
export PEXELS_API_KEY=your_key_here
export UNSPLASH_ACCESS_KEY=your_key_here  # optional
```

## REUSE Mode (Default)

**Purpose**: Fast, reliable testing without external dependencies.

**Behavior**:
- Uses pre-prepared fixture assets from `assets/fixtures/`
- Generates synthetic test images when fixtures are insufficient
- **Zero network calls** - tests will fail if network requests are attempted
- Creates test-appropriate license.json files

**Fixture Structure**:
```
assets/fixtures/
├── _generic/           # Generic fixtures for any topic
│   ├── image1.jpg
│   ├── video1.mp4
│   └── ...
├── ai-tools/          # Topic-specific fixtures (optional)
│   ├── specific1.jpg
│   └── ...
└── license.json       # Fixture metadata
```

**Asset Selection Priority**:
1. Topic-specific fixtures (`assets/fixtures/{slug}/`)
2. Generic fixtures (`assets/fixtures/_generic/`)
3. Synthetic generation if insufficient fixtures

### Preparing Fixtures

```bash
# Copy assets from existing downloads to fixture pool
python bin/prepare_fixtures.py --from-slug 2025-08-09_ai-tools

# Generate synthetic test assets
python bin/prepare_fixtures.py --make-synthetic 10

# List current fixture inventory
python bin/prepare_fixtures.py --list
```

## LIVE Mode (Opt-in)

**Purpose**: Validate actual API integration and behavior.

**When to Use**:
- Weekly integration validation
- Testing new provider integrations
- Verifying API changes haven't broken functionality
- Performance testing with real network conditions

**Safety Features**:
- **Budget enforcement**: Hard cap on API calls per run (default: 5)
- **Rate limiting**: Respects provider rate limits (default: 10/min)
- **API key validation**: Fails early if required keys are missing
- **Detailed logging**: All live fetches logged with `LIVE_FETCH` marker

**Budget Management**:
```bash
# Low budget for quick tests
export ASSET_LIVE_BUDGET=2
make test-live

# Higher budget for comprehensive testing
export ASSET_LIVE_BUDGET=10
make test-live
```

## Running Tests

### Standard Test Workflow

```bash
# 1. Default development testing (fast, no network)
make test

# 2. Weekly integration testing (requires API keys)
# Add API keys to .env file first
make test-live

# 3. Full validation before release
make test-all
```

### Individual Test Components

```bash
# Test specific components in reuse mode
TEST_ASSET_MODE=reuse python -m pytest tests/test_assets_reuse.py -v

# Test specific components in live mode
TEST_ASSET_MODE=live python -m pytest tests/test_assets_live.py -v

# Test E2E pipeline in reuse mode
TEST_ASSET_MODE=reuse python bin/test_e2e.py

# Test asset fetching directly
TEST_ASSET_MODE=reuse python bin/fetch_assets.py
```

## Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.reuse`: Tests that use fixture reuse mode (most tests)
- `@pytest.mark.liveapi`: Tests that require live API access

```bash
# Run only reuse tests
pytest -m "reuse"

# Run only live API tests  
pytest -m "liveapi"

# Run everything except live API tests (default)
pytest -m "not liveapi"
```

## Development Guidelines

### Adding New Tests

**For REUSE mode tests** (`tests/test_assets_reuse.py`):
```python
@pytest.mark.reuse
def test_my_feature(reuse_mode_env):
    # Test logic here - no network calls allowed
    pass
```

**For LIVE mode tests** (`tests/test_assets_live.py`):
```python
@pytest.mark.liveapi
def test_api_integration(live_mode_env):
    # Test logic here - will make actual API calls
    pass
```

### Fixture Management

**Creating fixtures for new functionality**:
1. Run pipeline in live mode once to generate real assets
2. Copy best assets to fixture pool: `python bin/prepare_fixtures.py --from-slug new-topic`
3. Generate synthetics if needed: `python bin/prepare_fixtures.py --make-synthetic 5`

**Best practices**:
- Keep fixture sizes reasonable (< 100MB total)
- Include variety of asset types (images, videos) 
- Update fixtures when asset quality logic changes
- Document fixture creation process for new team members

## Monitoring and Debugging

### Verifying Test Mode

```bash
# Check current mode
python -c "import os; print(f'Asset mode: {os.environ.get(\"TEST_ASSET_MODE\", \"default(reuse)\")}')"

# Verify no network calls in reuse mode
TEST_ASSET_MODE=reuse python bin/fetch_assets.py
grep -R "LIVE_FETCH" logs/ || echo "No live fetches (expected in reuse mode)"
```

### Live Mode Monitoring

```bash
# Check live fetch budget usage
grep "LIVE_FETCH" logs/pipeline.log | wc -l

# Monitor rate limiting
grep "Rate limit reached" logs/pipeline.log

# View budget enforcement
grep "budget exceeded" logs/pipeline.log
```

## Troubleshooting

### Common Issues

**"Network request attempted in REUSE mode"**:
- Indicates test is not properly isolated
- Check that `reuse_mode_env` fixture is being used
- Verify no direct API calls are bypassing the mode check

**"Live fetch budget exceeded"**:
- Increase budget: `export ASSET_LIVE_BUDGET=10`
- Or reduce test scope to stay within budget

**"Live mode requires API keys"**:
- Add required API keys to `.env` file
- Or set `fail_on_live_without_keys: false` in config

**Synthetic assets look wrong**:
- Check PIL/ImageFont installation
- Verify font paths for your OS in `generate_synthetic_assets()`

### Performance Optimization

**Slow reuse mode tests**:
- Check fixture file sizes - may need optimization
- Verify synthetic generation isn't creating oversized images
- Consider reducing fixture variety if tests are too slow

**Live mode rate limiting**:
- Adjust `live_rate_limit_per_min` in config
- Implement exponential backoff for specific providers
- Consider running live tests less frequently

## Integration with CI/CD

### Recommended Pipeline

```yaml
# Example GitHub Actions integration
test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v2
    - name: Run REUSE tests
      run: make test
      env:
        TEST_ASSET_MODE: reuse
    
# Weekly live integration test
test-live:
  runs-on: ubuntu-latest
  if: github.event.schedule  # Only on scheduled runs
  steps:
    - name: Run LIVE tests
      run: make test-live
      env:
        TEST_ASSET_MODE: live
        PIXABAY_API_KEY: ${{ secrets.PIXABAY_API_KEY }}
        PEXELS_API_KEY: ${{ secrets.PEXELS_API_KEY }}
```

## Security Considerations

- **API keys**: Never commit API keys to version control
- **Rate limits**: Respect provider rate limits to avoid account suspension
- **Budget controls**: Always use budget limits in automated testing
- **Fixture content**: Ensure fixture assets are properly licensed for test use

## Future Enhancements

Potential improvements to the test strategy:

1. **Mock provider responses**: More sophisticated mocking for edge cases
2. **Fixture rotation**: Automatic fixture updates from successful live runs
3. **Performance benchmarks**: Track asset fetch performance over time
4. **Provider-specific tests**: Separate test suites for each asset provider
5. **Visual diff testing**: Compare synthetic vs real asset quality

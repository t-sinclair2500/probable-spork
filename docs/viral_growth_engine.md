# Viral Growth Engine - Shorts & SEO Packaging

The Viral Growth Engine extends the content pipeline with automated shorts generation and SEO packaging capabilities, designed for maximum social media impact.

## Overview

This module provides two key capabilities:

1. **Shorts Generation**: Automatically creates 9:16 vertical clips from master videos with captions and branding
2. **SEO Packaging**: Generates optimized descriptions, tags, chapters, and end screens for YouTube

## Architecture

### Shorts Generation (`bin/viral/shorts.py`)

- **Segment Selection**: Intelligently picks the most "hookable" moments from the master video
- **Crop & Scale**: Converts 16:9 content to 9:16 with configurable anchor points
- **Caption Burning**: Converts SRT subtitles to styled ASS captions
- **Brand Overlays**: Adds logo and subscribe button with configurable positioning
- **Audio Normalization**: Targets -14 LUFS for consistent loudness
- **Metadata Stubs**: Generates social-ready filenames and metadata

### SEO Packaging (`bin/packaging/seo_packager.py`)

- **Description Generation**: Creates SEO-rich descriptions with keyword coverage
- **Tag Optimization**: Generates 15-20 tags including brand and topic variants
- **Chapter Creation**: Aligns chapters to scene boundaries with smart merging
- **Pinned Comments**: Creates CTAs with UTM tracking and disclosures

### End Screens (`bin/packaging/end_screens.py`)

- **End Screen Images**: Renders 1280×720 end screens with brand elements
- **CTA Overlays**: Creates alpha-channel MOV files for video overlays
- **Design System**: Uses brand palette and typography consistently

## Configuration

### Shorts Settings (`conf/shorts.yaml`)

```yaml
seed: 1337
counts:
  max_clips: 3
  min_clip_s: 18
  max_clip_s: 55
selection:
  prefer_selected_hooks: true
  min_scene_confidence: 0.0
  leadin_s: 0.8
  leadout_s: 0.6
crop:
  target_w: 1080
  target_h: 1920
  anchor: "center"  # center | right_rule_of_thirds | left_rule_of_thirds
captions:
  font: "assets/brand/fonts/Inter-Bold.ttf"
  font_size_pct: 5.0
  fill_rgba: [255,255,255,255]
  stroke_rgba: [0,0,0,220]
  bottom_margin_pct: 10.0
overlays:
  logo: "assets/brand/overlays/logo_white.png"
  subscribe: "assets/brand/overlays/subscribe.png"
  logo_pos: ["right","top"]
  subscribe_pos: ["right","bottom"]
audio:
  lufs_target: -14.0
  truepeak_max_db: -1.5
encoding:
  crf: 20
  pix_fmt: "yuv420p"
  preset: "medium"
filename:
  pattern: "{slug}__short_{n}__{keywords}__9x16.mp4"
  max_keywords: 4
```

### SEO Settings (`conf/seo.yaml`)

```yaml
templates:
  description: |
    {hook_line}

    {summary}

    What's inside:
    {bullets}

    Sources & credits:
    {citations}

    —
    If you found this useful, {cta}. {disclosure}

    Links:
    {links}

  pinned_comment: |
    Thanks for watching! {cta}
    Start here: {primary_link}
    Next up: {next_video_title} — {next_video_link}
    {disclosure}

tags:
  brand: ["ProbableSpork"]
  extra: ["tutorial","guide","how to","2025"]
  max_tags: 20

chapters:
  min_scene_s: 8
  merge_below_s: 6
  max_first_chapter_start_s: 5

cta:
  text: "subscribe for weekly breakdowns"
  next_video_title: "The No-Fluff Guide to {topic}"
  next_video_link: "https://example.com/next?utm_source=youtube&utm_medium=description&utm_campaign={slug}"

end_screen:
  width: 1280
  height: 720
  font: "assets/brand/fonts/Inter-Bold.ttf"
  palette: "assets/brand/style.yaml"
  subscribe_asset: "assets/brand/cta/subscribe_btn.png"
  next_frame_asset: "assets/brand/cta/next_video_frame.png"
  safe_area_pct: 0.9
  overlay_seconds: 10
```

## Usage

### Individual Steps

```bash
# Generate shorts from master video
python3 bin/viral/shorts.py --slug demo-viral

# Generate SEO packaging
python3 bin/packaging/seo_packager.py --slug demo-viral

# Create end screens and CTAs
python3 bin/packaging/end_screens.py --slug demo-viral
```

### Full Pipeline Integration

The viral growth steps are integrated into the main pipeline:

```bash
# Run full pipeline including viral growth
python3 bin/run_pipeline.py --slug demo-viral
```

Pipeline order:
1. `viral_lab` - Generate hooks/titles/thumbnails
2. `shorts_lab` - Create 9:16 clips (optional)
3. `seo_packaging` - Generate SEO content (required)
4. `end_screens` - Create CTA overlays (optional)

### Demo

Run the comprehensive demo to see all features:

```bash
python3 bin/viral/demo_viral_growth.py
```

## Output Structure

```
videos/
├── <slug>/
│   ├── shorts/
│   │   ├── <slug>__short_1__<keywords>__9x16.mp4
│   │   ├── <slug>__short_1__<keywords>__9x16.meta.json
│   │   ├── <slug>__short_2__<keywords>__9x16.mp4
│   │   └── <slug>__short_2__<keywords>__9x16.meta.json
│   └── <slug>_cc.mp4 (master video)
├── <slug>.metadata.json (updated with SEO data)

assets/
└── generated/
    └── <slug>/
        ├── end_screen_16x9.png
        └── cta_16x9.mov
```

## Key Features

### Deterministic Selection
- Fixed seed ensures consistent results across runs
- Prefers viral-selected hooks when available
- Falls back to early high-curiosity scenes

### Social Optimization
- Filenames include sanitized keywords for discoverability
- Metadata stubs ready for social platforms
- Optimized aspect ratios for mobile viewing

### Brand Consistency
- Uses design system palette and typography
- Configurable overlay positioning
- Consistent audio normalization

### SEO Excellence
- Keyword coverage analysis and enforcement
- Domain extraction from references
- UTM parameter integration
- Chapter alignment to content structure

## Dependencies

- **FFmpeg**: For video processing and encoding
- **PIL/Pillow**: For image generation (end screens)
- **PyYAML**: For configuration parsing
- **Brand Assets**: Fonts, logos, and overlay images

## Testing

```bash
# Run unit tests
python3 -m pytest tests/test_shorts_selection_and_render.py
python3 -m pytest tests/test_seo_packaging.py

# Integration test
python3 bin/viral/demo_viral_growth.py
```

## Success Criteria

- ✅ 1-3 shorts produced with correct 9:16 aspect ratio
- ✅ Captions burned in with proper styling and positioning
- ✅ Brand overlays applied with configurable positioning
- ✅ Audio normalized to -14 LUFS target
- ✅ SEO description includes keywords, bullets, citations
- ✅ Tags ≤ 20, deduped, include brand and topic variants
- ✅ Chapters align to scene starts, first chapter at 00:00-00:05
- ✅ End screen assets generated and ready for compositing
- ✅ All outputs deterministic and offline-capable
- ✅ Pipeline integration with proper step ordering
- ✅ Comprehensive test coverage

## Future Enhancements

- **A/B Testing**: Multiple caption styles and overlay positions
- **Platform Optimization**: TikTok, Instagram, YouTube Shorts specific formats
- **Analytics Integration**: Track performance of different hooks and cuts
- **AI Enhancement**: Use LLM for better segment selection and description generation
- **Batch Processing**: Process multiple videos simultaneously

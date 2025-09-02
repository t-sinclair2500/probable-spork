# Research Fixtures

This directory contains offline research data for use in `reuse` mode when live providers are disabled or return no results.

## File Format

Each fixture file should be named `<slug>.json` or `<topic>.json` and contain an array of source objects:

```json
[
  {
    "url": "https://example.com/article",
    "title": "Article Title",
    "text": "Full article content...",
    "ts": "2024-01-15T10:30:00Z",
    "domain": "example.com"
  }
]
```

## Fields

- `url`: Source URL (required)
- `title`: Article title (optional)
- `text`: Full article content (required)
- `ts`: Timestamp in ISO format (optional)
- `domain`: Domain name (optional, auto-extracted from URL if missing)

## Usage

When `mode: "reuse"` is set in `conf/research.yaml`, the research collector will:

1. Look for `data/fixtures/<slug>.json` first
2. If found and non-empty, use the fixture data
3. If not found or empty, fall back to live providers (if enabled)

## Example Fixture

```json
[
  {
    "url": "https://en.wikipedia.org/wiki/Design_thinking",
    "title": "Design thinking - Wikipedia",
    "text": "Design thinking refers to the set of cognitive, strategic and practical procedures used by designers in the process of designing, and to the body of knowledge that has been developed about how people reason when engaging with design problems...",
    "ts": "2024-01-15T10:30:00Z",
    "domain": "en.wikipedia.org"
  },
  {
    "url": "https://www.ideou.com/blogs/inspiration/what-is-design-thinking",
    "title": "What is Design Thinking?",
    "text": "Design thinking is a human-centered approach to innovation that draws from the designer's toolkit to integrate the needs of people, the possibilities of technology, and the requirements for business success...",
    "ts": "2024-01-15T11:00:00Z",
    "domain": "ideou.com"
  }
]
```

## Naming Convention

- Use the script slug or topic name as the filename
- Examples: `design-thinking.json`, `ai-ethics.json`, `sustainable-design.json`
- Keep filenames lowercase with hyphens for spaces

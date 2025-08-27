#!/usr/bin/env python3
import json
import os
import re
import time
from collections import Counter

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, guard_system, load_config, log_state, single_lock, parse_llm_json  # noqa: E402
from bin.fact_check import fact_check_content, should_gate_content  # noqa: E402
from urllib.parse import urlencode  # noqa: E402


def load_blog_cfg():
    p = os.path.join(BASE, "conf", "blog.yaml")
    if not os.path.exists(p):
        p = os.path.join(BASE, "conf", "blog.example.yaml")
    import yaml

    return yaml.safe_load(open(p, "r", encoding="utf-8"))


def choose_script_for_topic(topic):
    sdir = os.path.join(BASE, "scripts")
    cand = [f for f in os.listdir(sdir) if f.endswith(".txt")]
    cand.sort(reverse=True)
    for fn in cand:
        if re.sub(r"[^a-z0-9]+", "-", topic.lower()) in fn.lower():
            return os.path.join(sdir, fn)
    return os.path.join(sdir, cand[0]) if cand else None


log = get_logger("blog_generate_post")


def load_monetization_config() -> dict:
    """Load monetization configuration"""
    config_path = os.path.join(BASE, "conf", "monetization.yaml")
    if not os.path.exists(config_path):
        log.warning("No monetization.yaml found, using empty config")
        return {}
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        log.warning(f"Failed to load monetization config: {e}")
        return {}


def inject_monetization_elements(content: str, monetization_config: dict) -> str:
    """Inject affiliate disclosure and newsletter signup into blog content"""
    if not monetization_config:
        return content
    
    blog_config = monetization_config.get("blog", {})
    content_config = monetization_config.get("content", {})
    
    # Check minimum word count requirement
    min_words = content_config.get("min_words_for_monetization", 500)
    word_count = len(content.split())
    if word_count < min_words:
        log.info(f"Content too short for monetization ({word_count} < {min_words} words)")
        return content
    
    # Store monetization elements to inject
    elements_to_add = []
    
    # Add affiliate disclosure if enabled
    if content_config.get("include_affiliate_disclosure", True):
        disclosure = blog_config.get("affiliate_disclosure", "")
        if disclosure:
            elements_to_add.append(disclosure)
    
    # Add newsletter signup if enabled
    if content_config.get("include_newsletter_signup", True):
        newsletter_html = blog_config.get("newsletter_html_slot", "")
        if newsletter_html:
            elements_to_add.append(newsletter_html)
    
    if not elements_to_add:
        return content
    
    # Find a good insertion point (after first section but before conclusion)
    lines = content.split('\n')
    insertion_point = len(lines) // 2  # Default to middle
    
    # Look for a better insertion point (after first H2 section)
    h2_count = 0
    for i, line in enumerate(lines):
        if line.startswith('## '):
            h2_count += 1
            if h2_count == 2:  # Insert after first content section
                insertion_point = i
                break
    
    # Insert monetization elements
    for element in reversed(elements_to_add):  # Reverse to maintain order
        lines.insert(insertion_point, "")
        lines.insert(insertion_point + 1, element)
        lines.insert(insertion_point + 2, "")
    
    return '\n'.join(lines)


def add_utm_tracking_to_links(content: str, monetization_config: dict) -> str:
    """Add UTM tracking to external links in blog content"""
    blog_config = monetization_config.get("blog", {})
    utm_params = {
        "utm_source": blog_config.get("utm_source", "blog"),
        "utm_medium": blog_config.get("utm_medium", "article"),
        "utm_campaign": blog_config.get("utm_campaign", "ai_content_pipeline")
    }
    
    # This is a placeholder - in a real implementation, you'd parse markdown links
    # and add UTM parameters to external links
    # For now, just return content as-is
    return content


def count_words(text):
    """Count words in text, excluding common markdown elements."""
    # Remove code blocks, links, and image references
    clean_text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    clean_text = re.sub(r'`[^`]+`', '', clean_text)
    clean_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_text)
    clean_text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', clean_text)
    clean_text = re.sub(r'#+\s+', '', clean_text)
    clean_text = re.sub(r'[*_-]{1,3}', '', clean_text)
    
    words = re.findall(r'\b\w+\b', clean_text.lower())
    return len(words)


def validate_structure(markdown_content):
    """Validate blog post structure and return issues."""
    issues = []
    lines = markdown_content.split('\n')
    
    # Check for H1 title
    h1_found = any(line.strip().startswith('# ') for line in lines)
    if not h1_found:
        issues.append("Missing H1 title")
    
    # Check for H2/H3 headings
    h2_h3_count = sum(1 for line in lines if re.match(r'^#{2,3}\s+', line.strip()))
    if h2_h3_count < 2:
        issues.append("Insufficient H2/H3 headings (need at least 2)")
    
    # Check for bullet points
    bullet_count = sum(1 for line in lines if re.match(r'^\s*[-*+]\s+', line.strip()))
    if bullet_count == 0:
        issues.append("No bullet points found")
    
    # Check heading hierarchy
    heading_levels = []
    for line in lines:
        match = re.match(r'^(#{1,6})\s+', line.strip())
        if match:
            heading_levels.append(len(match.group(1)))
    
    for i in range(1, len(heading_levels)):
        if heading_levels[i] > heading_levels[i-1] + 1:
            issues.append("Improper heading hierarchy (skipped levels)")
            break
    
    return issues


def validate_content_quality(markdown_content, target_keywords=None):
    """Validate content quality and return quality metrics."""
    issues = []
    
    # Check for FAQ section if required
    has_faq = bool(re.search(r'##?\s*(?:FAQ|Frequently\s+Asked\s+Questions)', markdown_content, re.IGNORECASE))
    
    # Check for CTA (Call to Action)
    cta_patterns = [
        r'subscribe', r'newsletter', r'follow', r'contact', r'share',
        r'comment', r'feedback', r'join', r'learn more'
    ]
    has_cta = any(re.search(pattern, markdown_content, re.IGNORECASE) for pattern in cta_patterns)
    
    # Sentence length analysis
    sentences = re.split(r'[.!?]+', markdown_content)
    sentences = [s.strip() for s in sentences if s.strip()]
    word_counts = [len(s.split()) for s in sentences]
    
    if word_counts:
        avg_sentence_length = sum(word_counts) / len(word_counts)
        long_sentences = sum(1 for wc in word_counts if wc > 25)
        
        if avg_sentence_length > 20:
            issues.append("Average sentence length too long (improve readability)")
        
        if long_sentences > len(sentences) * 0.3:
            issues.append("Too many long sentences (>25 words)")
    
    # Paragraph analysis
    paragraphs = [p.strip() for p in markdown_content.split('\n\n') if p.strip() and not p.strip().startswith('#')]
    if paragraphs:
        avg_paragraph_words = sum(count_words(p) for p in paragraphs) / len(paragraphs)
        if avg_paragraph_words > 100:
            issues.append("Paragraphs too long (aim for 50-100 words)")
    
    return {
        'has_faq': has_faq,
        'has_cta': has_cta,
        'avg_sentence_length': avg_sentence_length if word_counts else 0,
        'issues': issues
    }


def validate_blog_post(markdown_content, min_words, max_words, include_faq=True, 
                       fact_check_config=None, global_config=None):
    """Comprehensive blog post validation with optional fact-checking."""
    validation_result = {
        'valid': True,
        'issues': [],
        'warnings': [],
        'metrics': {},
        'fact_check': None
    }
    
    # Word count validation
    word_count = count_words(markdown_content)
    validation_result['metrics']['word_count'] = word_count
    
    if word_count < min_words:
        validation_result['issues'].append(f"Word count too low: {word_count} < {min_words}")
        validation_result['valid'] = False
    elif word_count > max_words:
        validation_result['issues'].append(f"Word count too high: {word_count} > {max_words}")
        validation_result['valid'] = False
    
    # Structure validation
    structure_issues = validate_structure(markdown_content)
    validation_result['issues'].extend(structure_issues)
    if structure_issues:
        validation_result['valid'] = False
    
    # Content quality validation
    quality_result = validate_content_quality(markdown_content)
    validation_result['metrics'].update(quality_result)
    
    if include_faq and not quality_result['has_faq']:
        validation_result['warnings'].append("FAQ section recommended but not found")
    
    if not quality_result['has_cta']:
        validation_result['warnings'].append("Call-to-action not detected")
    
    validation_result['issues'].extend(quality_result['issues'])
    
    # Fact-checking validation (if enabled)
    if fact_check_config and fact_check_config.get('enabled', False) and global_config:
        try:
            log.info("Running fact-checking validation...")
            fact_check_result = fact_check_content(markdown_content, global_config)
            validation_result['fact_check'] = fact_check_result
            
            # Process fact-check issues
            fact_issues = fact_check_result.get('issues', [])
            summary = fact_check_result.get('summary', {})
            
            # Add fact-check issues to validation
            for issue in fact_issues:
                severity = issue.get('severity', 'info')
                claim = issue.get('claim', '')
                
                if severity == 'error':
                    validation_result['issues'].append(f"Fact-check error: {claim[:100]}...")
                elif severity == 'warning':
                    validation_result['warnings'].append(f"Fact-check warning: {claim[:100]}...")
            
            # Check if content should be gated
            gate_mode = fact_check_config.get('gate_mode', 'warn')
            severity_threshold = fact_check_config.get('severity_threshold', 'warning')
            
            should_block = should_gate_content(fact_check_result, gate_mode, severity_threshold)
            
            if should_block:
                validation_result['valid'] = False
                validation_result['issues'].append(
                    f"Content blocked by fact-checker: {summary.get('highest_severity', 'unknown')} "
                    f"severity issues found (threshold: {severity_threshold}, mode: {gate_mode})"
                )
                log.warning(f"Content blocked by fact-checker: {len(fact_issues)} issues found")
            elif fact_issues:
                log.info(f"Fact-check completed: {len(fact_issues)} issues found (mode: {gate_mode})")
                
        except Exception as e:
            log.error(f"Fact-checking failed: {e}")
            validation_result['warnings'].append(f"Fact-checking failed: {str(e)}")
    
    return validation_result


def main(brief=None):
    """Main function for blog post generation with optional brief context"""
    cfg = load_config()
    guard_system(cfg)
    bcfg = load_blog_cfg()
    monetization_config = load_monetization_config()
    work = os.path.join(BASE, "data", "cache", "blog_topic.json")
    if not os.path.exists(work):
        log_state("blog_generate_post", "SKIP", "no topic")
        return
    topic = json.load(open(work, "r", encoding="utf-8")).get("topic", "Productivity tips that save time")
    sfile = choose_script_for_topic(topic)
    if not sfile:
        log_state("blog_generate_post", "SKIP", "no scripts")
        return
    text = open(sfile, "r", encoding="utf-8").read()
    
    # Use brief settings if available, otherwise fall back to config defaults
    if brief:
        tone = brief.get('tone', getattr(getattr(cfg, "blog", object()), "tone", "informative"))
        mn = brief.get('blog', {}).get('words_min', getattr(getattr(cfg, "blog", object()), "min_words", 800))
        mx = brief.get('blog', {}).get('words_max', getattr(getattr(cfg, "blog", object()), "max_words", 1500))
        include_faq = brief.get('blog', {}).get('include_faq', bool(getattr(getattr(cfg, "blog", object()), "include_faq", True)))
        cta = brief.get('blog', {}).get('cta_text', getattr(getattr(cfg, "blog", object()), "inject_cta", "Thanks for reading."))
        
        # Log brief context for transparency
        log.info(f"Using brief settings: tone={tone}, words={mn}-{mx}, include_faq={include_faq}")
    else:
        tone = getattr(getattr(cfg, "blog", object()), "tone", "informative")
        mn = int(getattr(getattr(cfg, "blog", object()), "min_words", 800))
        mx = int(getattr(getattr(cfg, "blog", object()), "max_words", 1500))
        include_faq = bool(getattr(getattr(cfg, "blog", object()), "include_faq", True))
        cta = getattr(getattr(cfg, "blog", object()), "inject_cta", "Thanks for reading.")

    import requests
    
    # Load prompt templates
    def load_prompt_template(filename: str) -> str:
        """Load a prompt template from the prompts directory."""
        prompt_path = os.path.join(BASE, "prompts", filename)
        if not os.path.exists(prompt_path):
            raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    
    # Stage 1: Draft writer
    try:
        writer_template = load_prompt_template("blog_writer.txt")
        writer_prompt = writer_template.format(
            brief_context="",
            tone=tone,
            min_words=mn,
            max_words=mx,
            include_faq=str(include_faq).lower(),
            inject_cta=cta,
            script=text
        )
    except Exception as e:
        log.warning(f"Failed to load blog writer prompt template: {e}, using fallback")
        writer_prompt = (
            "You are a content strategist. Rewrite the given video script into a polished blog post in Markdown.\n\n"
            "Requirements:\n"
            "- Use the specified tone.\n"
            "- Target total words between MIN_WORDS and MAX_WORDS.\n"
            "- Structure: H1 title, intro, H2/H3 sections, bullets, optional FAQ, clear CTA.\n"
            "- Add natural subheadings and short paragraphs (2–4 sentences).\n"
            "- Do NOT include any front matter. Return PLAIN MARKDOWN only.\n\n"
            f"TONE: {tone}\nMIN_WORDS: {mn}\nMAX_WORDS: {mx}\nINCLUDE_FAQ: {str(include_faq).lower()}\nINJECT_CTA: {cta}\n\n"
            "SCRIPT:\n" + text
        )
    
    # Enhance prompt with brief context if available
    if brief:
        from bin.core import create_brief_context
        brief_context = create_brief_context(brief)
        writer_prompt = brief_context + writer_prompt
    
    writer_payload = {"model": cfg.llm.model, "prompt": writer_prompt, "stream": False}
    md1 = None
    try:
        r = requests.post(cfg.llm.endpoint, json=writer_payload, timeout=600)
        if r.ok:
            md1 = r.json().get("response", "").strip()
    except Exception:
        md1 = None

    # Stage 2: Copyediting pass (grammar, flow, tone consistency)
    md2 = md1
    if md1:
        try:
            ce_template = load_prompt_template("blog_copyedit.txt")
            ce_prompt = ce_template.format(article=md1)
        except Exception as e:
            log.warning(f"Failed to load blog copyedit prompt template: {e}, using fallback")
            ce_prompt = (
                "You are a copyediting agent. Improve grammar, clarity, and flow. Keep the original structure and headings.\n"
                "Return PLAIN MARKDOWN only.\n\n"
                "ARTICLE:\n" + md1
            )
        try:
            r2 = requests.post(cfg.llm.endpoint, json={"model": cfg.llm.model, "prompt": ce_prompt, "stream": False}, timeout=600)
            if r2.ok:
                md2 = r2.json().get("response", "").strip()
        except Exception:
            md2 = md1

    # Stage 3: SEO polish (title length, meta description suggestion inline as comments)
    md3 = md2
    if md2:
        try:
            seo_template = load_prompt_template("blog_seo.txt")
            seo_prompt = seo_template.format(article=md2)
        except Exception as e:
            log.warning(f"Failed to load blog SEO prompt template: {e}, using fallback")
            seo_prompt = (
                "You are an SEO copywriter. Tighten the title (≤65 chars) and ensure concise subheads.\n"
                "Insert a one-line meta description suggestion as an HTML comment at the top.\n"
                "Return PLAIN MARKDOWN only.\n\n"
                "ARTICLE:\n" + md2
            )
        try:
            r3 = requests.post(cfg.llm.endpoint, json={"model": cfg.llm.model, "prompt": seo_prompt, "stream": False}, timeout=600)
            if r3.ok:
                md3 = r3.json().get("response", "").strip()
        except Exception:
            md3 = md2

    md = md3 or ("# " + topic + "\n\n" + text[:800])
    
    # Filter out any content that contains excluded keywords
    if brief and brief.get('keywords_exclude'):
        from bin.core import filter_content_by_brief
        filtered_md, rejection_reasons = filter_content_by_brief(md, brief)
        if rejection_reasons:
            log_state("blog_generate_post", "REJECTED", f"Blog post contains excluded keywords: {rejection_reasons}")
            # Generate a replacement post without excluded terms
            replacement_prompt = writer_prompt + f"\n\nIMPORTANT: Do not use these terms: {', '.join(brief['keywords_exclude'])}"
            try:
                r_replacement = requests.post(cfg.llm.endpoint, json={"model": cfg.llm.model, "prompt": replacement_prompt, "stream": False}, timeout=600)
                if r_replacement.ok:
                    md = r_replacement.json().get("response", "").strip()
                    log_state("blog_generate_post", "REPLACED", "Generated replacement post without excluded keywords")
                else:
                    log_state("blog_generate_post", "FALLBACK", "Using fallback post after keyword rejection")
            except Exception:
                log_state("blog_generate_post", "FALLBACK", "Using fallback post after keyword rejection")
        else:
            md = filtered_md
    
    # Inject monetization elements (affiliate disclosure, newsletter signup)
    md = inject_monetization_elements(md, monetization_config)
    md = add_utm_tracking_to_links(md, monetization_config)

    # Get fact-checking configuration
    fact_check_config = bcfg.get('fact_check', {})
    
    # Validate the generated content
    validation_result = validate_blog_post(md, mn, mx, include_faq, fact_check_config, cfg)
    
    # Log validation results
    if validation_result['valid']:
        log.info(f"Content validation passed: {validation_result['metrics']['word_count']} words")
        log_state("blog_generate_post", "VALIDATE_OK", f"words={validation_result['metrics']['word_count']}")
    else:
        log.warning(f"Content validation issues: {'; '.join(validation_result['issues'])}")
        log_state("blog_generate_post", "VALIDATE_WARN", f"issues={len(validation_result['issues'])}")
    
    if validation_result['warnings']:
        log.info(f"Content warnings: {'; '.join(validation_result['warnings'])}")
    
    # Log detailed metrics
    metrics = validation_result['metrics']
    fact_check_result = validation_result.get('fact_check')
    
    metric_log = (f"Content metrics: words={metrics.get('word_count', 0)}, "
                  f"faq={metrics.get('has_faq', False)}, cta={metrics.get('has_cta', False)}, "
                  f"avg_sentence_len={metrics.get('avg_sentence_length', 0):.1f}")
    
    if fact_check_result:
        fact_metrics = fact_check_result.get('metrics', {})
        severity_counts = fact_metrics.get('severity_counts', {})
        metric_log += (f", fact_check_issues={fact_metrics.get('total_issues', 0)} "
                      f"(errors={severity_counts.get('error', 0)}, "
                      f"warnings={severity_counts.get('warning', 0)}, "
                      f"info={severity_counts.get('info', 0)})")
    
    log.info(metric_log)

    # Inline image reuse from assets folder when available
    try:
        base_key = os.path.basename(sfile).replace(".txt", "")
        assets_dir = os.path.join(BASE, "assets", base_key)
        if os.path.isdir(assets_dir):
            imgs = [f for f in os.listdir(assets_dir) if f.lower().endswith((".jpg",".jpeg",".png",".webp"))]
            imgs.sort()
            if imgs:
                inject = []
                for f in imgs[: min(4, len(imgs))]:
                    alt = os.path.splitext(os.path.basename(f))[0].replace("-"," ")
                    inject.append(f"![{alt}](assets/{base_key}/{f})")
                # Append an Images section if not already present
                if "\n## Images\n" not in md:
                    md = md + "\n\n## Images\n\n" + "\n".join(inject) + "\n"
                else:
                    md = md + "\n" + "\n".join(inject) + "\n"
    except Exception:
        pass
    out_md = os.path.join(BASE, "data", "cache", "post.md")
    meta = {
        "title": topic.title(),
        "slug": re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-"),
        "description": f"Insights on {topic} generated by our automation pipeline.",
        "tags": ["automation", "raspberry pi", "ai"],
        "category": "AI Tools",
        "validation": validation_result,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    json.dump(
        meta,
        open(os.path.join(BASE, "data", "cache", "post.meta.json"), "w", encoding="utf-8"),
        indent=2,
    )
    open(out_md, "w", encoding="utf-8").write(md)
    log_state("blog_generate_post", "OK", os.path.basename(out_md))
    log.info(f"Wrote {out_md} and post.meta.json (placeholder).")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Blog post generation")
    parser.add_argument("--brief-data", help="JSON string containing brief data")
    
    args = parser.parse_args()
    
    # Parse brief data if provided
    brief = None
    if args.brief_data:
        try:
            brief = json.loads(args.brief_data)
            log.info(f"Loaded brief: {brief.get('title', 'Untitled')}")
        except (json.JSONDecodeError, TypeError) as e:
            log.warning(f"Failed to parse brief data: {e}")
    
    with single_lock():
        main(brief)

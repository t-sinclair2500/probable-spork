#!/usr/bin/env python3
import json
import os
import re
import time

# Ensure repo root on path
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bin.core import BASE, get_logger, guard_system, load_config, log_state, single_lock, parse_llm_json  # noqa: E402


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


def main():
    cfg = load_config()
    guard_system(cfg)
    bcfg = load_blog_cfg()
    work = os.path.join(BASE, "data", "cache", "blog_topic.json")
    if not os.path.exists(work):
        log_state("blog_generate_post", "SKIP", "no topic")
        return
    topic = json.load(open(work, "r", encoding="utf-8")).get("topic", "AI tools that save time")
    sfile = choose_script_for_topic(topic)
    if not sfile:
        log_state("blog_generate_post", "SKIP", "no scripts")
        return
    text = open(sfile, "r", encoding="utf-8").read()
    # Iterative LLM rewrite pipeline with separate roles: writer -> copyeditor -> SEO polish
    tone = getattr(getattr(cfg, "blog", object()), "tone", "informative")
    mn = int(getattr(getattr(cfg, "blog", object()), "min_words", 800))
    mx = int(getattr(getattr(cfg, "blog", object()), "max_words", 1500))
    include_faq = bool(getattr(getattr(cfg, "blog", object()), "include_faq", True))
    cta = getattr(getattr(cfg, "blog", object()), "inject_cta", "Thanks for reading.")

    import requests
    # Stage 1: Draft writer
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
    with single_lock():
        main()

#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import time

import requests
import sys
import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from bin.core import BASE, load_config, log_state, single_lock, get_logger

log = get_logger("llm_cluster")

try:
    from bin.core import parse_llm_json  # when repo root is on sys.path
except Exception:
    # Fallback: local parser identical to bin.core.parse_llm_json
    def parse_llm_json(text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.DOTALL)
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            m = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if m:
                return json.loads(m.group(0))
            raise ValueError("No JSON object found in LLM output.")


def call_ollama(prompt, cfg, models_config=None):
    """Call Ollama with specified model configuration."""
    try:
        # Use new model_runner system
        from bin.model_runner import model_session
        
        # Get model name from config
        if models_config and 'cluster' in models_config.get('models', {}):
            model_name = models_config['models']['cluster']['name']
        else:
            # Fallback to global config
            model_name = cfg["llm"]["model"]
        
        # Use model session for deterministic load/unload
        with model_session(model_name) as session:
            # Load clustering prompt template
            prompt_path = os.path.join(BASE, "prompts", "cluster_topics.txt")
            with open(prompt_path, "r", encoding="utf-8") as f:
                template = f.read()
            
            # Format prompt with brief context if available
            if brief:
                from bin.core import create_brief_context
                brief_context = create_brief_context(brief)
                system_prompt = template.format(brief_context=brief_context)
            else:
                system_prompt = template.format(brief_context="")
            
            return session.chat(system=system_prompt, user=prompt)
            
    except Exception as e:
        log.warning(f"Model runner failed, falling back to legacy: {e}")
        
        # Fallback to legacy system
        url = cfg["llm"]["endpoint"]
        model = cfg["llm"]["model"]
        payload = {"model": model, "prompt": prompt, "stream": False}
        r = requests.post(url, json=payload, timeout=600)
        r.raise_for_status()
        # Ollama returns {"response": "..."} with the text
        return r.json().get("response", "")


def main(brief=None, models_config=None):
    cfg = load_config()
    os.makedirs(os.path.join(BASE, "data"), exist_ok=True)
    
    # Load models configuration if not provided
    if models_config is None:
        try:
            import yaml
            models_path = os.path.join(BASE, "conf", "models.yaml")
            if os.path.exists(models_path):
                with open(models_path, 'r', encoding='utf-8') as f:
                    models_config = yaml.safe_load(f)
                log.info("Loaded models configuration")
        except Exception as e:
            log.warning(f"Failed to load models configuration: {e}")
            models_config = {}
    
    # Log brief context if available
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_cluster", "START", f"brief={brief_title}")
        log.info(f"Running with brief: {brief_title}")
    else:
        log_state("llm_cluster", "START", "brief=none")
        log.info("Running without brief - using default behavior")
    
    # Collect recent titles/tags from sqlite
    db_path = os.path.join(BASE, "data", "trending_topics.db")
    rows = []
    if os.path.exists(db_path):
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        for ts, source, title, tags in cur.execute(
            "SELECT ts, source, title, tags FROM trends ORDER BY rowid DESC LIMIT 50"
        ):
            rows.append({"title": title, "tags": tags, "source": source})
        con.close()
    
    # Build prompt
    with open(os.path.join(BASE, "prompts", "cluster_topics.txt"), "r", encoding="utf-8") as f:
        template = f.read()
    
    # Enhance prompt with brief context if available
    if brief:
        from bin.core import create_brief_context
        brief_context = create_brief_context(brief)
        template = brief_context + template
    
    prompt = template + "\nINPUT:\n" + json.dumps(rows)
    
    # Call local LLM
    topics = []
    try:
        out = call_ollama(prompt, cfg, models_config)
        parsed = parse_llm_json(out)
        topics = parsed.get("topics", [])
    except Exception:
        # Fallback topics - use brief keywords if available
        if brief and brief.get('keywords_include'):
            primary_keyword = brief['keywords_include'][0] if brief['keywords_include'] else "topic"
            topics = [
                {
                    "topic": primary_keyword,
                    "score": 0.8,
                    "hook": f"5 {primary_keyword} to save hours",
                    "keywords": brief['keywords_include'][:3],
                }
            ]
        else:
            topics = [
                {
                    "topic": "productivity tips",
                    "score": 0.6,
                    "hook": "5 productivity tips to save hours",
                    "keywords": ["productivity", "tips"],
                },
                {
                    "topic": "space trivia",
                    "score": 0.5,
                    "hook": "10 wild space facts",
                    "keywords": ["space", "trivia"],
                },
            ]
    
    # Filter out topics that contain excluded keywords
    if brief and brief.get('keywords_exclude'):
        exclude_terms = [term.lower() for term in brief['keywords_exclude']]
        filtered_topics = []
        
        for topic in topics:
            topic_text = f"{topic.get('topic', '')} {' '.join(topic.get('keywords', []))}".lower()
            if not any(exclude_term in topic_text for exclude_term in exclude_terms):
                filtered_topics.append(topic)
            else:
                log.info(f"Filtered out topic '{topic.get('topic')}' due to excluded keywords")
        
        topics = filtered_topics
    
    # Enrich with created_at and clamp to top 10 by score
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for t in topics:
        t.setdefault("score", 0.5)
        t.setdefault("keywords", [])
        t["created_at"] = now
    topics.sort(key=lambda x: float(x.get("score", 0.0)), reverse=True)
    topics = topics[:10]
    
    # Save queue
    queue_path = os.path.join(BASE, "data", "topics_queue.json")
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(topics, f, indent=2)
    
    # Include brief context in final log
    if brief:
        brief_title = brief.get('title', 'Untitled')
        log_state("llm_cluster", "OK", f"topics={len(topics)};brief={brief_title}")
    else:
        log_state("llm_cluster", "OK", f"topics={len(topics)}")
    
    print(f"Wrote {queue_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="LLM topic clustering")
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

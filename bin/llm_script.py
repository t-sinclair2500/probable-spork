#!/usr/bin/env python3
import os, json, requests, time, re
from util import single_lock, log_state, load_global_config, BASE, ensure_dirs

def call_ollama(prompt, cfg):
    url = cfg["llm"]["endpoint"]
    model = cfg["llm"]["model"]
    payload = {"model": model, "prompt": prompt, "stream": False}
    r = requests.post(url, json=payload, timeout=1800)
    r.raise_for_status()
    return r.json().get("response","")

def main():
    cfg = load_global_config(); ensure_dirs(cfg)
    # Pick the newest outline
    outlines = [p for p in os.listdir(os.path.join(BASE,"scripts")) if p.endswith(".outline.json")]
    if not outlines:
        log_state("llm_script","SKIP","no outlines"); print("No outlines"); return
    outlines.sort(reverse=True)
    opath = os.path.join(BASE,"scripts", outlines[0])
    data = json.load(open(opath,"r",encoding="utf-8"))
    with open(os.path.join(BASE,"prompts","script_writer.txt"),"r",encoding="utf-8") as f:
        template = f.read()
    # Simple prompt: feed outline JSON and instructions
    tone = cfg.get("pipeline", {}).get("tone", "conversational")
    target_len_sec = int(cfg.get("pipeline", {}).get("video_length_seconds", 420))
    prompt = (
        "OUTLINE:\n" + json.dumps(data) + "\n\n" + template +
        f"\nTone: {tone}. Target length (sec): {target_len_sec}. Return plain text only."
    )
    try:
        text = call_ollama(prompt, cfg)
    except Exception:
        # Fallback: synthesize a simple script from outline beats
        lines = []
        title = (data.get("title_options") or ["Untitled"])[0]
        lines.append(f"Title: {title}")
        for sec in data.get("sections", []):
            label = sec.get("label", "Section")
            lines.append(f"\n{label}")
            for b in sec.get("beats", []):
                br = (sec.get("broll") or [""])[0] if isinstance(sec.get("broll"), list) else ""
                tag = f" [B-ROLL: {br}]" if br else ""
                lines.append(f"- {b}.{tag}")
        lines.append("\nCTA: Subscribe for more!")
        text = "\n".join(lines)
    # Save script text + minimal metadata
    base = opath.replace(".outline.json","")
    with open(base + ".txt","w",encoding="utf-8") as f: f.write(text)
    meta = {
        "title": data["title_options"][0] if data.get("title_options") else "Untitled",
        "description": "Auto-generated with local LLM.",
        "tags": data.get("tags", ["education"])
    }
    with open(base + ".metadata.json","w",encoding="utf-8") as f: json.dump(meta,f,indent=2)
    log_state("llm_script","OK",os.path.basename(base)+".txt")
    print("Wrote script and metadata.")

if __name__ == "__main__":
    with single_lock():
        main()

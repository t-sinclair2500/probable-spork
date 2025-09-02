from __future__ import annotations

import argparse
import sys

from pathlib import Path

# Ensure repo root on path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gradio as gr

from bin.ui.run_helpers import (
    discover_slugs,
    health_check,
    latest_artifacts,
    stream_process,
)
from bin.utils.config import _read_yaml


def _load_ui_cfg():
    p = ROOT / "conf" / "ui.yaml"
    return (
        _read_yaml(str(p))
        if p.exists()
        else {
            "server": {"port": 7860, "share": False},
            "defaults": {
                "mode": "reuse",
                "yt_only": False,
                "enable_viral": True,
                "enable_shorts": True,
                "enable_seo": True,
                "seed": 1337,
                "from_step": "",
            },
            "paths": {"briefs_dir": "conf/briefs"},
            "ui": {"max_log_lines": 2000},
        }
    )


CFG = _load_ui_cfg()


def save_brief(slug: str, brief_text: str) -> str:
    p = ROOT / "conf" / "ui.yaml"
    return (
        _read_yaml(str(p))
        if p.exists()
        else {
            "server": {"port": 7860, "share": False},
            "defaults": {
                "mode": "reuse",
                "yt_only": False,
                "enable_viral": True,
                "enable_shorts": True,
                "enable_seo": True,
                "seed": 1337,
                "from_step": "",
            },
            "paths": {"briefs_dir": "conf/briefs"},
            "ui": {"max_log_lines": 2000},
        }
    )


CFG = _load_ui_cfg()


def save_brief(slug: str, brief_text: str) -> str:
    if not slug:
        return "ERR: slug is required"
    out_dir = ROOT / CFG["paths"]["briefs_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slug}.yaml"
    path.write_text(brief_text or "", encoding="utf-8")
    return f"Saved brief → {path}"


def refresh_slugs() -> list[str]:
    return discover_slugs()


def run_full_pipeline(
    slug, mode, yt_only, enable_viral, enable_shorts, enable_seo, seed, from_step
):
    if not slug:
        yield "[ui] Please enter or select a slug."
        return
    # Compose command
    python_bin = "python"
    cmd = [python_bin, "bin/run_pipeline.py", "--slug", slug]
    # Mode + flags
    cmd += ["--mode", mode]
    if yt_only:
        cmd += ["--yt-only"]
    cmd += ["--seed", str(seed)]
    if from_step:
        cmd += ["--from-step", from_step]
    # Viral flags (only append if explicitly false to avoid surprising defaults)
    cmd += ["--enable-viral"] if enable_viral else ["--no-viral"]
    cmd += ["--enable-shorts"] if enable_shorts else ["--no-shorts"]
    cmd += ["--enable-seo"] if enable_seo else ["--no-seo"]

    yield f"[ui] running: {' '.join(cmd)}"
    last_n = int(CFG["ui"]["max_log_lines"])
    buf = []
    for line in stream_process(cmd):
        buf.append(line)
        if len(buf) > last_n:
            buf = buf[-last_n:]
        yield "\n".join(buf)
    yield "\n".join(buf)  # final snapshot


def ensure_models():
    # Best-effort: call a small helper script if present; else ping Ollama tags
    try:
        import subprocess

        out = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if out.returncode != 0:
            return f"[ui] Ollama not reachable (rc={out.returncode}). Heuristics-only fallback will be used."
        tags = [ln.split()[0] for ln in out.stdout.splitlines()[1:] if ln.strip()]
        need = ["llama3.2:3b"]  # minimal set for viral/scoring
        missing = [t for t in need if t not in tags]
        if missing:
            pull = subprocess.run(["ollama", "pull", *missing], text=True)
            return (
                "[ui] Models ensured (pulled)."
                if pull.returncode == 0
                else f"[ui] Pull failed: {missing}"
            )
        return "[ui] Models available."
    except Exception as e:
        return f"[ui] Could not verify models: {e}"


def refresh_artifacts(slug: str):
    arts = latest_artifacts(slug)
    qa_text = ""
    try:
        from bin.ui.components import format_qa_summary

        qa_text = format_qa_summary(arts.get("qa_report"))
    except Exception as e:
        qa_text = f"QA summary error: {e}"
    return (
        arts.get("thumbs", []),
        arts.get("shorts", []),
        arts.get("metadata", None),
        arts.get("qa_report", None),
        qa_text,
    )


def ui_main():
    # Initial data
    slugs = refresh_slugs()
    hc = health_check()
    defaults = CFG["defaults"]
    with gr.Blocks(
        title="Probable Spork — Operator Console", css=".small {font-size: 12px}"
    ) as demo:
        gr.Markdown("## 🎬 Probable Spork — Operator Console (Mac-first, local-only)")

        with gr.Row():
            with gr.Column(scale=1):
                slug_dd = gr.Dropdown(
                    choices=slugs,
                    label="Existing Slug(s)",
                    value=slugs[0] if slugs else None,
                )
                slug_tb = gr.Textbox(
                    label="Slug (new or existing)",
                    placeholder="e.g., demo-001",
                    value=slugs[0] if slugs else "",
                )

                with gr.Accordion("Brief (YAML) — optional", open=False):
                    brief_txt = gr.Code(
                        label="brief.yaml", language="yaml", value="", lines=12
                    )
                    save_brief_btn = gr.Button("💾 Save Brief")
                    brief_status = gr.Markdown("", elem_classes=["small"])
                    save_brief_btn.click(
                        save_brief, inputs=[slug_tb, brief_txt], outputs=brief_status
                    )

                with gr.Row():
                    mode_dd = gr.Radio(
                        choices=["reuse", "live"], label="Mode", value=defaults["mode"]
                    )
                    yt_only_cb = gr.Checkbox(
                        label="YouTube publish only (skip ingestion)",
                        value=defaults["yt_only"],
                    )
                with gr.Row():
                    enable_viral_cb = gr.Checkbox(
                        label="Enable Viral Lab", value=defaults["enable_viral"]
                    )
                    enable_shorts_cb = gr.Checkbox(
                        label="Enable Shorts", value=defaults["enable_shorts"]
                    )
                    enable_seo_cb = gr.Checkbox(
                        label="Enable SEO Packaging", value=defaults["enable_seo"]
                    )
                with gr.Row():
                    seed_tb = gr.Number(
                        label="Seed", value=defaults["seed"], precision=0
                    )
                    from_step_dd = gr.Dropdown(
                        choices=[
                            "",
                            "research",
                            "ground",
                            "script",
                            "storyboard",
                            "animatics",
                            "assemble",
                            "viral_lab",
                            "shorts_lab",
                            "seo_packaging",
                            "qa",
                        ],
                        label="From Step (optional)",
                        value=defaults["from_step"],
                    )

                run_btn = gr.Button("▶️ Run Full Pipeline", variant="primary")
                qa_only_btn = gr.Button("🧪 Run QA Only")
                models_btn = gr.Button("🧰 Ensure Models")
                slugs_btn = gr.Button("🔄 Refresh Slugs")

                # Health panel
                gr.Markdown(
                    f"**Health:** ffmpeg: `{hc['ffmpeg']}` · ffprobe: `{hc['ffprobe']}` · VideoToolbox: `{hc['videotoolbox']}`",
                    elem_classes=["small"],
                )

            with gr.Column(scale=2):
                log_box = gr.Textbox(label="Live Logs", value="", lines=28)
                with gr.Tab("Artifacts"):
                    thumbs_gallery = gr.Gallery(
                        label="Thumbnails", columns=3, height=220
                    )
                    shorts_files = gr.Files(label="Shorts (mp4)", interactive=False)
                    meta_file = gr.File(label="metadata.json")
                    qa_file = gr.File(label="qa_report.json")
                    qa_summary = gr.Markdown("QA: no report yet.")
                refresh_btn = gr.Button("📂 Refresh Artifacts (current slug)")

        # Wiring
        def on_slug_select(existing_slug, typed_slug):
            # prefer typed if not empty; else dropdown
            slug = typed_slug.strip() or (existing_slug or "")
            return slug

        slug_dd.change(on_slug_select, [slug_dd, slug_tb], [slug_tb])
        slugs_btn.click(lambda: gr.update(choices=refresh_slugs()), None, [slug_dd])

        models_btn.click(lambda: ensure_models(), None, [log_box])

        run_btn.click(
            run_full_pipeline,
            inputs=[
                slug_tb,
                mode_dd,
                yt_only_cb,
                enable_viral_cb,
                enable_shorts_cb,
                enable_seo_cb,
                seed_tb,
                from_step_dd,
            ],
            outputs=[log_box],
        )

        def run_qa(slug):
            if not slug:
                return "[ui] Set slug first."
            cmd = ["python", "bin/qa/run_gates.py", "--slug", slug]
            buf = []
            for line in stream_process(cmd):
                buf.append(line)
                yield "\n".join(buf[-CFG["ui"]["max_log_lines"] :])
            yield "\n".join(buf)

        qa_only_btn.click(run_qa, inputs=[slug_tb], outputs=[log_box])

        refresh_btn.click(
            refresh_artifacts,
            inputs=[slug_tb],
            outputs=[thumbs_gallery, shorts_files, meta_file, qa_file, qa_summary],
        )

    return demo


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--share", action="store_true", default=CFG["server"].get("share", False)
    )
    parser.add_argument(
        "--port", type=int, default=int(CFG["server"].get("port", 7860))
    )
    args = parser.parse_args()
    demo = ui_main()
    demo.launch(server_port=args.port, share=args.share)

#!/usr/bin/env python3
import os, sys
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def make_thumb(text: str, out_path: str, size=(1280,720)):
    img = Image.new("RGB", size, (20,20,20))
    draw = ImageDraw.Draw(img)
    # Brand stripe
    draw.rectangle([(0,0),(size[0], 120)], fill=(230,40,55))
    # Title text
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
    except Exception:
        font = ImageFont.load_default()
    text = (text[:50] + "…") if len(text) > 50 else text
    tw, th = draw.textsize(text, font=font)
    draw.text(((size[0]-tw)//2, (120-th)//2), text, font=font, fill=(255,255,255))
    img.save(out_path, format="PNG")

def main():
    title = sys.argv[1] if len(sys.argv) > 1 else "New Video"
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE, "videos", "thumbnail.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    make_thumb(title, out)
    print("Wrote thumbnail:", out)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import os, json, re
from PIL import Image, ImageDraw, ImageFont
from bin.util import single_lock, log_state, load_global_config, BASE, ensure_dirs

def safe_text(t, max_len=28):
    t = re.sub(r'\s+', ' ', t).strip()
    return (t[:max_len] + '…') if len(t) > max_len else t

def main():
    cfg = load_global_config(); ensure_dirs(cfg)
    scripts_dir = os.path.join(BASE,"scripts")
    files = [f for f in os.listdir(scripts_dir) if f.endswith(".metadata.json")]
    if not files:
        log_state("make_thumbnail","SKIP","no metadata"); print("No metadata"); return
    files.sort(reverse=True)
    meta = json.load(open(os.path.join(scripts_dir, files[0]),"r",encoding="utf-8"))
    title = safe_text(meta.get("title","New Video"))
    out_png = os.path.join(BASE,"videos", files[0].replace(".metadata.json",".png"))

    # Simple 1280x720 banner
    W,H = 1280,720
    img = Image.new("RGB",(W,H),(20,24,35))
    d = ImageDraw.Draw(img)
    # Simple stripe
    d.rectangle([0,H-120,W,H], fill=(255,196,0))
    # Title text
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 72)
    except:
        font = ImageFont.load_default()
    d.text((50, H-110), title, fill=(0,0,0), font=font)
    img.save(out_png, "PNG")
    log_state("make_thumbnail","OK", os.path.basename(out_png))
    print(f"Wrote thumbnail {out_png} (placeholder).")

if __name__ == "__main__":
    with single_lock():
        main()

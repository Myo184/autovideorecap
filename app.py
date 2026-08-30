# ================================================================
# 👑 VIP MAGIC VIDEO AUTO RECAP — GOOGLE COLAB (MONGODB CONNECTED)
# FAST ONE-PASS FFMPEG EDITION • VIP API CONNECTED
# ================================================================
# Recommended Runtime: T4 GPU (Runtime > Change runtime type > T4 GPU)

import os, sys, subprocess, importlib.util, shutil
import base64
import socket
import platform
import urllib.request


# ----------------------------------------------------------------
# 0) AUTO INSTALL DEPENDENCIES
# ----------------------------------------------------------------
def run_pip(*args):
    subprocess.check_call([sys.executable, "-m", "pip", *args])

def clean_reinstall_pillow():
    print("🧹 Fixing Pillow/PIL compatibility...")
    subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "Pillow"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    import site, glob
    candidates = []
    for base in site.getsitepackages() + [site.getusersitepackages()]:
        candidates.extend(glob.glob(os.path.join(base, "PIL")))
        candidates.extend(glob.glob(os.path.join(base, "Pillow-*.dist-info")))
        candidates.extend(glob.glob(os.path.join(base, "pillow-*.dist-info")))

    for path in candidates:
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
        elif os.path.exists(path):
            try: os.remove(path)
            except OSError: pass

    run_pip("install", "-q", "--no-cache-dir", "--force-reinstall", "Pillow==11.3.0")

    for module_name in list(sys.modules):
        if module_name == "PIL" or module_name.startswith("PIL."):
            del sys.modules[module_name]
    importlib.invalidate_caches()

print("📦 Installing Python packages...")
run_pip("install", "-q", "-U",
        "gradio",
        "gradio_client",
        "faster-whisper",
        "edge-tts",
        "google-genai",
        "opencv-python-headless",
        "numpy",
        "soundfile",
        "voxcpm")

clean_reinstall_pillow()

print("🎞️ Installing FFmpeg & Myanmar fonts...")
subprocess.run(["apt-get", "update", "-qq"], check=False)
subprocess.run(["apt-get", "install", "-y", "-qq", "ffmpeg", "fonts-noto-core", "fonts-noto-extra"], check=False)

# ----------------------------------------------------------------
# 1) IMPORTS
# ----------------------------------------------------------------
import gradio as gr
from gradio_client import Client
from faster_whisper import WhisperModel
import cv2
import asyncio
import edge_tts
import time
import numpy as np
import re
import json
import uuid
import tempfile
import glob
import torch
import soundfile as sf
from google import genai
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ================================================================
# 2) APP CONFIG & HF SPACE NAME (MONGODB CONNECTED)
# ================================================================
# Admin Portal Space that owns the Video VIP database and /verify API.
# You can override this in Hugging Face Space Variables/Secrets with VIP_ADMIN_SPACE_ID.
HF_SPACE_ID = os.getenv("VIP_ADMIN_SPACE_ID", "yufei184905/Vipcodemadclone").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

# VoxCPM2 is loaded lazily only when Voice Design / Voice Clone is selected.
# The model is public; HF_TOKEN is automatically picked up by huggingface_hub if present.
VOXCPM_MODEL_ID = os.getenv("VOXCPM_MODEL_ID", "openbmb/VoxCPM2").strip()
VOXCPM_DEVICE = os.getenv("VOXCPM_DEVICE", "cuda" if torch.cuda.is_available() else "cpu").strip()
_VOXCPM_MODEL = None

EDGE_VOICES = {
    "👩 Myanmar Female • Nilar": "my-MM-NilarNeural",
    "👨 Myanmar Male • Thiha": "my-MM-ThihaNeural",
}

VOXCPM_VOICE_PRESETS = {
    "🎬 Deep Male Movie Narrator": "A deep adult male movie narrator, cinematic, confident, dramatic, clear Burmese pronunciation, controlled emotion",
    "⚡ Young Male Energetic": "A young adult male voice, energetic, bright, fast and engaging, clear Burmese pronunciation",
    "🌙 Calm Male Documentary": "A calm mature male documentary narrator, warm, steady, trustworthy, natural Burmese pronunciation",
    "💎 Young Female Premium": "A young adult female voice, premium, clean, warm and engaging, natural Burmese pronunciation",
    "🔥 Female Energetic Recap": "A young female movie recap narrator, energetic, exciting, expressive, fast but clear Burmese pronunciation",
    "🌸 Soft Female Storyteller": "A gentle female storyteller, soft, warm, emotional, smooth and natural Burmese pronunciation",
    "✍️ Custom Voice Description": "",
}

MAX_SUBTITLE_DURATION_SECONDS = 7.0
MODEL_NAME = "gemini-2.5-flash"
SYSTEM_INSTRUCTION = (
    "You are a professional Burmese movie-recap narrator and story editor. "
    "Do NOT translate dialogue line-by-line. Re-tell the events as a coherent narrator who already understands the scene. "
    "Use natural spoken Burmese that sounds like a skilled YouTube/TikTok movie recap storyteller. "
    "Follow this rhythm when appropriate: Hook -> explain what is happening -> build tension or emotion -> smooth transition -> next event. "
    "Keep chronology and factual meaning faithful to the supplied subtitle content. Do not invent characters, motives, objects, or plot events that are not supported. "
    "Use suspense transitions only where they fit naturally; do not repeat stock phrases in every line. "
    "Avoid literal subtitle phrasing, stiff translation, excessive slang, and over-dramatization. "
    "Keep each output concise enough for voice narration and synchronized recap video."
)

USER_LIMIT_TRACKER = {}

# ================================================================
# 3) FONT DETECTION
# ================================================================
def find_myanmar_font():
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansMyanmar-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansMyanmar-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansMyanmarUI-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansMyanmarUI-Regular.ttf",
        "/content/Myanmar font.ttf",
        "/content/Myanmar_font.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p

    patterns = [
        "/usr/share/fonts/**/*Myanmar*.ttf",
        "/usr/share/fonts/**/*Myanmar*.otf",
        "/content/**/*Myanmar*.ttf",
    ]
    for pat in patterns:
        found = glob.glob(pat, recursive=True)
        if found:
            return found[0]
    return None

FONT_PATH = find_myanmar_font()
print("🔤 Myanmar font:", FONT_PATH or "NOT FOUND - fallback default used")

# ================================================================
# 4) WHISPER MODEL LOADING
# ================================================================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
print(f"🧠 Loading Faster-Whisper Base Model on {DEVICE} ({COMPUTE_TYPE})...")
whisper_model = WhisperModel("base", device=DEVICE, compute_type=COMPUTE_TYPE, cpu_threads=4)
print("✅ Whisper Loaded Successfully.")

# ================================================================
# 5) HELPERS
# ================================================================
def normalize_file_path(value):
    if value is None: return None
    if isinstance(value, str): return value
    if isinstance(value, dict): return value.get("path") or value.get("name")
    if hasattr(value, "name"): return value.name
    return str(value)

def safe_kernel_size(v, minimum=3):
    k = max(minimum, int(v))
    if k % 2 == 0: k += 1
    return k

def hex_to_rgb(hex_str):
    if not hex_str: return (255, 255, 0)
    hex_str = hex_str.lstrip("#")
    if len(hex_str) != 6: return (255, 255, 0)
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def segment_myanmar_syllables(text):
    return re.findall(r"[a-zA-Z0-9\s\-\.,!\?]+|[\u1000-\u102a\u103f\u1040-\u1049]+[\u102b-\u103e\u1060-\u109f]*|[^\s]", text)

def wrap_text_myanmar_smart(text, font, max_width, draw):
    cleaned_text = text.replace(" ြ", "ြ").replace("ြ ", "ြ").strip()
    tokens = segment_myanmar_syllables(cleaned_text)
    lines, current_line = [], ""
    for token in tokens:
        test_line = current_line + token
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if (bbox[2] - bbox[0]) <= max_width or not current_line:
            current_line = test_line
        else:
            lines.append(current_line.strip())
            current_line = token
    if current_line:
        lines.append(current_line.strip())
    return lines

def draw_line(draw, position, text, font, fill_color, stroke_w, stroke_c):
    clean_text = text.replace(" ြ", "ြ").replace("ြ ", "ြ")
    draw.text(position, clean_text, font=font, fill=fill_color, stroke_width=stroke_w, stroke_fill=stroke_c)

def update_preview_image(video_value, blur_y_percent, blur_height_percent, blur_strength):
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None: return None

        h, w = frame.shape[:2]
        blur_h = max(8, int(h * (float(blur_height_percent) / 100.0)))
        center_y = int(h * (float(blur_y_percent) / 100.0))
        blur_y = max(0, min(center_y - blur_h // 2, h - blur_h))
        k = safe_kernel_size(blur_strength)

        preview = frame.copy()
        roi = preview[blur_y:blur_y + blur_h, 0:w]
        if roi.size:
            sw, sh = max(1, w // 4), max(1, blur_h // 4)
            small = cv2.resize(roi, (sw, sh), interpolation=cv2.INTER_LINEAR)
            ks = safe_kernel_size(max(3, k // 4))
            blurred = cv2.GaussianBlur(small, (ks, ks), 0)
            preview[blur_y:blur_y + blur_h, 0:w] = cv2.resize(blurred, (w, blur_h), interpolation=cv2.INTER_LINEAR)
            cv2.rectangle(preview, (0, blur_y), (w - 1, blur_y + blur_h - 1), (0, 0, 255), 3)

        return Image.fromarray(cv2.cvtColor(preview, cv2.COLOR_BGR2RGB))
    except Exception:
        return None


def video_first_frame_data_uri(video_value):
    """Return a lightweight JPEG data URI for the browser-side drag blur editor."""
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        return ""
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = cap.read()
        if not ret or frame is None:
            return ""
        h, w = frame.shape[:2]
        max_w = 900
        if w > max_w:
            scale = max_w / float(w)
            frame = cv2.resize(frame, (max_w, max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return ""
        return 'data:image/jpeg;base64,' + base64.b64encode(encoded.tobytes()).decode('ascii')
    except Exception as exc:
        print(f'⚠️ Blur editor preview error: {exc}')
        return ""
    finally:
        if cap is not None:
            cap.release()


def sync_blur_editor(evt: gr.EventData):
    """Receive browser drag/resize percentages from the custom blur editor."""
    try:
        center = float(evt.center)
        height = float(evt.height)
    except Exception:
        return 78.0, 12.0
    height = max(3.0, min(45.0, height))
    half = height / 2.0
    center = max(half, min(100.0 - half, center))
    return round(center, 2), round(height, 2)


BLUR_EDITOR_TEMPLATE = r"""
<div class="drag-blur-editor">
  <div class="drag-blur-toolbar">
    <div>
      <div class="drag-blur-title">✋ Drag Blur Editor</div>
      <div class="drag-blur-help">Purple band ကို drag လုပ်ပြီးရွှေ့ပါ • အပေါ်/အောက် handle ကိုဆွဲပြီး အမြင့်ပြောင်းပါ</div>
    </div>
    <button class="drag-blur-reset" type="button">Reset</button>
  </div>
  <div class="drag-blur-stage">
    <img class="drag-blur-image" src="${value}" draggable="false" alt="Video preview">
    <div class="drag-blur-empty">🎬 Video upload လုပ်ပြီး Blur Band ကို mouse နဲ့တိုက်ရိုက်ညှိနိုင်ပါတယ်</div>
    <div class="drag-blur-band">
      <div class="drag-blur-handle drag-blur-handle-top" title="Drag to resize"></div>
      <div class="drag-blur-grip">⋮⋮ DRAG BLUR AREA ⋮⋮</div>
      <div class="drag-blur-handle drag-blur-handle-bottom" title="Drag to resize"></div>
    </div>
  </div>
  <div class="drag-blur-readout">
    <span>Center <b class="drag-center-value">78%</b></span>
    <span>Height <b class="drag-height-value">12%</b></span>
    <span class="drag-blur-saved">✓ Final render position synced</span>
  </div>
</div>
"""

BLUR_EDITOR_CSS = r"""
.drag-blur-editor { width:100%; color:#eef2ff; user-select:none; }
.drag-blur-toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:10px; }
.drag-blur-title { font-size:14px; font-weight:900; color:#fff; }
.drag-blur-help { margin-top:3px; font-size:11px; color:#8f9abb; line-height:1.45; }
.drag-blur-reset { border:1px solid rgba(167,139,250,.28); background:rgba(139,92,246,.10); color:#ddd6fe; padding:7px 11px; border-radius:10px; font-size:11px; font-weight:800; cursor:pointer; }
.drag-blur-reset:hover { background:rgba(139,92,246,.19); }
.drag-blur-stage { position:relative; width:100%; min-height:260px; overflow:hidden; border-radius:18px; border:1px solid rgba(139,125,255,.25); background:#070a16; touch-action:none; box-shadow:inset 0 0 0 1px rgba(255,255,255,.02); }
.drag-blur-image { display:block; width:100%; height:auto; min-height:260px; max-height:590px; object-fit:contain; background:#050713; pointer-events:none; }
.drag-blur-empty { position:absolute; inset:0; display:grid; place-items:center; padding:24px; text-align:center; color:#71809f; font-size:12px; pointer-events:none; background:linear-gradient(135deg,rgba(13,18,38,.95),rgba(6,9,20,.96)); }
.drag-blur-stage.has-image .drag-blur-empty { display:none; }
.drag-blur-band { position:absolute; left:0; width:100%; top:72%; height:12%; min-height:26px; cursor:grab; border-top:2px solid #a78bfa; border-bottom:2px solid #22d3ee; background:rgba(124,58,237,.09); backdrop-filter:blur(10px); -webkit-backdrop-filter:blur(10px); box-shadow:0 0 25px rgba(124,58,237,.18), inset 0 0 30px rgba(34,211,238,.06); }
.drag-blur-band:active { cursor:grabbing; }
.drag-blur-grip { position:absolute; left:50%; top:50%; transform:translate(-50%,-50%); padding:7px 13px; white-space:nowrap; border-radius:999px; background:rgba(8,11,25,.78); border:1px solid rgba(196,181,253,.32); color:#e9d5ff; font-size:10px; font-weight:900; letter-spacing:.08em; pointer-events:none; box-shadow:0 6px 20px rgba(0,0,0,.25); }
.drag-blur-handle { position:absolute; left:50%; width:82px; height:12px; transform:translateX(-50%); z-index:5; cursor:ns-resize; }
.drag-blur-handle:after { content:""; position:absolute; left:16px; right:16px; top:4px; height:4px; border-radius:999px; background:#fff; box-shadow:0 0 0 1px rgba(124,58,237,.28),0 2px 8px rgba(0,0,0,.28); }
.drag-blur-handle-top { top:-7px; }
.drag-blur-handle-bottom { bottom:-7px; }
.drag-blur-readout { display:flex; flex-wrap:wrap; align-items:center; gap:8px; margin-top:9px; font-size:11px; color:#a8b2ca; }
.drag-blur-readout span { padding:6px 9px; border-radius:9px; background:rgba(15,20,42,.62); border:1px solid rgba(148,163,184,.12); }
.drag-blur-readout b { color:#fff; }
.drag-blur-readout .drag-blur-saved { color:#86efac; border-color:rgba(52,211,153,.16); background:rgba(52,211,153,.06); }
@media (max-width:720px) { .drag-blur-stage{min-height:210px}.drag-blur-image{min-height:210px}.drag-blur-help{max-width:270px}.drag-blur-grip{font-size:9px;padding:6px 9px} }
"""

BLUR_EDITOR_JS = r"""
const stage = element.querySelector('.drag-blur-stage');
const image = element.querySelector('.drag-blur-image');
const band = element.querySelector('.drag-blur-band');
const topHandle = element.querySelector('.drag-blur-handle-top');
const bottomHandle = element.querySelector('.drag-blur-handle-bottom');
const resetBtn = element.querySelector('.drag-blur-reset');
const centerLabel = element.querySelector('.drag-center-value');
const heightLabel = element.querySelector('.drag-height-value');
let center = 78.0;
let height = 12.0;
let mode = null;
let startY = 0;
let startCenter = center;
let startHeight = height;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
function imageReady() {
  const ready = !!image.getAttribute('src') && image.naturalWidth > 0;
  stage.classList.toggle('has-image', ready);
  return ready;
}
function normalize() {
  height = clamp(height, 3, 45);
  const half = height / 2;
  center = clamp(center, half, 100 - half);
}
function draw() {
  normalize();
  band.style.top = `${center - height / 2}%`;
  band.style.height = `${height}%`;
  centerLabel.textContent = `${center.toFixed(1)}%`;
  heightLabel.textContent = `${height.toFixed(1)}%`;
}
function emitValue() {
  normalize();
  trigger('change', {center: Number(center.toFixed(2)), height: Number(height.toFixed(2))});
}
function pointerPercent(ev) {
  const rect = stage.getBoundingClientRect();
  return ((ev.clientY - rect.top) / Math.max(1, rect.height)) * 100;
}
function begin(ev, nextMode) {
  if (!imageReady()) return;
  ev.preventDefault();
  ev.stopPropagation();
  mode = nextMode;
  startY = pointerPercent(ev);
  startCenter = center;
  startHeight = height;
  stage.setPointerCapture?.(ev.pointerId);
}
band.addEventListener('pointerdown', (ev) => {
  if (ev.target === topHandle || ev.target === bottomHandle) return;
  begin(ev, 'move');
});
topHandle.addEventListener('pointerdown', (ev) => begin(ev, 'top'));
bottomHandle.addEventListener('pointerdown', (ev) => begin(ev, 'bottom'));
stage.addEventListener('pointermove', (ev) => {
  if (!mode) return;
  ev.preventDefault();
  const now = pointerPercent(ev);
  const delta = now - startY;
  if (mode === 'move') {
    center = startCenter + delta;
  } else if (mode === 'top') {
    const startTop = startCenter - startHeight / 2;
    const fixedBottom = startCenter + startHeight / 2;
    const newTop = clamp(startTop + delta, 0, fixedBottom - 3);
    height = fixedBottom - newTop;
    center = (fixedBottom + newTop) / 2;
  } else if (mode === 'bottom') {
    const fixedTop = startCenter - startHeight / 2;
    const startBottom = startCenter + startHeight / 2;
    const newBottom = clamp(startBottom + delta, fixedTop + 3, 100);
    height = newBottom - fixedTop;
    center = (fixedTop + newBottom) / 2;
  }
  draw();
});
function endDrag(ev) {
  if (!mode) return;
  mode = null;
  try { stage.releasePointerCapture?.(ev.pointerId); } catch (_) {}
  draw();
  emitValue();
}
stage.addEventListener('pointerup', endDrag);
stage.addEventListener('pointercancel', endDrag);
resetBtn.addEventListener('click', (ev) => {
  ev.preventDefault();
  center = 78;
  height = 12;
  draw();
  emitValue();
});
image.addEventListener('load', () => { imageReady(); draw(); });
image.addEventListener('error', () => { stage.classList.remove('has-image'); });
imageReady();
draw();
"""

# ================================================================
# 6) TRANSLATION MODULE
# ================================================================
def google_backup_translate(text, source_lang="en"):
    from urllib.parse import quote
    import urllib.request
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl=my&dt=t&q={quote(text)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        res = urllib.request.urlopen(req, timeout=8).read().decode("utf-8")
        return json.loads(res)[0][0][0] or text
    except Exception:
        return text

def translate_segments_batch(segments, user_api_key, source_lang="en", tone_style="Thriller"):
    if not segments: return segments
    if not user_api_key or not user_api_key.strip():
        for seg in segments:
            seg["mm_text"] = google_backup_translate(seg["text"], source_lang)
        return segments

    payload_dict = {str(i): seg["text"] for i, seg in enumerate(segments)}
    large_prompt_text = json.dumps(payload_dict, ensure_ascii=False, indent=2)

    prompt = f"""
Rewrite the following chronological subtitle chunks from '{source_lang}' as connected Burmese MOVIE RECAP NARRATION.
Narrative Mode: {tone_style}

STORYTELLING TARGET:
- Sound like one narrator retelling the movie, NOT actors speaking dialogue and NOT a literal translator.
- Preserve the actual sequence and meaning of the supplied chunks.
- Turn dialogue into narration where possible: who does what, what changes, what the viewer needs to understand next.
- Use a strong hook or curiosity line only when the scene supports it.
- Build suspense/emotion gradually, then use a short natural transition into the next event.
- Examples of transition style (use sparingly, not repeatedly):
  “ဒါပေမယ့် သူမသိသေးတာတစ်ခုရှိနေပါတယ်…”
  “အဲဒီအချိန်မှာပဲ မထင်မှတ်ထားတဲ့အရာတစ်ခု ဖြစ်လာပါတယ်…”
  “ဒီဖြစ်ရပ်က နောက်ထပ်ပြဿနာကြီးတစ်ခုရဲ့ အစပဲဖြစ်ပါတယ်…”
- Do not invent unsupported plot details. If the subtitle context is uncertain, narrate conservatively.
- Avoid repeating names/pronouns unnecessarily.
- Keep Burmese natural, spoken, clear, and engaging for AI voiceover.
- Keep each value reasonably concise so timing remains usable.

TONE GUIDE:
- Viral Story Recap: fast, gripping, natural storyteller flow with controlled suspense.
- Thriller: tense, mysterious, darker suspense.
- Comedy: light, witty, playful without changing facts.
- Dramatic: emotional, cinematic, serious.
- Action/Epic: energetic, urgent, high-impact.
- Neutral: clean documentary-style recap.

OUTPUT RULES:
1. Return VALID JSON ONLY.
2. Keep every input key identical (0, 1, 2...).
3. Each value must be Burmese recap narration corresponding to that chunk, while maintaining continuity with nearby chunks.
4. No markdown, notes, explanations, or extra keys.

Chronological subtitle JSON:
{large_prompt_text}
"""
    translated_map = {}
    try:
        client = genai.Client(api_key=user_api_key.strip())
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={"system_instruction": SYSTEM_INSTRUCTION, "temperature": 0.65}
        )
        res_text = (response.text or "").strip()
        res_text = re.sub(r"^```(?:json)?\s*", "", res_text)
        res_text = re.sub(r"\s*```$", "", res_text)
        translated_map = json.loads(res_text)
    except Exception as e:
        print(f"⚠️ Gemini API Warning: {e}. Missing lines will use Google Translate backup.")

    for i, seg in enumerate(segments):
        key = str(i)
        seg["mm_text"] = translated_map.get(key) or google_backup_translate(seg["text"], source_lang)

    return segments

# ================================================================
# 7) TTS • EDGE + VOXCPM2 VOICE DESIGN / VOICE CLONE
# ================================================================
def generate_voice_sync(text, voice_id, filename, desired_tts_rate=1.15, target_duration_sec=None):
    """Edge-TTS standard Burmese voice."""
    rate_percentage = int((float(desired_tts_rate) - 1.0) * 100)
    if target_duration_sec and target_duration_sec > 0:
        cps = len(text) / target_duration_sec
        if cps > 15: rate_percentage += 30
        elif cps > 11: rate_percentage += 15
        elif cps > 7: rate_percentage += 5

    rate_percentage = max(-50, min(100, rate_percentage))
    rate_str = f"{rate_percentage:+d}%"

    async def _async_gen():
        communicate = edge_tts.Communicate(text, voice_id, rate=rate_str)
        await communicate.save(filename)

    try:
        asyncio.run(_async_gen())
    except RuntimeError:
        import threading
        holder = {"error": None}
        def runner():
            try: asyncio.run(_async_gen())
            except Exception as exc: holder["error"] = exc
        t = threading.Thread(target=runner)
        t.start(); t.join()
        if holder["error"]: raise holder["error"]


def get_voxcpm_model():
    """Lazy-load VoxCPM2 so Edge-TTS users do not consume VoxCPM VRAM."""
    global _VOXCPM_MODEL
    if _VOXCPM_MODEL is not None:
        return _VOXCPM_MODEL

    try:
        from voxcpm import VoxCPM
    except Exception as exc:
        raise RuntimeError(f"VoxCPM package import မရပါ: {exc}") from exc

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    print(f"🎙️ Loading VoxCPM2: {VOXCPM_MODEL_ID} on {VOXCPM_DEVICE} ...")
    try:
        _VOXCPM_MODEL = VoxCPM.from_pretrained(
            VOXCPM_MODEL_ID,
            load_denoiser=False,
            device=VOXCPM_DEVICE,
            # Avoid a long torch.compile warm-up on T4/Colab. Set True later if desired.
            optimize=False,
        )
    except Exception as exc:
        raise RuntimeError(f"VoxCPM2 model load မအောင်မြင်ပါ: {exc}") from exc

    print("✅ VoxCPM2 loaded.")
    return _VOXCPM_MODEL


def normalize_clone_reference(reference_value, work_dir, max_seconds=15):
    """Convert uploaded reference audio to 16 kHz mono WAV for consistent cloning."""
    src = normalize_file_path(reference_value)
    if not src or not os.path.exists(src):
        raise gr.Error("🎙️ Voice Clone အတွက် Reference Audio (MP3/WAV) upload လုပ်ပါ။")

    dst = os.path.join(work_dir, "voxcpm_reference_16k.wav")
    proc = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", src, "-t", str(int(max_seconds)), "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", dst,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if proc.returncode != 0 or not os.path.exists(dst):
        raise gr.Error("Reference audio ပြင်ဆင်၍ မရပါ: " + (proc.stderr or "Unknown FFmpeg error"))
    return dst


def voxcpm_pace_instruction(rate):
    rate = float(rate)
    if rate >= 1.45:
        return "very fast movie recap pace, energetic but clearly articulated"
    if rate >= 1.28:
        return "fast movie recap pace, engaging and clear"
    if rate >= 1.12:
        return "slightly fast natural narration pace"
    if rate <= 0.95:
        return "slow calm narration pace"
    return "natural narration pace"


def generate_voxcpm_audio(
    text,
    filename,
    mode="design",
    voice_preset="🎬 Deep Male Movie Narrator",
    custom_voice_description="",
    reference_wav_path=None,
    reference_transcript="",
    desired_speed=1.20,
    cfg_value=2.0,
    inference_timesteps=10,
    seed=42,
):
    """Generate VoxCPM2 voice design or zero-shot voice cloning audio."""
    model = get_voxcpm_model()
    clean_text = (text or "").strip()
    if not clean_text:
        raise ValueError("TTS text is empty")

    cfg_value = max(1.0, min(3.0, float(cfg_value)))
    inference_timesteps = max(4, min(30, int(inference_timesteps)))
    try:
        seed_value = int(seed) if seed is not None else None
    except Exception:
        seed_value = 42

    kwargs = {
        "text": clean_text,
        "cfg_value": cfg_value,
        "inference_timesteps": inference_timesteps,
        "seed": seed_value,
        "normalize": False,
    }

    if mode == "clone":
        if not reference_wav_path or not os.path.exists(reference_wav_path):
            raise ValueError("Voice clone reference audio is missing")

        transcript = (reference_transcript or "").strip()
        if transcript:
            # Ultimate Cloning: same reference clip is used for continuation + isolated reference.
            kwargs["prompt_wav_path"] = reference_wav_path
            kwargs["prompt_text"] = transcript
            kwargs["reference_wav_path"] = reference_wav_path
        else:
            # Controllable / isolated reference cloning.
            kwargs["reference_wav_path"] = reference_wav_path
            pace = voxcpm_pace_instruction(desired_speed)
            kwargs["text"] = f"({pace}){clean_text}"
    else:
        desc = VOXCPM_VOICE_PRESETS.get(voice_preset, "")
        if voice_preset == "✍️ Custom Voice Description":
            desc = (custom_voice_description or "").strip()
        pace = voxcpm_pace_instruction(desired_speed)
        full_desc = ", ".join(x for x in [desc, pace] if x)
        if full_desc:
            kwargs["text"] = f"({full_desc}){clean_text}"

    wav = model.generate(**kwargs)
    sample_rate = int(getattr(model.tts_model, "sample_rate", 48000))
    sf.write(filename, np.asarray(wav, dtype=np.float32), sample_rate)
    return filename


def probe_duration(path, fallback=1.0):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
        )
        return float(r.stdout.strip())
    except Exception:
        return fallback


def update_voice_engine_panels(engine):
    """Switch engine-specific controls while keeping external clone upload visible."""
    engine = str(engine or "")
    is_edge = engine.startswith("⚡")
    is_design = "Voice Design" in engine
    return (
        gr.update(visible=is_edge),
        gr.update(visible=is_design),
        gr.update(visible=True),  # Clone upload is intentionally always visible.
    )


def inspect_clone_reference(reference_value):
    """Confirm that an uploaded external voice is detected and report duration."""
    path = normalize_file_path(reference_value)
    if not path or not os.path.exists(path):
        return "<div class='ref-status warn'>⚠️ MP3/WAV reference voice ကို upload သို့မဟုတ် microphone နဲ့ record လုပ်ပါ။</div>"

    duration = probe_duration(path, fallback=0.0)
    name = os.path.basename(path)
    if duration <= 0:
        return f"<div class='ref-status warn'>⚠️ <b>{name}</b> ကိုတွေ့ပေမယ့် duration မဖတ်နိုင်ပါ။</div>"
    if duration < 3.0:
        return f"<div class='ref-status warn'>⚠️ <b>{name}</b> • {duration:.1f}s — reference တိုလွန်းပါတယ်။ 5–15 sec ကြည်လင်တဲ့အသံကို အကြံပြုပါတယ်။</div>"
    if duration > 15.0:
        return f"<div class='ref-status ok'>✅ <b>{name}</b> • {duration:.1f}s — detected. Voice Clone မှာ ပထမ 15 sec ကို အသုံးပြုပါမယ်။</div>"
    return f"<div class='ref-status ok'>✅ <b>{name}</b> • {duration:.1f}s — VoxCPM2 cloning အတွက် reference ready ဖြစ်ပါတယ်။</div>"


def generate_voice_preview(
    voice_engine,
    edge_voice_name,
    voice_preset,
    custom_voice_description,
    clone_reference,
    clone_transcript,
    clone_consent,
    desired_speed,
    voxcpm_cfg,
    voxcpm_steps,
    voxcpm_seed,
):
    """Generate a short preview without processing a movie."""
    work_dir = tempfile.mkdtemp(prefix="yf_voice_preview_")
    sample_text = "မင်္ဂလာပါ။ YF Recap မှာ ဒီအသံနဲ့ ရုပ်ရှင်ဇာတ်လမ်းကို ပြန်လည်တင်ဆက်ပေးသွားမှာ ဖြစ်ပါတယ်။"

    if str(voice_engine).startswith("⚡"):
        out = os.path.join(work_dir, "edge_preview.mp3")
        voice_id = EDGE_VOICES.get(edge_voice_name, "my-MM-NilarNeural")
        generate_voice_sync(sample_text, voice_id, out, desired_tts_rate=desired_speed)
        return out

    if "Voice Design" in str(voice_engine):
        out = os.path.join(work_dir, "voxcpm_design_preview.wav")
        generate_voxcpm_audio(
            sample_text, out, mode="design", voice_preset=voice_preset,
            custom_voice_description=custom_voice_description,
            desired_speed=desired_speed, cfg_value=voxcpm_cfg,
            inference_timesteps=voxcpm_steps, seed=voxcpm_seed,
        )
        return out

    if not clone_consent:
        raise gr.Error("Voice Clone အသုံးပြုရန် အသံပိုင်ရှင်၏ ခွင့်ပြုချက်ရှိကြောင်း checkbox ကို အမှန်ခြစ်ပါ။")
    ref = normalize_clone_reference(clone_reference, work_dir)
    out = os.path.join(work_dir, "voxcpm_clone_preview.wav")
    generate_voxcpm_audio(
        sample_text, out, mode="clone", reference_wav_path=ref,
        reference_transcript=clone_transcript, desired_speed=desired_speed,
        cfg_value=voxcpm_cfg, inference_timesteps=voxcpm_steps, seed=voxcpm_seed,
    )
    return out


# ================================================================
# 7B) FAST FFMPEG RENDER HELPERS
# ================================================================
def ffmpeg_has_encoder(name):
    try:
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False
        )
        return name.lower() in (r.stdout or "").lower()
    except Exception:
        return False

HAS_NVENC = bool(torch.cuda.is_available() and ffmpeg_has_encoder("h264_nvenc"))
RENDER_ENGINE_LABEL = "NVIDIA NVENC GPU" if HAS_NVENC else "FFmpeg CPU (libx264)"
print(f"🚀 Fast render engine: {RENDER_ENGINE_LABEL}")

def ass_color(hex_str):
    """Convert #RRGGBB to ASS &H00BBGGRR format."""
    value = (hex_str or "#FFFFFF").strip().lstrip("#")
    if len(value) != 6:
        value = "FFFFFF"
    r, g, b = value[0:2], value[2:4], value[4:6]
    return f"&H00{b}{g}{r}".upper()

def ass_time(seconds):
    seconds = max(0.0, float(seconds))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def escape_ass_text(value):
    value = (value or "").replace("\\", r"\\")
    value = value.replace("{", r"\{").replace("}", r"\}")
    value = value.replace("\r", " ").replace("\n", r"\N")
    return value

def detect_font_family(font_path):
    if not font_path:
        return "Noto Sans Myanmar"
    try:
        r = subprocess.run(
            ["fc-scan", "--format=%{family}", font_path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, check=False
        )
        family = (r.stdout or "").strip().splitlines()[0].split(",")[0].strip() if (r.stdout or "").strip() else ""
        if family:
            return family
    except Exception:
        pass
    return "Noto Sans Myanmar"

ASS_FONT_FAMILY = detect_font_family(FONT_PATH)

def build_ass_subtitles(
    subtitle_segments, output_path, target_w, target_h,
    subtitle_size_percent, sub_pos_percent, text_color, stroke_color
):
    font_size = max(24, int(target_h * (float(subtitle_size_percent) / 100.0)))
    outline = max(2, int(font_size * 0.085))
    margin_v = max(8, int(target_h * (float(sub_pos_percent) / 100.0)))

    # Wrap each subtitle once here instead of measuring/drawing it on every video frame.
    try:
        pil_font = ImageFont.truetype(FONT_PATH, font_size) if FONT_PATH else ImageFont.load_default()
        dummy = Image.new("RGB", (target_w, target_h), "black")
        draw = ImageDraw.Draw(dummy)
    except Exception:
        pil_font = None
        draw = None

    header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: {target_w}\nPlayResY: {target_h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\nYCbCr Matrix: TV.709\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{ASS_FONT_FAMILY},{font_size},{ass_color(text_color)},&H000000FF,{ass_color(stroke_color)},&H66000000,-1,0,0,0,100,100,0,0,1,{outline},0,2,30,30,{margin_v},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""

    lines = [header]
    for seg in subtitle_segments:
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue
        if pil_font is not None and draw is not None:
            wrapped = wrap_text_myanmar_smart(txt, pil_font, int(target_w * 0.90), draw)
            txt = r"\N".join(wrapped)
        txt = escape_ass_text(txt).replace(r"\\N", r"\N")
        lines.append(
            f"Dialogue: 0,{ass_time(seg['start'])},{ass_time(seg['end'])},Default,,0,0,0,,{txt}\n"
        )

    Path(output_path).write_text("".join(lines), encoding="utf-8-sig")
    return output_path

def ffmpeg_filter_escape(path):
    # Escaping for file paths used inside FFmpeg filter arguments.
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")

def parse_ffmpeg_time(value):
    try:
        h, m, s = value.strip().split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    except Exception:
        return 0.0

def run_ffmpeg_with_progress(cmd, total_duration, progress, start=0.70, end=0.98, desc="🚀 Fast Rendering"):
    """Run FFmpeg while translating -progress output into the Gradio progress bar."""
    cmd = list(cmd)
    # Place progress controls before output path (last item).
    output_path = cmd.pop()
    cmd.extend(["-progress", "pipe:1", "-nostats", output_path])
    recent = []
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, universal_newlines=True
    )
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.strip()
        if line:
            recent.append(line)
            if len(recent) > 80:
                recent.pop(0)
        if line.startswith("out_time="):
            elapsed = parse_ffmpeg_time(line.split("=", 1)[1])
            frac = min(1.0, elapsed / max(float(total_duration), 0.1))
            progress(start + (end - start) * frac, desc=f"{desc} ({int(frac * 100)}%)")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("FFmpeg render failed:\n" + "\n".join(recent[-20:]))

def build_video_filter_graph(
    target_w, target_h, render_fps, total_duration,
    background_fill, enable_zoom, zoom_level, mirror_flip, filter_color,
    blur_y_percent, blur_height_percent, blur_strength,
    ass_path, logo_input_index=None
):
    fg_filters = [f"fps={render_fps}"]
    z = max(1.0, float(zoom_level))
    if enable_zoom and z > 1.001:
        fg_filters.append(f"crop=iw/{z:.4f}:ih/{z:.4f}")
    if mirror_flip:
        fg_filters.append("hflip")
    if filter_color == "Chrome Cool":
        fg_filters.append("eq=brightness=0.045:contrast=1.03:saturation=0.92")
    elif filter_color == "Warm Cinema":
        fg_filters.append("eq=brightness=0.025:contrast=1.06:saturation=1.10")
    fg_filters.append(f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease")
    fg_filters.append("setsar=1")
    fg_chain = ",".join(fg_filters)

    parts = []
    if background_fill == "Blur Background":
        # C-level FFmpeg blur and scaling; no Python frame loop.
        parts.append("[0:v]split=2[vbgsrc][vfgsrc]")
        bg_w, bg_h = max(160, target_w // 4), max(160, target_h // 4)
        parts.append(
            f"[vbgsrc]fps={render_fps},scale={bg_w}:{bg_h}:force_original_aspect_ratio=increase,"
            f"crop={bg_w}:{bg_h},boxblur=10:1,scale={target_w}:{target_h},setsar=1[bg]"
        )
        parts.append(f"[vfgsrc]{fg_chain}[fg]")
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=0[base]")
    else:
        parts.append(f"color=c=0x050713:s={target_w}x{target_h}:r={render_fps}:d={float(total_duration):.3f}[bg]")
        parts.append(f"[0:v]{fg_chain}[fg]")
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=0[base]")

    blur_h = max(8, int(target_h * (float(blur_height_percent) / 100.0)))
    center_y = int(target_h * (float(blur_y_percent) / 100.0))
    blur_y = max(0, min(center_y - blur_h // 2, target_h - blur_h))
    radius = max(2, min(32, int(float(blur_strength) / 6)))
    parts.append("[base]split=2[main][bandsrc]")
    parts.append(
        f"[bandsrc]crop={target_w}:{blur_h}:0:{blur_y},boxblur={radius}:1[band]"
    )
    parts.append(f"[main][band]overlay=0:{blur_y}[blurred]")

    current = "blurred"
    if logo_input_index is not None:
        logo_w = max(72, int(target_w * 0.16))
        parts.append(f"[{logo_input_index}:v]scale={logo_w}:-1[logo]")
        parts.append(f"[{current}][logo]overlay=W-w-24:24:format=auto[withlogo]")
        current = "withlogo"

    ass_escaped = ffmpeg_filter_escape(ass_path)
    font_dir = ffmpeg_filter_escape(os.path.dirname(FONT_PATH) if FONT_PATH else "/usr/share/fonts")
    parts.append(
        f"[{current}]ass=filename='{ass_escaped}':fontsdir='{font_dir}',format=yuv420p[vout]"
    )
    return ";\n".join(parts)


# ================================================================
# 8) ULTRA-FAST FFMPEG VIDEO RECAP PROCESSOR
# ================================================================
def process_magic_recap_video(
    video_value,
    user_api_key,
    ratio_select,
    background_fill,
    enable_zoom,
    zoom_level,
    logo_value,
    bgm_value,
    bgm_volume,
    mirror_flip,
    filter_color,
    voice_engine,
    edge_voice_name,
    voice_preset,
    custom_voice_description,
    clone_reference,
    clone_transcript,
    clone_consent,
    voxcpm_cfg,
    voxcpm_steps,
    voxcpm_seed,
    tone_style,
    text_color,
    stroke_color,
    blur_y_percent,
    blur_height_percent,
    blur_strength,
    sub_pos_percent,
    subtitle_size_percent,
    desired_speed,
    render_mode,
    session_id,
    vip_access_state,
    progress=gr.Progress(track_tqdm=False)
):
    video_path = normalize_file_path(video_value)
    logo_path = normalize_file_path(logo_value)
    bgm_path = normalize_file_path(bgm_value)
    clone_reference_path = normalize_file_path(clone_reference)

    if not video_path or not os.path.exists(video_path):
        raise gr.Error("❌ Video file မတွေ့ပါ။")
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        raise gr.Error("🔒 VIP Access မရှိသေးပါ။ VIP Code ဖြင့် Login ဝင်ပါ။")

    if "Voice Clone" in str(voice_engine):
        if not clone_consent:
            raise gr.Error("🎙️ Voice Clone အသုံးပြုရန် အသံပိုင်ရှင်၏ ခွင့်ပြုချက်ရှိကြောင်း checkbox ကို အမှန်ခြစ်ပါ။")
        if not clone_reference_path or not os.path.exists(clone_reference_path):
            raise gr.Error("🎙️ VoxCPM Voice Clone အတွက် Reference Audio upload လုပ်ပါ။")

    role = vip_access_state.get("role", "vip")
    member_label = vip_access_state.get("label", "VIP Member")
    daily_limit = vip_access_state.get("daily_limit")
    user_identifier = f"{role}:{session_id}"
    now = time.time()

    if daily_limit is not None:
        daily_limit = int(daily_limit)
        data = USER_LIMIT_TRACKER.get(user_identifier)
        if not data or (now - data["first_time"]) >= 86400:
            USER_LIMIT_TRACKER[user_identifier] = {"count": 0, "first_time": now}
            data = USER_LIMIT_TRACKER[user_identifier]
        if data["count"] >= daily_limit:
            remain = max(0, 86400 - (now - data["first_time"]))
            h, m = int(remain // 3600), int((remain % 3600) // 60)
            raise gr.Error(f"❌ {member_label} daily quota ပြည့်ပါပြီ ({daily_limit} vids/day)။ {h}နာရီ {m}မိနစ်နောက် ပြန်စမ်းပါ။")

    work_dir = tempfile.mkdtemp(prefix=f"magic_fast_{session_id[:8]}_")
    output_video_path = os.path.join(work_dir, "final_recap_fast.mp4")
    cap = None

    try:
        # 1) Speech-to-text (GPU when CUDA is available)
        progress(0.04, desc="🎙️ 01/06 • Speech ကိုဖတ်ယူနေသည်...")
        segments_raw, info = whisper_model.transcribe(
            video_path, beam_size=1, vad_filter=True, condition_on_previous_text=False
        )
        raw_segments = [
            {"start": float(seg.start), "end": float(seg.end), "text": (seg.text or "").strip()}
            for seg in segments_raw if (seg.text or "").strip()
        ]

        cap = cv2.VideoCapture(video_path)
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = frame_count / source_fps if source_fps > 0 else 0.0
        cap.release(); cap = None

        if not raw_segments:
            raw_segments = [{
                "start": 0.0,
                "end": min(6.0, max(video_duration, 2.0)),
                "text": "This is an interesting movie scene."
            }]

        # Split long subtitle segments for narration timing.
        segments = []
        for seg in raw_segments:
            dur = max(0.1, seg["end"] - seg["start"])
            if MAX_SUBTITLE_DURATION_SECONDS > 0 and dur > MAX_SUBTITLE_DURATION_SECONDS:
                words = seg["text"].split()
                chunks_count = max(1, int(np.ceil(dur / MAX_SUBTITLE_DURATION_SECONDS)))
                words_per_chunk = max(1, int(np.ceil(len(words) / chunks_count)))
                for i in range(chunks_count):
                    chunk = words[i * words_per_chunk:(i + 1) * words_per_chunk]
                    if not chunk:
                        continue
                    segments.append({
                        "start": seg["start"] + i * (dur / chunks_count),
                        "end": min(seg["end"], seg["start"] + (i + 1) * (dur / chunks_count)),
                        "text": " ".join(chunk),
                    })
            else:
                segments.append(seg)

        # 2) Translation / recap rewrite
        detected_lang = getattr(info, "language", None) or "en"
        progress(0.20, desc=f"🧠 02/06 • Burmese recap ပြောင်းနေသည် ({detected_lang})...")
        segments = translate_segments_batch(
            segments, user_api_key, source_lang=detected_lang, tone_style=tone_style
        )

        # 3) TTS — Edge-TTS / VoxCPM2 Voice Design / VoxCPM2 Voice Clone
        engine_label = str(voice_engine or "⚡ Edge TTS")
        progress(0.33, desc=f"🎙️ 03/06 • {engine_label} ပြင်ဆင်နေသည်...")
        audio_segments, subtitle_segments = [], []
        total_adjusted_duration = 0.0
        total_segments = max(1, len(segments))

        clone_ref_16k = None
        if "Voice Clone" in engine_label:
            progress(0.34, desc="🎙️ VoxCPM2 • Reference Voice ပြင်ဆင်နေသည်...")
            clone_ref_16k = normalize_clone_reference(clone_reference_path, work_dir)
            progress(0.35, desc="🧠 VoxCPM2 model ကို load လုပ်နေသည်... ပထမအကြိမ်တွင် model download ကြာနိုင်ပါသည်။")
            get_voxcpm_model()
        elif "Voice Design" in engine_label:
            progress(0.35, desc="🧠 VoxCPM2 model ကို load လုပ်နေသည်... ပထမအကြိမ်တွင် model download ကြာနိုင်ပါသည်။")
            get_voxcpm_model()

        for idx, seg in enumerate(segments):
            mm_text = (seg.get("mm_text") or seg["text"]).replace(" ြ", "ြ").replace("ြ ", "ြ").strip()
            if not mm_text:
                continue
            orig_dur = max(0.15, float(seg.get("end", 0.0)) - float(seg.get("start", 0.0)))

            if engine_label.startswith("⚡"):
                audio_path = os.path.join(work_dir, f"tts_{idx:04d}.mp3")
                voice_id = EDGE_VOICES.get(edge_voice_name, "my-MM-NilarNeural")
                generate_voice_sync(
                    mm_text, voice_id, audio_path,
                    desired_tts_rate=float(desired_speed), target_duration_sec=orig_dur,
                )
            elif "Voice Design" in engine_label:
                audio_path = os.path.join(work_dir, f"tts_{idx:04d}.wav")
                generate_voxcpm_audio(
                    mm_text, audio_path, mode="design",
                    voice_preset=voice_preset,
                    custom_voice_description=custom_voice_description,
                    desired_speed=desired_speed,
                    cfg_value=voxcpm_cfg,
                    inference_timesteps=voxcpm_steps,
                    seed=(int(voxcpm_seed or 42) + idx),
                )
            else:
                audio_path = os.path.join(work_dir, f"tts_{idx:04d}.wav")
                generate_voxcpm_audio(
                    mm_text, audio_path, mode="clone",
                    reference_wav_path=clone_ref_16k,
                    reference_transcript=clone_transcript,
                    desired_speed=desired_speed,
                    cfg_value=voxcpm_cfg,
                    inference_timesteps=voxcpm_steps,
                    seed=(int(voxcpm_seed or 42) + idx),
                )

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
                continue

            audio_dur = max(0.1, probe_duration(audio_path, fallback=orig_dur))
            subtitle_segments.append({
                "start": total_adjusted_duration,
                "end": total_adjusted_duration + audio_dur,
                "text": mm_text,
            })
            audio_segments.append(audio_path)
            total_adjusted_duration += audio_dur
            progress(
                0.35 + 0.18 * ((idx + 1) / total_segments),
                desc=f"🎙️ 03/06 • {engine_label} {idx + 1}/{total_segments}",
            )

        if not subtitle_segments:
            raise RuntimeError("TTS Voice ဖန်တီး၍ မရပါ။")

        # 4) Merge narration audio and optional BGM.
        progress(0.55, desc="🔊 04/06 • Audio tracks ပေါင်းနေသည်...")
        concat_list = os.path.join(work_dir, "audio_concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for af in audio_segments:
                escaped_path = af.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        merged_voice = os.path.join(work_dir, "voice_track.m4a")
        audio_merge = subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", concat_list,
            "-c:a", "aac", "-b:a", "160k", merged_voice,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        if audio_merge.returncode != 0 or not os.path.exists(merged_voice):
            raise RuntimeError("Voice audio merge failed: " + (audio_merge.stderr or "Unknown error"))

        final_audio = merged_voice
        if bgm_path and os.path.exists(bgm_path):
            mixed_audio = os.path.join(work_dir, "mixed_audio.m4a")
            vol_val = max(0.0, min(1.0, float(bgm_volume) / 100.0))
            mix = subprocess.run([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                "-i", merged_voice, "-stream_loop", "-1", "-i", bgm_path,
                "-filter_complex",
                f"[1:a]volume={vol_val:.4f}[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "[aout]", "-c:a", "aac", "-b:a", "160k", mixed_audio,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
            if mix.returncode == 0 and os.path.exists(mixed_audio):
                final_audio = mixed_audio

        # 5) Build ASS subtitles once. FFmpeg/libass burns them in C instead of PIL on every frame.
        progress(0.62, desc="💬 05/06 • Subtitle track ပြင်ဆင်နေသည်...")
        target_w, target_h = (720, 1280) if ratio_select == "9:16 (TikTok/Reels)" else (1280, 720)
        render_fps = 24 if "Turbo" in str(render_mode) else 30
        ass_path = os.path.join(work_dir, "recap_subtitles.ass")
        build_ass_subtitles(
            subtitle_segments, ass_path, target_w, target_h,
            subtitle_size_percent, sub_pos_percent, text_color, stroke_color
        )

        # 6) ONE-PASS render: background + resize + mirror + blur band + logo + subtitles + audio.
        progress(0.70, desc=f"🚀 06/06 • Fast Render စနေသည် — {RENDER_ENGINE_LABEL}")

        input_args = ["-stream_loop", "-1", "-i", video_path]
        logo_idx = None
        next_idx = 1
        if logo_path and os.path.exists(logo_path):
            logo_idx = next_idx
            input_args.extend(["-loop", "1", "-i", logo_path])
            next_idx += 1
        audio_idx = next_idx
        input_args.extend(["-i", final_audio])

        filter_graph = build_video_filter_graph(
            target_w=target_w,
            target_h=target_h,
            render_fps=render_fps,
            total_duration=total_adjusted_duration,
            background_fill=background_fill,
            enable_zoom=enable_zoom,
            zoom_level=zoom_level,
            mirror_flip=mirror_flip,
            filter_color=filter_color,
            blur_y_percent=blur_y_percent,
            blur_height_percent=blur_height_percent,
            blur_strength=blur_strength,
            ass_path=ass_path,
            logo_input_index=logo_idx,
        )
        filter_script = os.path.join(work_dir, "video_filters.txt")
        with open(filter_script, "w", encoding="utf-8") as f:
            f.write(filter_graph)

        base_cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            *input_args,
            "-filter_complex_script", filter_script,
            "-map", "[vout]", "-map", f"{audio_idx}:a:0",
            "-t", f"{total_adjusted_duration:.3f}",
            "-r", str(render_fps),
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
        ]

        # GPU encoder first when available. If NVENC fails, automatically retry on CPU.
        if HAS_NVENC:
            nvenc_cmd = base_cmd + [
                "-c:v", "h264_nvenc", "-preset", "p2" if render_fps == 24 else "p4",
                "-cq", "24" if render_fps == 24 else "21",
                "-b:v", "0", output_video_path,
            ]
            try:
                run_ffmpeg_with_progress(
                    nvenc_cmd, total_adjusted_duration, progress,
                    start=0.70, end=0.98, desc="⚡ GPU Rendering"
                )
            except Exception as gpu_error:
                print(f"⚠️ NVENC failed, falling back to CPU: {gpu_error}")
                if os.path.exists(output_video_path):
                    try: os.remove(output_video_path)
                    except OSError: pass
                cpu_cmd = base_cmd + [
                    "-c:v", "libx264", "-preset", "veryfast" if render_fps == 24 else "fast",
                    "-crf", "24" if render_fps == 24 else "21",
                    output_video_path,
                ]
                run_ffmpeg_with_progress(
                    cpu_cmd, total_adjusted_duration, progress,
                    start=0.70, end=0.98, desc="🚀 CPU Fast Rendering"
                )
        else:
            cpu_cmd = base_cmd + [
                "-c:v", "libx264", "-preset", "veryfast" if render_fps == 24 else "fast",
                "-crf", "24" if render_fps == 24 else "21",
                output_video_path,
            ]
            run_ffmpeg_with_progress(
                cpu_cmd, total_adjusted_duration, progress,
                start=0.70, end=0.98, desc="🚀 Fast Rendering"
            )

        if not os.path.exists(output_video_path) or os.path.getsize(output_video_path) < 1024:
            raise RuntimeError("Final video file မထွက်လာပါ။")

        if daily_limit is not None:
            USER_LIMIT_TRACKER[user_identifier]["count"] += 1

        progress(1.0, desc="✅ Recap Video အောင်မြင်စွာ ထုတ်ပြီးပါပြီ။")
        return output_video_path

    except gr.Error:
        raise
    except Exception as e:
        print(f"[PROCESS ERROR] {type(e).__name__}: {e}")
        raise gr.Error(f"❌ အမှားဖြစ်ပါသည်: {e}")
    finally:
        if cap is not None:
            cap.release()


# ================================================================
# 9) VIP UNLOCK VIA MONGODB API
# ================================================================
def unlock_vip(vip_code):
    code_value = (vip_code or "").strip().upper()
    if not code_value:
        return (
            {"authenticated": False},
            gr.update(visible=True),
            gr.update(visible=False),
            "<div class='login-error'>⚠️ VIP Code ထည့်ပါ။</div>",
            ""
        )

    if not HF_SPACE_ID:
        return (
            {"authenticated": False},
            gr.update(visible=True),
            gr.update(visible=False),
            "<div class='login-error'>❌ VIP Admin Space ID မသတ်မှတ်ရသေးပါ။</div>",
            ""
        )

    try:
        # Use positional input for maximum compatibility with Gradio API schemas.
        client = Client(HF_SPACE_ID, token=HF_TOKEN or None, verbose=False)
        result = client.predict(code_value, api_name="/verify")

        # gr.JSON normally returns a dict, but keep compatibility with older Gradio versions.
        if isinstance(result, (list, tuple)) and len(result) == 1:
            result = result[0]

        if isinstance(result, str):
            data = json.loads(result)
        elif isinstance(result, dict):
            data = result
        else:
            try:
                data = dict(result)
            except Exception:
                raise RuntimeError(f"Unexpected verify response type: {type(result).__name__}")

        if not data.get("valid"):
            msg = data.get("msg") or "❌ VIP Code စစ်ဆေးမှု မအောင်မြင်ပါ။"
            return (
                {"authenticated": False},
                gr.update(visible=True),
                gr.update(visible=False),
                f"<div class='login-error'>{msg}</div>",
                ""
            )

        access_state = {
            "authenticated": True,
            "code": data.get("code", code_value),
            "label": data.get("label", "VIP Member"),
            "role": data.get("role", "vip"),
            "daily_limit": data.get("daily_limit"),
            "expiry": data.get("expiry", ""),
        }

        quota = (
            "Unlimited Videos"
            if access_state["daily_limit"] is None
            else f"{access_state['daily_limit']} Videos / 24 Hours"
        )

        member_html = f"""
        <div class="member-strip">
            <div>
                <div class="member-small">ACCESS GRANTED ({access_state['expiry']} အထိ)</div>
                <div class="member-name">👑 {access_state['label']} ({str(access_state['role']).upper()})</div>
            </div>
            <div class="quota-badge">{quota}</div>
        </div>
        """

        return (
            access_state,
            gr.update(visible=False),
            gr.update(visible=True),
            "<div class='login-success'>✅ VIP Access Granted</div>",
            member_html
        )

    except json.JSONDecodeError:
        return (
            {"authenticated": False},
            gr.update(visible=True),
            gr.update(visible=False),
            "<div class='login-error'>❌ Admin API response format မမှန်ပါ။</div>",
            ""
        )
    except Exception as e:
        print(f"[VIP API ERROR] Space={HF_SPACE_ID} | {type(e).__name__}: {e}")
        return (
            {"authenticated": False},
            gr.update(visible=True),
            gr.update(visible=False),
            "<div class='login-error'>❌ VIP Server ကို ချိတ်ဆက်၍မရပါ။ Admin Space/API ကို စစ်ပါ။</div>",
            ""
        )

def logout_vip():
    return ({"authenticated": False}, gr.update(visible=True), gr.update(visible=False), "<div class='login-muted'>VIP Code ဖြင့် ပြန်ဝင်နိုင်ပါသည်။</div>", "", "")

# ================================================================
# 10) MAIN APP INTERFACE
# ================================================================
def create_app_legacy():
    css = """
    :root {
      --bg-0:#050713; --bg-1:#090d1d; --panel:rgba(13,18,38,.88);
      --panel-2:rgba(20,27,55,.82); --line:rgba(139,125,255,.24);
      --purple:#8b5cf6; --violet:#a78bfa; --cyan:#22d3ee;
      --green:#34d399; --gold:#f8d477; --text:#f8fafc; --muted:#9aa6c4;
    }
    body, .gradio-container { background: radial-gradient(circle at 15% 0%, #18204b 0, transparent 32%), radial-gradient(circle at 90% 8%, #341b62 0, transparent 28%), linear-gradient(180deg,var(--bg-1),var(--bg-0)) !important; }
    .gradio-container { max-width: 1320px !important; margin: 0 auto !important; color:var(--text) !important; padding-bottom:36px !important; }
    .hero-pro { position:relative; overflow:hidden; padding:30px 32px; border:1px solid var(--line); border-radius:28px; background:linear-gradient(135deg,rgba(25,32,70,.94),rgba(15,18,38,.94)); box-shadow:0 24px 80px rgba(0,0,0,.32); margin:10px 0 20px; }
    .hero-pro:after { content:""; position:absolute; width:260px; height:260px; right:-70px; top:-90px; border-radius:50%; background:radial-gradient(circle,rgba(34,211,238,.20),transparent 66%); }
    .brand-row { display:flex; align-items:center; gap:14px; margin-bottom:10px; }
    .brand-mark { width:64px; height:64px; border-radius:20px; display:grid; place-items:center; font-size:24px; font-weight:950; color:#fff; background:linear-gradient(135deg, rgba(124,58,237,.95), rgba(6,182,212,.92)); border:1px solid rgba(255,255,255,.16); box-shadow:0 12px 32px rgba(34,211,238,.18); }
    .brand-text { display:flex; flex-direction:column; gap:4px; }
    .brand-kicker { color:#8ff5d1; font-size:12px; font-weight:900; letter-spacing:.14em; }
    .brand-name { color:#ffffff; font-size:24px; font-weight:950; line-height:1; }
    .brand-tag { color:var(--muted); font-size:12px; }
    .top-badge { display:inline-flex; align-items:center; gap:8px; padding:7px 12px; border-radius:999px; background:rgba(52,211,153,.10); border:1px solid rgba(52,211,153,.24); color:#8ff5d1; font-size:12px; font-weight:800; letter-spacing:.08em; }
    .hero-title { margin:12px 0 8px; font-size:clamp(30px,5vw,52px); line-height:1.02; font-weight:950; letter-spacing:-.04em; background:linear-gradient(90deg,#fff 0%,#c4b5fd 48%,#67e8f9 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; }
    .hero-sub { color:var(--muted); font-size:14px; max-width:780px; }
    .mini-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; margin-top:18px; }
    .mini-card { padding:11px 13px; border-radius:14px; background:rgba(8,12,28,.55); border:1px solid rgba(148,163,184,.14); }
    .mini-card b { display:block; color:#eef2ff; font-size:13px; }
    .mini-card span { color:#7f8aa8; font-size:11px; }
    .glass-card, .login-card-pro { border:1px solid var(--line) !important; background:linear-gradient(180deg,rgba(19,25,52,.90),rgba(10,14,31,.92)) !important; border-radius:22px !important; padding:16px !important; box-shadow:0 15px 45px rgba(0,0,0,.20); }
    .login-shell-pro { max-width:640px; margin:24px auto 50px !important; }
    .login-card-pro { padding:28px !important; }
    .login-icon { width:58px; height:58px; display:grid; place-items:center; margin:0 auto 12px; border-radius:18px; background:linear-gradient(135deg,rgba(139,92,246,.30),rgba(34,211,238,.18)); border:1px solid rgba(167,139,250,.32); font-size:28px; }
    .login-head { text-align:center; font-size:25px; font-weight:900; margin:0; color:#fff; }
    .login-copy { text-align:center; color:var(--muted); margin:7px 0 18px; font-size:13px; }
    .login-error,.login-success,.login-muted { padding:11px 14px; border-radius:13px; text-align:center; margin-top:10px; font-size:13px; }
    .login-error { background:rgba(239,68,68,.11); border:1px solid rgba(239,68,68,.26); color:#fecaca; }
    .login-success { background:rgba(52,211,153,.11); border:1px solid rgba(52,211,153,.28); color:#a7f3d0; }
    .login-muted { background:rgba(148,163,184,.08); border:1px solid rgba(148,163,184,.16); color:#cbd5e1; }
    .member-strip { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:14px 16px; border:1px solid rgba(52,211,153,.22); border-radius:18px; background:linear-gradient(90deg,rgba(52,211,153,.08),rgba(34,211,238,.04)); margin-bottom:12px; }
    .member-small { color:#7dd3fc; font-size:10px; font-weight:800; letter-spacing:.08em; }
    .member-name { color:#fff; font-size:15px; font-weight:850; margin-top:2px; }
    .quota-badge { white-space:nowrap; border:1px solid rgba(248,212,119,.28); color:var(--gold); background:rgba(248,212,119,.07); border-radius:999px; padding:7px 11px; font-size:11px; font-weight:800; }
    .section-cap { display:flex; align-items:center; gap:10px; margin:2px 0 11px; font-weight:900; color:#e8eaff; }
    .section-cap span { display:grid; place-items:center; width:31px; height:31px; border-radius:10px; background:rgba(139,92,246,.15); border:1px solid rgba(139,92,246,.22); }
    .engine-box { padding:11px 13px; border-radius:14px; border:1px solid rgba(34,211,238,.18); background:rgba(34,211,238,.055); color:#bae6fd; font-size:12px; margin-bottom:10px; }
    .voice-note { padding:10px 12px; border-radius:12px; background:rgba(139,92,246,.07); border:1px solid rgba(167,139,250,.16); color:#c4b5fd; font-size:11px; line-height:1.55; margin:4px 0 10px; }
    .clone-note { padding:10px 12px; border-radius:12px; background:rgba(245,158,11,.07); border:1px solid rgba(245,158,11,.18); color:#fde68a; font-size:11px; line-height:1.55; }
    .voice-engine-shell { padding:12px; border-radius:16px; border:1px solid rgba(34,211,238,.16); background:linear-gradient(135deg,rgba(34,211,238,.045),rgba(139,92,246,.045)); margin-top:8px; }
    .clone-always-card { margin-top:12px !important; padding:14px !important; border:1px solid rgba(245,158,11,.22) !important; border-radius:18px !important; background:linear-gradient(180deg,rgba(65,39,12,.26),rgba(23,18,34,.56)) !important; }
    .clone-title-row { display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:6px; }
    .clone-title { color:#fff7d6; font-size:14px; font-weight:900; }
    .clone-ready-pill { border:1px solid rgba(52,211,153,.25); background:rgba(52,211,153,.09); color:#a7f3d0; border-radius:999px; padding:5px 9px; font-size:10px; font-weight:900; letter-spacing:.06em; }
    .clone-sub { color:#d8c79b; font-size:11px; line-height:1.55; margin-bottom:10px; }
    .ref-status { margin-top:8px; padding:9px 11px; border-radius:11px; font-size:11px; line-height:1.45; }
    .ref-status.ok { border:1px solid rgba(52,211,153,.22); background:rgba(52,211,153,.07); color:#bbf7d0; }
    .ref-status.warn { border:1px solid rgba(245,158,11,.22); background:rgba(245,158,11,.07); color:#fde68a; }
    #voice-engine-radio label { border-radius:13px !important; }
    #voice-preview-btn { border-radius:14px !important; font-weight:850 !important; }
    #check-ref-btn { border-radius:12px !important; }
    #generate-btn { min-height:60px !important; border:0 !important; border-radius:17px !important; font-size:17px !important; font-weight:950 !important; letter-spacing:.02em; color:white !important; background:linear-gradient(100deg,#7c3aed 0%,#8b5cf6 42%,#06b6d4 100%) !important; box-shadow:0 13px 36px rgba(124,58,237,.30) !important; }
    #generate-btn:hover { transform:translateY(-1px); filter:brightness(1.06); }
    #logout-btn { border-radius:12px !important; }
    .output-card { border-color:rgba(52,211,153,.18) !important; }
    .footer-note { text-align:center; color:#65708e; font-size:11px; padding:18px 0 2px; }
    @media (max-width:760px) { .hero-pro{padding:22px 18px}.mini-grid{grid-template-columns:1fr}.member-strip{align-items:flex-start;flex-direction:column}.quota-badge{align-self:flex-start} }
    """
    theme = gr.themes.Soft(primary_hue="violet", secondary_hue="cyan", neutral_hue="slate")

    # Browser-side guard for temporary Quick-Tunnel reconnects.
    # It keeps the page warm, shows a small connection indicator, and removes only
    # Gradio's transient reconnect toast (real app errors are left untouched).
    connection_js = r"""
    () => {
      if (window.__YF_RECAP_CONNECTION_GUARD__) return;
      window.__YF_RECAP_CONNECTION_GUARD__ = true;

      const badge = document.createElement('div');
      badge.id = 'yf-connection-badge';
      badge.style.cssText = [
        'position:fixed','right:14px','bottom:14px','z-index:99999',
        'padding:7px 11px','border-radius:999px','font-size:11px','font-weight:800',
        'font-family:Arial,sans-serif','backdrop-filter:blur(12px)',
        'border:1px solid rgba(52,211,153,.28)','background:rgba(6,24,30,.82)',
        'color:#a7f3d0','box-shadow:0 8px 24px rgba(0,0,0,.22)'
      ].join(';');
      badge.textContent = '● YF Cloud Connected';
      document.body.appendChild(badge);

      const setBadge = (ok) => {
        if (ok) {
          badge.textContent = '● YF Cloud Connected';
          badge.style.color = '#a7f3d0';
          badge.style.borderColor = 'rgba(52,211,153,.28)';
          badge.style.background = 'rgba(6,24,30,.82)';
        } else {
          badge.textContent = '● Reconnecting…';
          badge.style.color = '#fde68a';
          badge.style.borderColor = 'rgba(245,158,11,.35)';
          badge.style.background = 'rgba(40,25,8,.88)';
        }
      };

      async function pingYF() {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 7000);
        try {
          const r = await fetch(location.origin + '/', {
            method: 'HEAD', cache: 'no-store', credentials: 'same-origin', signal: controller.signal
          });
          setBadge(r.ok || r.status < 500);
        } catch (_) {
          setBadge(false);
        } finally {
          clearTimeout(timer);
        }
      }

      // Keep the Quick Tunnel path active without hammering the server.
      pingYF();
      setInterval(pingYF, 20000);

      // Gradio retries automatically. Hide only the temporary reconnect toast so
      // the editor is not covered by a large error popup during a short reconnect.
      setInterval(() => {
        document.querySelectorAll('[role="alert"]').forEach((el) => {
          const t = (el.innerText || '').toLowerCase();
          if (t.includes('connection to the server was lost') && t.includes('attempting reconnection')) {
            const buttons = el.querySelectorAll('button');
            if (buttons.length) {
              buttons[buttons.length - 1].click();
            } else {
              el.style.display = 'none';
            }
          }
        });
      }, 1200);
    }
    """

    with gr.Blocks(title="⚡ YF Recap • VoxCPM2 Full Voice Studio") as app:
        app._yf_theme = theme
        app._yf_css = css
        app._yf_js = connection_js
        session_id_state = gr.State(lambda: str(uuid.uuid4()))
        vip_access_state = gr.State({"authenticated": False})

        gr.HTML(f"""
        <section class="hero-pro">
          <div class="brand-row">
            <div class="brand-mark">YF</div>
            <div class="brand-text">
              <div class="brand-kicker">NEXT UI DESIGN</div>
              <div class="brand-name">YF Recap</div>
              <div class="brand-tag">Premium movie recap studio • External Voice Upload • VoxCPM2 Clone</div>
            </div>
          </div>
          <div class="top-badge">● FAST ENGINE ONLINE</div>
          <div class="hero-title">YF Recap Studio</div>
          <div class="hero-sub">Movie → Speech-to-Text → Burmese AI Recap → Voice → Styled Subtitle → One-Pass Fast Render</div>
          <div class="mini-grid">
            <div class="mini-card"><b>⚡ One-Pass Render</b><span>FFmpeg filter pipeline</span></div>
            <div class="mini-card"><b>🎮 {RENDER_ENGINE_LABEL}</b><span>GPU auto / CPU fallback</span></div>
            <div class="mini-card"><b>💬 Burmese Subtitle</b><span>libass + Myanmar font</span></div>
          </div>
        </section>
        """)

        with gr.Column(visible=True, elem_classes=["login-shell-pro"]) as login_panel:
            with gr.Column(elem_classes=["login-card-pro"]):
                gr.HTML("""
                <div class="login-icon">YF</div>
                <div class="login-head">YF Recap Access</div>
                <div class="login-copy">Admin Portal မှ ထုတ်ပေးထားသော YF Recap VIP Code ကို ထည့်ပါ</div>
                """)
                vip_code_input = gr.Textbox(
                    label="VIP ACCESS CODE", placeholder="VIP-XXXX-XXXX-XXXX", type="password"
                )
                unlock_btn = gr.Button("🔓 ENTER YF RECAP", variant="primary", elem_id="generate-btn")
                login_status = gr.HTML()

        with gr.Column(visible=False) as main_panel:
            with gr.Row():
                with gr.Column(scale=9):
                    member_status_html = gr.HTML()
                with gr.Column(scale=1, min_width=100):
                    logout_btn = gr.Button("Logout", variant="secondary", elem_id="logout-btn")

            with gr.Row(equal_height=False):
                with gr.Column(scale=7):
                    with gr.Column(elem_classes=["glass-card"]):
                        gr.HTML('<div class="section-cap"><span>🎬</span> Source Video</div>')
                        video_input = gr.Video(label="Upload Original Movie / Clip", sources=["upload"])
                    with gr.Column(elem_classes=["glass-card"]):
                        gr.HTML('<div class="section-cap"><span>👁</span> Manual Subtitle Blur Editor</div>')
                        blur_editor = gr.HTML(
                            value=video_first_frame_data_uri,
                            inputs=[video_input],
                            html_template=BLUR_EDITOR_TEMPLATE,
                            css_template=BLUR_EDITOR_CSS,
                            js_on_load=BLUR_EDITOR_JS,
                            apply_default_css=False,
                            container=False,
                        )

                with gr.Column(scale=5):
                    with gr.Column(elem_classes=["glass-card"]):
                        gr.HTML('<div class="section-cap"><span>🧠</span> AI Recap</div>')
                        user_api_key = gr.Textbox(
                            label="Gemini API Key (Optional)", type="password",
                            placeholder="Story Recap quality အတွက် Gemini API Key ထည့်ပါ — မထည့်ပါက literal Google Translate backup သုံးမည်"
                        )
                        tone_style = gr.Dropdown(
                            choices=["Viral Story Recap", "Thriller", "Comedy", "Dramatic", "Action/Epic", "Neutral"],
                            value="Viral Story Recap", label="Narrative Tone"
                        )
                        with gr.Column(elem_classes=["voice-engine-shell"]):
                            voice_engine = gr.Radio(
                                choices=[
                                    "⚡ Edge TTS • Fast",
                                    "🎨 VoxCPM2 Voice Design",
                                    "🎙️ VoxCPM2 Voice Clone",
                                ],
                                value="⚡ Edge TTS • Fast",
                                label="🎙️ Voice Engine",
                                elem_id="voice-engine-radio",
                            )

                            with gr.Column(visible=True) as edge_voice_panel:
                                edge_voice_select = gr.Dropdown(
                                    choices=list(EDGE_VOICES.keys()),
                                    value="👩 Myanmar Female • Nilar",
                                    label="Standard Burmese Voice",
                                )

                            with gr.Column(visible=False) as voxcpm_design_panel:
                                gr.HTML('<div class="voice-note">🎨 <b>VoxCPM2 Voice Design</b> • Reference အသံမလိုပါ။ Preset သို့ Custom Voice Description နဲ့ narration voice အသစ်ဖန်တီးနိုင်ပါတယ်။</div>')
                                voice_preset = gr.Dropdown(
                                    choices=list(VOXCPM_VOICE_PRESETS.keys()),
                                    value="🎬 Deep Male Movie Narrator",
                                    label="Voice Style",
                                )
                                custom_voice_description = gr.Textbox(
                                    label="Custom Voice Description",
                                    placeholder="ဥပမာ: Mature female narrator, elegant, dramatic, calm, clear Burmese pronunciation",
                                    lines=2,
                                )

                        # External voice upload stays visible for every engine.
                        # It is consumed only when VoxCPM2 Voice Clone is selected.
                        with gr.Column(visible=True, elem_classes=["clone-always-card"]) as voxcpm_clone_panel:
                            gr.HTML("""
                            <div class="clone-title-row">
                              <div class="clone-title">🎙️ External Voice • VoxCPM2 Clone</div>
                              <div class="clone-ready-pill">ALWAYS READY</div>
                            </div>
                            <div class="clone-sub">
                              အပြင်က MP3/WAV အသံကို ဒီနေရာမှာ အချိန်မရွေး upload လုပ်ထားနိုင်ပါတယ်။
                              Voice Engine ကို <b>VoxCPM2 Voice Clone</b> ရွေးထားတဲ့အခါမှ ဒီ reference အသံကို final narration အတွက် အသုံးပြုပါမယ်။
                              5–15 sec ကြည်လင်ပြီး background music မပါတဲ့ speech ကို အကြံပြုပါတယ်။
                            </div>
                            """)
                            clone_reference = gr.Audio(
                                label="📤 External Reference Voice • MP3 / WAV / Mic",
                                sources=["upload", "microphone"],
                                type="filepath",
                            )
                            clone_check_btn = gr.Button("✓ Check Reference", variant="secondary", elem_id="check-ref-btn")
                            clone_reference_status = gr.HTML(
                                "<div class='ref-status warn'>Reference voice မထည့်ရသေးပါ။ MP3/WAV upload သို့ mic record လုပ်နိုင်ပါတယ်။</div>"
                            )
                            clone_transcript = gr.Textbox(
                                label="Reference Transcript • Optional",
                                placeholder="Reference audio ထဲမှာပြောထားတဲ့ စာသားကို အတိအကျရေးပါ။ မထည့်လည်း zero-shot clone သုံးနိုင်ပါတယ်။",
                                lines=2,
                            )
                            clone_consent = gr.Checkbox(
                                label="ဒီ reference အသံကို clone အသုံးပြုရန် ခွင့်ပြုချက်ရှိပါသည်",
                                value=False,
                            )

                        desired_speed = gr.Slider(0.9, 1.6, value=1.25, step=0.05, label="Voice Pace")
                        with gr.Accordion("⚙️ VoxCPM2 Quality Settings", open=False):
                            voxcpm_cfg = gr.Slider(1.0, 3.0, value=2.0, step=0.1, label="CFG Guidance")
                            voxcpm_steps = gr.Slider(4, 20, value=10, step=1, label="Inference Steps")
                            voxcpm_seed = gr.Number(value=42, precision=0, label="Seed")
                        voice_preview_btn = gr.Button("▶ Preview Selected Voice", variant="secondary", elem_id="voice-preview-btn")
                        voice_preview_audio = gr.Audio(label="Voice Preview", interactive=False)

                    with gr.Column(elem_classes=["glass-card"]):
                        gr.HTML('<div class="section-cap"><span>🚀</span> Performance</div>')
                        gr.HTML(f'<div class="engine-box">Render Engine: <b>{RENDER_ENGINE_LABEL}</b><br>Turbo mode သည် 24 FPS ဖြင့် frame အရေအတွက်လျှော့ပြီး ပိုမြန်စေပါသည်။</div>')
                        render_mode = gr.Radio(
                            choices=["⚡ Turbo 24 FPS (Recommended)", "🎬 Balanced 30 FPS"],
                            value="⚡ Turbo 24 FPS (Recommended)", label="Render Mode"
                        )
                        ratio_select = gr.Dropdown(
                            choices=["9:16 (TikTok/Reels)", "16:9 (Landscape)"],
                            value="9:16 (TikTok/Reels)", label="Output Ratio"
                        )
                        background_fill = gr.Radio(
                            choices=["Blur Background", "Black Background"],
                            value="Blur Background", label="Background Fill"
                        )

            with gr.Row(equal_height=False):
                with gr.Column(elem_classes=["glass-card"]):
                    gr.HTML('<div class="section-cap"><span>💬</span> Subtitle Design</div>')
                    with gr.Row():
                        text_color_input = gr.ColorPicker(label="Text", value="#FFFF00")
                        stroke_color_input = gr.ColorPicker(label="Outline", value="#000000")
                    sub_pos_percent = gr.Slider(0, 60, value=15, step=1, label="Bottom Position (%)")
                    subtitle_size_percent = gr.Slider(2.0, 7.0, value=3.8, step=0.1, label="Font Size (%)")

                with gr.Column(elem_classes=["glass-card"]):
                    gr.HTML("""<div class="section-cap"><span>🌫</span> Blur Strength</div>
                    <div class="engine-box">
                      <b>Position & Height</b> ကို အပေါ်က video preview ပေါ်မှာ mouse နဲ့တိုက်ရိုက် drag/resize လုပ်ပါ။
                      ဒီနေရာမှာ final blur အားကိုပဲ ချိန်ရပါမယ်။
                    </div>""")
                    blur_y_percent = gr.Number(value=78, visible=False)
                    blur_height_percent = gr.Number(value=12, visible=False)
                    blur_strength = gr.Slider(5, 151, value=51, step=2, label="Final Blur Strength")

            with gr.Accordion("✨ Brand, BGM & Advanced", open=False):
                with gr.Row():
                    bgm_file = gr.Audio(label="Background Music", type="filepath")
                    bgm_vol = gr.Slider(1, 50, value=15, step=1, label="BGM Volume (%)")
                with gr.Row():
                    logo_file = gr.File(label="Logo PNG", file_types=["image"])
                    filter_color = gr.Dropdown(
                        choices=["None", "Chrome Cool", "Warm Cinema"], value="None", label="Color Look"
                    )
                with gr.Row():
                    enable_zoom = gr.Checkbox(label="Zoom & Crop", value=False)
                    zoom_level = gr.Slider(1.0, 3.0, value=1.0, step=0.1, label="Zoom Level")
                    mirror_flip = gr.Checkbox(label="Mirror Flip", value=True)

            submit_btn = gr.Button("⚡ GENERATE FAST VIP RECAP", variant="primary", elem_id="generate-btn")

            with gr.Column(elem_classes=["glass-card", "output-card"]):
                gr.HTML('<div class="section-cap"><span>✅</span> Final Output</div>')
                output_video = gr.Video(label="Rendered Recap Video")

            gr.HTML('<div class="footer-note">YF RECAP • External Voice Upload • VoxCPM2 Clone • FFmpeg / NVENC</div>')

        unlock_btn.click(
            unlock_vip, [vip_code_input],
            [vip_access_state, login_panel, main_panel, login_status, member_status_html]
        )
        vip_code_input.submit(
            unlock_vip, [vip_code_input],
            [vip_access_state, login_panel, main_panel, login_status, member_status_html]
        )
        logout_btn.click(
            logout_vip, [],
            [vip_access_state, login_panel, main_panel, login_status, member_status_html, vip_code_input]
        )

        voice_engine.change(
            update_voice_engine_panels,
            inputs=[voice_engine],
            outputs=[edge_voice_panel, voxcpm_design_panel, voxcpm_clone_panel],
        )
        clone_check_btn.click(
            fn=inspect_clone_reference,
            inputs=[clone_reference],
            outputs=[clone_reference_status],
        )
        clone_reference.change(
            fn=inspect_clone_reference,
            inputs=[clone_reference],
            outputs=[clone_reference_status],
        )

        voice_preview_btn.click(
            fn=generate_voice_preview,
            inputs=[
                voice_engine, edge_voice_select, voice_preset, custom_voice_description,
                clone_reference, clone_transcript, clone_consent, desired_speed,
                voxcpm_cfg, voxcpm_steps, voxcpm_seed,
            ],
            outputs=voice_preview_audio,
        )

        blur_editor.change(
            fn=sync_blur_editor,
            outputs=[blur_y_percent, blur_height_percent],
            queue=False,
            show_progress="hidden",
        )

        submit_btn.click(
            fn=process_magic_recap_video,
            inputs=[
                video_input, user_api_key, ratio_select, background_fill, enable_zoom, zoom_level,
                logo_file, bgm_file, bgm_vol, mirror_flip, filter_color,
                voice_engine, edge_voice_select, voice_preset, custom_voice_description,
                clone_reference, clone_transcript, clone_consent,
                voxcpm_cfg, voxcpm_steps, voxcpm_seed, tone_style,
                text_color_input, stroke_color_input, blur_y_percent, blur_height_percent, blur_strength,
                sub_pos_percent, subtitle_size_percent, desired_speed, render_mode,
                session_id_state, vip_access_state
            ],
            outputs=output_video
        )

    return app


# ================================================================
# YF RECAP V3 — STAGED STUDIO WORKFLOW
# Upload -> Analyze -> Script -> Voice -> Layout -> Mixer -> Render
# ================================================================

def _fmt_clock(seconds):
    seconds = max(0.0, float(seconds or 0.0))
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m:02d}:{s:05.2f}"


def _srt_clock(seconds):
    seconds = max(0.0, float(seconds or 0.0))
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        s += 1; ms -= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def group_transcript_scenes(raw_segments, max_scene_seconds=28.0, silence_gap=2.8):
    """Fast narrative-scene grouping from Whisper timing; avoids a second full video decode."""
    scenes, current = [], []
    for seg in raw_segments:
        if not current:
            current = [seg]
            continue
        gap = float(seg["start"]) - float(current[-1]["end"])
        span = float(seg["end"]) - float(current[0]["start"])
        if gap >= silence_gap or span >= max_scene_seconds:
            scenes.append(current)
            current = [seg]
        else:
            current.append(seg)
    if current:
        scenes.append(current)

    out = []
    for i, items in enumerate(scenes, 1):
        text = " ".join((x.get("text") or "").strip() for x in items).strip()
        if not text:
            continue
        out.append({
            "scene": i,
            "start": float(items[0]["start"]),
            "end": float(items[-1]["end"]),
            "text": text,
        })
    return out


def analyze_movie_v3(video_value, vip_access_state, progress=gr.Progress(track_tqdm=False)):
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        raise gr.Error("🎬 Movie/Video upload လုပ်ပါ။")
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        raise gr.Error("🔒 VIP Code ဖြင့် Login ဝင်ပါ။")

    progress(0.08, desc="🎙️ Speech & dialogue ကို Analyze လုပ်နေသည်...")
    segments_raw, info = whisper_model.transcribe(
        video_path, beam_size=1, vad_filter=True, condition_on_previous_text=False
    )
    raw_segments = [
        {"start": float(s.start), "end": float(s.end), "text": (s.text or "").strip()}
        for s in segments_raw if (s.text or "").strip()
    ]

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    duration = (frame_count / fps) if fps > 0 else (raw_segments[-1]["end"] if raw_segments else 0.0)

    if not raw_segments:
        raise gr.Error("🎙️ Video ထဲက speech/dialogue ကို ဖတ်မရပါ။ Audio ပါ/မပါ စစ်ပါ။")

    progress(0.72, desc="🧠 Narrative scenes ခွဲနေသည်...")
    scenes = group_transcript_scenes(raw_segments)
    lang = getattr(info, "language", None) or "en"

    state = {
        "video_path": video_path,
        "duration": float(duration),
        "fps": float(fps),
        "width": width,
        "height": height,
        "language": lang,
        "raw_segments": raw_segments,
        "scenes": scenes,
        "analyzed_at": time.time(),
    }

    rows = []
    for sc in scenes[:160]:
        preview = sc["text"].replace("\n", " ")
        if len(preview) > 150:
            preview = preview[:147] + "..."
        rows.append([sc["scene"], _fmt_clock(sc["start"]), _fmt_clock(sc["end"]), preview])

    progress(1.0, desc="✅ Analyze ပြီးပါပြီ")
    summary = (
        f"### ✅ Movie Analysis Ready\n"
        f"**Duration:** {_fmt_clock(duration)}  ·  **Detected Language:** `{lang}`  ·  "
        f"**Narrative Scenes:** {len(scenes)}  ·  **Speech Chunks:** {len(raw_segments)}\n\n"
        "အောက်က **Generate Viral Recap Script** ကိုနှိပ်ပြီး script ဖန်တီးပါ။"
    )
    return state, summary, rows


def _target_seconds(choice, source_duration):
    mapping = {
        "⚡ 1 Minute Short": 60,
        "🎬 3 Minute Recap": 180,
        "🔥 5 Minute Recap": 300,
        "🍿 10 Minute Recap": 600,
    }
    if choice in mapping:
        return mapping[choice]
    return min(max(90, source_duration * 0.20), 720)


def generate_recap_script_v3(analysis_state, user_api_key, tone_style, recap_length,
                             progress=gr.Progress(track_tqdm=False)):
    if not isinstance(analysis_state, dict) or not analysis_state.get("scenes"):
        raise gr.Error("🧠 အရင်ဆုံး Analyze Movie ကိုနှိပ်ပါ။")

    scenes = analysis_state["scenes"]
    source_duration = float(analysis_state.get("duration", 0.0))
    target_sec = _target_seconds(recap_length, source_duration)
    progress(0.08, desc="✍️ Viral recap structure စီနေသည်...")

    # Keep prompt payload bounded while retaining chronology.
    max_scenes = 110
    if len(scenes) > max_scenes:
        stride = len(scenes) / max_scenes
        selected = [scenes[min(len(scenes)-1, int(i * stride))] for i in range(max_scenes)]
    else:
        selected = scenes

    payload = [
        {
            "scene": int(s["scene"]),
            "start": round(float(s["start"]), 2),
            "end": round(float(s["end"]), 2),
            "source": s["text"][:1300],
        }
        for s in selected
    ]

    script_segments = []
    api_key = (user_api_key or "").strip()
    if api_key:
        prompt = f"""
You are editing a Burmese viral movie recap.
Create a coherent narrator script from the chronological SOURCE SCENES below.

Narrative tone: {tone_style}
Approximate final narration target: {int(target_sec)} seconds.

CRITICAL STORY RULES:
- Retell the story like a skilled Burmese YouTube/TikTok movie recap narrator.
- Use Hook -> clear event explanation -> tension/emotion -> natural transition -> next event.
- Do NOT translate dialogue line by line.
- Select important scenes; skip repetition and filler.
- Never invent unsupported plot facts, motives, characters, objects, or endings.
- Natural spoken Burmese; concise enough for narration.
- Suspense phrases should be used sparingly, only when they fit.
- Every output item MUST use start/end values that come from (or stay inside) a supplied source scene.
- Keep chronological order.

Return VALID JSON ONLY in exactly this shape:
{{"segments":[{{"start":0.0,"end":8.2,"text":"Burmese narration"}}]}}
No markdown and no extra keys.

SOURCE SCENES:
{json.dumps(payload, ensure_ascii=False)}
"""
        try:
            progress(0.25, desc="✨ Gemini က Viral Recap Script ရေးနေသည်...")
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config={"system_instruction": SYSTEM_INSTRUCTION, "temperature": 0.72},
            )
            raw = (response.text or "").strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            for item in parsed.get("segments", []):
                text = str(item.get("text", "")).strip()
                if not text:
                    continue
                st = max(0.0, float(item.get("start", 0.0)))
                en = max(st + 0.35, float(item.get("end", st + 3.0)))
                en = min(max(en, st + 0.35), source_duration if source_duration > 0 else en)
                script_segments.append({"start": st, "end": en, "text": text})
        except Exception as exc:
            print("⚠️ V3 script Gemini fallback:", exc)

    if not script_segments:
        progress(0.35, desc="📝 Backup recap script ပြင်ဆင်နေသည်...")
        # Fallback: use the most informative chronological scenes and translate them.
        desired_count = max(4, min(len(selected), int(target_sec / 12)))
        if len(selected) > desired_count:
            stride = len(selected) / desired_count
            fallback_scenes = [selected[min(len(selected)-1, int(i * stride))] for i in range(desired_count)]
        else:
            fallback_scenes = selected
        temp = [{"start": s["start"], "end": s["end"], "text": s["text"]} for s in fallback_scenes]
        translated = translate_segments_batch(
            temp, api_key, source_lang=analysis_state.get("language", "en"), tone_style=tone_style
        )
        script_segments = [
            {"start": float(s["start"]), "end": float(s["end"]), "text": (s.get("mm_text") or s["text"]).strip()}
            for s in translated if (s.get("mm_text") or s.get("text"))
        ]

    # Keep clean chronology and cap pathological responses.
    script_segments = sorted(script_segments, key=lambda x: x["start"])[:120]
    editor_lines = []
    for i, s in enumerate(script_segments, 1):
        editor_lines.append(
            f"#{i:03d} [{s['start']:.2f} --> {s['end']:.2f}] | {s['text']}"
        )
    editor_text = "\n".join(editor_lines)
    approx_chars = sum(len(s["text"]) for s in script_segments)
    progress(1.0, desc="✅ Script Ready — Review/Edit လုပ်နိုင်ပါပြီ")
    status = (
        f"### ✏️ Script Ready for Review\n"
        f"**Selected scenes:** {len(script_segments)} · **Target:** ~{int(target_sec/60)} min · **Characters:** {approx_chars:,}\n\n"
        "`|` နောက်က Burmese narration ကို လိုသလိုပြင်နိုင်ပါတယ်။ Timestamp ကို မဖျက်ပါနဲ့။"
    )
    return editor_text, status


_SCRIPT_LINE_RE = re.compile(
    r"^\s*#?\d*\s*\[\s*([0-9.]+)\s*-->\s*([0-9.]+)\s*\]\s*\|\s*(.+?)\s*$"
)


def parse_script_editor(text):
    segments = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = _SCRIPT_LINE_RE.match(line)
        if not m:
            continue
        st, en, narration = float(m.group(1)), float(m.group(2)), m.group(3).strip()
        if narration and en > st:
            segments.append({"start": st, "end": en, "text": narration})
    return segments


def write_srt_file(subtitle_segments, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, s in enumerate(subtitle_segments, 1):
            f.write(f"{i}\n{_srt_clock(s['start'])} --> {_srt_clock(s['end'])}\n{s['text']}\n\n")
    return path


def video_has_audio(path):
    r = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "a:0",
        "-show_entries", "stream=index", "-of", "csv=p=0", path
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    return bool((r.stdout or "").strip())


def _atempo_filters(rate):
    rate = max(0.05, min(20.0, float(rate)))
    vals = []
    while rate > 2.0:
        vals.append(2.0); rate /= 2.0
    while rate < 0.5:
        vals.append(0.5); rate /= 0.5
    vals.append(rate)
    return ",".join(f"atempo={v:.6f}" for v in vals)


def build_original_story_audio(video_path, source_segments, voice_durations, output_path):
    if not video_has_audio(video_path) or not source_segments:
        return None
    parts, labels = [], []
    for i, (seg, out_dur) in enumerate(zip(source_segments, voice_durations)):
        st, en = float(seg["start"]), float(seg["end"])
        src_dur = max(0.15, en - st)
        target = max(0.15, float(out_dur))
        rate = src_dur / target
        label = f"oa{i}"
        parts.append(
            f"[0:a]atrim=start={st:.3f}:end={en:.3f},asetpts=PTS-STARTPTS,{_atempo_filters(rate)}[{label}]"
        )
        labels.append(f"[{label}]")
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=0:a=1[origstory]")
    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", video_path,
        "-filter_complex", ";".join(parts), "-map", "[origstory]",
        "-c:a", "aac", "-b:a", "160k", output_path,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode == 0 and os.path.exists(output_path):
        return output_path
    print("⚠️ Original story audio unavailable:", r.stderr[-500:] if r.stderr else "")
    return None


def mix_story_audio(voice_path, original_path, bgm_path, narration_volume, original_volume,
                    bgm_volume, auto_duck_bgm, output_path):
    inputs = ["-i", voice_path]
    orig_idx = None; bgm_idx = None; idx = 1
    if original_path and os.path.exists(original_path) and float(original_volume) > 0:
        orig_idx = idx; inputs += ["-i", original_path]; idx += 1
    if bgm_path and os.path.exists(bgm_path) and float(bgm_volume) > 0:
        bgm_idx = idx; inputs += ["-stream_loop", "-1", "-i", bgm_path]; idx += 1

    nv = max(0.0, min(2.0, float(narration_volume) / 100.0))
    ov = max(0.0, min(1.0, float(original_volume) / 100.0))
    bv = max(0.0, min(1.0, float(bgm_volume) / 100.0))
    if bgm_idx is not None and auto_duck_bgm:
        filters = [f"[0:a]volume={nv:.4f},asplit=2[voicemix][voicesc]"]
        mix_labels = ["[voicemix]"]
    else:
        filters = [f"[0:a]volume={nv:.4f}[voice]"]
        mix_labels = ["[voice]"]
    if orig_idx is not None:
        filters.append(f"[{orig_idx}:a]volume={ov:.4f}[orig]")
        mix_labels.append("[orig]")
    if bgm_idx is not None:
        filters.append(f"[{bgm_idx}:a]volume={bv:.4f}[bgmraw]")
        if auto_duck_bgm:
            filters.append("[bgmraw][voicesc]sidechaincompress=threshold=0.015:ratio=10:attack=12:release=350[bgm]")
        else:
            filters.append("[bgmraw]anull[bgm]")
        mix_labels.append("[bgm]")
    filters.append("".join(mix_labels) + f"amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2,alimiter=limit=0.95[aout]")

    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(filters), "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k", output_path,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("Audio mixer failed: " + (r.stderr or "Unknown error")[-700:])
    return output_path


def build_story_video_filter_graph(source_segments, voice_durations, target_w, target_h, render_fps,
                                   total_duration, background_fill, enable_zoom, zoom_level,
                                   mirror_flip, filter_color, blur_y_percent, blur_height_percent,
                                   blur_strength, ass_path, logo_input_index=None):
    parts, clip_labels = [], []
    for i, (seg, out_dur) in enumerate(zip(source_segments, voice_durations)):
        st, en = float(seg["start"]), float(seg["end"])
        src_dur = max(0.15, en - st)
        out_dur = max(0.15, float(out_dur))
        factor = out_dur / src_dur
        label = f"clip{i}"
        parts.append(
            f"[0:v]trim=start={st:.3f}:end={en:.3f},setpts=(PTS-STARTPTS)*{factor:.8f},fps={render_fps}[{label}]"
        )
        clip_labels.append(f"[{label}]")
    parts.append("".join(clip_labels) + f"concat=n={len(clip_labels)}:v=1:a=0[storysrc]")

    z = max(1.0, float(zoom_level))
    fg_filters = []
    if enable_zoom and z > 1.001:
        fg_filters.append(f"crop=iw/{z:.4f}:ih/{z:.4f}")
    if mirror_flip:
        fg_filters.append("hflip")
    if filter_color == "Chrome Cool":
        fg_filters.append("eq=brightness=0.045:contrast=1.03:saturation=0.92")
    elif filter_color == "Warm Cinema":
        fg_filters.append("eq=brightness=0.025:contrast=1.06:saturation=1.10")
    fg_filters += [f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease", "setsar=1"]
    fg_chain = ",".join(fg_filters)

    if background_fill == "Blur Background":
        parts.append("[storysrc]split=2[vbgsrc][vfgsrc]")
        bg_w, bg_h = max(160, target_w // 4), max(160, target_h // 4)
        parts.append(
            f"[vbgsrc]scale={bg_w}:{bg_h}:force_original_aspect_ratio=increase,crop={bg_w}:{bg_h},"
            f"boxblur=10:1,scale={target_w}:{target_h},setsar=1[bg]"
        )
        parts.append(f"[vfgsrc]{fg_chain}[fg]")
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[base]")
    else:
        parts.append(f"color=c=0x050713:s={target_w}x{target_h}:r={render_fps}:d={total_duration:.3f}[bg]")
        parts.append(f"[storysrc]{fg_chain}[fg]")
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[base]")

    blur_h = max(8, int(target_h * (float(blur_height_percent) / 100.0)))
    center_y = int(target_h * (float(blur_y_percent) / 100.0))
    blur_y = max(0, min(center_y - blur_h // 2, target_h - blur_h))
    radius = max(2, min(32, int(float(blur_strength) / 6)))
    parts.append("[base]split=2[main][bandsrc]")
    parts.append(f"[bandsrc]crop={target_w}:{blur_h}:0:{blur_y},boxblur={radius}:1[band]")
    parts.append(f"[main][band]overlay=0:{blur_y}[blurred]")
    current = "blurred"
    if logo_input_index is not None:
        logo_w = max(72, int(target_w * 0.16))
        parts.append(f"[{logo_input_index}:v]scale={logo_w}:-1[logo]")
        parts.append(f"[{current}][logo]overlay=W-w-24:24:format=auto[withlogo]")
        current = "withlogo"
    ass_escaped = ffmpeg_filter_escape(ass_path)
    font_dir = ffmpeg_filter_escape(os.path.dirname(FONT_PATH) if FONT_PATH else "/usr/share/fonts")
    parts.append(f"[{current}]ass=filename='{ass_escaped}':fontsdir='{font_dir}',format=yuv420p[vout]")
    return ";\n".join(parts)


def render_reviewed_script_v3(
    analysis_state, script_editor,
    ratio_select, background_fill, enable_zoom, zoom_level, logo_value,
    bgm_value, narration_volume, original_volume, bgm_volume, auto_duck_bgm,
    mirror_flip, filter_color,
    voice_engine, edge_voice_name, voice_preset, custom_voice_description,
    clone_reference, clone_transcript, clone_consent,
    voxcpm_cfg, voxcpm_steps, voxcpm_seed,
    text_color, stroke_color, blur_y_percent, blur_height_percent, blur_strength,
    sub_pos_percent, subtitle_size_percent, desired_speed, render_mode,
    session_id, vip_access_state,
    progress=gr.Progress(track_tqdm=False)
):
    if not isinstance(analysis_state, dict) or not analysis_state.get("video_path"):
        raise gr.Error("🧠 အရင် Analyze Movie လုပ်ပါ။")
    script_segments = parse_script_editor(script_editor)
    if not script_segments:
        raise gr.Error("✏️ Script Editor ထဲမှာ valid script မရှိပါ။ Generate Script ပြန်လုပ်ပါ။")
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        raise gr.Error("🔒 VIP Login ပြန်ဝင်ပါ။")

    video_path = analysis_state["video_path"]
    logo_path = normalize_file_path(logo_value)
    bgm_path = normalize_file_path(bgm_value)
    clone_reference_path = normalize_file_path(clone_reference)
    if "Voice Clone" in str(voice_engine):
        if not clone_consent:
            raise gr.Error("🎙️ Voice Clone permission checkbox ကို အမှန်ခြစ်ပါ။")
        if not clone_reference_path or not os.path.exists(clone_reference_path):
            raise gr.Error("🎙️ Reference MP3/WAV upload လုပ်ပါ။")

    work_dir = tempfile.mkdtemp(prefix=f"yf_v3_{str(session_id)[:8]}_")
    voice_files, subtitle_segments, voice_durations, successful_source_segments = [], [], [], []
    timeline = 0.0
    total = len(script_segments)

    progress(0.03, desc="🎙️ Reviewed script ကနေ narration ထုတ်နေသည်...")
    for idx, seg in enumerate(script_segments):
        text = seg["text"].strip()
        src_dur = max(0.3, seg["end"] - seg["start"])
        if "Edge TTS" in str(voice_engine):
            audio = os.path.join(work_dir, f"voice_{idx:03d}.mp3")
            voice_id = EDGE_VOICES.get(edge_voice_name, "my-MM-NilarNeural")
            generate_voice_sync(text, voice_id, audio, desired_tts_rate=desired_speed, target_duration_sec=src_dur)
        else:
            audio = os.path.join(work_dir, f"voice_{idx:03d}.wav")
            generate_voxcpm_audio(
                text, audio,
                mode="clone" if "Voice Clone" in str(voice_engine) else "design",
                voice_preset=voice_preset, custom_voice_description=custom_voice_description,
                reference_wav_path=clone_reference_path, reference_transcript=clone_transcript,
                desired_speed=desired_speed, cfg_value=voxcpm_cfg,
                inference_timesteps=voxcpm_steps, seed=(int(voxcpm_seed or 42) + idx),
            )
        if not os.path.exists(audio) or os.path.getsize(audio) == 0:
            continue
        dur = max(0.15, probe_duration(audio, fallback=src_dur))
        voice_files.append(audio)
        voice_durations.append(dur)
        successful_source_segments.append({"start": float(seg["start"]), "end": float(seg["end"]), "text": text})
        subtitle_segments.append({"start": timeline, "end": timeline + dur, "text": text})
        timeline += dur
        progress(0.04 + 0.37 * ((idx + 1) / total), desc=f"🎙️ Narration {idx+1}/{total}")

    if not voice_files:
        raise gr.Error("Voice narration ထုတ်မရပါ။")
    # Ensure source list matches exactly the voice clips that succeeded.
    source_segments = successful_source_segments

    concat_list = os.path.join(work_dir, "voice_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for p in voice_files:
            f.write("file '" + p.replace("'", "'\\''") + "'\n")
    merged_voice = os.path.join(work_dir, "YF_Recap_Narration.m4a")
    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c:a", "aac", "-b:a", "192k", merged_voice
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0 or not os.path.exists(merged_voice):
        raise RuntimeError("Narration merge failed: " + (r.stderr or "Unknown")[-600:])

    narration_mp3 = os.path.join(work_dir, "YF_Recap_Narration.mp3")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", merged_voice,
                    "-c:a", "libmp3lame", "-b:a", "192k", narration_mp3], check=False)

    progress(0.45, desc="🎚️ Original Audio + BGM Mixer ပြင်နေသည်...")
    original_story = None
    if float(original_volume) > 0:
        original_story = build_original_story_audio(
            video_path, source_segments, voice_durations, os.path.join(work_dir, "original_story.m4a")
        )
    final_audio = mix_story_audio(
        merged_voice, original_story, bgm_path, narration_volume, original_volume,
        bgm_volume, auto_duck_bgm, os.path.join(work_dir, "final_mix.m4a")
    )

    target_w, target_h = (720, 1280) if ratio_select == "9:16 (TikTok/Reels)" else (1280, 720)
    render_fps = 24 if "Turbo" in str(render_mode) else 30
    ass_path = os.path.join(work_dir, "YF_Recap_Subtitles.ass")
    build_ass_subtitles(subtitle_segments, ass_path, target_w, target_h,
                        subtitle_size_percent, sub_pos_percent, text_color, stroke_color)
    srt_path = write_srt_file(subtitle_segments, os.path.join(work_dir, "YF_Recap_Subtitles.srt"))
    script_path = os.path.join(work_dir, "YF_Recap_Script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script_editor.strip() + "\n")

    progress(0.58, desc=f"⚡ Scene-aligned Fast Render — {RENDER_ENGINE_LABEL}")
    input_args = ["-i", video_path]
    logo_idx = None; next_idx = 1
    if logo_path and os.path.exists(logo_path):
        logo_idx = next_idx
        input_args += ["-loop", "1", "-i", logo_path]
        next_idx += 1
    audio_idx = next_idx
    input_args += ["-i", final_audio]

    graph = build_story_video_filter_graph(
        source_segments, voice_durations, target_w, target_h, render_fps, timeline,
        background_fill, enable_zoom, zoom_level, mirror_flip, filter_color,
        blur_y_percent, blur_height_percent, blur_strength, ass_path, logo_idx
    )
    graph_path = os.path.join(work_dir, "story_filters.txt")
    Path(graph_path).write_text(graph, encoding="utf-8")
    out_video = os.path.join(work_dir, "YF_Recap_Final.mp4")
    base = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *input_args,
        "-filter_complex_script", graph_path, "-map", "[vout]", "-map", f"{audio_idx}:a:0",
        "-t", f"{timeline:.3f}", "-r", str(render_fps), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
    ]
    if HAS_NVENC:
        cmd = base + ["-c:v", "h264_nvenc", "-preset", "p3", "-cq", "23", "-b:v", "0", out_video]
        try:
            run_ffmpeg_with_progress(cmd, timeline, progress, 0.60, 0.97, "⚡ GPU Story Render")
        except Exception as exc:
            print("⚠️ NVENC fallback:", exc)
            cmd = base + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", out_video]
            run_ffmpeg_with_progress(cmd, timeline, progress, 0.60, 0.97, "🚀 CPU Story Render")
    else:
        cmd = base + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", out_video]
        run_ffmpeg_with_progress(cmd, timeline, progress, 0.60, 0.97, "🚀 CPU Story Render")

    if not os.path.exists(out_video):
        raise RuntimeError("Final MP4 was not created.")
    progress(1.0, desc="✅ YF Recap V3 Complete")
    return out_video, srt_path, narration_mp3, script_path, "### ✅ Export Complete\nMP4 + SRT + MP3 + Script အားလုံးအဆင်သင့်ဖြစ်ပါပြီ။"


# ---- Combined manual layout editor: Blur band + Subtitle vertical position ----
def sync_layout_editor(evt: gr.EventData):
    try:
        center = float(evt.center)
        height = float(evt.height)
        subtitle_bottom = float(evt.subtitleBottom)
    except Exception:
        return 78.0, 12.0, 15.0
    height = max(3.0, min(45.0, height))
    center = max(height/2, min(100-height/2, center))
    subtitle_bottom = max(2.0, min(65.0, subtitle_bottom))
    return round(center, 2), round(height, 2), round(subtitle_bottom, 2)


LAYOUT_EDITOR_TEMPLATE = r"""
<div class="yf-layout-editor">
  <div class="yf-layout-head"><div><b>✋ Drag Layout Editor</b><small>Purple = Blur • Yellow = Subtitle position</small></div><button type="button" class="yf-reset">Reset</button></div>
  <div class="yf-stage">
    <img class="yf-img" src="${value}" draggable="false">
    <div class="yf-empty">🎬 Video upload ပြီး Blur + Subtitle ကို mouse နဲ့တိုက်ရိုက်ညှိပါ</div>
    <div class="yf-blur"><i class="yf-top"></i><span>⋮⋮ DRAG BLUR ⋮⋮</span><i class="yf-bottom"></i></div>
    <div class="yf-sub"><span>SUBTITLE • DRAG UP / DOWN</span></div>
  </div>
  <div class="yf-read"><span>Blur <b class="yc">78%</b></span><span>Height <b class="yh">12%</b></span><span>Subtitle Bottom <b class="ys">15%</b></span><em>✓ Final render synced</em></div>
</div>
"""

LAYOUT_EDITOR_CSS = r"""
.yf-layout-editor{width:100%;color:#eef2ff;user-select:none}.yf-layout-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px}.yf-layout-head b{font-size:14px}.yf-layout-head small{display:block;color:#8896b7;margin-top:3px}.yf-reset{border:1px solid #554c88;background:#17152d;color:#ddd6fe;border-radius:10px;padding:7px 11px;cursor:pointer}.yf-stage{position:relative;overflow:hidden;min-height:280px;border-radius:18px;border:1px solid #34345e;background:#050713;touch-action:none}.yf-img{display:block;width:100%;height:auto;min-height:280px;max-height:620px;object-fit:contain;pointer-events:none}.yf-empty{position:absolute;inset:0;display:grid;place-items:center;color:#71809f;background:#090d1df0;padding:20px;text-align:center}.yf-stage.ready .yf-empty{display:none}.yf-blur{position:absolute;left:0;top:72%;height:12%;width:100%;min-height:25px;border-top:2px solid #a78bfa;border-bottom:2px solid #22d3ee;background:#7c3aed18;backdrop-filter:blur(9px);cursor:grab}.yf-blur span{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);background:#080b19d9;border:1px solid #a78bfa66;padding:6px 11px;border-radius:999px;font-size:10px;font-weight:900}.yf-blur i{position:absolute;left:50%;width:80px;height:12px;transform:translateX(-50%);cursor:ns-resize}.yf-blur i:after{content:"";position:absolute;left:18px;right:18px;top:4px;height:4px;background:white;border-radius:999px}.yf-top{top:-7px}.yf-bottom{bottom:-7px}.yf-sub{position:absolute;left:6%;right:6%;top:82%;height:34px;border:2px dashed #facc15;background:#facc1517;border-radius:10px;display:grid;place-items:center;cursor:ns-resize;box-shadow:0 0 24px #facc1518}.yf-sub span{background:#0b0d18de;color:#fde68a;padding:5px 9px;border-radius:8px;font-size:10px;font-weight:900}.yf-read{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px;font-size:11px}.yf-read span,.yf-read em{padding:6px 9px;border-radius:9px;background:#0f142a;border:1px solid #25304b;font-style:normal}.yf-read em{color:#86efac}.yf-read b{color:white}@media(max-width:720px){.yf-stage,.yf-img{min-height:220px}}
"""

LAYOUT_EDITOR_JS = r"""
const stage=element.querySelector('.yf-stage'), img=element.querySelector('.yf-img'), blur=element.querySelector('.yf-blur'), topH=element.querySelector('.yf-top'), botH=element.querySelector('.yf-bottom'), sub=element.querySelector('.yf-sub'), reset=element.querySelector('.yf-reset');
const yc=element.querySelector('.yc'),yh=element.querySelector('.yh'),ys=element.querySelector('.ys');
let center=78,height=12,subBottom=15,mode=null,startY=0,sc=center,sh=height,sb=subBottom;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function ready(){const ok=!!img.getAttribute('src')&&img.naturalWidth>0;stage.classList.toggle('ready',ok);return ok}
function norm(){height=clamp(height,3,45);center=clamp(center,height/2,100-height/2);subBottom=clamp(subBottom,2,65)}
function draw(){norm();blur.style.top=`${center-height/2}%`;blur.style.height=`${height}%`;sub.style.top=`${100-subBottom-7}%`;yc.textContent=`${center.toFixed(1)}%`;yh.textContent=`${height.toFixed(1)}%`;ys.textContent=`${subBottom.toFixed(1)}%`}
function emit(){norm();trigger('change',{center:+center.toFixed(2),height:+height.toFixed(2),subtitleBottom:+subBottom.toFixed(2)})}
function pct(e){const r=stage.getBoundingClientRect();return((e.clientY-r.top)/Math.max(1,r.height))*100}
function begin(e,m){if(!ready())return;e.preventDefault();e.stopPropagation();mode=m;startY=pct(e);sc=center;sh=height;sb=subBottom;stage.setPointerCapture?.(e.pointerId)}
blur.addEventListener('pointerdown',e=>{if(e.target===topH||e.target===botH)return;begin(e,'move')});topH.addEventListener('pointerdown',e=>begin(e,'top'));botH.addEventListener('pointerdown',e=>begin(e,'bottom'));sub.addEventListener('pointerdown',e=>begin(e,'sub'));
stage.addEventListener('pointermove',e=>{if(!mode)return;e.preventDefault();const d=pct(e)-startY;if(mode==='move')center=sc+d;else if(mode==='top'){const b=sc+sh/2,t=clamp(sc-sh/2+d,0,b-3);height=b-t;center=(b+t)/2}else if(mode==='bottom'){const t=sc-sh/2,b=clamp(sc+sh/2+d,t+3,100);height=b-t;center=(b+t)/2}else if(mode==='sub')subBottom=sb-d;draw()});
function end(e){if(!mode)return;mode=null;try{stage.releasePointerCapture?.(e.pointerId)}catch(_){ }draw();emit()}stage.addEventListener('pointerup',end);stage.addEventListener('pointercancel',end);reset.addEventListener('click',e=>{e.preventDefault();center=78;height=12;subBottom=15;draw();emit()});img.addEventListener('load',()=>{ready();draw()});img.addEventListener('error',()=>stage.classList.remove('ready'));ready();draw();
"""


def create_app():
    css = r"""
    :root{--bg:#050713;--panel:#0e1429;--panel2:#111a35;--line:#29345a;--violet:#8b5cf6;--cyan:#22d3ee;--gold:#facc15;--text:#f8fafc;--muted:#8f9abb;--green:#34d399}
    body,.gradio-container{background:radial-gradient(circle at 10% 0,#172554 0,transparent 28%),radial-gradient(circle at 92% 3%,#3b1768 0,transparent 26%),linear-gradient(180deg,#090d1d,#050713)!important}.gradio-container{max-width:1360px!important;margin:auto!important;color:var(--text)!important}.yf-hero{padding:26px 28px;border:1px solid #38436b;border-radius:26px;background:linear-gradient(135deg,#161f43f2,#0d1228f5);box-shadow:0 22px 70px #0006;margin:8px 0 18px}.yf-brand{display:flex;align-items:center;gap:14px}.yf-logo{width:62px;height:62px;border-radius:20px;display:grid;place-items:center;font-size:24px;font-weight:950;background:linear-gradient(135deg,#7c3aed,#06b6d4);box-shadow:0 12px 35px #22d3ee2c}.yf-name{font-size:27px;font-weight:950}.yf-tag{font-size:12px;color:var(--muted)}.yf-flow{display:flex;gap:7px;flex-wrap:wrap;margin-top:18px}.yf-flow span{padding:7px 9px;border:1px solid #2b365b;background:#080d20b8;border-radius:10px;font-size:10px;font-weight:800;color:#c7d2fe}.glass-card{border:1px solid #263252!important;background:linear-gradient(180deg,#121a35eb,#0a1025f2)!important;border-radius:20px!important;padding:16px!important;box-shadow:0 13px 40px #0003}.step-head{display:flex;align-items:center;gap:9px;font-weight:950;margin-bottom:10px}.step-no{width:28px;height:28px;display:grid;place-items:center;border-radius:9px;background:#7c3aed2b;border:1px solid #8b5cf655;color:#ddd6fe}.hint{font-size:11px;color:#8492b3;line-height:1.5}.login-shell-pro{max-width:620px;margin:26px auto!important}.login-card-pro{border:1px solid #334166!important;background:#0d142cf5!important;border-radius:22px!important;padding:26px!important}.login-head{text-align:center;font-size:24px;font-weight:950}.login-copy{text-align:center;color:#8f9abb;font-size:12px;margin:6px 0 15px}.member-strip{padding:12px 15px;border:1px solid #34d39945;background:#34d3990d;border-radius:15px;margin-bottom:10px}.member-name{font-weight:900}.member-small{font-size:10px;color:#7dd3fc}.quota-badge{font-size:10px;color:#fde68a}.clone-always-card{border:1px solid #7c3aed48!important;border-radius:16px!important;padding:12px!important;background:#7c3aed0b!important}#analyze-btn,#script-btn,#render-btn{min-height:52px!important;border:0!important;border-radius:14px!important;font-weight:950!important}#analyze-btn{background:linear-gradient(90deg,#2563eb,#06b6d4)!important}#script-btn{background:linear-gradient(90deg,#7c3aed,#a855f7)!important}#render-btn{background:linear-gradient(90deg,#7c3aed,#06b6d4)!important;min-height:60px!important;font-size:17px!important}.export-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.footer-note{text-align:center;color:#5f6d8d;font-size:10px;padding:18px}@media(max-width:800px){.export-grid{grid-template-columns:1fr 1fr}.yf-hero{padding:20px 17px}}
    """
    theme = gr.themes.Soft(primary_hue="violet", secondary_hue="cyan", neutral_hue="slate")
    connection_js = r"""
    (()=>{if(document.getElementById('yf-conn'))return;const d=document.createElement('div');d.id='yf-conn';d.style='position:fixed;right:12px;bottom:12px;z-index:99999;background:#07111be8;color:#86efac;border:1px solid #34d39955;border-radius:999px;padding:7px 10px;font:700 10px Arial';d.textContent='● YF Cloud Connected';document.body.appendChild(d);})();
    """

    with gr.Blocks(title="YF Recap V3 • Story Studio") as app:
        app._yf_theme=theme; app._yf_css=css; app._yf_js=connection_js
        session_id_state=gr.State(lambda:str(uuid.uuid4()))
        vip_access_state=gr.State({"authenticated":False})
        analysis_state=gr.State({})

        gr.HTML("""<section class='yf-hero'><div class='yf-brand'><div class='yf-logo'>YF</div><div><div class='yf-name'>YF Recap V3</div><div class='yf-tag'>Story Studio • Review before render • VoxCPM2 • Scene-aligned export</div></div></div><div class='yf-flow'><span>1 Upload</span><span>2 Analyze Scenes</span><span>3 Viral Script</span><span>4 Review/Edit</span><span>5 Voice</span><span>6 Drag Layout</span><span>7 Audio Mixer</span><span>8 Fast Render</span><span>9 Export</span></div></section>""")

        with gr.Column(visible=True,elem_classes=["login-shell-pro"]) as login_panel:
            with gr.Column(elem_classes=["login-card-pro"]):
                gr.HTML("<div class='login-head'>YF Recap Access</div><div class='login-copy'>Admin Portal မှ ထုတ်ထားသော Video Recap VIP Code ကို ထည့်ပါ</div>")
                vip_code_input=gr.Textbox(label="VIP ACCESS CODE",placeholder="VIP-XXXX-XXXX-XXXX",type="password")
                unlock_btn=gr.Button("🔓 ENTER YF RECAP",variant="primary")
                login_status=gr.HTML()

        with gr.Column(visible=False) as main_panel:
            with gr.Row():
                with gr.Column(scale=9): member_status_html=gr.HTML()
                with gr.Column(scale=1,min_width=100): logout_btn=gr.Button("Logout")

            # STEP 1 + 2
            with gr.Row(equal_height=False):
                with gr.Column(scale=7,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>1</span> Upload Movie</div>")
                    video_input=gr.Video(label="Original Movie / Clip",sources=["upload"])
                    analyze_btn=gr.Button("🧠 ANALYZE MOVIE & SCENES",variant="primary",elem_id="analyze-btn")
                with gr.Column(scale=5,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>2</span> Analyze Scenes</div><div class='hint'>Whisper speech timing ကိုသုံးပြီး narrative scene blocks ခွဲပေးပါတယ်။ Full visual re-decode မလုပ်လို့ Colab မှာ ပိုမြန်ပါတယ်။</div>")
                    analysis_status=gr.Markdown("Movie upload ပြီး Analyze ကိုနှိပ်ပါ။")
                    scene_table=gr.Dataframe(headers=["Scene","Start","End","Speech / Context"],datatype=["number","str","str","str"],interactive=False,wrap=True,value=[])

            # STEP 3 + 4
            with gr.Row(equal_height=False):
                with gr.Column(scale=4,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>3</span> Generate Viral Recap Script</div>")
                    user_api_key=gr.Textbox(label="Gemini API Key",type="password",placeholder="Best storytelling quality အတွက်ထည့်ပါ")
                    tone_style=gr.Dropdown(choices=["Viral Story Recap","Thriller","Comedy","Dramatic","Action/Epic","Neutral"],value="Viral Story Recap",label="Narrative Tone")
                    recap_length=gr.Dropdown(choices=["⚡ 1 Minute Short","🎬 3 Minute Recap","🔥 5 Minute Recap","🍿 10 Minute Recap","🧠 Auto Smart Length"],value="🔥 5 Minute Recap",label="Target Recap Length")
                    script_btn=gr.Button("✨ GENERATE VIRAL RECAP SCRIPT",variant="primary",elem_id="script-btn")
                    script_status=gr.Markdown()
                with gr.Column(scale=8,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>4</span> User Review / Edit Script</div><div class='hint'>`|` နောက်က Burmese narration ကို ပြင်ပါ။ `[start --> end]` timestamp ကို မဖျက်ပါနဲ့ — final scene alignment အတွက်သုံးပါတယ်။</div>")
                    script_editor=gr.Textbox(label="Editable Recap Script",lines=18,placeholder="#001 [0.00 --> 12.20] | ဒီနေရာမှာ recap narration ပေါ်လာပါမယ်...")

            # STEP 5 voice
            with gr.Row(equal_height=False):
                with gr.Column(scale=7,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>5</span> Choose Voice / VoxCPM2 Clone</div>")
                    voice_engine=gr.Radio(choices=["⚡ Edge TTS • Fast","🎨 VoxCPM2 Voice Design","🎙️ VoxCPM2 Voice Clone"],value="⚡ Edge TTS • Fast",label="Voice Engine")
                    with gr.Row():
                        edge_voice_select=gr.Dropdown(choices=list(EDGE_VOICES.keys()),value="👩 Myanmar Female • Nilar",label="Edge Voice")
                        voice_preset=gr.Dropdown(choices=list(VOXCPM_VOICE_PRESETS.keys()),value="🎬 Deep Male Movie Narrator",label="VoxCPM2 Voice Style")
                    custom_voice_description=gr.Textbox(label="Custom Voice Description",lines=2)
                    with gr.Column(elem_classes=["clone-always-card"]):
                        gr.Markdown("**🎙 External Reference Voice — always visible** · MP3/WAV upload သို့ microphone record လုပ်နိုင်ပါတယ်။")
                        clone_reference=gr.Audio(label="Reference Voice",sources=["upload","microphone"],type="filepath")
                        clone_reference_status=gr.HTML("<div>Reference voice မထည့်ရသေးပါ။</div>")
                        clone_check_btn=gr.Button("✓ Check Reference")
                        clone_transcript=gr.Textbox(label="Reference Transcript (Optional)",lines=2)
                        clone_consent=gr.Checkbox(label="ဒီ reference အသံကို clone အသုံးပြုရန် ခွင့်ပြုချက်ရှိပါသည်")
                    desired_speed=gr.Slider(0.9,1.6,value=1.22,step=.05,label="Voice Pace")
                    with gr.Accordion("VoxCPM2 Quality",open=False):
                        voxcpm_cfg=gr.Slider(1.0,3.0,value=2.0,step=.1,label="CFG")
                        voxcpm_steps=gr.Slider(4,20,value=10,step=1,label="Steps")
                        voxcpm_seed=gr.Number(value=42,precision=0,label="Seed")
                    voice_preview_btn=gr.Button("▶ VOICE PREVIEW")
                    voice_preview_audio=gr.Audio(label="Preview",interactive=False)
                with gr.Column(scale=5,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>6</span> Subtitle + Blur by Drag</div>")
                    layout_editor=gr.HTML(value=video_first_frame_data_uri,inputs=[video_input],html_template=LAYOUT_EDITOR_TEMPLATE,css_template=LAYOUT_EDITOR_CSS,js_on_load=LAYOUT_EDITOR_JS,apply_default_css=False,container=False)
                    blur_y_percent=gr.Number(value=78,visible=False); blur_height_percent=gr.Number(value=12,visible=False); sub_pos_percent=gr.Number(value=15,visible=False)
                    with gr.Row():
                        text_color=gr.ColorPicker(label="Subtitle Text",value="#FFFF00")
                        stroke_color=gr.ColorPicker(label="Outline",value="#000000")
                    with gr.Row():
                        subtitle_size=gr.Slider(2.0,7.0,value=3.8,step=.1,label="Font Size")
                        blur_strength=gr.Slider(5,151,value=51,step=2,label="Blur Strength")

            # STEP 7 mixer + visual options
            with gr.Row(equal_height=False):
                with gr.Column(scale=6,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>7</span> Original Audio + BGM Mixer</div>")
                    bgm_file=gr.Audio(label="Background Music",type="filepath")
                    narration_vol=gr.Slider(0,150,value=100,step=1,label="Narration Volume %")
                    original_vol=gr.Slider(0,60,value=10,step=1,label="Original Movie Audio %")
                    bgm_vol=gr.Slider(0,50,value=12,step=1,label="BGM Volume %")
                    auto_duck=gr.Checkbox(label="Auto Duck BGM while Narrator speaks",value=True)
                with gr.Column(scale=6,elem_classes=["glass-card"]):
                    gr.HTML("<div class='step-head'><span class='step-no'>8</span> Fast Render Settings</div>")
                    with gr.Row():
                        ratio_select=gr.Dropdown(choices=["9:16 (TikTok/Reels)","16:9 (Landscape)"],value="9:16 (TikTok/Reels)",label="Output Ratio")
                        render_mode=gr.Radio(choices=["⚡ Turbo 24 FPS (Recommended)","🎬 Balanced 30 FPS"],value="⚡ Turbo 24 FPS (Recommended)",label="Render Mode")
                    background_fill=gr.Radio(choices=["Blur Background","Black Background"],value="Blur Background",label="Background")
                    with gr.Row():
                        logo_file=gr.File(label="YF / Brand Logo PNG",file_types=["image"])
                        filter_color=gr.Dropdown(choices=["None","Chrome Cool","Warm Cinema"],value="None",label="Color Look")
                    with gr.Row():
                        enable_zoom=gr.Checkbox(label="Zoom & Crop",value=False)
                        zoom_level=gr.Slider(1.0,3.0,value=1.0,step=.1,label="Zoom")
                        mirror_flip=gr.Checkbox(label="Mirror Flip",value=False)

            render_btn=gr.Button("⚡ RENDER REVIEWED YF RECAP",variant="primary",elem_id="render-btn")
            render_status=gr.Markdown()

            # STEP 9 exports
            with gr.Column(elem_classes=["glass-card"]):
                gr.HTML("<div class='step-head'><span class='step-no'>9</span> MP4 + SRT + MP3 + Script</div>")
                final_video=gr.Video(label="Final YF Recap")
                with gr.Row():
                    srt_file=gr.File(label="SRT Subtitle")
                    mp3_file=gr.File(label="Narration MP3")
                    script_file=gr.File(label="Reviewed Script")
            gr.HTML("<div class='footer-note'>YF RECAP V3 • Story-first workflow • Review before Render • VoxCPM2 • Scene-aligned video • Cloudflare</div>")

        unlock_btn.click(unlock_vip,[vip_code_input],[vip_access_state,login_panel,main_panel,login_status,member_status_html])
        vip_code_input.submit(unlock_vip,[vip_code_input],[vip_access_state,login_panel,main_panel,login_status,member_status_html])
        logout_btn.click(logout_vip,[],[vip_access_state,login_panel,main_panel,login_status,member_status_html,vip_code_input])

        analyze_btn.click(analyze_movie_v3,[video_input,vip_access_state],[analysis_state,analysis_status,scene_table])
        script_btn.click(generate_recap_script_v3,[analysis_state,user_api_key,tone_style,recap_length],[script_editor,script_status])
        clone_check_btn.click(inspect_clone_reference,[clone_reference],[clone_reference_status])
        clone_reference.change(inspect_clone_reference,[clone_reference],[clone_reference_status])
        voice_preview_btn.click(generate_voice_preview,[voice_engine,edge_voice_select,voice_preset,custom_voice_description,clone_reference,clone_transcript,clone_consent,desired_speed,voxcpm_cfg,voxcpm_steps,voxcpm_seed],voice_preview_audio)
        layout_editor.change(sync_layout_editor,outputs=[blur_y_percent,blur_height_percent,sub_pos_percent],queue=False,show_progress="hidden")

        render_btn.click(
            render_reviewed_script_v3,
            inputs=[analysis_state,script_editor,ratio_select,background_fill,enable_zoom,zoom_level,logo_file,
                    bgm_file,narration_vol,original_vol,bgm_vol,auto_duck,mirror_flip,filter_color,
                    voice_engine,edge_voice_select,voice_preset,custom_voice_description,clone_reference,clone_transcript,clone_consent,
                    voxcpm_cfg,voxcpm_steps,voxcpm_seed,text_color,stroke_color,blur_y_percent,blur_height_percent,blur_strength,
                    sub_pos_percent,subtitle_size,desired_speed,render_mode,session_id_state,vip_access_state],
            outputs=[final_video,srt_file,mp3_file,script_file,render_status]
        )
    return app


# ================================================================
# 11) COLAB PUBLIC LAUNCH — CLOUDFLARE (NO gradio.live)
# ================================================================
# This launcher keeps the Gradio UI local (share=False) and exposes it
# through a Cloudflare Quick Tunnel. No Gradio share link is created.

PUBLIC_PORT = int(os.getenv("YF_RECAP_PORT", "7860"))


def _wait_for_port(host="127.0.0.1", port=7860, timeout=45):
    """Wait until the local Gradio server is accepting TCP connections."""
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        try:
            with socket.create_connection((host, int(port)), timeout=1.0):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def _cloudflared_download_url():
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        asset = "cloudflared-linux-amd64"
    elif machine in ("aarch64", "arm64"):
        asset = "cloudflared-linux-arm64"
    else:
        raise RuntimeError(f"Unsupported CPU architecture for cloudflared: {machine}")
    return f"https://github.com/cloudflare/cloudflared/releases/latest/download/{asset}"


def ensure_cloudflared():
    """Download cloudflared once in the Colab/runtime filesystem."""
    preferred_dir = "/content" if os.path.isdir("/content") else tempfile.gettempdir()
    binary = os.path.join(preferred_dir, "cloudflared")

    if os.path.isfile(binary) and os.access(binary, os.X_OK):
        return binary

    print("☁️ Installing Cloudflare Tunnel...")
    url = _cloudflared_download_url()
    try:
        urllib.request.urlretrieve(url, binary)
    except Exception:
        # wget is often more resilient in Colab, so keep it as a fallback.
        subprocess.run(["wget", "-q", "-O", binary, url], check=True)

    os.chmod(binary, 0o755)
    print("✅ cloudflared ready:", binary)
    return binary


def start_cloudflare_tunnel(origin_url):
    """Start a stable Cloudflare Quick Tunnel and keep draining logs."""
    import threading

    binary = ensure_cloudflared()
    local_url = str(origin_url).rstrip("/")

    # Force HTTP/2 because QUIC/UDP can be unstable or blocked in Colab.
    cmd = [
        binary,
        "tunnel",
        "--no-autoupdate",
        "--protocol", "http2",      # avoid QUIC/UDP instability in Colab
        "--edge-ip-version", "4",  # force IPv4 path
        "--loglevel", "error",     # keep Colab output clean
        "--url", local_url,
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    url_pattern = re.compile(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com")
    state = {"url": None, "last_error": ""}
    url_ready = threading.Event()

    print("☁️ Creating YF Recap public link...")
    print("ℹ️ Gradio share=False — gradio.live is NOT being used.")
    print("ℹ️ Cloudflare transport: HTTP/2 (Colab stable mode)")

    def _drain_cloudflare_logs():
        """Continuously read cloudflared stdout so its pipe never blocks."""
        try:
            if process.stdout is None:
                return
            for raw_line in iter(process.stdout.readline, ""):
                if not raw_line:
                    break
                clean = raw_line.strip()
                match = url_pattern.search(clean)
                if match and state["url"] is None:
                    state["url"] = match.group(0)
                    url_ready.set()

                lower = clean.lower()

                # Quick Tunnel may cancel/reopen Gradio streaming requests.
                # These lines are noisy but usually non-fatal, so do not flood Colab.
                transient_cancel = (
                    "context canceled" in lower
                    or "failed to serve incoming request" in lower
                )
                if transient_cancel:
                    continue

                if " error" in lower or "err " in lower or "failed" in lower:
                    state["last_error"] = clean
                    print("Cloudflare:", clean)
        except Exception as exc:
            state["last_error"] = str(exc)
        finally:
            # Wake the waiter if cloudflared exits before URL creation.
            url_ready.set()

    log_thread = threading.Thread(
        target=_drain_cloudflare_logs,
        name="cloudflared-log-reader",
        daemon=True,
    )
    log_thread.start()

    # Wait for URL without stopping the background stdout reader.
    deadline = time.time() + 75
    while time.time() < deadline:
        if state["url"]:
            public_url = state["url"]
            print("\n" + "=" * 66)
            print("🚀 YF RECAP PUBLIC LINK")
            print(public_url)
            print("=" * 66 + "\n")
            print("📌 ဒီ Colab cell run နေသရွေ့ link အလုပ်လုပ်ပါမယ်။")
            print("📌 Runtime disconnect/restart ဖြစ်ရင် link အသစ်ထွက်ပါမယ်။\n")
            return process, public_url, log_thread

        if process.poll() is not None:
            raise RuntimeError(
                "Cloudflare tunnel stopped before producing a URL. "
                + (state["last_error"] or f"exit={process.returncode}")
            )
        time.sleep(0.2)

    if process.poll() is None:
        process.terminate()
    raise RuntimeError(
        "Cloudflare public URL 75 seconds အတွင်း မရပါ။ "
        + (state["last_error"] or "Colab network ကိုစစ်ပြီး ပြန် Run ပါ။")
    )


def launch_yf_recap_cloudflare():
    """Run YF Recap in Colab with Cloudflare ONLY (no gradio.live, no localhost iframe)."""
    import gradio.utils as gr_utils
    import gradio.networking as gr_networking

    # Gradio 6 treats Colab as a hosted notebook and may try its own
    # gradio.live tunnel / localhost iframe. We use Cloudflare instead,
    # so disable hosted-notebook detection only while launching locally.
    original_colab_check = gr_utils.colab_check
    original_hosted_check = gr_utils.is_hosted_notebook
    original_url_ok = gr_networking.url_ok

    def _not_colab():
        return False

    def _local_url_ok(url):
        u = str(url or "")
        if (
            u.startswith("http://127.0.0.1:")
            or u.startswith("http://localhost:")
            or u.startswith("http://0.0.0.0:")
        ):
            return True
        return original_url_ok(url)

    gr_utils.colab_check = _not_colab
    gr_utils.is_hosted_notebook = _not_colab
    gr_networking.url_ok = _local_url_ok

    demo = create_app()

    try:
        demo.queue(
            status_update_rate=5.0,     # fewer streaming status packets through Quick Tunnel
            api_open=False,
            max_size=6,
            default_concurrency_limit=1,
        ).launch(
            server_name="127.0.0.1",
            server_port=PUBLIC_PORT,
            share=False,                 # never use gradio.live
            inline=False,                # never show Colab localhost iframe
            inbrowser=False,
            debug=False,
            prevent_thread_lock=True,
            show_error=True,
            quiet=True,                  # hide localhost/share messages
            ssl_keyfile=None,
            ssl_certfile=None,
            theme=getattr(demo, "_yf_theme", None),
            css=getattr(demo, "_yf_css", None),
            js=getattr(demo, "_yf_js", None),
            max_threads=12,
            state_session_capacity=300,
            pwa=True,
        )
    finally:
        gr_utils.colab_check = original_colab_check
        gr_utils.is_hosted_notebook = original_hosted_check
        gr_networking.url_ok = original_url_ok

    # Cloudflare connects privately to this origin. Users never see it.
    local_origin = f"http://127.0.0.1:{PUBLIC_PORT}"

    if not _wait_for_port("127.0.0.1", PUBLIC_PORT, timeout=60):
        raise RuntimeError(
            f"YF Recap local server did not start on port {PUBLIC_PORT}. "
            "Check the Python traceback above."
        )

    tunnel_process, public_url, _log_thread = start_cloudflare_tunnel(local_origin)

    # After successful startup, clear Colab logs and show only the
    # Cloudflare public link.
    try:
        from IPython.display import clear_output, display, HTML
        clear_output(wait=True)
        html = (
            '<div style="font-family:Arial,sans-serif;padding:18px 0;">'
            '<div style="font-size:15px;font-weight:800;margin-bottom:8px;">YF RECAP LIVE LINK</div>'
            f'<a href="{public_url}" target="_blank" style="font-size:18px;font-weight:800;word-break:break-all;">{public_url}</a>'
            '</div>'
        )
        display(HTML(html))
    except Exception:
        print(public_url, flush=True)

    # Keep Gradio + Cloudflare alive without recurring output.
    try:
        while True:
            if tunnel_process.poll() is not None:
                raise RuntimeError(
                    f"Cloudflare tunnel disconnected (exit={tunnel_process.returncode}). "
                    "Run this cell again to create a new Cloudflare link."
                )
            if not _wait_for_port("127.0.0.1", PUBLIC_PORT, timeout=2):
                raise RuntimeError(
                    "YF Recap local server stopped responding. "
                    "The Colab runtime may have restarted or run out of RAM/VRAM."
                )
            time.sleep(12)
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel_process.poll() is None:
            tunnel_process.terminate()
        try:
            demo.close()
        except Exception:
            pass

    return public_url


if __name__ == "__main__":
    launch_yf_recap_cloudflare()

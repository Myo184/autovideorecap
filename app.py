# ================================================================
# 👑 VIP MAGIC VIDEO AUTO RECAP — GOOGLE COLAB (MONGODB CONNECTED)
# FAST ONE-PASS FFMPEG EDITION • VIP API CONNECTED
# ================================================================
# Recommended Runtime: T4 GPU (Runtime > Change runtime type > T4 GPU)

import os, sys, subprocess, importlib.util, shutil

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
    "You are a professional movie recap writer. Translate and summarize movie subtitle lines "
    "into natural, engaging, thrilling Burmese recap style. Keep sentences clear and concise for speech."
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
Translate the following subtitle lines from '{source_lang}' into natural Burmese movie recap narration.
Tone Style: {tone_style}. Keep sentences concise for speech timing.

CRITICAL RULES:
1. Return VALID JSON ONLY.
2. Keep keys identical (0, 1, 2...).
3. Values must be natural Burmese translations.
4. No markdown formatting.

Input JSON:
{large_prompt_text}
"""
    translated_map = {}
    try:
        client = genai.Client(api_key=user_api_key.strip())
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config={"system_instruction": SYSTEM_INSTRUCTION, "temperature": 0.3}
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
    engine = str(engine or "")
    is_edge = engine.startswith("⚡")
    is_design = "Voice Design" in engine
    is_clone = "Voice Clone" in engine
    return (
        gr.update(visible=is_edge),
        gr.update(visible=is_design),
        gr.update(visible=is_clone),
    )


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
def create_app():
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
    #generate-btn { min-height:60px !important; border:0 !important; border-radius:17px !important; font-size:17px !important; font-weight:950 !important; letter-spacing:.02em; color:white !important; background:linear-gradient(100deg,#7c3aed 0%,#8b5cf6 42%,#06b6d4 100%) !important; box-shadow:0 13px 36px rgba(124,58,237,.30) !important; }
    #generate-btn:hover { transform:translateY(-1px); filter:brightness(1.06); }
    #logout-btn { border-radius:12px !important; }
    .output-card { border-color:rgba(52,211,153,.18) !important; }
    .footer-note { text-align:center; color:#65708e; font-size:11px; padding:18px 0 2px; }
    @media (max-width:760px) { .hero-pro{padding:22px 18px}.mini-grid{grid-template-columns:1fr}.member-strip{align-items:flex-start;flex-direction:column}.quota-badge{align-self:flex-start} }
    """
    theme = gr.themes.Soft(primary_hue="violet", secondary_hue="cyan", neutral_hue="slate")

    with gr.Blocks(css=css, theme=theme, title="⚡ YF Recap • VoxCPM2") as app:
        session_id_state = gr.State(lambda: str(uuid.uuid4()))
        vip_access_state = gr.State({"authenticated": False})

        gr.HTML(f"""
        <section class="hero-pro">
          <div class="brand-row">
            <div class="brand-mark">YF</div>
            <div class="brand-text">
              <div class="brand-kicker">NEXT UI DESIGN</div>
              <div class="brand-name">YF Recap</div>
              <div class="brand-tag">Premium movie recap studio • VoxCPM2 Voice Clone</div>
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
                        gr.HTML('<div class="section-cap"><span>👁</span> Subtitle Blur Preview</div>')
                        preview_image = gr.Image(label="Preview", interactive=False)

                with gr.Column(scale=5):
                    with gr.Column(elem_classes=["glass-card"]):
                        gr.HTML('<div class="section-cap"><span>🧠</span> AI Recap</div>')
                        user_api_key = gr.Textbox(
                            label="Gemini API Key (Optional)", type="password",
                            placeholder="မထည့်ပါက Google Translate backup သုံးမည်"
                        )
                        tone_style = gr.Dropdown(
                            choices=["Thriller", "Comedy", "Dramatic", "Action/Epic", "Neutral"],
                            value="Thriller", label="Narrative Tone"
                        )
                        voice_engine = gr.Radio(
                            choices=[
                                "⚡ Edge TTS • Fast",
                                "🎨 VoxCPM2 Voice Design",
                                "🎙️ VoxCPM2 Voice Clone",
                            ],
                            value="⚡ Edge TTS • Fast",
                            label="Voice Engine",
                        )

                        with gr.Column(visible=True) as edge_voice_panel:
                            edge_voice_select = gr.Dropdown(
                                choices=list(EDGE_VOICES.keys()),
                                value="👩 Myanmar Female • Nilar",
                                label="Standard Burmese Voice",
                            )

                        with gr.Column(visible=False) as voxcpm_design_panel:
                            gr.HTML('<div class="voice-note">VoxCPM2 Voice Design • Reference အသံမလိုပါ။ Burmese narration အတွက် voice style အသစ်ကို AI ကဖန်တီးပေးမည်။</div>')
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

                        with gr.Column(visible=False) as voxcpm_clone_panel:
                            gr.HTML('<div class="clone-note">🎙️ VoxCPM2 Voice Clone • ကြည်လင်သော 5–15 sec reference audio သုံးပါ။ Transcript အတိအကျ ထည့်လျှင် Ultimate Cloning mode သုံးမည်။</div>')
                            clone_reference = gr.Audio(
                                label="Reference Voice (MP3/WAV)",
                                sources=["upload", "microphone"],
                                type="filepath",
                            )
                            clone_transcript = gr.Textbox(
                                label="Reference Transcript (Optional • exact words)",
                                placeholder="Reference audio ထဲမှာ ပြောထားတဲ့ စာသားကို အတိအကျရေးပါ။ မရေးလည်း clone လုပ်နိုင်ပါတယ်။",
                                lines=2,
                            )
                            clone_consent = gr.Checkbox(
                                label="အသံပိုင်ရှင်၏ ခွင့်ပြုချက်ရှိသော အသံကိုသာ Voice Clone လုပ်မည်",
                                value=False,
                            )

                        desired_speed = gr.Slider(0.9, 1.6, value=1.25, step=0.05, label="Voice Pace")
                        with gr.Accordion("VoxCPM2 Quality Settings", open=False):
                            voxcpm_cfg = gr.Slider(1.0, 3.0, value=2.0, step=0.1, label="CFG Guidance")
                            voxcpm_steps = gr.Slider(4, 20, value=10, step=1, label="Inference Steps")
                            voxcpm_seed = gr.Number(value=42, precision=0, label="Seed")
                        voice_preview_btn = gr.Button("▶ Preview Selected Voice", variant="secondary")
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
                    gr.HTML('<div class="section-cap"><span>🌫</span> Subtitle Blur Band</div>')
                    blur_y_percent = gr.Slider(0, 100, value=78, step=1, label="Blur Center")
                    blur_height_percent = gr.Slider(3, 30, value=12, step=1, label="Blur Height (%)")
                    blur_strength = gr.Slider(5, 151, value=51, step=2, label="Blur Strength")

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

            gr.HTML('<div class="footer-note">YF RECAP • FFmpeg / NVENC • VoxCPM2 Voice Design + Voice Clone</div>')

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
        voice_preview_btn.click(
            fn=generate_voice_preview,
            inputs=[
                voice_engine, edge_voice_select, voice_preset, custom_voice_description,
                clone_reference, clone_transcript, clone_consent, desired_speed,
                voxcpm_cfg, voxcpm_steps, voxcpm_seed,
            ],
            outputs=voice_preview_audio,
        )

        p_inputs = [video_input, blur_y_percent, blur_height_percent, blur_strength]
        for trig in p_inputs:
            trig.change(update_preview_image, inputs=p_inputs, outputs=preview_image)

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
# 11) LAUNCH — FAST UI EDITION
# ================================================================
if __name__ == "__main__":
    demo = create_app()
    demo.queue(default_concurrency_limit=1).launch(share=True, debug=True)

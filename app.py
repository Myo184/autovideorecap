# ================================================================
# 👑 VIP MAGIC VIDEO AUTO RECAP — GOOGLE COLAB (MONGODB CONNECTED)
# Connected to Hugging Face API: yufei184905/movievipcode
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
        "numpy")

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
from google import genai
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont

# ================================================================
# 2) APP CONFIG & HF SPACE NAME (MONGODB CONNECTED)
# ================================================================
# Admin Portal Space that owns the Video VIP database and /verify API.
# You can override this in Hugging Face Space Variables/Secrets with VIP_ADMIN_SPACE_ID.
HF_SPACE_ID = os.getenv("VIP_ADMIN_SPACE_ID", "yufei184905/Vipcodemadclone").strip()
HF_TOKEN = os.getenv("HF_TOKEN", "").strip()

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
# 7) TTS & AUDIO PROBE
# ================================================================
def generate_voice_sync(text, voice_id, filename, desired_tts_rate=1.15, target_duration_sec=None):
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

def probe_duration(path, fallback=1.0):
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False
        )
        return float(r.stdout.strip())
    except Exception:
        return fallback

# ================================================================
# 8) HIGH-SPEED VIDEO RECAP PROCESSOR (NO 55% HANG)
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
    voice_gender,
    tone_style,
    text_color,
    stroke_color,
    blur_y_percent,
    blur_height_percent,
    blur_strength,
    sub_pos_percent,
    subtitle_size_percent,
    desired_speed,
    session_id,
    vip_access_state,
    progress=gr.Progress(track_tqdm=False)
):
    video_path = normalize_file_path(video_value)
    logo_path = normalize_file_path(logo_value)
    bgm_path = normalize_file_path(bgm_value)

    if not video_path or not os.path.exists(video_path):
        raise gr.Error("❌ Video file မတွေ့ပါ။")

    # Check VIP Session
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        raise gr.Error("🔒 VIP Access မရှိသေးပါ။ ကျေးဇူးပြု၍ VIP Code ဖြင့် Login ဝင်ပါ။")

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
            raise gr.Error(f"❌ {member_label} daily quota ပြည့်သွားပါပြီ ({daily_limit} vids/day)။ ပြန်စမ်းရန် {h}နာရီ {m}မိနစ် ကျန်ပါသည်။")

    work_dir = tempfile.mkdtemp(prefix=f"magic_recap_{session_id[:8]}_")
    output_video_path = os.path.join(work_dir, "final_recap.mp4")

    cap = None
    video_writer = None

    try:
        # A) Speech to Text
        progress(0.05, desc="🎙️ 01. စာသားဖတ်ယူနေပါသည်...")
        segments_raw, info = whisper_model.transcribe(video_path, beam_size=1, vad_filter=True)
        raw_segments = [{"start": float(seg.start), "end": float(seg.end), "text": seg.text} for seg in segments_raw]

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        orig_w, orig_h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        video_duration = (frame_count / fps) if fps > 0 else 0

        if not raw_segments:
            raw_segments = [{"start": 0.0, "end": min(6.0, max(video_duration, 2.0)), "text": "This is an interesting movie scene."}]

        # Split segments
        segments = []
        for seg in raw_segments:
            s_start, s_end, s_text = seg["start"], seg["end"], (seg["text"] or "").strip()
            if not s_text: continue
            dur = max(0.1, s_end - s_start)
            if MAX_SUBTITLE_DURATION_SECONDS > 0 and dur > MAX_SUBTITLE_DURATION_SECONDS:
                words = s_text.split()
                chunks_count = max(1, int(np.ceil(dur / MAX_SUBTITLE_DURATION_SECONDS)))
                words_per_chunk = max(1, int(np.ceil(len(words) / chunks_count)))
                for i in range(chunks_count):
                    w_sub = words[i * words_per_chunk:(i + 1) * words_per_chunk]
                    if not w_sub: continue
                    segments.append({
                        "start": s_start + i * (dur / chunks_count),
                        "end": min(s_end, s_start + (i + 1) * (dur / chunks_count)),
                        "text": " ".join(w_sub)
                    })
            else:
                segments.append(seg)

        # B) Translate
        detected_lang = getattr(info, "language", None) or "en"
        progress(0.20, desc=f"⚡ 02. မြန်မာ Recap ဘာသာပြန်နေပါသည် ({detected_lang})...")
        segments = translate_segments_batch(segments, user_api_key, source_lang=detected_lang, tone_style=tone_style)

        # C) Dimensions
        target_w, target_h = (720, 1280) if ratio_select == "9:16 (TikTok/Reels)" else (1280, 720)

        # Logo
        logo_img = None
        if logo_path and os.path.exists(logo_path):
            try:
                logo_cv = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
                if logo_cv is not None and logo_cv.shape[1] > 0:
                    l_w = int(target_w * 0.16)
                    l_h = max(1, int(l_w * (logo_cv.shape[0] / logo_cv.shape[1])))
                    logo_img = cv2.resize(logo_cv, (l_w, l_h), interpolation=cv2.INTER_AREA)
            except Exception: pass

        # D) TTS Generation
        progress(0.35, desc="🎙️ 03. မြန်မာ AI အသံဖန်တီးနေပါသည်...")
        audio_segments, subtitle_segments = [], []
        total_adjusted_duration = 0.0
        voice_id = "my-MM-NilarNeural" if "မိန်းကလေး" in voice_gender else "my-MM-ThihaNeural"

        for idx, seg in enumerate(segments):
            mm_text = (seg.get("mm_text") or seg["text"]).replace(" ြ", "ြ").replace("ြ ", "ြ").strip()
            if not mm_text: continue
            orig_start, orig_end = float(seg.get("start", 0.0)), float(seg.get("end", 0.0))
            orig_dur = max(0.15, orig_end - orig_start)

            raw_audio = os.path.join(work_dir, f"raw_{idx:04d}.mp3")
            speed_audio = os.path.join(work_dir, f"speed_{idx:04d}.mp3")

            generate_voice_sync(mm_text, voice_id, raw_audio, desired_tts_rate=1.15, target_duration_sec=orig_dur)
            if not os.path.exists(raw_audio) or os.path.getsize(raw_audio) == 0: continue

            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw_audio, "-filter:a", f"atempo={float(desired_speed):.3f}", "-vn", speed_audio], check=False)
            if not os.path.exists(speed_audio): shutil.copy2(raw_audio, speed_audio)

            audio_dur = max(0.1, probe_duration(speed_audio, fallback=orig_dur))
            subtitle_segments.append({"start": total_adjusted_duration, "end": total_adjusted_duration + audio_dur, "text": mm_text})
            audio_segments.append(speed_audio)
            total_adjusted_duration += audio_dur

        if not subtitle_segments:
            raise RuntimeError("TTS Voice ဖန်တီး၍ မရပါ။")

        # E) HIGH-SPEED VIDEO RENDER
        progress(0.50, desc="🎬 04. Video Frame များကို Render လုပ်နေပါသည်...")
        final_burn_temp = os.path.join(work_dir, "final_burn_temp.mp4")
        video_writer = cv2.VideoWriter(final_burn_temp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (target_w, target_h))

        font_size = max(18, int(target_h * (float(subtitle_size_percent) / 100.0)))
        font_primary = ImageFont.truetype(FONT_PATH, font_size) if FONT_PATH else ImageFont.load_default()
        text_rgb, stroke_rgb = hex_to_rgb(text_color), hex_to_rgb(stroke_color)
        stroke_w = max(2, int(font_size * 0.10))

        blur_h = max(8, int(target_h * (float(blur_height_percent) / 100.0)))
        center_y = int(target_h * (float(blur_y_percent) / 100.0))
        blur_y = max(0, min(center_y - blur_h // 2, target_h - blur_h))
        blur_k = safe_kernel_size(blur_strength)

        total_output_frames = max(1, int(total_adjusted_duration * fps))
        sub_idx = 0
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        for f_idx in range(total_output_frames):
            c_sec = f_idx / fps
            ret, orig_frame = cap.read()
            if not ret or orig_frame is None:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, orig_frame = cap.read()
                if not ret or orig_frame is None:
                    orig_frame = np.zeros((orig_h, orig_w, 3), dtype=np.uint8)

            # BG
            if background_fill == "Blur Background":
                small_bg = cv2.resize(orig_frame, (max(1, target_w // 4), max(1, target_h // 4)), interpolation=cv2.INTER_LINEAR)
                small_bg = cv2.GaussianBlur(small_bg, (21, 21), 0)
                bg_layer = cv2.resize(small_bg, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
            else:
                bg_layer = np.zeros((target_h, target_w, 3), dtype=np.uint8)

            # Zoom/Crop
            fg = orig_frame
            z = float(zoom_level)
            if enable_zoom and z > 1.0:
                ch, cw = max(1, int(orig_h / z)), max(1, int(orig_w / z))
                fg = orig_frame[max(0, (orig_h - ch) // 2):max(0, (orig_h - ch) // 2) + ch, max(0, (orig_w - cw) // 2):max(0, (orig_w - cw) // 2) + cw]

            scale = min(target_w / fg.shape[1], target_h / fg.shape[0])
            fg_resized = cv2.resize(fg, (max(1, int(fg.shape[1] * scale)), max(1, int(fg.shape[0] * scale))), interpolation=cv2.INTER_LINEAR)
            if mirror_flip: fg_resized = cv2.flip(fg_resized, 1)

            if filter_color == "Chrome Cool": fg_resized = cv2.convertScaleAbs(fg_resized, alpha=1.0, beta=15)
            elif filter_color == "Warm Cinema": fg_resized = cv2.convertScaleAbs(fg_resized, alpha=1.05, beta=5)

            y0, x0 = (target_h - fg_resized.shape[0]) // 2, (target_w - fg_resized.shape[1]) // 2
            bg_layer[y0:y0 + fg_resized.shape[0], x0:x0 + fg_resized.shape[1]] = fg_resized
            frame = bg_layer

            # Logo
            if logo_img is not None:
                ly, lx = 25, max(0, target_w - logo_img.shape[1] - 25)
                lh, lw = logo_img.shape[:2]
                if ly + lh <= target_h and lx + lw <= target_w:
                    if logo_img.shape[2] == 4:
                        alpha = logo_img[:, :, 3].astype(np.float32) / 255.0
                        for c in range(3): frame[ly:ly+lh, lx:lx+lw, c] = alpha * logo_img[:, :, c] + (1.0 - alpha) * frame[ly:ly+lh, lx:lx+lw, c]
                    else:
                        frame[ly:ly+lh, lx:lx+lw] = logo_img[:, :, :3]

            # Blur
            if blur_h > 0 and blur_y + blur_h <= target_h:
                roi = frame[blur_y:blur_y + blur_h, 0:target_w]
                if roi.size:
                    sm = cv2.resize(roi, (max(1, target_w // 4), max(1, blur_h // 4)), interpolation=cv2.INTER_LINEAR)
                    b_sm = cv2.GaussianBlur(sm, (safe_kernel_size(max(3, blur_k // 4)), safe_kernel_size(max(3, blur_k // 4))), 0)
                    frame[blur_y:blur_y + blur_h, 0:target_w] = cv2.resize(b_sm, (target_w, blur_h), interpolation=cv2.INTER_LINEAR)

            # Subtitle
            while sub_idx + 1 < len(subtitle_segments) and c_sec > subtitle_segments[sub_idx]["end"]:
                sub_idx += 1
            s = subtitle_segments[sub_idx]
            text_str = s["text"] if s["start"] <= c_sec <= s["end"] else ""

            if text_str:
                pil_img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                draw = ImageDraw.Draw(pil_img)
                lines = wrap_text_myanmar_smart(text_str, font_primary, int(target_w * 0.90), draw)
                line_metrics = []
                total_text_h = 0
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font_primary, stroke_width=stroke_w)
                    lh = max(1, bbox[3] - bbox[1])
                    line_metrics.append((line, max(1, bbox[2] - bbox[0]), lh))
                    total_text_h += lh + 10
                total_text_h = max(0, total_text_h - 10)

                bottom_margin = int(target_h * (float(sub_pos_percent) / 100.0))
                curr_y = max(8, min(target_h - total_text_h - bottom_margin, target_h - total_text_h - 8))
                for line, lw, lh in line_metrics:
                    draw_line(draw, (max(4, (target_w - lw) // 2), curr_y), line, font_primary, text_rgb, stroke_w, stroke_rgb)
                    curr_y += lh + 10
                frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            video_writer.write(frame)

            if f_idx % int(fps * 2) == 0:
                frac = f_idx / total_output_frames
                progress(0.50 + 0.35 * frac, desc=f"🎬 Rendering Video ({int(frac * 100)}%)...")

        cap.release(); cap = None
        video_writer.release(); video_writer = None

        # F) Audio Concat & BGM
        progress(0.88, desc="🔊 05. Voiceover နှင့် BGM Audio ပေါင်းစပ်နေပါသည်...")
        merged_voice = os.path.join(work_dir, "voice_track.m4a")
        concat_list = os.path.join(work_dir, "audio_concat.txt")
        with open(concat_list, "w", encoding="utf-8") as f:
            for af in audio_segments:
                escaped_path = af.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat_list, "-c:a", "aac", "-b:a", "192k", merged_voice], check=False)

        final_audio = merged_voice
        if bgm_path and os.path.exists(bgm_path):
            mixed_audio = os.path.join(work_dir, "mixed_audio.m4a")
            vol_val = float(bgm_volume) / 100.0
            filter_cmd = f"[1:a]volume={vol_val},aloop=loop=-1:size=2e+09[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", merged_voice, "-i", bgm_path, "-filter_complex", filter_cmd, "-map", "[aout]", "-c:a", "aac", "-b:a", "192k", mixed_audio], check=False)
            if os.path.exists(mixed_audio): final_audio = mixed_audio

        # G) Final Video Output
        progress(0.95, desc="⚡ 06. Final MP4 ဗီဒီယို ထုတ်ယူနေပါသည်...")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", final_burn_temp, "-i", final_audio,
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "21", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", output_video_path
        ], check=False)

        if daily_limit is not None:
            USER_LIMIT_TRACKER[user_identifier]["count"] += 1

        progress(1.0, desc="✅ အောင်မြင်စွာ ပြုလုပ်ပြီးပါပြီ။")
        return output_video_path

    except Exception as e:
        raise gr.Error(f"❌ အမှားဖြစ်ပါသည်: {e}")
    finally:
        if cap is not None: cap.release()
        if video_writer is not None: video_writer.release()

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
    :root { --vip-bg: #070914; --vip-panel: rgba(17, 20, 38, .94); --vip-border: rgba(155, 123, 255, .28); --vip-gold: #f5c76b; --vip-text: #f7f7fb; }
    .gradio-container { max-width: 1260px !important; margin: 0 auto !important; background: linear-gradient(180deg, #090b17 0%, #070914 100%) !important; color: var(--vip-text); }
    .vip-hero { padding: 24px 28px; border: 1px solid var(--vip-border); border-radius: 22px; background: linear-gradient(135deg, rgba(34,37,67,.96), rgba(13,16,31,.96)); margin-bottom: 18px; }
    .vip-kicker { color: var(--vip-gold); letter-spacing: .16em; font-size: 12px; font-weight: 800; }
    .vip-title { font-size: clamp(24px, 4vw, 42px); font-weight: 900; margin: 7px 0; background: linear-gradient(90deg, #ffffff, #cfc3ff, #f5c76b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .login-card { border: 1px solid var(--vip-border); border-radius: 24px; padding: 28px; background: linear-gradient(180deg, rgba(26,29,53,.98), rgba(13,16,31,.98)); }
    .login-error { background: rgba(239,68,68,.12); border: 1px solid rgba(239,68,68,.28); color: #fecaca; padding: 10px; border-radius: 12px; text-align: center; }
    .login-success { background: rgba(34,197,94,.12); border: 1px solid rgba(34,197,94,.28); color: #bbf7d0; padding: 10px; border-radius: 12px; text-align: center; }
    .member-strip { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; border: 1px solid var(--vip-border); border-radius: 16px; background: rgba(139,92,246,.09); margin-bottom: 16px; }
    .member-name { font-size: 16px; font-weight: 800; color: #fff; }
    .quota-badge { border: 1px solid rgba(245,199,107,.35); color: var(--vip-gold); background: rgba(245,199,107,.08); border-radius: 999px; padding: 7px 11px; font-size: 12px; font-weight: 800; }
    .app-card { border: 1px solid var(--vip-border) !important; background: var(--vip-panel) !important; border-radius: 18px !important; padding: 12px !important; }
    #generate-btn { border: 0 !important; font-weight: 850 !important; border-radius: 14px !important; min-height: 52px; font-size: 17px !important; background: linear-gradient(90deg, #7657ff, #9b6dff) !important; }
    """
    theme = gr.themes.Soft(primary_hue="violet", secondary_hue="amber")

    with gr.Blocks(css=css, theme=theme, title="👑 VIP Video Auto Recap") as app:
        session_id_state = gr.State(lambda: str(uuid.uuid4()))
        vip_access_state = gr.State({"authenticated": False})

        gr.HTML("""
        <div class="vip-hero">
            <div class="vip-kicker">AI VIDEO STUDIO • VIP CLOUD EDITION</div>
            <div class="vip-title">👑 Magic Video Auto Recap</div>
            <div style="color:#a8adc3; font-size:14px;">Speech-to-Text • Burmese AI Recap • Voice Narration • Subtitle Burn • BGM Support</div>
        </div>
        """)

        # VIP Login Panel
        with gr.Column(visible=True, elem_classes=["login-shell"]) as login_panel:
            with gr.Column(elem_classes=["login-card"]):
                gr.HTML("<h2 style='text-align:center;'>👑 VIP Member Login</h2><p style='text-align:center; color:#a8adc3;'>Admin Portal မှ ထုတ်ပေးထားသော VIP Code ကို ထည့်သွင်းပါ</p>")
                vip_code_input = gr.Textbox(label="VIP CODE", placeholder="Format: VIP-XXXX-XXXX-XXXX", type="password")
                unlock_btn = gr.Button("🔓 Unlock VIP Studio", variant="primary")
                login_status = gr.HTML()

        # Main VIP App Panel
        with gr.Column(visible=False) as main_panel:
            with gr.Row():
                member_status_html = gr.HTML()
                logout_btn = gr.Button("↩ Logout", scale=0)

            with gr.Row():
                with gr.Column(scale=7):
                    with gr.Column(elem_classes=["app-card"]):
                        video_input = gr.Video(label="🎥 Upload Original Video", sources=["upload"])
                    with gr.Column(elem_classes=["app-card"]):
                        preview_image = gr.Image(label="Live Subtitle Blur Preview", interactive=False)

                with gr.Column(scale=5):
                    with gr.Column(elem_classes=["app-card"]):
                        user_api_key = gr.Textbox(label="🔑 Gemini API Key (Optional)", type="password", placeholder="မထည့်ပါက Google Translate backup သုံးမည်")
                        ratio_select = gr.Dropdown(choices=["9:16 (TikTok/Reels)", "16:9 (Landscape)"], value="9:16 (TikTok/Reels)", label="📐 Output Ratio")
                        background_fill = gr.Radio(choices=["Blur Background", "Black Background"], value="Blur Background", label="🖼️ Background Fill")

                    with gr.Column(elem_classes=["app-card"]):
                        voice_select = gr.Radio(choices=["🧕 မိန်းကလေး (Female)", "👨 ယောကျာ်လေး (Male)"], value="🧕 မိန်းကလေး (Female)", label="🎙️ AI Voice")
                        tone_style = gr.Dropdown(choices=["Thriller", "Comedy", "Dramatic", "Action/Epic", "Neutral"], value="Thriller", label="🎬 Narrative Tone")
                        desired_speed = gr.Slider(minimum=1.0, maximum=1.6, value=1.35, step=0.05, label="⚡ Voice Speed")

            with gr.Row():
                with gr.Column(elem_classes=["app-card"]):
                    with gr.Row():
                        text_color_input = gr.ColorPicker(label="Text Color", value="#FFFF00")
                        stroke_color_input = gr.ColorPicker(label="Outline Color", value="#000000")
                    sub_pos_percent = gr.Slider(minimum=0, maximum=90, value=15, step=1, label="📝 Subtitle Bottom Position (%)")
                    subtitle_size_percent = gr.Slider(minimum=2.0, maximum=7.0, value=3.8, step=0.1, label="🔠 Font Size (%)")

                with gr.Column(elem_classes=["app-card"]):
                    blur_y_percent = gr.Slider(minimum=0, maximum=100, value=78, step=1, label="📍 Blur Center (0=Top, 100=Bottom)")
                    blur_height_percent = gr.Slider(minimum=3, maximum=35, value=12, step=1, label="↕️ Blur Height (%)")
                    blur_strength = gr.Slider(minimum=5, maximum=151, value=51, step=2, label="🌫️ Blur Strength")

            with gr.Accordion("⚙️ Background Music (BGM) & Advanced Settings", open=False):
                with gr.Row():
                    bgm_file = gr.Audio(label="🎵 Background Music (BGM)", type="filepath")
                    bgm_vol = gr.Slider(minimum=1, maximum=50, value=15, step=1, label="🔊 BGM Volume (%)")
                with gr.Row():
                    enable_zoom = gr.Checkbox(label="Zoom & Crop", value=False)
                    zoom_level = gr.Slider(minimum=1.0, maximum=3.0, value=1.0, step=0.1, label="Zoom Level")
                    mirror_flip = gr.Checkbox(label="Mirror Flip", value=True)
                with gr.Row():
                    logo_file = gr.File(label="Logo (PNG)", file_types=["image"])
                    filter_color = gr.Dropdown(choices=["None", "Chrome Cool", "Warm Cinema"], value="None", label="🎨 Color Filter")

            submit_btn = gr.Button("✨ GENERATE VIP RECAP VIDEO", variant="primary", elem_id="generate-btn")

            with gr.Column(elem_classes=["app-card"]):
                output_video = gr.Video(label="✅ Final Recap Video Output")

        # Events
        unlock_btn.click(unlock_vip, [vip_code_input], [vip_access_state, login_panel, main_panel, login_status, member_status_html])
        vip_code_input.submit(unlock_vip, [vip_code_input], [vip_access_state, login_panel, main_panel, login_status, member_status_html])
        logout_btn.click(logout_vip, [], [vip_access_state, login_panel, main_panel, login_status, member_status_html, vip_code_input])

        p_inputs = [video_input, blur_y_percent, blur_height_percent, blur_strength]
        for trig in p_inputs:
            trig.change(update_preview_image, inputs=p_inputs, outputs=preview_image)

        submit_btn.click(
            fn=process_magic_recap_video,
            inputs=[
                video_input, user_api_key, ratio_select, background_fill, enable_zoom, zoom_level,
                logo_file, bgm_file, bgm_vol, mirror_flip, filter_color, voice_select, tone_style,
                text_color_input, stroke_color_input, blur_y_percent, blur_height_percent, blur_strength,
                sub_pos_percent, subtitle_size_percent, desired_speed, session_id_state, vip_access_state
            ],
            outputs=output_video
        )

    return app

# ================================================================
# 11) LAUNCH
# ================================================================
if __name__ == "__main__":
    demo = create_app()
    demo.queue(default_concurrency_limit=1).launch(share=True, debug=True)

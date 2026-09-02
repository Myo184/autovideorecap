# ================================================================
# 👑 VIP MAGIC VIDEO AUTO RECAP — GOOGLE COLAB (MONGODB CONNECTED)
# FAST ONE-PASS FFMPEG EDITION • VIP API CONNECTED
# ================================================================
# Recommended Runtime: T4 GPU (Runtime > Change runtime type > T4 GPU)

import os, sys, subprocess, importlib.util, shutil
from importlib import metadata as importlib_metadata
import threading
import base64
import socket
import platform
import urllib.request
import zipfile

YF_BUILD = "V6.9.2 • GRADIO 6 FIX • ONE-RUN SETUP • STEADY VOICE"
print(f"✨ YF Recap build: {YF_BUILD}")

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


def _installed_distribution_version(name):
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def _module_is_available(module_name):
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


PYTHON_313_PLUS = sys.version_info[:2] >= (3, 13)

LOCKED_PACKAGES = {
    # Binary/scientific stack: keep these together to prevent ABI errors.
    # Keep the current Colab 3.13 binary stack intact. Downgrading these inside
    # a live notebook is what causes numpy.dtype-size / ufunc ABI crashes.
    "numpy": "2.1.3" if PYTHON_313_PLUS else "1.26.4",
    "scipy": "1.16.3" if PYTHON_313_PLUS else "1.13.1",
    "opencv-python-headless": "5.0.0.93" if PYTHON_313_PLUS else "4.11.0.86",
    "Pillow": "11.3.0",
    "librosa": "0.11.0",
    "soundfile": "0.14.0" if PYTHON_313_PLUS else "0.13.1",
    # VoxCPM 2.x explicitly requires Gradio >=6,<7. Keep this entire web stack
    # on the mutually compatible versions already supplied by current Colab.
    "gradio": "6.26.0" if PYTHON_313_PLUS else "6.26.0",
    "gradio_client": "2.6.1" if PYTHON_313_PLUS else "2.6.1",
    "fastapi": "0.141.1" if PYTHON_313_PLUS else "0.141.1",
    "starlette": "1.6.0" if PYTHON_313_PLUS else "1.6.0",
    "pydantic": "2.13.4" if PYTHON_313_PLUS else "2.13.4",
    # App services.
    "faster-whisper": "1.2.0",
    "edge-tts": "7.2.3",
    "gTTS": "2.5.4",
    "google-genai": "2.12.1" if PYTHON_313_PLUS else "2.12.1",
    "voxcpm": "2.0.3",
}

# Distribution name -> import name. Distribution-version checks are more
# reliable than importing packages while pip may still need to repair them.
LOCKED_IMPORTS = {
    "numpy": "numpy", "scipy": "scipy", "opencv-python-headless": "cv2",
    "Pillow": "PIL", "librosa": "librosa", "soundfile": "soundfile",
    "gradio": "gradio", "gradio_client": "gradio_client", "fastapi": "fastapi",
    "starlette": "starlette", "pydantic": "pydantic",
    "faster-whisper": "faster_whisper", "edge-tts": "edge_tts", "gTTS": "gtts",
    "google-genai": "google.genai", "voxcpm": "voxcpm",
}


def ensure_supported_python():
    # Select a matching scientific lock above instead of forcing Colab users to
    # downgrade Python. Python 3.13 is supported by the Colab NumPy 2.1 lock.
    if not ((3, 10) <= sys.version_info[:2] < (3, 14)):
        raise RuntimeError(
            f"YF Recap requires Python 3.10–3.13; current Python is "
            f"{sys.version_info.major}.{sys.version_info.minor}. "
            "Please use a supported Google Colab runtime."
        )


def install_locked_packages():
    """Install exact tested versions only when the environment differs."""
    mismatches = []
    for package, wanted in LOCKED_PACKAGES.items():
        current = _installed_distribution_version(package)
        if current != wanted:
            mismatches.append((package, current, wanted))

    if not mismatches:
        print("✅ All YF packages match the lock — install skipped")
        return False

    changed_packages = {package for package, _current, _wanted in mismatches}

    print("🔒 Restoring tested package lock:")
    for package, current, wanted in mismatches:
        print(f"   • {package}: {current or 'missing'} → {wanted}")

    pinned = [f"{name}=={version}" for name, version in LOCKED_PACKAGES.items()]
    command = [
        sys.executable, "-m", "pip", "install",
        "--upgrade", "--upgrade-strategy", "only-if-needed", *pinned,
    ]
    install = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, check=False,
    )
    if install.returncode != 0:
        # Do not hide pip's useful resolver message behind CalledProcessError.
        details = (install.stdout or "No pip details returned.")[-6000:]
        print("❌ pip dependency resolver output:\n" + details)
        raise RuntimeError(
            "Locked package installation failed. Read the pip resolver output "
            "printed immediately above to see the exact conflicting package."
        )

    failed = []
    for package, wanted in LOCKED_PACKAGES.items():
        actual = _installed_distribution_version(package)
        if actual != wanted:
            failed.append(f"{package}={actual or 'missing'} (wanted {wanted})")
    if failed:
        raise RuntimeError("Package lock verification failed: " + ", ".join(failed))

    # Restart only if THIS run actually replaced a loaded binary package.
    # Installing pure/app packages such as VoxCPM, Edge-TTS or faster-whisper
    # can continue directly in the same run.
    binary_distributions = {
        "numpy", "scipy", "opencv-python-headless", "Pillow", "soundfile"
    }
    loaded_binary_modules = any(
        name in sys.modules for name in ("numpy", "scipy", "PIL", "cv2", "soundfile")
    )
    if changed_packages.intersection(binary_distributions) and loaded_binary_modules:
        raise RuntimeError(
            "✅ Locked packages were installed successfully. Please restart the "
            "Colab runtime once, then run this cell again. This one-time restart "
            "prevents NumPy binary incompatibility."
        )
    print("✅ Missing app packages installed — continuing without restart")
    return True


def verify_locked_imports():
    missing = [module for package, module in LOCKED_IMPORTS.items()
               if not _module_is_available(module)]
    if missing:
        raise RuntimeError("Locked package import check failed: " + ", ".join(missing))
    print("✅ Locked package import check passed")


def verify_torch_audio_pair():
    """Preserve Colab's CUDA-matched Torch; verify Torchaudio uses same release."""
    torch_version = _installed_distribution_version("torch")
    if not torch_version:
        raise RuntimeError("Colab PyTorch is missing. Select a T4 GPU runtime and reconnect.")
    torch_base = torch_version.split("+")[0]
    torchaudio_version = _installed_distribution_version("torchaudio")
    if not torchaudio_version or torchaudio_version.split("+")[0] != torch_base:
        print(f"🎧 Matching torchaudio to Colab torch {torch_base}...")
        run_pip("install", "-q", "--no-deps", f"torchaudio=={torch_base}")
    final_audio_version = _installed_distribution_version("torchaudio")
    if not final_audio_version or final_audio_version.split("+")[0] != torch_base:
        raise RuntimeError(
            f"Torch/Torchaudio mismatch: torch={torch_version}, "
            f"torchaudio={final_audio_version or 'missing'}"
        )
    print(f"✅ CUDA audio pair: torch {torch_version} / torchaudio {final_audio_version}")


print("📦 Checking locked Python packages...")
ensure_supported_python()
install_locked_packages()
verify_locked_imports()
verify_torch_audio_pair()

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
from gtts import gTTS
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

# VoxCPM2 is loaded lazily only when Voice Clone is selected.
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
GEMINI_FLASH_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]
GEMINI_LAST_SELECTED_MODEL = None
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
print("🔤 Default Myanmar font:", FONT_PATH or "NOT FOUND - fallback default used")

# Subtitle font styles. Put these .ttf files in /content/fonts/ or /content/ on Colab.
FONT_STYLE_FILES = {
    "Noto Sans Myanmar (Default)": [],
    "Myanmar Phetsot": ["Myanmar Phetsot Version 2.0 2017.ttf"],
    "Padauk Book Bold": ["Padauk-bookbold.ttf"],
    "Myanmar Sagar": ["Myanmar Sagar Version 2.0 2017.ttf"],
    "Myanmar Pyu": ["Myanmar Pyu Version 2.0 2017.ttf"],
    "Myanmar Pyu Pro": ["Myanmar Pyu Pro Version 2.0 2017.ttf"],
    "Custom Uploaded Font": [],
}

FONT_SEARCH_DIRS = [
    "/content/fonts",
    "/content",
    os.path.join(os.getcwd(), "fonts"),
    os.getcwd(),
    "/mnt/data",  # useful in ChatGPT/container testing; harmless in Colab
]

# Font files uploaded from the YF Recap UI are copied here and registered at runtime.
RUNTIME_FONT_DIR = "/content/yf_recap_fonts" if os.path.isdir("/content") else os.path.join(tempfile.gettempdir(), "yf_recap_fonts")
os.makedirs(RUNTIME_FONT_DIR, exist_ok=True)
RUNTIME_FONT_PATHS = {}

# Premium bundle support: every TTF/OTF inside the user's ZIP is registered as
# an individual subtitle choice.  The dropdown remains searchable, so a large
# collection stays easy to use on mobile as well as desktop.
PREMIUM_FONT_DIR = os.path.join(RUNTIME_FONT_DIR, "premium_bundle")


def _premium_font_style_name(font_path, group_hint=""):
    stem = os.path.splitext(os.path.basename(font_path))[0]
    group = str(group_hint or "").strip()
    return f"Premium • {group} • {stem}" if group else f"Premium • {stem}"


def _safe_extract_premium_fonts(zip_path):
    """Extract only TTF/OTF files from a trusted user font archive.

    Font files are flattened using their numbered bundle folder plus filename,
    which avoids duplicate names such as Burma027-Regular.ttf overwriting one
    another.
    """
    # This helper runs during module startup, before normalize_file_path() is
    # declared lower in the file, so resolve Gradio's common file values here.
    if isinstance(zip_path, dict):
        src = zip_path.get("path") or zip_path.get("name") or zip_path.get("orig_name")
    else:
        src = str(zip_path or "")
    if not src or not os.path.isfile(src):
        raise ValueError("Premium Font ZIP file မတွေ့ပါ။")
    if not zipfile.is_zipfile(src):
        raise ValueError("Upload လုပ်ထားတဲ့ file က valid ZIP မဟုတ်ပါ။")

    os.makedirs(PREMIUM_FONT_DIR, exist_ok=True)
    registered = []
    with zipfile.ZipFile(src) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            archive_name = info.filename.replace("\\", "/")
            ext = os.path.splitext(archive_name)[1].lower()
            if ext not in (".ttf", ".otf"):
                continue
            # A font bundle should be small; this guard also avoids archive abuse.
            if info.file_size <= 0 or info.file_size > 25 * 1024 * 1024:
                continue
            folders = [p for p in archive_name.split("/")[:-1] if p]
            group = next((p for p in reversed(folders) if p.isdigit()), "")
            safe_name = (group + "__" if group else "") + os.path.basename(archive_name)
            dst = os.path.join(PREMIUM_FONT_DIR, safe_name)
            with archive.open(info, "r") as read_f, open(dst, "wb") as write_f:
                shutil.copyfileobj(read_f, write_f)
            style = _premium_font_style_name(dst, group)
            RUNTIME_FONT_PATHS[style] = dst
            FONT_STYLE_FILES[style] = []
            registered.append(style)
    return registered


def install_premium_font_bundle(zip_value):
    """UI handler: install a ZIP and refresh the subtitle dropdown choices."""
    try:
        registered = _safe_extract_premium_fonts(zip_value)
    except Exception as exc:
        return (
            f"<div class='font-warn'>⚠️ Premium font ZIP မထည့်နိုင်ပါ: {exc}</div>",
            gr.update(choices=list(FONT_STYLE_FILES.keys())),
            gr.update(),
        )
    if not registered:
        return (
            "<div class='font-warn'>⚠️ ZIP ထဲမှာ TTF/OTF font မတွေ့ပါ။</div>",
            gr.update(choices=list(FONT_STYLE_FILES.keys())),
            gr.update(),
        )
    preferred = registered[0]
    return (
        f"<div class='font-ok'>✅ Premium fonts <b>{len(registered)}</b> ခု ထည့်ပြီးပါပြီ။ Subtitle Font Style မှာ search လုပ်ပြီးရွေးပါ။</div>",
        gr.update(choices=list(FONT_STYLE_FILES.keys()), value=preferred),
        subtitle_font_status(preferred),
    )


def _autoload_premium_font_bundle():
    """Load a ZIP already placed beside the Colab app, when available."""
    candidates = [
        "/content/PREMIUM FONT.zip",
        "/content/PREMIUM_FONT.zip",
        # Works when app.py and the supplied ZIP are downloaded together.
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "PREMIUM FONT.zip") if "__file__" in globals() else "",
        os.path.join(os.getcwd(), "PREMIUM FONT.zip"),
        os.path.join(os.getcwd(), "PREMIUM_FONT.zip"),
        "/mnt/data/PREMIUM FONT.zip",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            try:
                loaded = _safe_extract_premium_fonts(candidate)
                if loaded:
                    print(f"🔤 Premium subtitle fonts loaded: {len(loaded)}")
                    return len(loaded)
            except Exception as exc:
                print(f"⚠️ Premium font ZIP could not be loaded: {exc}")
    return 0


PREMIUM_FONT_COUNT = _autoload_premium_font_bundle()

def _font_style_from_filename(filename):
    base = os.path.basename(filename or "").lower()
    for style, names in FONT_STYLE_FILES.items():
        for name in names:
            if base == name.lower():
                return style
    # Friendly partial matching in case the browser slightly changes the name.
    aliases = {
        "phetsot": "Myanmar Phetsot",
        "padauk": "Padauk Book Bold",
        "sagar": "Myanmar Sagar",
        "pyu pro": "Myanmar Pyu Pro",
        "pyu": "Myanmar Pyu",
    }
    for key, style in aliases.items():
        if key in base:
            return style
    return None

def install_uploaded_subtitle_fonts(files, selected_style):
    """Install known YF fonts or any arbitrary TTF/OTF uploaded by the user.

    Known filenames are mapped to their friendly dropdown names. Any other valid
    font becomes `Custom Uploaded Font` (the last arbitrary font uploaded wins).
    The dropdown is automatically switched to the last successfully installed font.
    """
    if not files:
        return (
            "<div class='font-warn'>⚠️ Font files မတင်ရသေးပါ။ TTF/OTF font ကို upload လုပ်နိုင်ပါတယ်။</div>",
            subtitle_font_status(selected_style),
            gr.update(),
        )
    if not isinstance(files, (list, tuple)):
        files = [files]

    installed, failed = [], []
    selected_after_upload = selected_style

    for value in files:
        src = normalize_file_path(value)
        if not src or not os.path.isfile(src):
            failed.append(os.path.basename(str(src or value)))
            continue

        ext = os.path.splitext(src)[1].lower()
        if ext not in (".ttf", ".otf"):
            failed.append(os.path.basename(src))
            continue

        style = _font_style_from_filename(src)
        if not style:
            style = "Custom Uploaded Font"

        try:
            if style == "Custom Uploaded Font":
                # Preserve extension and keep a predictable runtime filename.
                dst = os.path.join(RUNTIME_FONT_DIR, "YF_Custom_Subtitle_Font" + ext)
            else:
                dst = os.path.join(RUNTIME_FONT_DIR, FONT_STYLE_FILES[style][0])
            shutil.copy2(src, dst)
            RUNTIME_FONT_PATHS[style] = dst
            selected_after_upload = style
            family = detect_font_family(dst)
            installed.append(f"{style} ({family})" if family else style)
        except Exception as exc:
            print(f"⚠️ Font install failed for {src}: {exc}")
            failed.append(os.path.basename(src))

    try:
        subprocess.run(["fc-cache", "-f", RUNTIME_FONT_DIR], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        pass

    parts = []
    if installed:
        parts.append("✅ Installed: <b>" + ", ".join(dict.fromkeys(installed)) + "</b>")
    if failed:
        parts.append("❌ Failed: " + ", ".join(failed))
    msg = "<div class='font-ok'>" + "<br>".join(parts or ["Font upload completed."]) + "</div>"
    return msg, subtitle_font_status(selected_after_upload), gr.update(value=selected_after_upload)


def resolve_subtitle_font(font_style):
    style = str(font_style or "Noto Sans Myanmar (Default)")

    runtime_path = RUNTIME_FONT_PATHS.get(style)
    if runtime_path and os.path.isfile(runtime_path):
        return runtime_path

    names = FONT_STYLE_FILES.get(style, [])
    for directory in FONT_SEARCH_DIRS:
        for name in names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate

    if style == "Noto Sans Myanmar (Default)":
        return FONT_PATH

    # Missing custom/known font: safe fallback so render never crashes.
    return FONT_PATH


def subtitle_font_status(font_style):
    requested = str(font_style or "Noto Sans Myanmar (Default)")
    runtime_path = RUNTIME_FONT_PATHS.get(requested)
    if runtime_path and os.path.isfile(runtime_path):
        family = detect_font_family(runtime_path)
        return f"<div class='font-ok'>✅ Final subtitle font: <b>{family or requested}</b></div>"

    if requested == "Noto Sans Myanmar (Default)":
        return "<div class='font-ok'>✅ Font: <b>Noto Sans Myanmar</b></div>"

    if requested == "Custom Uploaded Font":
        return (
            "<div class='font-warn'>⚠️ Custom font မတင်ရသေးပါ။ အောက်က Upload မှာ TTF/OTF font တင်ပါ။ "
            "တင်ပြီးတာနဲ့ Final subtitle ကို အဲဒီ font နဲ့ render လုပ်ပါမယ်။</div>"
        )

    # Known bundled-style name: see whether its expected file exists.
    path = resolve_subtitle_font(requested)
    expected_names = FONT_STYLE_FILES.get(requested, [])
    found_custom = bool(path and os.path.basename(path) in expected_names)
    if found_custom:
        family = detect_font_family(path)
        return f"<div class='font-ok'>✅ Final subtitle font: <b>{family or requested}</b></div>"

    return (
        f"<div class='font-warn'>⚠️ <b>{requested}</b> file မတွေ့သေးပါ။ "
        "TTF/OTF file ကို Upload လုပ်ပါ။ အခု Noto fallback သုံးမယ်။</div>"
    )

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


def _subtitle_visual_len(value):
    """Count visible Burmese/Latin characters, ignoring combining marks, spaces and punctuation."""
    import unicodedata
    punctuation = set("၊။,.!?;:…—–-_'\"()[]{}")
    count = 0
    for ch in (value or ""):
        if ch.isspace() or ch in punctuation:
            continue
        # Myanmar vowel signs / virama / medials / tone marks are combining parts
        # of the same visible syllable and should not count as separate letters.
        if unicodedata.combining(ch):
            continue
        count += 1
    return count


def _split_long_unspaced_subtitle_unit(unit, max_chars=35):
    """Fallback splitter for a very long Burmese unit with no spaces.

    Splits only at Myanmar syllable/grapheme-like boundaries, never through a
    combining-mark sequence. Normal spaced phrases do not use this fallback.
    """
    unit = (unit or "").strip()
    if not unit:
        return []
    try:
        clusters = segment_myanmar_syllables(unit)
    except Exception:
        clusters = [unit]
    out, current = [], ""
    for cluster in clusters:
        proposal = current + cluster
        if current and _subtitle_visual_len(proposal) > max_chars:
            out.append(current.strip())
            current = cluster
        else:
            current = proposal
    if current.strip():
        out.append(current.strip())
    return out or [unit]


def split_subtitle_display_chunks(text, min_chars=25, max_chars=35):
    """Create readable one-card subtitles without cutting normal words/phrases.

    Rules:
    - Aim for 25-35 visible characters per subtitle event.
    - Keep whitespace-delimited words/phrases intact.
    - Prefer breaks after Burmese/Latin sentence punctuation.
    - Only split inside a unit when it is itself longer than max_chars and has
      no usable spaces; that fallback uses Myanmar syllable boundaries.
    """
    text = (text or "").replace(" ြ", "ြ").replace("ြ ", "ြ")
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    # Keep trailing punctuation attached to each whitespace-delimited unit.
    raw_units = [u for u in re.findall(r"\S+", text) if u]
    units = []
    for unit in raw_units:
        if _subtitle_visual_len(unit) > max_chars:
            units.extend(_split_long_unspaced_subtitle_unit(unit, max_chars=max_chars))
        else:
            units.append(unit)

    chunks, current = [], ""
    sentence_end = ("။", "!", "?", "…")
    soft_end = ("၊", ",", ";", ":")

    for unit in units:
        proposal = unit if not current else f"{current} {unit}"
        proposal_len = _subtitle_visual_len(proposal)
        current_len = _subtitle_visual_len(current)

        # If adding the next intact unit would overflow, close the current card.
        if current and proposal_len > max_chars:
            chunks.append(current.strip())
            current = unit
        else:
            current = proposal

        cur_len = _subtitle_visual_len(current)
        # Natural punctuation breaks are preferred once the card is readable.
        if cur_len >= min_chars and current.endswith(sentence_end):
            chunks.append(current.strip())
            current = ""
        elif cur_len >= min_chars and current.endswith(soft_end) and cur_len >= max_chars - 4:
            chunks.append(current.strip())
            current = ""

    if current.strip():
        chunks.append(current.strip())

    # Avoid a tiny final card when it can safely join the previous one.
    if len(chunks) >= 2 and _subtitle_visual_len(chunks[-1]) < min_chars:
        merged = f"{chunks[-2]} {chunks[-1]}".strip()
        if _subtitle_visual_len(merged) <= max_chars + 3:
            chunks[-2] = merged
            chunks.pop()

    return [c for c in chunks if c]


def read_video_middle_frame(cap):
    """Read the frame at roughly 50% of a video, with a first-frame fallback."""
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if frame_count > 1:
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count // 2))
    ret, frame = cap.read()
    if ret and frame is not None:
        return True, frame

    # Some browser-uploaded/codecs do not support accurate seeking.
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    return cap.read()


def update_preview_image(video_value, blur_y_percent, blur_height_percent, blur_strength):
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        return None
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = read_video_middle_frame(cap)
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
    """Return a midpoint-frame JPEG data URI for the browser-side drag blur editor."""
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        return ""
    cap = None
    try:
        cap = cv2.VideoCapture(video_path)
        ret, frame = read_video_middle_frame(cap)
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
# 5B) GEMINI FLASH AUTO MODEL FALLBACK
# ================================================================
def _normalize_gemini_model_name(name):
    name = str(name or "").strip()
    return name.split("models/", 1)[-1] if name.startswith("models/") else name


def gemini_generate_auto(client, contents, system_instruction=None, purpose="Gemini"):
    """Try currently supported Flash models in priority order.

    The Gemini API changes model availability over time and availability can
    also differ by API key/account.  We first ask the API which models this
    key can see, then try the stable Flash candidates one-by-one.  Sampling
    parameters such as temperature are intentionally not sent because newer
    Gemini 3 Flash models no longer accept some legacy sampling parameters.
    """
    global GEMINI_LAST_SELECTED_MODEL
    candidates = list(GEMINI_FLASH_MODELS)

    # Prefer models the current API key actually exposes.  If listing fails,
    # simply use the known stable candidate order.
    try:
        available = set()
        for m in client.models.list():
            model_name = _normalize_gemini_model_name(getattr(m, "name", ""))
            if model_name:
                available.add(model_name)
        visible = [m for m in candidates if m in available]
        if visible:
            candidates = visible
    except Exception as list_exc:
        print(f"ℹ️ Gemini model listing unavailable; using fallback list: {list_exc}")

    last_error = None
    config = {"system_instruction": system_instruction} if system_instruction else None
    for model_name in candidates:
        try:
            print(f"🧠 {purpose}: trying {model_name} ...")
            kwargs = {
                "model": model_name,
                "contents": contents,
            }
            if config:
                kwargs["config"] = config
            response = client.models.generate_content(**kwargs)
            if response is not None and (getattr(response, "text", None) or "").strip():
                GEMINI_LAST_SELECTED_MODEL = model_name
                print(f"✅ {purpose}: selected {model_name}")
                return response, model_name
            last_error = RuntimeError(f"{model_name} returned empty text")
        except Exception as exc:
            last_error = exc
            print(f"⚠️ {purpose}: {model_name} unavailable: {exc}")

    raise RuntimeError(f"Gemini Flash models အားလုံးအသုံးမပြုနိုင်ပါ: {last_error}")


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
        response, selected_model = gemini_generate_auto(
            client,
            prompt,
            system_instruction=SYSTEM_INSTRUCTION,
            purpose="Recap translation",
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
# 7) TTS • EDGE + VOXCPM2 VOICE CLONE
# ================================================================
def generate_voice_sync(text, voice_id, filename, desired_tts_rate=1.15, target_duration_sec=None, retries=3):
    """Edge-TTS standard Burmese voice with retry protection.

    Edge's public speech endpoint occasionally returns ``NoAudioReceived`` even
    for valid requests.  Retry a few times before the render pipeline falls back to another Burmese voice and then Google TTS.
    """
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

    last_error = None
    for attempt in range(1, max(1, int(retries)) + 1):
        try:
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except OSError:
                pass

            try:
                asyncio.run(_async_gen())
            except RuntimeError:
                import threading
                holder = {"error": None}
                def runner():
                    try:
                        asyncio.run(_async_gen())
                    except Exception as exc:
                        holder["error"] = exc
                t = threading.Thread(target=runner, daemon=True)
                t.start(); t.join()
                if holder["error"]:
                    raise holder["error"]

            if os.path.exists(filename) and os.path.getsize(filename) > 512:
                return filename
            raise RuntimeError("Edge TTS returned no usable audio data")
        except Exception as exc:
            last_error = exc
            print(f"⚠️ Edge TTS attempt {attempt}/{retries} failed: {exc}")
            if attempt < retries:
                time.sleep(1.25 * attempt)

    raise RuntimeError(f"Edge TTS unavailable after {retries} attempts: {last_error}")


def generate_gtts_burmese_fallback(text, filename, desired_speed=1.0):
    """Generate Burmese speech with Google TTS as a fallback for Edge-TTS."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("gTTS fallback received empty text")

    out_path = str(filename)
    raw_path = out_path + ".gtts_raw.mp3"
    try:
        if os.path.exists(raw_path):
            os.remove(raw_path)
        gTTS(text=text, lang="my", slow=False).save(raw_path)
        if not os.path.exists(raw_path) or os.path.getsize(raw_path) == 0:
            raise RuntimeError("gTTS returned no audio")

        speed = max(0.5, min(2.0, float(desired_speed or 1.0)))
        if abs(speed - 1.0) < 0.02:
            shutil.copy2(raw_path, out_path)
        else:
            r = subprocess.run(
                [
                    "ffmpeg", "-y", "-loglevel", "error", "-i", raw_path,
                    "-filter:a", f"atempo={speed:.3f}", "-vn", out_path,
                ],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False,
            )
            if r.returncode != 0 or not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
                raise RuntimeError((r.stderr or "gTTS FFmpeg conversion failed")[-800:])
        print("✅ Edge TTS fallback: Google TTS Burmese audio generated")
        return out_path
    finally:
        try:
            if os.path.exists(raw_path):
                os.remove(raw_path)
        except OSError:
            pass


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

    # Keep reproducibility without assuming that the installed VoxCPM API
    # accepts a `seed=` keyword.  Some VoxCPM builds expose seed at a higher
    # level while others reject it inside VoxCPM._generate().
    if seed_value is not None:
        try:
            np.random.seed(seed_value % (2**32 - 1))
            torch.manual_seed(seed_value)
            if torch.cuda.is_available():
                torch.cuda.manual_seed_all(seed_value)
        except Exception:
            pass

    kwargs = {
        "text": clean_text,
        "cfg_value": cfg_value,
        "inference_timesteps": inference_timesteps,
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

    # VoxCPM has changed its generate/_generate keyword list across releases.
    # Call it defensively: when the installed build rejects a keyword, remove
    # only that unsupported keyword and retry instead of aborting the recap.
    generate_kwargs = dict(kwargs)
    removed_compat_args = []
    for _compat_try in range(8):
        try:
            wav = model.generate(**generate_kwargs)
            break
        except TypeError as exc:
            msg = str(exc)
            match = re.search(r"unexpected keyword argument ['\"]([^'\"]+)['\"]", msg)
            if not match:
                raise
            bad_arg = match.group(1)
            if bad_arg not in generate_kwargs:
                raise
            generate_kwargs.pop(bad_arg, None)
            removed_compat_args.append(bad_arg)
            print(f"⚙️ VoxCPM compatibility: '{bad_arg}' is unsupported by this installed version; retrying without it.")
    else:
        raise RuntimeError("VoxCPM generate compatibility retry limit reached")

    if removed_compat_args:
        print("✅ VoxCPM compatibility mode active; removed unsupported args:", ", ".join(removed_compat_args))

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
    display_name = name if len(name) <= 32 else name[:14] + "…" + name[-12:]
    if duration <= 0:
        return f"<div class='ref-status warn'>⚠️ <b>{display_name}</b> ကိုတွေ့ပေမယ့် duration မဖတ်နိုင်ပါ။</div>"
    if duration < 3.0:
        return f"<div class='ref-status warn'>⚠️ <b>{display_name}</b> • {duration:.1f}s — reference တိုလွန်းပါတယ်။ 5–15 sec ကြည်လင်တဲ့အသံကို အကြံပြုပါတယ်။</div>"
    if duration > 15.0:
        return f"<div class='ref-status ok'>✅ <b>{display_name}</b> • {duration:.1f}s — detected. Voice Clone မှာ ပထမ 15 sec ကို အသုံးပြုပါမယ်။</div>"
    return f"<div class='ref-status ok'>✅ <b>{display_name}</b> • {duration:.1f}s — VoxCPM2 cloning အတွက် reference ready ဖြစ်ပါတယ်။</div>"


def accept_clone_upload(reference_value):
    """Store UploadButton's file path without showing Gradio's changing file card."""
    path = normalize_file_path(reference_value)
    return path or "", inspect_clone_reference(path)


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
    subtitle_size_percent, sub_pos_percent, text_color, stroke_color, font_style="Noto Sans Myanmar (Default)"
):
    selected_font_path = resolve_subtitle_font(font_style)
    selected_font_family = detect_font_family(selected_font_path) if selected_font_path else ASS_FONT_FAMILY
    # V6.8.3: TRUE subtitle size control.
    # The previous formula used target_h plus a hard 22px minimum. On 16:9
    # (720px high), many slider values collapsed to the same 22px size, so
    # moving the slider appeared to do nothing.  Use a 1–10 visual scale and
    # map it against the SHORT side of the output frame.  This keeps the same
    # perceived size in both 9:16 and 16:9 and makes every slider movement
    # materially change the ASS font size.
    size_setting = max(1.0, min(10.0, float(subtitle_size_percent)))
    short_side = float(min(target_w, target_h))
    size_norm = (size_setting - 1.0) / 9.0
    font_size = max(18, int(round(short_side * (0.030 + (0.070 * size_norm)))))
    outline = max(2, int(round(font_size * 0.075)))
    # sub_pos_percent now means exact subtitle CENTER Y from the top of the final frame.
    subtitle_y_percent = max(3.0, min(97.0, float(sub_pos_percent)))
    subtitle_x = int(target_w * 0.50)
    subtitle_y = int(target_h * (subtitle_y_percent / 100.0))
    margin_v = 0

    # Wrap each subtitle once here instead of measuring/drawing it on every video frame.
    try:
        pil_font = ImageFont.truetype(selected_font_path, font_size) if selected_font_path else ImageFont.load_default()
        dummy = Image.new("RGB", (target_w, target_h), "black")
        draw = ImageDraw.Draw(dummy)
    except Exception:
        pil_font = None
        draw = None

    header = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: {target_w}\nPlayResY: {target_h}\nWrapStyle: 2\nScaledBorderAndShadow: yes\nYCbCr Matrix: TV.709\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{selected_font_family},{font_size},{ass_color(text_color)},&H000000FF,{ass_color(stroke_color)},&H66000000,-1,0,0,0,100,100,0,0,1,{outline},0,5,30,30,{margin_v},1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""

    lines = [header]
    for seg in subtitle_segments:
        txt = (seg.get("text") or "").strip()
        if not txt:
            continue
        if pil_font is not None and draw is not None:
            wrapped = wrap_text_myanmar_smart(txt, pil_font, int(target_w * 0.94), draw)
            txt = r"\N".join(wrapped)
        txt = escape_ass_text(txt).replace(r"\\N", r"\N")
        positioned_txt = rf"{{\an5\pos({subtitle_x},{subtitle_y})}}" + txt
        lines.append(
            f"Dialogue: 0,{ass_time(seg['start'])},{ass_time(seg['end'])},Default,,0,0,0,,{positioned_txt}\n"
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
    """Run FFmpeg while translating progress into percent + live ETA."""
    cmd = list(cmd)
    output_path = cmd.pop()
    cmd.extend(["-progress", "pipe:1", "-nostats", output_path])
    recent = []
    started = time.time()
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
            elapsed_video = parse_ffmpeg_time(line.split("=", 1)[1])
            frac = max(0.0, min(1.0, elapsed_video / max(float(total_duration), 0.1)))
            wall_elapsed = max(0.01, time.time() - started)
            eta = (wall_elapsed * (1.0 - frac) / frac) if frac >= 0.02 else None
            eta_text = f" • ETA {_fmt_eta_seconds(eta)}" if eta is not None else " • ETA calculating…"
            progress(start + (end - start) * frac, desc=f"{desc} ({int(frac * 100)}%){eta_text}")
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError("FFmpeg render failed:\n" + "\n".join(recent[-20:]))


def normalize_blur_zones(blur_layout_value, fallback_height=12.0):
    """Accept legacy center-Y values or the new JSON list of up to three blur rectangles."""
    default = [{"x": 0.0, "y": 72.0, "w": 100.0, "h": float(fallback_height or 12.0)}]
    raw = blur_layout_value
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            raw = parsed.get("zones", parsed) if isinstance(parsed, dict) else parsed
        except Exception:
            raw = None
    if isinstance(raw, list):
        zones = []
        for item in raw[:3]:
            if not isinstance(item, dict) or item.get("enabled", True) is False:
                continue
            try:
                x = max(0.0, min(97.0, float(item.get("x", 0))))
                y = max(0.0, min(97.0, float(item.get("y", 72))))
                w = max(3.0, min(100.0 - x, float(item.get("w", 100))))
                h = max(3.0, min(100.0 - y, float(item.get("h", fallback_height))))
                zones.append({"x": x, "y": y, "w": w, "h": h})
            except Exception:
                continue
        return zones
    try:
        center = float(blur_layout_value)
        height = max(3.0, min(45.0, float(fallback_height)))
        return [{"x": 0.0, "y": max(0.0, min(100.0 - height, center - height / 2)), "w": 100.0, "h": height}]
    except Exception:
        return default


def append_blur_zones(parts, input_label, zones, target_w, target_h, blur_strength, prefix="blur"):
    """Append chained crop/boxblur/overlay filters and return the final label."""
    current = input_label
    radius = max(2, min(32, int(float(blur_strength) / 6)))
    for index, zone in enumerate(zones[:3], 1):
        x = max(0, min(target_w - 2, int(target_w * zone["x"] / 100.0)))
        y = max(0, min(target_h - 2, int(target_h * zone["y"] / 100.0)))
        w = max(2, min(target_w - x, int(target_w * zone["w"] / 100.0)))
        h = max(2, min(target_h - y, int(target_h * zone["h"] / 100.0)))
        zone_radius = max(1, min(radius, min(w, h) // 4))
        main, src, band, out = (f"{prefix}main{index}", f"{prefix}src{index}", f"{prefix}band{index}", f"{prefix}out{index}")
        parts.append(f"[{current}]split=2[{main}][{src}]")
        parts.append(f"[{src}]crop={w}:{h}:{x}:{y},boxblur={zone_radius}:1[{band}]")
        parts.append(f"[{main}][{band}]overlay={x}:{y}[{out}]")
        current = out
    return current

def build_video_filter_graph(
    target_w, target_h, render_fps, total_duration,
    background_fill, enable_zoom, zoom_level, mirror_flip, filter_color,
    blur_y_percent, blur_height_percent, blur_strength,
    ass_path, logo_input_index=None, font_style="Noto Sans Myanmar (Default)"
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

    zones = normalize_blur_zones(blur_y_percent, blur_height_percent)
    current = append_blur_zones(parts, "base", zones, target_w, target_h, blur_strength, "mainblur")
    if logo_input_index is not None:
        logo_w = max(72, int(target_w * 0.16))
        parts.append(f"[{logo_input_index}:v]scale={logo_w}:-1[logo]")
        parts.append(f"[{current}][logo]overlay=W-w-24:24:format=auto[withlogo]")
        current = "withlogo"

    ass_escaped = ffmpeg_filter_escape(ass_path)
    active_font_path = resolve_subtitle_font(font_style)
    font_dir = ffmpeg_filter_escape(os.path.dirname(active_font_path) if active_font_path else "/usr/share/fonts")
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
    subtitle_font_style,
    desired_speed,
    render_mode,
    session_id,
    vip_access_state,
    progress=gr.Progress(track_tqdm=False)
):
    video_path = normalize_file_path(video_value)
    logo_path = normalize_file_path(logo_value)
    bgm_path = None  # BGM removed in V6.7
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
            display_chunks = split_subtitle_display_chunks(mm_text, min_chars=25, max_chars=35)
            if not display_chunks:
                display_chunks = [mm_text]
            total_chars = max(1, sum(len(c) for c in display_chunks))
            chunk_cursor = total_adjusted_duration
            for chunk in display_chunks:
                chunk_share = len(chunk) / total_chars
                chunk_dur = max(0.65, audio_dur * chunk_share)
                subtitle_segments.append({
                    "start": chunk_cursor,
                    "end": chunk_cursor + chunk_dur,
                    "text": chunk,
                })
                chunk_cursor += chunk_dur
            audio_segments.append(audio_path)
            total_adjusted_duration += audio_dur
            if subtitle_segments:
                subtitle_segments[-1]["end"] = total_adjusted_duration
            progress(
                0.35 + 0.18 * ((idx + 1) / total_segments),
                desc=f"🎙️ 03/06 • {engine_label} {idx + 1}/{total_segments}",
            )

        if not subtitle_segments:
            raise RuntimeError("TTS Voice ဖန်တီး၍ မရပါ။")

        # 4) Merge narration audio only. BGM is disabled in V6.7.
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
            subtitle_size_percent, sub_pos_percent, text_color, stroke_color, subtitle_font_style
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

        consume_video_quota(vip_access_state)

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
def _vip_api_dict(result):
    if isinstance(result, (list, tuple)) and len(result) == 1:
        result = result[0]
    if isinstance(result, str):
        return json.loads(result)
    if isinstance(result, dict):
        return result
    return dict(result)


def _member_quota_html(data):
    limit = data.get("daily_limit")
    used = int(data.get("used_today", 0) or 0)
    remaining = data.get("remaining_today")
    if limit is None:
        quota = f"Unlimited Videos · ဒီနေ့ထုတ်ပြီး {used}"
    else:
        limit = int(limit)
        remaining = max(0, int(remaining if remaining is not None else limit - used))
        quota = f"ဒီနေ့ထုတ်ပြီး {used}/{limit} · ကျန် {remaining} Videos"
    return f"""
    <div class="member-strip">
        <div>
            <div class="member-small">ACCESS GRANTED ({data.get('expiry', '')} အထိ)</div>
            <div class="member-name">👑 {data.get('label', 'VIP Member')} ({str(data.get('role', 'vip')).upper()})</div>
        </div>
        <div class="quota-badge">{quota}</div>
    </div>
    """


def refresh_member_quota(vip_access_state):
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        return ""
    try:
        client = Client(HF_SPACE_ID, token=HF_TOKEN or None, verbose=False)
        data = _vip_api_dict(client.predict(vip_access_state.get("code", ""), api_name="/verify"))
        return _member_quota_html(data) if data.get("valid") else f"<div class='login-error'>{data.get('msg', 'VIP status error')}</div>"
    except Exception as exc:
        print(f"[VIP QUOTA REFRESH ERROR] {type(exc).__name__}: {exc}")
        return _member_quota_html(vip_access_state)


def consume_video_quota(vip_access_state):
    """Register one successful render on the admin server and reject over-limit delivery."""
    code = str((vip_access_state or {}).get("code", "")).strip().upper()
    if not code:
        raise gr.Error("🔒 VIP Code မရှိပါ။ Login ပြန်ဝင်ပါ။")
    try:
        client = Client(HF_SPACE_ID, token=HF_TOKEN or None, verbose=False)
        data = _vip_api_dict(client.predict(code, api_name="/consume_video"))
    except Exception as exc:
        print(f"[VIP CONSUME ERROR] {type(exc).__name__}: {exc}")
        raise gr.Error("❌ Daily video quota server ကို ချိတ်ဆက်၍မရပါ။ Video ကို count မစစ်ဘဲ ထုတ်မပေးနိုင်ပါ။")
    if not data.get("valid") or not data.get("allowed"):
        raise gr.Error(data.get("msg") or "❌ ဒီနေ့ video limit ပြည့်ပါပြီ။")
    return data


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
        data = _vip_api_dict(result)

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
            "used_today": data.get("used_today", 0),
            "remaining_today": data.get("remaining_today"),
            "expiry": data.get("expiry", ""),
        }

        member_html = _member_quota_html(access_state)

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

    /* V6.7 mobile-first refinement */
    .audio-clean-card{border-color:#10b98142!important;background:linear-gradient(180deg,#071c1b99,#0a1325f0)!important}
    .clean-audio-badge{margin-top:10px;padding:9px 11px;border-radius:12px;background:#10b98112;border:1px solid #34d39935;color:#a7f3d0;font-size:11px;font-weight:800;line-height:1.45}
    .gradio-container label span{font-weight:800!important}
    @media(max-width:860px){
      .gradio-container{max-width:100%!important;padding:6px!important}
      .glass-card{margin-bottom:8px!important}
      .gradio-container video{width:100%!important;max-height:58vh!important;border-radius:14px!important}
      .gradio-container input,.gradio-container textarea,.gradio-container select{font-size:16px!important}
      .gradio-container button{min-height:52px!important;border-radius:14px!important}
      #auto-recap-btn{min-height:62px!important;font-size:17px!important;bottom:8px!important}
      #yf-download-btn{width:100%!important;min-height:58px!important}
      .final-top{align-items:flex-start!important}.final-badge{font-size:9px!important}
    }
    @media(max-width:480px){
      .yf-hero{padding:15px 12px!important}.yf-name{font-size:19px!important}.yf-tag{line-height:1.35!important}
      .glass-card{padding:10px!important;border-radius:15px!important}
      .step-head{font-size:13px!important}.hint{font-size:10px!important}
      .gradio-container video{max-height:55vh!important}
      #auto-recap-btn{font-size:16px!important}
    }
    """
    # V6.8.3 — complete Aurora UI redesign. This intentionally overrides the
    # older V6.8.2 palette while keeping all backend/component IDs intact.
    css += r"""
    :root{
      --aurora-bg:#05060b;--aurora-panel:#0d1019cc;--aurora-panel2:#111725d9;
      --aurora-line:#28354d;--aurora-mint:#56f2c7;--aurora-cyan:#43d9ff;
      --aurora-purple:#9b6cff;--aurora-pink:#ff5fb7;--aurora-text:#f7fbff;
      --aurora-muted:#96a6be;--aurora-warning:#ffd166;--aurora-danger:#ff6b83;
    }
    html,body{background:#05060b!important}
    body,.gradio-container{
      background:
        radial-gradient(900px 460px at -5% -5%,#00d4a91f 0%,transparent 62%),
        radial-gradient(820px 430px at 105% 2%,#9b6cff20 0%,transparent 60%),
        radial-gradient(650px 360px at 50% 105%,#ff5fb714 0%,transparent 70%),
        linear-gradient(180deg,#070913 0%,#05060b 60%,#04050a 100%)!important;
      color:var(--aurora-text)!important;
    }
    .gradio-container{max-width:1020px!important;padding:12px 14px 88px!important}

    /* Hero */
    .wiz-hero{
      border:1px solid #ffffff12!important;
      border-radius:30px!important;
      background:linear-gradient(145deg,#111522e8,#0a0d16e8)!important;
      box-shadow:0 28px 90px #0009,inset 0 1px #ffffff0d!important;
      backdrop-filter:blur(22px)!important;
      padding:25px!important;
    }
    .wiz-hero:before{content:"";position:absolute;inset:-2px;border-radius:31px;padding:1px;background:linear-gradient(125deg,#56f2c780,#43d9ff30,#9b6cff60,#ff5fb730);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
    .wiz-hero:after{width:300px!important;height:300px!important;right:-100px!important;top:-150px!important;background:radial-gradient(circle,#9b6cff2a,transparent 67%)!important}
    .wiz-logo{position:relative!important;isolation:isolate;width:62px!important;height:62px!important;flex-basis:62px!important;border-radius:20px!important;background:#0c1019!important;border:1px solid #56f2c744!important;box-shadow:0 0 0 5px #56f2c70a,0 14px 45px #43d9ff20!important;overflow:hidden}
    .wiz-logo:before{content:"";position:absolute;inset:-45%;z-index:-1;background:conic-gradient(from 0deg,#56f2c7,#43d9ff,#9b6cff,#ff5fb7,#56f2c7);animation:yfLogoSpin 7s linear infinite}
    .wiz-logo:after{content:"";position:absolute;inset:2px;z-index:-1;border-radius:18px;background:#0a0d14}
    .wiz-logo span{font-weight:1000;letter-spacing:-.06em;background:linear-gradient(120deg,#fff,#b9fff0 45%,#d9c8ff);-webkit-background-clip:text;background-clip:text;color:transparent}
    @keyframes yfLogoSpin{to{transform:rotate(360deg)}}
    .wiz-name{font-size:29px!important;letter-spacing:-.04em!important;background:linear-gradient(90deg,#fff,#c9fff2 43%,#d5c7ff 80%);-webkit-background-clip:text;background-clip:text;color:transparent}
    .wiz-sub{color:#7f91aa!important;letter-spacing:.13em!important;font-size:9px!important;font-weight:850!important}
    .wiz-note{color:#a6b4c8!important}.wiz-note b{color:#72f7d4!important}

    /* Wizard progress */
    .wiz-progress-wrap{background:linear-gradient(180deg,#05060bf2 72%,transparent)!important;backdrop-filter:blur(16px)!important}
    .wiz-line{background:linear-gradient(90deg,#223047,#33415b)!important}
    .wiz-node span{background:#0b0f18!important;border-color:#31405a!important;color:#71829c!important;transition:.25s ease!important}
    .wiz-node.active span{background:linear-gradient(135deg,#0f6c64,#336bd8 55%,#7652d1)!important;border-color:#72f7d4!important;box-shadow:0 0 0 5px #56f2c70d,0 0 25px #43d9ff32!important;transform:scale(1.08)}
    .wiz-node.done span{background:linear-gradient(135deg,#087a61,#0aa487)!important;border-color:#56f2c7!important;box-shadow:0 0 18px #56f2c725!important}
    .wiz-step-label{color:#72f7d4!important}

    /* Glass cards / fields */
    .wizard-card,.login-card-pro{
      border:1px solid #ffffff12!important;
      background:linear-gradient(180deg,#101520d9,#090d15e8)!important;
      box-shadow:0 24px 70px #0008,inset 0 1px #ffffff0b!important;
      backdrop-filter:blur(22px)!important;
      border-radius:25px!important;
    }
    .wizard-badge{border-color:#56f2c73d!important;background:linear-gradient(90deg,#56f2c711,#43d9ff0d)!important;color:#8dffe1!important;letter-spacing:.08em!important}
    .wizard-title{color:#f8fbff!important;letter-spacing:-.025em!important}
    .wizard-copy,.hint,.clone-copy{color:#95a6bd!important}
    .engine-panel{background:linear-gradient(180deg,#0b1019d9,#0a0d15dd)!important;border-color:#2b3950!important}
    .clone-panel{background:linear-gradient(145deg,#25153b8c,#0a1018dc)!important;border-color:#9b6cff52!important}
    .generate-summary,.download-note{background:#070b12d9!important;border-color:#26354c!important;color:#9eacc0!important}
    .clean-audio-badge{background:#56f2c70a!important;border-color:#56f2c738!important;color:#8affe0!important}

    /* Gradio form controls */
    .gradio-container input,.gradio-container textarea,.gradio-container select{
      border-radius:13px!important;
    }
    .gradio-container input:focus,.gradio-container textarea:focus,.gradio-container select:focus{
      outline:none!important;box-shadow:0 0 0 2px #56f2c72c,0 0 22px #43d9ff16!important;border-color:#56f2c778!important;
    }
    input[type=range]{accent-color:#56f2c7!important}

    /* Subtitle live size preview */
    .sub-size-preview{margin:8px 0 13px;padding:12px;border-radius:16px;border:1px solid #2b3a50;background:linear-gradient(145deg,#080c13,#0e1420);box-shadow:inset 0 1px #ffffff08}
    .sub-size-meta{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
    .sub-size-meta span{font-size:8px;font-weight:950;letter-spacing:.14em;color:#72839b}.sub-size-meta b{font-size:11px;color:#72f7d4}
    .sub-size-stage{min-height:78px;border-radius:12px;display:grid;place-items:center;text-align:center;padding:12px;background:radial-gradient(circle at 50% 120%,#9b6cff22,transparent 58%),#05070c;border:1px solid #ffffff0b;overflow:hidden}
    .sub-size-stage span{font-family:"Noto Sans Myanmar",sans-serif;font-weight:900;line-height:1.3;color:#ffe66d;text-shadow:-2px -2px 0 #000,2px -2px 0 #000,-2px 2px 0 #000,2px 2px 0 #000;transition:font-size .22s ease}
    .sub-size-preview small{display:block;margin-top:7px;color:#76879e;font-size:9px;line-height:1.45}

    /* Live process card */
    .process-card{border-color:#43d9ff35!important;background:linear-gradient(135deg,#07121ae8,#121326e8)!important;box-shadow:0 18px 46px #0006,inset 0 1px #ffffff09!important}
    .process-spinner{border-color:#56f2c725!important;border-top-color:#56f2c7!important;border-right-color:#9b6cff!important;box-shadow:0 0 20px #43d9ff20!important}
    .process-top strong{color:#72f7d4!important}.process-track{height:9px!important;background:#03060b!important;border-color:#243249!important}.process-track i{background:linear-gradient(90deg,#56f2c7,#43d9ff,#9b6cff,#ff5fb7)!important;background-size:220% 100%!important;animation:yfProgressFlow 2s linear infinite!important;box-shadow:0 0 18px #43d9ff54!important}
    @keyframes yfProgressFlow{to{background-position:220% 0}}
    .eta-card.ready{border-color:#56f2c732!important;background:linear-gradient(105deg,#56f2c70d,#43d9ff0c,#9b6cff0d)!important}.eta-icon{background:#56f2c70e!important;border-color:#56f2c72b!important}

    /* Button system — hover lift + glow + press feedback + shimmer */
    .gradio-container button,#yf-download-btn{
      position:relative!important;overflow:hidden!important;isolation:isolate!important;
      transition:transform .18s ease,box-shadow .22s ease,border-color .22s ease,filter .22s ease!important;
      -webkit-tap-highlight-color:transparent!important;
    }
    .gradio-container button:hover,#yf-download-btn:hover{transform:translateY(-2px) scale(1.006)!important;filter:brightness(1.08)!important}
    .gradio-container button:active,#yf-download-btn:active{transform:translateY(1px) scale(.985)!important;transition-duration:.07s!important}
    .wiz-next{background:linear-gradient(105deg,#0e9f82,#178fb6 48%,#6f50d7)!important;border:1px solid #78f9d745!important;box-shadow:0 10px 28px #43d9ff1b!important}
    .wiz-next:hover{box-shadow:0 15px 38px #43d9ff2d,0 0 0 1px #56f2c72c inset!important}
    .wiz-back{background:linear-gradient(180deg,#121824,#0b1019)!important;border-color:#34425a!important;color:#c7d1df!important}.wiz-back:hover{border-color:#71839d!important;box-shadow:0 10px 26px #0005!important}

    #auto-recap-btn{
      min-height:68px!important;border-radius:18px!important;font-size:16px!important;letter-spacing:.015em!important;
      background:linear-gradient(105deg,#0eaa87 0%,#158eb2 35%,#6651d6 67%,#d34b9b 100%)!important;
      background-size:220% 100%!important;
      border:1px solid #ffffff24!important;
      box-shadow:0 18px 46px #43d9ff24,0 0 0 1px #56f2c71f inset!important;
      animation:yfButtonFlow 5s ease infinite!important;
    }
    #auto-recap-btn:before,#yf-download-btn:before{content:"";position:absolute;z-index:-1;top:-100%;left:-40%;width:35%;height:300%;transform:rotate(20deg);background:linear-gradient(90deg,transparent,#ffffff35,transparent);animation:yfShine 3.6s ease-in-out infinite}
    #auto-recap-btn:hover{box-shadow:0 22px 58px #43d9ff38,0 0 30px #9b6cff24!important}
    @keyframes yfButtonFlow{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
    @keyframes yfShine{0%,65%{left:-55%;opacity:0}72%{opacity:1}100%{left:125%;opacity:0}}

    #yf-download-btn{background:linear-gradient(105deg,#079b78,#0b8ba8,#4e61d8)!important;border-color:#56f2c74a!important;box-shadow:0 15px 38px #56f2c71d!important}
    #yf-download-btn:hover{box-shadow:0 20px 48px #56f2c72d!important}

    .final-stage{border-color:#56f2c72e!important;background:linear-gradient(145deg,#0a1417d9,#0d1020e8)!important}.final-badge{background:#56f2c70c!important;border-color:#56f2c738!important;color:#8affe0!important}
    .footer-note{color:#4d5c72!important;letter-spacing:.05em!important}

    @media(max-width:720px){
      .gradio-container{padding:6px 7px 82px!important}.wiz-hero{padding:18px 14px!important;border-radius:22px!important}.wiz-logo{width:50px!important;height:50px!important;flex-basis:50px!important;border-radius:16px!important}.wiz-logo:after{border-radius:14px!important}.wiz-name{font-size:22px!important}.wizard-card{padding:13px!important;border-radius:19px!important}.wizard-title{font-size:18px!important}
      #auto-recap-btn{min-height:64px!important;bottom:10px!important;border-radius:16px!important;font-size:15px!important}
      .sub-size-stage{min-height:70px}.process-card{padding:12px!important}.process-main>span{font-size:9.5px!important}

    }
    @media(prefers-reduced-motion:reduce){.wiz-logo:before,.process-track i,#auto-recap-btn,#auto-recap-btn:before,#yf-download-btn:before{animation:none!important}.gradio-container button,#yf-download-btn{transition:none!important}}
    """
    theme = gr.themes.Soft(primary_hue="emerald", secondary_hue="violet", neutral_hue="slate")

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

                        desired_speed = gr.Slider(0.9, 1.1, value=1.0, step=0.05, label="Voice Pace • Normal (Fixed)", interactive=False)
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
                    sub_pos_percent = gr.Slider(4, 96, value=82, step=1, label="Subtitle Y Position (%)")
                    subtitle_size_percent = gr.Slider(1.0, 10.0, value=5.5, step=0.5, label="Subtitle Size • 1 Small — 10 Large")

                with gr.Column(elem_classes=["glass-card"]):
                    gr.HTML("""<div class="section-cap"><span>🌫</span> Blur Strength</div>
                    <div class="engine-box">
                      <b>Position & Height</b> ကို အပေါ်က video preview ပေါ်မှာ mouse နဲ့တိုက်ရိုက် drag/resize လုပ်ပါ။
                      ဒီနေရာမှာ final blur အားကိုပဲ ချိန်ရပါမယ်။
                    </div>""")
                    blur_y_percent = gr.Number(value=78, visible=False)
                    blur_height_percent = gr.Number(value=12, visible=False)
                    blur_strength = gr.Slider(5, 151, value=51, step=2, label="Final Blur Strength")

            with gr.Accordion("✨ Brand & Advanced", open=False):
                bgm_file = gr.State(None)
                bgm_vol = gr.State(0)
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

        submit_evt = submit_btn.click(
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
        submit_evt.success(
            refresh_member_quota,
            inputs=[vip_access_state],
            outputs=[member_status_html],
            queue=False,
            show_progress="hidden",
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


def _sample_video_frames_for_story(video_path, duration, max_frames=18):
    """Return small, timestamped RGB frames for Gemini visual story analysis.

    Sampling frames (instead of uploading the whole movie) keeps the request
    fast and makes this work for silent clips as well as dialogue-heavy videos.
    """
    duration = max(0.5, float(duration or 0.0))
    count = max(3, min(int(max_frames), max(3, int(np.ceil(duration / 7.0)))))
    # Keep the first/last visual beat, but avoid exact black frames at 0 seconds.
    start = min(0.35, duration * 0.15)
    end = max(start, duration - min(0.35, duration * 0.15))
    moments = np.linspace(start, end, num=count).tolist()
    cap = cv2.VideoCapture(video_path)
    frames = []
    try:
        for moment in moments:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(moment) * 1000.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            h, w = frame.shape[:2]
            scale = min(1.0, 640.0 / max(1, w))
            if scale < 1.0:
                frame = cv2.resize(frame, (max(1, int(w * scale)), max(1, int(h * scale))), interpolation=cv2.INTER_AREA)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append({"time": float(moment), "image": Image.fromarray(rgb)})
    finally:
        cap.release()
    return frames


def _visual_scenes_from_gemini(video_path, duration, user_api_key):
    """Ask Gemini to describe chronological visual events, including hard subtitles.

    The supplied API key is deliberately required.  Whisper can still handle an
    audio-only recap without it, but a silent video needs a vision-capable model.
    """
    api_key = (user_api_key or "").strip()
    if not api_key:
        return []
    frames = _sample_video_frames_for_story(video_path, duration)
    if not frames:
        return []

    prompt = f"""
You are analyzing chronological frames from one movie/video clip ({duration:.2f} seconds total).
Each image is labelled with its timestamp. Describe only what can actually be seen.

Create short chronological visual-story scenes. Read any visible on-screen subtitle/text only when legible, but do not invent dialogue, names, motives, or events that are not visible. Combine adjacent frames when they show one continuing event.

Return VALID JSON ONLY in this exact shape:
{{"scenes":[{{"start":0.0,"end":5.0,"text":"Objective visual event description"}}]}}

Rules:
- Keep start/end inside 0–{duration:.2f}, in chronological order.
- Cover the important visual events across the full clip, including silent action.
- `text` must be factual visual context suitable for a later Burmese recap writer.
"""
    contents = [prompt]
    for item in frames:
        contents.extend([f"Frame timestamp: {item['time']:.2f} seconds", item["image"]])

    try:
        client = genai.Client(api_key=api_key)
        response, selected_model = gemini_generate_auto(
            client, contents,
            system_instruction="Analyze video frames faithfully. Never invent unseen story facts.",
            purpose="Visual movie analysis",
        )
        raw = (response.text or "").strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
    except Exception as exc:
        print(f"⚠️ Visual analysis unavailable; continuing with speech only: {exc}")
        return []

    scenes, last_end = [], 0.0
    for item in parsed.get("scenes", []):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        try:
            start = max(0.0, float(item.get("start", last_end)))
            end = float(item.get("end", start + 4.0))
        except (TypeError, ValueError):
            continue
        start = max(last_end, min(start, duration))
        end = min(duration, max(start + 0.35, end))
        if end <= start:
            continue
        scenes.append({"scene": len(scenes) + 1, "start": start, "end": end, "text": text})
        last_end = end
    return scenes


def _combine_audio_and_visual_scenes(audio_scenes, visual_scenes):
    """Use visual context for every scene and attach overlapping dialogue when present."""
    if not visual_scenes:
        return audio_scenes
    combined = []
    for visual in visual_scenes:
        spoken = []
        for audio in audio_scenes:
            if float(audio["end"]) > float(visual["start"]) and float(audio["start"]) < float(visual["end"]):
                spoken.append((audio.get("text") or "").strip())
        visual_text = (visual.get("text") or "").strip()
        dialogue = " ".join(x for x in spoken if x)
        text = f"Visual: {visual_text}"
        if dialogue:
            text += f"\nDialogue heard: {dialogue}"
        combined.append({
            "scene": len(combined) + 1,
            "start": float(visual["start"]),
            "end": float(visual["end"]),
            "text": text,
        })
    return combined


def analyze_movie_v3(video_value, vip_access_state, user_api_key="", progress=gr.Progress(track_tqdm=False)):
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        raise gr.Error("🎬 Movie/Video upload လုပ်ပါ။")
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        raise gr.Error("🔒 VIP Code ဖြင့် Login ဝင်ပါ။")

    progress(0.08, desc="🎙️ Speech & dialogue ကို Analyze လုပ်နေသည်...")
    try:
        segments_raw, info = whisper_model.transcribe(
            video_path, beam_size=1, vad_filter=True, condition_on_previous_text=False
        )
        raw_segments = [
            {"start": float(s.start), "end": float(s.end), "text": (s.text or "").strip()}
            for s in segments_raw if (s.text or "").strip()
        ]
    except Exception as exc:
        # A completely silent MP4 can have no audio stream at all.  That must
        # not block the visual/Gemini route.
        print(f"ℹ️ Speech track unavailable; switching to visual analysis: {exc}")
        info = None
        raw_segments = []

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    duration = (frame_count / fps) if fps > 0 else (raw_segments[-1]["end"] if raw_segments else 0.0)

    audio_scenes = group_transcript_scenes(raw_segments)
    progress(0.55, desc="👁️ Video scenes ကိုဖတ်နေသည်...")
    visual_scenes = _visual_scenes_from_gemini(video_path, duration, user_api_key)
    scenes = _combine_audio_and_visual_scenes(audio_scenes, visual_scenes)
    if not scenes:
        raise gr.Error(
            "🎙️ Speech/dialogue မဖတ်မိပါ။ Silent video ကို visual အနေနဲ့ရေးရန် Gemini API Key ထည့်ပြီး ပြန်စမ်းပါ။"
        )

    progress(0.72, desc="🧠 Narrative scenes ခွဲနေသည်...")
    lang = getattr(info, "language", None) or "en"

    state = {
        "video_path": video_path,
        "duration": float(duration),
        "fps": float(fps),
        "width": width,
        "height": height,
        "language": lang,
        "raw_segments": raw_segments,
        "audio_scenes": audio_scenes,
        "visual_scenes": visual_scenes,
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
        f"**Narrative Scenes:** {len(scenes)}  ·  **Speech Chunks:** {len(raw_segments)}  ·  **Visual Scenes:** {len(visual_scenes)}\n\n"
        "အောက်က **Generate Viral Recap Script** ကိုနှိပ်ပြီး script ဖန်တီးပါ။"
    )
    return state, summary, rows


def _target_seconds(choice, source_duration):
    """Resolve requested recap duration.

    Default / unspecified mode now targets the SAME duration as the uploaded
    source video. Manual 1/3/5/10 minute choices still override this behavior.
    """
    mapping = {
        "⚡ 1 Minute Short": 60,
        "🎬 3 Minute Recap": 180,
        "🔥 5 Minute Recap": 300,
        "🍿 10 Minute Recap": 600,
    }
    if choice in mapping:
        return mapping[choice]

    # 🎞 Unspecified mode = preserve uploaded-video duration as the recap target.
    return max(1.0, float(source_duration or 0.0))


def generate_recap_script_v3(analysis_state, user_api_key, tone_style, recap_length,
                             progress=gr.Progress(track_tqdm=False)):
    if not isinstance(analysis_state, dict) or not analysis_state.get("scenes"):
        raise gr.Error("🧠 အရင်ဆုံး Analyze Movie ကိုနှိပ်ပါ။")

    scenes = analysis_state["scenes"]
    source_duration = float(analysis_state.get("duration", 0.0))
    # This renderer deliberately preserves the uploaded video's duration, so a
    # requested 3/5/10-minute setting cannot create a longer visual timeline.
    target_sec = min(_target_seconds(recap_length, source_duration), max(1.0, source_duration))
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
Target spoken-script size: approximately {int(target_sec * 14.5)} Burmese visible characters overall.
When the target is close to the source duration, preserve nearly all meaningful chronological events instead of aggressively summarizing.
Write a detailed, connected narration that fills about 92–100% of the requested duration at a NORMAL,
steady Burmese speaking pace. Prefer a fuller script over a short summary, while never adding unsupported facts.

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
            response, selected_model = gemini_generate_auto(
                client,
                prompt,
                system_instruction=SYSTEM_INSTRUCTION,
                purpose="Viral recap script",
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
    progress(1.0, desc="✅ Viral Recap Script Ready")
    status = (
        f"### ✅ Viral Recap Script Ready\n"
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
    # YF Recap: original movie audio is intentionally removed.
    original_volume = 0
    original_path = None
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




def mix_story_audio_full_duration(voice_path, source_video_path, bgm_path, narration_volume,
                                  original_volume, bgm_volume, auto_duck_bgm,
                                  total_duration, output_path):
    """Narration-only final audio, padded to the uploaded video's duration.

    YF Recap V6.7 intentionally removes BOTH the original movie audio and BGM.
    Only generated narration is present in the final MP4.  Silence is padded at
    the end when narration is shorter than the source so duration stays locked.
    """
    total_duration = max(0.5, float(total_duration))
    nv = max(0.0, min(2.0, float(narration_volume) / 100.0))
    filters = (
        f"[0:a]volume={nv:.4f},"
        f"apad=whole_dur={total_duration:.3f},"
        f"atrim=duration={total_duration:.3f},"
        "alimiter=limit=0.95[aout]"
    )
    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", voice_path,
        "-filter_complex", filters,
        "-map", "[aout]",
        "-t", f"{total_duration:.3f}",
        "-c:a", "aac", "-b:a", "160k",
        output_path,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("Narration-only audio build failed: " + (r.stderr or "Unknown error")[-800:])
    return output_path


def fit_narration_clip_to_slot(audio_path, slot_duration, output_path):
    """Tempo-adjust one narration clip so it exactly fills its source scene.

    This is the key sync rule: a line whose script timestamp is 12–18 seconds
    always occupies that six-second video window, rather than being concatenated
    immediately after the preceding TTS line.
    """
    target = max(0.35, float(slot_duration))
    source = max(0.05, probe_duration(audio_path, fallback=target))
    # atempo > 1 speeds speech up; < 1 slows it down. `_atempo_filters` safely
    # splits extreme values into FFmpeg-supported 0.5–2.0 stages.
    tempo = source / target
    filters = (
        f"[0:a]aresample=48000,{_atempo_filters(tempo)},"
        f"apad=whole_dur={target:.3f},atrim=duration={target:.3f}[aout]"
    )
    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", audio_path,
        "-filter_complex", filters, "-map", "[aout]",
        "-c:a", "pcm_s16le", output_path,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("Narration timing fit failed: " + (r.stderr or "Unknown error")[-700:])
    return output_path


def build_timeline_narration_track(voice_files, source_segments, total_duration, output_path):
    """Place each fitted narration clip at its actual source-video timestamp."""
    if not voice_files or not source_segments or len(voice_files) != len(source_segments):
        raise RuntimeError("Narration timeline has no matching voice/scene clips.")
    inputs, filters, labels = [], [], []
    for idx, (audio_path, segment) in enumerate(zip(voice_files, source_segments)):
        delay_ms = max(0, int(round(float(segment.get("start", 0.0)) * 1000.0)))
        inputs.extend(["-i", audio_path])
        label = f"v{idx}"
        filters.append(f"[{idx}:a]aresample=48000,adelay={delay_ms}:all=1[{label}]")
        labels.append(f"[{label}]")
    filters.append(
        "".join(labels)
        + f"amix=inputs={len(labels)}:duration=longest:normalize=0,"
          f"apad=whole_dur={float(total_duration):.3f},"
          f"atrim=duration={float(total_duration):.3f},alimiter=limit=0.95[aout]"
    )
    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", ";".join(filters), "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k", output_path,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("Narration timeline build failed: " + (r.stderr or "Unknown error")[-700:])
    return output_path


def build_continuous_narration_track(voice_files, output_path):
    """Join generated clips without changing their natural speaking speed."""
    if not voice_files:
        raise RuntimeError("Narration track has no voice clips.")
    inputs, labels = [], []
    for idx, audio_path in enumerate(voice_files):
        inputs.extend(["-i", audio_path])
        labels.append(f"[{idx}:a]")
    filters = (
        "".join(labels)
        + f"concat=n={len(labels)}:v=0:a=1,aresample=48000,alimiter=limit=0.95[aout]"
    )
    r = subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
        "-filter_complex", filters, "-map", "[aout]",
        "-c:a", "aac", "-b:a", "192k", output_path,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if r.returncode != 0 or not os.path.exists(output_path):
        raise RuntimeError("Continuous narration build failed: " + (r.stderr or "Unknown error")[-700:])
    return output_path


def build_full_source_video_filter_graph(target_w, target_h, render_fps, total_duration,
                                         background_fill, enable_zoom, zoom_level,
                                         mirror_flip, filter_color, blur_y_percent,
                                         blur_height_percent, blur_strength, ass_path,
                                         logo_input_index=None,
                                         font_style="Noto Sans Myanmar (Default)"):
    """Render the COMPLETE uploaded video, preserving its duration exactly."""
    parts = []
    z = max(1.0, float(zoom_level))
    fg_filters = [f"fps={render_fps}"]
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
        parts.append("[0:v]split=2[vbgsrc][vfgsrc]")
        bg_w, bg_h = max(160, target_w // 4), max(160, target_h // 4)
        parts.append(
            f"[vbgsrc]fps={render_fps},scale={bg_w}:{bg_h}:force_original_aspect_ratio=increase,"
            f"crop={bg_w}:{bg_h},boxblur=10:1,scale={target_w}:{target_h},setsar=1[bg]"
        )
        parts.append(f"[vfgsrc]{fg_chain}[fg]")
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[base]")
    else:
        parts.append(f"color=c=0x050713:s={target_w}x{target_h}:r={render_fps}:d={total_duration:.3f}[bg]")
        parts.append(f"[0:v]{fg_chain}[fg]")
        parts.append("[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1[base]")

    zones = normalize_blur_zones(blur_y_percent, blur_height_percent)
    current = append_blur_zones(parts, "base", zones, target_w, target_h, blur_strength, "fullblur")

    if logo_input_index is not None:
        logo_w = max(72, int(target_w * 0.16))
        parts.append(f"[{logo_input_index}:v]scale={logo_w}:-1[logo]")
        parts.append(f"[{current}][logo]overlay=W-w-24:24:format=auto[withlogo]")
        current = "withlogo"

    ass_escaped = ffmpeg_filter_escape(ass_path)
    active_font_path = resolve_subtitle_font(font_style)
    font_dir = ffmpeg_filter_escape(
        os.path.dirname(active_font_path) if active_font_path else "/usr/share/fonts"
    )
    parts.append(
        f"[{current}]ass=filename='{ass_escaped}':fontsdir='{font_dir}',format=yuv420p[vout]"
    )
    return ";\n".join(parts)


def build_story_video_filter_graph(source_segments, voice_durations, target_w, target_h, render_fps,
                                   total_duration, background_fill, enable_zoom, zoom_level,
                                   mirror_flip, filter_color, blur_y_percent, blur_height_percent,
                                   blur_strength, ass_path, logo_input_index=None,
                                   font_style="Noto Sans Myanmar (Default)"):
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

    zones = normalize_blur_zones(blur_y_percent, blur_height_percent)
    current = append_blur_zones(parts, "base", zones, target_w, target_h, blur_strength, "storyblur")
    if logo_input_index is not None:
        logo_w = max(72, int(target_w * 0.16))
        parts.append(f"[{logo_input_index}:v]scale={logo_w}:-1[logo]")
        parts.append(f"[{current}][logo]overlay=W-w-24:24:format=auto[withlogo]")
        current = "withlogo"
    ass_escaped = ffmpeg_filter_escape(ass_path)
    active_font_path = resolve_subtitle_font(font_style)
    font_dir = ffmpeg_filter_escape(os.path.dirname(active_font_path) if active_font_path else "/usr/share/fonts")
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
    sub_pos_percent, subtitle_size_percent, subtitle_font_style, desired_speed, render_mode,
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
    source_duration = max(0.5, float(analysis_state.get("duration", 0.0) or 0.0))
    if source_duration <= 0.5:
        source_duration = max(0.5, probe_duration(video_path, fallback=1.0))
    total = len(script_segments)

    total_started_at = time.time()
    voice_started_at = time.time()
    progress(0.03, desc="🎙️ Recap narration ထုတ်နေသည်... • ETA calculating…")
    for idx, seg in enumerate(script_segments):
        text = seg["text"].strip()
        src_dur = max(0.3, seg["end"] - seg["start"])
        if "Edge TTS" in str(voice_engine):
            audio = os.path.join(work_dir, f"voice_{idx:03d}.mp3")
            voice_id = EDGE_VOICES.get(edge_voice_name, "my-MM-NilarNeural")
            try:
                generate_voice_sync(
                    text, voice_id, audio,
                    desired_tts_rate=1.0,
                    target_duration_sec=None,
                    retries=3,
                )
            except Exception as edge_exc:
                # V6 has no Voice Design fallback. Retry with the other Burmese
                # Edge voice so a transient per-voice failure does not require a second click.
                alternate_voice = "my-MM-ThihaNeural" if voice_id == "my-MM-NilarNeural" else "my-MM-NilarNeural"
                print(f"⚠️ Edge TTS primary voice failed; retrying alternate Burmese voice: {edge_exc}")
                try:
                    generate_voice_sync(
                        text, alternate_voice, audio,
                        desired_tts_rate=1.0,
                        target_duration_sec=None,
                        retries=3,
                    )
                except Exception as second_exc:
                    print(f"⚠️ Both Edge Burmese voices failed; using Google TTS Burmese fallback: {second_exc}")
                    try:
                        generate_gtts_burmese_fallback(
                            text,
                            audio,
                            desired_speed=1.0,
                        )
                    except Exception as gtts_exc:
                        raise gr.Error(
                            "Narration voice server နှစ်မျိုးလုံးအသုံးမပြုနိုင်ပါ။ Edge TTS နှင့် Google TTS fallback နှစ်ခုလုံး fail ဖြစ်ပါတယ်။ "
                            f"({gtts_exc})"
                        )
        else:
            # The only non-Edge engine in V6 is VoxCPM2 Voice Clone.
            audio = os.path.join(work_dir, f"voice_{idx:03d}.wav")
            generate_voxcpm_audio(
                text, audio,
                mode="clone",
                voice_preset="", custom_voice_description="",
                reference_wav_path=clone_reference_path, reference_transcript=clone_transcript,
                desired_speed=1.0, cfg_value=voxcpm_cfg,
                inference_timesteps=voxcpm_steps, seed=(int(voxcpm_seed or 42) + idx),
            )
        if not os.path.exists(audio) or os.path.getsize(audio) == 0:
            continue
        # Preserve the voice at its natural pace. Retiming happens to video.
        slot_start = max(0.0, min(float(seg["start"]), source_duration - 0.35))
        slot_end = min(source_duration, max(slot_start + 0.35, float(seg["end"])))
        dur = max(0.1, probe_duration(audio, fallback=src_dur))
        voice_files.append(audio)
        voice_durations.append(dur)
        successful_source_segments.append({"start": slot_start, "end": slot_end, "text": text})
        display_chunks = split_subtitle_display_chunks(text, min_chars=25, max_chars=35)
        if not display_chunks:
            display_chunks = [text]
        total_chars = max(1, sum(len(c) for c in display_chunks))
        chunk_cursor = sum(voice_durations[:-1])
        for chunk in display_chunks:
            chunk_share = len(chunk) / total_chars
            chunk_dur = max(0.65, dur * chunk_share)
            subtitle_segments.append({"start": chunk_cursor, "end": chunk_cursor + chunk_dur, "text": chunk})
            chunk_cursor += chunk_dur
        if subtitle_segments:
            subtitle_segments[-1]["end"] = sum(voice_durations)
        completed = idx + 1
        voice_elapsed = max(0.01, time.time() - voice_started_at)
        voice_eta = (voice_elapsed / completed) * max(0, total - completed)
        progress(
            0.04 + 0.37 * (completed / total),
            desc=f"🎙️ Narration {completed}/{total} • ETA {_fmt_eta_seconds(voice_eta)}"
        )

    if not voice_files:
        raise gr.Error("Voice narration ထုတ်မရပါ။")
    # Ensure source list matches exactly the voice clips that succeeded.
    source_segments = successful_source_segments

    narration_duration = max(0.5, sum(voice_durations))
    merged_voice = os.path.join(work_dir, "YF_Recap_Narration.m4a")
    build_continuous_narration_track(voice_files, merged_voice)

    narration_mp3 = os.path.join(work_dir, "YF_Recap_Narration.mp3")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", merged_voice,
                    "-c:a", "libmp3lame", "-b:a", "192k", narration_mp3], check=False)

    progress(0.45, desc="🎙️ Narration-only audio ပြင်နေသည်...")
    final_audio = mix_story_audio_full_duration(
        merged_voice, video_path, bgm_path, narration_volume, original_volume,
        bgm_volume, auto_duck_bgm, narration_duration,
        os.path.join(work_dir, "final_mix_full_duration.m4a")
    )

    target_w, target_h = (720, 1280) if ratio_select == "9:16 (TikTok/Reels)" else (1280, 720)
    render_fps = 24 if "Turbo" in str(render_mode) else 30
    ass_path = os.path.join(work_dir, "YF_Recap_Subtitles.ass")
    build_ass_subtitles(subtitle_segments, ass_path, target_w, target_h,
                        subtitle_size_percent, sub_pos_percent, text_color, stroke_color, subtitle_font_style)
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
        source_segments, voice_durations, target_w, target_h, render_fps, narration_duration,
        background_fill, enable_zoom, zoom_level, mirror_flip, filter_color,
        blur_y_percent, blur_height_percent, blur_strength, ass_path, logo_idx,
        subtitle_font_style
    )
    graph_path = os.path.join(work_dir, "story_filters.txt")
    Path(graph_path).write_text(graph, encoding="utf-8")
    out_video = os.path.join(work_dir, "YF_Recap_Final.mp4")
    base = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *input_args,
        "-filter_complex_script", graph_path, "-map", "[vout]", "-map", f"{audio_idx}:a:0",
        "-t", f"{narration_duration:.3f}", "-r", str(render_fps), "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
    ]
    if HAS_NVENC:
        cmd = base + ["-c:v", "h264_nvenc", "-preset", "p3", "-cq", "23", "-b:v", "0", out_video]
        try:
            run_ffmpeg_with_progress(cmd, narration_duration, progress, 0.60, 0.97, "⚡ GPU Story Render")
        except Exception as exc:
            print("⚠️ NVENC fallback:", exc)
            cmd = base + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", out_video]
            run_ffmpeg_with_progress(cmd, narration_duration, progress, 0.60, 0.97, "🚀 CPU Story Render")
    else:
        cmd = base + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", out_video]
        run_ffmpeg_with_progress(cmd, narration_duration, progress, 0.60, 0.97, "🚀 CPU Story Render")

    if not os.path.exists(out_video):
        raise RuntimeError("Final MP4 was not created.")

    # Publish to a stable output path.  The preview and the dedicated download
    # button both point to this exact file instead of a temporary work file.
    published_video = publish_final_video_for_download(out_video, session_id)

    total_elapsed = time.time() - total_started_at
    progress(1.0, desc=f"✅ YF Recap Complete • {_fmt_eta_seconds(total_elapsed)}")
    return (
        published_video, srt_path, narration_mp3, script_path,
        f"### ✅ Complete\nFinal video duration: **{_fmt_eta_seconds(narration_duration)}** • Voice pace: **Normal (steady)** • Custom font applied: **{subtitle_font_style}**  \n**Actual processing time:** {_fmt_eta_seconds(total_elapsed)}"
    )


# ================================================================
# STABLE FINAL OUTPUT / DOWNLOAD
# ================================================================
YF_OUTPUT_DIR = os.getenv(
    "YF_OUTPUT_DIR",
    "/content/yf_recap_outputs" if os.path.isdir("/content") else "/mnt/data/yf_recap_outputs",
)
os.makedirs(YF_OUTPUT_DIR, exist_ok=True)


def publish_final_video_for_download(source_path, session_id):
    """Copy the rendered MP4 to a stable path served by Gradio's direct file endpoint."""
    if not source_path or not os.path.exists(source_path):
        raise RuntimeError("Rendered video file is missing before publish.")
    safe_session = re.sub(r"[^A-Za-z0-9_-]+", "", str(session_id or "session"))[:32] or "session"
    destination = os.path.join(YF_OUTPUT_DIR, f"YF_Recap_Final_{safe_session}.mp4")
    tmp_destination = destination + ".part"
    shutil.copy2(source_path, tmp_destination)
    os.replace(tmp_destination, destination)
    return destination


# ---- Combined manual layout editor: Blur band + Subtitle vertical position ----
def sync_layout_editor(evt: gr.EventData):
    try:
        zones = getattr(evt, "zones", None)
        if not isinstance(zones, list):
            zones = [{"x": 0, "y": float(evt.center) - float(evt.height) / 2, "w": 100, "h": float(evt.height)}]
        clean_zones = normalize_blur_zones(zones, 12.0)
        layout_json = json.dumps(clean_zones, separators=(",", ":"))
        first_height = clean_zones[0]["h"] if clean_zones else 12.0
        # Exact subtitle center Y, measured from the TOP of the preview/final frame.
        raw_y = getattr(evt, "subtitleY", None)
        if raw_y is None:
            # Compatibility with older editor payloads that stored bottom margin.
            old_bottom = float(getattr(evt, "subtitleBottom", 15.0))
            raw_y = 100.0 - old_bottom - 3.0
        subtitle_y = float(raw_y)
    except Exception:
        return '[{"x":0,"y":72,"w":100,"h":12}]', 12.0, 82.0
    subtitle_y = max(4.0, min(96.0, subtitle_y))
    return layout_json, round(first_height, 2), round(subtitle_y, 2)


LAYOUT_EDITOR_TEMPLATE = r"""
<div class="yf-layout-editor">
  <div class="yf-layout-head"><div><b>✋ Multi Blur Layout Editor</b><small>Blur ကိုရွှေ့ပါ • ဘေး/အပေါ်/အောက် handle ဆွဲပြီး အနံ/အမြင့်ပြောင်းပါ</small></div><button type="button" class="yf-reset">Reset</button></div>
  <div class="yf-stage">
    <img class="yf-img" src="${value}" draggable="false">
    <div class="yf-empty">🎬 Video upload ပြီး Blur + Subtitle ကို mouse နဲ့တိုက်ရိုက်ညှိပါ</div>
    <div class="yf-blur active" data-zone="0"><i class="yf-edge yf-top"></i><i class="yf-edge yf-right"></i><i class="yf-edge yf-bottom"></i><i class="yf-edge yf-left"></i><span>BLUR 1</span></div>
    <div class="yf-blur disabled" data-zone="1"><i class="yf-edge yf-top"></i><i class="yf-edge yf-right"></i><i class="yf-edge yf-bottom"></i><i class="yf-edge yf-left"></i><span>BLUR 2</span></div>
    <div class="yf-blur disabled" data-zone="2"><i class="yf-edge yf-top"></i><i class="yf-edge yf-right"></i><i class="yf-edge yf-bottom"></i><i class="yf-edge yf-left"></i><span>BLUR 3</span></div>
    <div class="yf-sub"><span>SUBTITLE • DRAG UP / DOWN</span></div>
  </div>
  <div class="yf-zone-tabs"><small>Blur area:</small><button type="button" class="on" data-pick="0">1</button><button type="button" data-pick="1">＋2</button><button type="button" data-pick="2">＋3</button><button type="button" class="yf-remove">Remove</button></div>
  <div class="yf-read"><span>Selected <b class="yz">1</b></span><span>Width <b class="yw">100%</b></span><span>Height <b class="yh">12%</b></span><span>Subtitle Y <b class="ys">82%</b></span><em>✓ Final render synced</em></div>
</div>
"""

LAYOUT_EDITOR_CSS = r"""
.yf-layout-editor{width:100%;color:#fffaf0;user-select:none}.yf-layout-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:10px}.yf-layout-head b{font-size:14px;color:#fff7df}.yf-layout-head small{display:block;color:#9db8ae;margin-top:3px}.yf-reset{border:1px solid #d6ad5b66;background:#172a27;color:#f8dfaa;border-radius:10px;padding:7px 11px;cursor:pointer}.yf-stage{position:relative;isolation:isolate;overflow:hidden;min-height:280px;border-radius:18px;border:1px solid #3c665d;background:#06110f;touch-action:none}.yf-img{position:relative;z-index:1;display:block;width:100%;height:auto;min-height:280px;max-height:620px;object-fit:contain;pointer-events:none}.yf-empty{position:absolute;z-index:2;inset:0;display:grid;place-items:center;color:#84a49a;background:#071612f2;padding:20px;text-align:center}.yf-stage.ready .yf-empty{display:none}.yf-blur{position:absolute;z-index:4;min-width:28px;min-height:25px;border:2px solid #2dd4bf;background:#0f766e2b;backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);cursor:grab;box-shadow:0 0 22px #14b8a640}.yf-blur.active{border-color:#e7bd68;z-index:5}.yf-blur.disabled{display:none}.yf-blur span{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);white-space:nowrap;background:#06110fe8;border:1px solid #e7bd6870;color:#ffe8b5;padding:5px 9px;border-radius:999px;font-size:9px;font-weight:900;pointer-events:none}.yf-edge{position:absolute;display:block}.yf-top,.yf-bottom{left:18%;right:18%;height:14px;cursor:ns-resize}.yf-top{top:-8px}.yf-bottom{bottom:-8px}.yf-left,.yf-right{top:18%;bottom:18%;width:14px;cursor:ew-resize}.yf-left{left:-8px}.yf-right{right:-8px}.yf-edge:after{content:"";position:absolute;background:#fff7df;border-radius:999px}.yf-top:after,.yf-bottom:after{left:20%;right:20%;top:5px;height:4px}.yf-left:after,.yf-right:after{top:20%;bottom:20%;left:5px;width:4px}.yf-sub{position:absolute;z-index:20;left:6%;right:6%;top:82%;transform:translateY(-50%);height:38px;border:2px dashed #ffe08a;background:#07120fd9;border-radius:11px;display:grid;place-items:center;cursor:ns-resize;box-shadow:0 0 0 2px #0008,0 8px 26px #0009,0 0 22px #f4c95d45}.yf-sub span{position:relative;z-index:21;background:#fff8e7;color:#16352e;border:1px solid #e7bd68;padding:5px 10px;border-radius:8px;font-size:10px;font-weight:950}.yf-zone-tabs{display:flex;align-items:center;gap:7px;margin-top:10px}.yf-zone-tabs small{color:#9db8ae;margin-right:2px}.yf-zone-tabs button{width:34px;height:32px;border-radius:9px;border:1px solid #335d54;background:#0b1c18;color:#a9c7bd;font-weight:900;cursor:pointer}.yf-zone-tabs button.on{border-color:#e7bd68;color:#ffe8b5;background:#d6ad5b1d}.yf-zone-tabs .yf-remove{width:auto;padding:0 10px;margin-left:auto;color:#ffb4b4;border-color:#e56b6b66}.yf-read{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px;font-size:11px}.yf-read span,.yf-read em{padding:6px 9px;border-radius:9px;background:#0b1c18;border:1px solid #294d45;font-style:normal}.yf-read em{color:#6ee7b7}.yf-read b{color:#fff1c7}@media(max-width:720px){.yf-stage,.yf-img{min-height:220px}}
"""

LAYOUT_EDITOR_JS = r"""
const stage=element.querySelector('.yf-stage'),img=element.querySelector('.yf-img'),bands=[...element.querySelectorAll('.yf-blur')],tabs=[...element.querySelectorAll('[data-pick]')],sub=element.querySelector('.yf-sub'),reset=element.querySelector('.yf-reset'),remove=element.querySelector('.yf-remove');
const yz=element.querySelector('.yz'),yw=element.querySelector('.yw'),yh=element.querySelector('.yh'),ys=element.querySelector('.ys');
let zones=[{x:0,y:72,w:100,h:12,on:true},{x:12,y:50,w:76,h:11,on:false},{x:20,y:30,w:60,h:10,on:false}],active=0,subY=82,drag=null;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function ready(){const ok=!!img.getAttribute('src')&&img.naturalWidth>0;stage.classList.toggle('ready',ok);return ok}
function norm(z){z.w=clamp(z.w,3,100);z.h=clamp(z.h,3,45);z.x=clamp(z.x,0,100-z.w);z.y=clamp(z.y,0,100-z.h)}
function draw(){zones.forEach((z,i)=>{norm(z);const b=bands[i];b.classList.toggle('disabled',!z.on);b.classList.toggle('active',i===active&&z.on);b.style.left=z.x+'%';b.style.top=z.y+'%';b.style.width=z.w+'%';b.style.height=z.h+'%'});tabs.forEach((t,i)=>{t.classList.toggle('on',i===active);t.textContent=(zones[i].on?'':'＋')+(i+1)});const z=zones[active];yz.textContent=active+1;yw.textContent=z.w.toFixed(1)+'%';yh.textContent=z.h.toFixed(1)+'%';ys.textContent=subY.toFixed(1)+'%';sub.style.top=subY+'%';remove.style.visibility=active===0?'hidden':'visible'}
function emit(){const payload=zones.filter(z=>z.on).map(({x,y,w,h})=>({x:+x.toFixed(2),y:+y.toFixed(2),w:+w.toFixed(2),h:+h.toFixed(2)}));trigger('change',{zones:payload,subtitleY:+subY.toFixed(2)})}
function point(e){const r=stage.getBoundingClientRect();return{x:(e.clientX-r.left)*100/Math.max(1,r.width),y:(e.clientY-r.top)*100/Math.max(1,r.height)}}
function begin(e,i,mode){if(!ready())return;e.preventDefault();e.stopPropagation();active=i;const p=point(e),z=zones[i];drag={mode,sx:p.x,sy:p.y,z:{...z},subY};stage.setPointerCapture?.(e.pointerId);draw()}
bands.forEach((b,i)=>{b.addEventListener('pointerdown',e=>begin(e,i,e.target.classList.contains('yf-top')?'top':e.target.classList.contains('yf-bottom')?'bottom':e.target.classList.contains('yf-left')?'left':e.target.classList.contains('yf-right')?'right':'move'))});sub.addEventListener('pointerdown',e=>begin(e,active,'sub'));
stage.addEventListener('pointermove',e=>{if(!drag)return;e.preventDefault();const p=point(e),dx=p.x-drag.sx,dy=p.y-drag.sy,z=zones[active],s=drag.z;if(drag.mode==='move'){z.x=s.x+dx;z.y=s.y+dy}else if(drag.mode==='left'){z.x=s.x+dx;z.w=s.w-dx}else if(drag.mode==='right')z.w=s.w+dx;else if(drag.mode==='top'){z.y=s.y+dy;z.h=s.h-dy}else if(drag.mode==='bottom')z.h=s.h+dy;else if(drag.mode==='sub')subY=clamp(drag.subY+dy,4,96);norm(z);draw()});
function end(e){if(!drag)return;drag=null;try{stage.releasePointerCapture?.(e.pointerId)}catch(_){ }draw();emit()}stage.addEventListener('pointerup',end);stage.addEventListener('pointercancel',end);
tabs.forEach((t,i)=>t.addEventListener('click',e=>{e.preventDefault();active=i;zones[i].on=true;draw();emit()}));remove.addEventListener('click',e=>{e.preventDefault();if(active>0){zones[active].on=false;active=0;draw();emit()}});reset.addEventListener('click',e=>{e.preventDefault();zones=[{x:0,y:72,w:100,h:12,on:true},{x:12,y:50,w:76,h:11,on:false},{x:20,y:30,w:60,h:10,on:false}];active=0;subY=82;draw();emit()});img.addEventListener('load',()=>{ready();draw();emit()});img.addEventListener('error',()=>stage.classList.remove('ready'));ready();draw();
"""



def _fmt_eta_seconds(seconds):
    """Human-friendly ETA formatter used in cards and progress descriptions."""
    if seconds is None:
        return "calculating…"
    try:
        seconds = max(0, int(round(float(seconds))))
    except Exception:
        return "calculating…"
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def update_voice_engine_panels_v6(engine):
    """V6 exposes only Edge TTS and VoxCPM2 Voice Clone."""
    engine = str(engine or "")
    is_edge = "Edge TTS" in engine
    is_clone = "Voice Clone" in engine
    return (
        gr.update(visible=is_edge),
        gr.update(visible=is_clone),
        gr.update(visible=is_clone),
    )


def estimate_processing_eta(analysis_state, script_editor, voice_engine, render_mode, desired_speed, voxcpm_steps):
    """Estimate remaining processing time before Render. It is intentionally a range."""
    segments = parse_script_editor(script_editor)
    if not segments:
        return """
        <div class='eta-card waiting'>
          <div class='eta-icon'>⏱</div><div>
          <b>Estimated completion time</b><span>Generate the Viral Recap Script first.</span>
          </div>
        </div>"""

    chars = sum(len(s.get("text", "")) for s in segments)
    pace = max(0.85, min(1.7, float(desired_speed or 1.2)))
    # Approximate final spoken duration. This is not a promise; language and cloned voice pacing vary.
    spoken_seconds = max(15.0, chars / (8.6 * pace))
    count = max(1, len(segments))
    engine = str(voice_engine or "")
    steps = max(4.0, float(voxcpm_steps or 10))

    if "Edge TTS" in engine:
        tts_low = count * 0.45 + spoken_seconds * 0.10
        tts_high = count * 1.25 + spoken_seconds * 0.32
        first_load_note = ""
    elif "Voice Clone" in engine:
        step_factor = steps / 10.0
        tts_low = 45 + spoken_seconds * 0.95 * step_factor
        tts_high = 120 + spoken_seconds * 2.10 * step_factor
        first_load_note = "First VoxCPM2 load/download can add ~2–5 min."
    else:
        step_factor = steps / 10.0
        tts_low = 35 + spoken_seconds * 0.80 * step_factor
        tts_high = 100 + spoken_seconds * 1.80 * step_factor
        first_load_note = "First VoxCPM2 load/download can add ~2–5 min."

    turbo = "Turbo" in str(render_mode or "")
    if HAS_NVENC:
        render_low = spoken_seconds * (0.12 if turbo else 0.18) + 15
        render_high = spoken_seconds * (0.34 if turbo else 0.48) + 45
    else:
        render_low = spoken_seconds * (0.55 if turbo else 0.75) + 25
        render_high = spoken_seconds * (1.15 if turbo else 1.45) + 75

    overhead_low, overhead_high = 20, 55
    low = tts_low + render_low + overhead_low
    high = tts_high + render_high + overhead_high
    # Avoid oddly narrow ranges for real-world cloud/network variation.
    high = max(high, low * 1.35)
    duration_text = _fmt_eta_seconds(spoken_seconds)
    note_html = f"<small>{first_load_note}</small>" if first_load_note else ""
    return f"""
    <div class='eta-card ready'>
      <div class='eta-icon'>⏱</div>
      <div class='eta-main'>
        <b>Estimated processing: {_fmt_eta_seconds(low)} – {_fmt_eta_seconds(high)}</b>
        <span>Expected final recap length ~ {duration_text} • {RENDER_ENGINE_LABEL}</span>
        {note_html}
      </div>
    </div>"""


def render_start_status(analysis_state, script_editor, voice_engine, render_mode, desired_speed, voxcpm_steps):
    estimate = estimate_processing_eta(analysis_state, script_editor, voice_engine, render_mode, desired_speed, voxcpm_steps)
    return estimate.replace("Estimated processing:", "Rendering started • estimated:")



# ----------------------------------------------------------------
# LIVE PROCESS STATUS (V6.8.2)
# ----------------------------------------------------------------
# The long render runs in the Gradio queue. A small non-queued Timer polls
# this per-session state so mobile users always see visible activity, stage,
# percent, elapsed time and an estimated remaining time.
PROCESS_STATUS = {}
PROCESS_STATUS_LOCK = threading.Lock()


def _set_process_status(session_id, **updates):
    sid = str(session_id or "default")
    with PROCESS_STATUS_LOCK:
        current = dict(PROCESS_STATUS.get(sid, {}))
        current.update(updates)
        current["updated"] = time.time()
        PROCESS_STATUS[sid] = current
    return current


def _get_process_status(session_id):
    sid = str(session_id or "default")
    with PROCESS_STATUS_LOCK:
        return dict(PROCESS_STATUS.get(sid, {}))


def _auto_recap_eta_window(video_value, recap_length, voice_engine, render_mode, voxcpm_steps):
    """Return numeric low/high ETA seconds for the live countdown card."""
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        return None, None
    duration = probe_duration(video_path, fallback=300.0)
    target = _target_seconds(recap_length, duration)
    engine = str(voice_engine or "")
    steps = max(4.0, float(voxcpm_steps or 10))
    if "Edge TTS" in engine:
        low = 45 + target * 0.55
        high = 180 + target * 1.45
    else:
        factor = steps / 10.0
        low = 70 + target * 0.85 * factor
        high = 240 + target * 2.10 * factor
    if not HAS_NVENC:
        low += target * 0.35
        high += target * 0.90
    elif "Balanced" in str(render_mode or ""):
        low += target * 0.12
        high += target * 0.30
    high = max(high, low * 1.25)
    return float(low), float(high)


def _processing_status_html(session_id):
    st = _get_process_status(session_id)
    state = st.get("state", "idle")
    if state == "idle":
        return """
        <div class='process-card idle'>
          <div class='process-icon'>◷</div>
          <div class='process-main'><b>Waiting to start</b><span>AUTO RECAP နှိပ်လိုက်ရင် live processing status ကို ဒီနေရာမှာပြမယ်။</span></div>
        </div>"""

    started = float(st.get("started") or time.time())
    elapsed = max(0.0, time.time() - started)
    progress_pct = max(0, min(100, int(st.get("progress", 0) or 0)))
    stage = str(st.get("stage") or "Processing…")
    eta_low = st.get("eta_low")
    eta_high = st.get("eta_high")

    if state == "done":
        return f"""
        <div class='process-card done'>
          <div class='process-icon done-icon'>✓</div>
          <div class='process-main'><div class='process-top'><b>Complete</b><strong>100%</strong></div>
          <span>Final video အဆင်သင့်ဖြစ်ပါပြီ • Total {_fmt_eta_seconds(elapsed)}</span>
          <div class='process-track'><i style='width:100%'></i></div></div>
        </div>"""

    if state == "error":
        message = str(st.get("error") or "Processing failed")
        return f"""
        <div class='process-card error'>
          <div class='process-icon error-icon'>!</div>
          <div class='process-main'><div class='process-top'><b>Processing stopped</b><strong>ERROR</strong></div>
          <span>{message}</span></div>
        </div>"""

    # During a long stage, keep the bar visibly moving toward (but never past)
    # 95% using the original ETA as a secondary estimate. Actual backend
    # progress remains the lower bound and wins whenever it advances.
    projected = progress_pct
    if eta_high and float(eta_high) > 0:
        projected = max(projected, min(95, int((elapsed / float(eta_high)) * 95)))
    progress_pct = projected

    if eta_low is not None and eta_high is not None:
        remain_low = max(0.0, float(eta_low) - elapsed)
        remain_high = max(0.0, float(eta_high) - elapsed)
        if remain_high <= 1:
            remaining = "finishing…"
        else:
            remaining = f"~ {_fmt_eta_seconds(remain_low)} – {_fmt_eta_seconds(remain_high)}"
    else:
        remaining = "calculating…"

    # Escape the handful of characters that can break our tiny status card.
    stage = (stage.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return f"""
    <div class='process-card running'>
      <div class='process-spinner'></div>
      <div class='process-main'>
        <div class='process-top'><b>{stage}</b><strong>{progress_pct}%</strong></div>
        <span>⏱ Elapsed {_fmt_eta_seconds(elapsed)} &nbsp;•&nbsp; Remaining {remaining}</span>
        <div class='process-track'><i style='width:{progress_pct}%'></i></div>
        <small>⚠️ ဒီ page / Colab cell ကို processing ပြီးတဲ့အထိ မပိတ်ပါနဲ့။</small>
      </div>
    </div>"""


class _LiveProgress:
    """Forward Gradio progress and mirror it into the on-page live status card."""
    def __init__(self, parent, session_id):
        self.parent = parent
        self.session_id = session_id

    def __call__(self, value=0.0, desc=None, **kwargs):
        try:
            frac = max(0.0, min(1.0, float(value)))
        except Exception:
            frac = 0.0
        updates = {"state": "running", "progress": int(frac * 100)}
        if desc:
            updates["stage"] = str(desc)
        _set_process_status(self.session_id, **updates)
        return self.parent(frac, desc=desc, **kwargs)


class _ProgressSlice:
    """Map a child task's 0..1 progress into one part of overall Auto Recap."""
    def __init__(self, parent, start, end):
        self.parent = parent
        self.start = float(start)
        self.end = float(end)

    def __call__(self, value=0.0, desc=None, **kwargs):
        try:
            value = max(0.0, min(1.0, float(value)))
        except Exception:
            value = 0.0
        mapped = self.start + (self.end - self.start) * value
        return self.parent(mapped, desc=desc, **kwargs)


def estimate_auto_recap_eta(video_value, recap_length, voice_engine, render_mode, voxcpm_steps):
    """Quick ETA shown immediately after the single AUTO RECAP button is pressed."""
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        return """<div class='eta-card waiting'><div class='eta-icon'>⏱</div><div><b>Upload a movie first</b><span>ပြီးရင် AUTO RECAP တစ်ခုပဲနှိပ်ပါ။</span></div></div>"""
    duration = probe_duration(video_path, fallback=300.0)
    target = _target_seconds(recap_length, duration)
    engine = str(voice_engine or "")
    steps = max(4.0, float(voxcpm_steps or 10))
    if "Edge TTS" in engine:
        # Includes room for Edge network retry and alternate Burmese Edge voice.
        low = 45 + target * 0.55
        high = 180 + target * 1.45
        note = "Edge TTS မရရင် alternate Burmese Edge voice ကို auto retry လုပ်မယ်။"
    else:
        factor = steps / 10.0
        low = 70 + target * 0.85 * factor
        high = 240 + target * 2.10 * factor
        note = "First VoxCPM2 model load can take extra time."
    if not HAS_NVENC:
        low += target * 0.35
        high += target * 0.90
    elif "Balanced" in str(render_mode or ""):
        low += target * 0.12
        high += target * 0.30
    return f"""<div class='eta-card ready'><div class='eta-icon'>⏱</div><div class='eta-main'><b>AUTO RECAP started • estimated {_fmt_eta_seconds(low)} – {_fmt_eta_seconds(high)}</b><span>Analyze → Viral Script → Voice → Render → Export ကို တစ်ခါတည်းလုပ်နေမယ်။</span><small>{note}</small></div></div>"""


def auto_recap_pipeline_v5(
    video_value, user_api_key, tone_style, recap_length,
    ratio_select, background_fill, enable_zoom, zoom_level, logo_value,
    bgm_value, narration_volume, original_volume, bgm_volume, auto_duck_bgm,
    mirror_flip, filter_color,
    voice_engine, edge_voice_name, voice_preset, custom_voice_description,
    clone_reference, clone_transcript, clone_consent,
    voxcpm_cfg, voxcpm_steps, voxcpm_seed,
    text_color, stroke_color, blur_y_percent, blur_height_percent, blur_strength,
    sub_pos_percent, subtitle_size_percent, subtitle_font_style, desired_speed, render_mode,
    session_id, vip_access_state,
    progress=gr.Progress(track_tqdm=False),
):
    """One user action: Analyze → script → narration → render → exports, with live UI status."""
    if not isinstance(vip_access_state, dict) or not vip_access_state.get("authenticated"):
        _set_process_status(session_id, state="error", error="VIP Login ပြန်ဝင်ပါ။")
        raise gr.Error("🔒 VIP Login ပြန်ဝင်ပါ။")
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        _set_process_status(session_id, state="error", error="Movie / clip ကိုအရင် Upload လုပ်ပါ။")
        raise gr.Error("🎬 Movie / clip ကိုအရင် Upload လုပ်ပါ။")

    if "Voice Clone" in str(voice_engine):
        ref = normalize_file_path(clone_reference)
        if not clone_consent:
            _set_process_status(session_id, state="error", error="Voice Clone permission checkbox လိုအပ်ပါတယ်။")
            raise gr.Error("🎙️ Voice Clone permission checkbox ကို အမှန်ခြစ်ပါ။")
        if not ref or not os.path.exists(ref):
            _set_process_status(session_id, state="error", error="Voice Clone Reference MP3/WAV လိုအပ်ပါတယ်။")
            raise gr.Error("🎙️ Voice Clone အတွက် Reference MP3/WAV ထည့်ပါ။")

    started = time.time()
    previous = _get_process_status(session_id)
    eta_low = previous.get("eta_low")
    eta_high = previous.get("eta_high")
    if eta_low is None or eta_high is None:
        eta_low, eta_high = _auto_recap_eta_window(video_value, recap_length, voice_engine, render_mode, voxcpm_steps)

    _set_process_status(
        session_id, state="running", started=started, progress=1,
        stage="🎬 AUTO RECAP စတင်နေသည်…", eta_low=eta_low, eta_high=eta_high, error=""
    )
    live_progress = _LiveProgress(progress, session_id)

    try:
        live_progress(0.01, desc="🎬 AUTO RECAP စတင်နေသည်…")

        # Stage 1: speech / scene analysis (hidden from the user UI).
        analysis, _analysis_summary, _scene_rows = analyze_movie_v3(
            video_value, vip_access_state, user_api_key=user_api_key,
            progress=_ProgressSlice(live_progress, 0.01, 0.18),
        )

        # Stage 2: viral storytelling script (hidden from the user UI).
        live_progress(0.18, desc="🧠 Movie story ကို recap script အဖြစ်ရေးနေသည်…")
        script_text, _script_summary = generate_recap_script_v3(
            analysis, user_api_key, tone_style, recap_length,
            progress=_ProgressSlice(live_progress, 0.18, 0.34),
        )

        # Stage 3: narration + scene render + exports. The child function's
        # Gradio progress (including FFmpeg render ETA) is mirrored live.
        live_progress(0.34, desc="🎙️ Narration + subtitles + video render ပြင်ဆင်နေသည်…")
        result = render_reviewed_script_v3(
            analysis, script_text,
            ratio_select, background_fill, enable_zoom, zoom_level, logo_value,
            bgm_value, narration_volume, original_volume, bgm_volume, auto_duck_bgm,
            mirror_flip, filter_color,
            voice_engine, edge_voice_name, voice_preset, custom_voice_description,
            clone_reference, clone_transcript, clone_consent,
            voxcpm_cfg, voxcpm_steps, voxcpm_seed,
            text_color, stroke_color, blur_y_percent, blur_height_percent, blur_strength,
            sub_pos_percent, subtitle_size_percent, subtitle_font_style, desired_speed, render_mode,
            session_id, vip_access_state,
            progress=_ProgressSlice(live_progress, 0.34, 1.0),
        )
        out_video, srt_path, mp3_path, script_path, _old_status = result
        consume_video_quota(vip_access_state)
        elapsed = time.time() - started
        _set_process_status(
            session_id, state="done", progress=100,
            stage="✅ Final video အဆင်သင့်ဖြစ်ပါပြီ", finished=time.time()
        )
        status = (
            "### ✅ AUTO RECAP COMPLETE\n"
            "Analyze + Viral Script + Narration + Subtitle + Render အားလုံးပြီးပါပြီ။  \n"
            f"**Total time:** {_fmt_eta_seconds(elapsed)}"
        )
        return out_video, out_video, srt_path, mp3_path, script_path, status
    except Exception as e:
        _set_process_status(
            session_id, state="error", progress=0,
            stage="❌ Processing stopped", error=str(e)[:500]
        )
        raise

def _wizard_progress_html(step):
    step = max(1, min(6, int(step)))
    labels = ["Upload", "Recap", "Voice", "Subtitle", "Generate", "Result"]
    dots = []
    for i, label in enumerate(labels, 1):
        cls = "done" if i < step else ("active" if i == step else "")
        dots.append(
            f"<div class='wiz-node {cls}'><span>{'✓' if i < step else i}</span><small>{label}</small></div>"
        )
    return (
        "<div class='wiz-progress'>"
        + "<div class='wiz-line'></div>"
        + "".join(dots)
        + f"</div><div class='wiz-step-label'>STEP {step} / 6</div>"
    )


def _wizard_payload(step):
    step = max(1, min(6, int(step)))
    return (
        _wizard_progress_html(step),
        gr.update(visible=step == 1),
        gr.update(visible=step == 2),
        gr.update(visible=step == 3),
        gr.update(visible=step == 4),
        gr.update(visible=step == 5),
        gr.update(visible=step == 6),
        step,
    )


def _restore_wizard_after_reconnect(saved_step):
    """Keep the user on the same wizard page after a tunnel/browser reconnect.

    Long Colab renders can outlive a temporary Cloudflare/WebSocket reconnect.
    BrowserState supplies the last visible step instead of rebuilding at Step 1.
    Never restore the result page automatically: Step 6 is opened only by the
    render event's success callback after the final files exist.
    """
    try:
        step = int(saved_step or 1)
    except Exception:
        step = 1
    if step >= 6:
        step = 5
    return _wizard_payload(step)


def _wizard_after_upload(video_value):
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        raise gr.Error("🎬 အရင်ဆုံး Video ကို upload လုပ်ပေးပါ။")
    return _wizard_payload(2)


def _wizard_validate_voice(engine, clone_reference, clone_consent):
    if "Voice Clone" in str(engine):
        ref = normalize_file_path(clone_reference)
        if not ref or not os.path.exists(ref):
            raise gr.Error("🎙 Voice Clone ရွေးထားပါက Reference Voice MP3/WAV ထည့်ပေးပါ။")
        if not clone_consent:
            raise gr.Error("Voice Clone အသုံးပြုရန် permission checkbox ကိုအတည်ပြုပေးပါ။")
    return _wizard_payload(4)


def _start_auto_recap_feedback(video_value, recap_length, voice_engine, render_mode, voxcpm_steps, session_id):
    """Immediate mobile feedback + initialize the live ETA/countdown state."""
    video_path = normalize_file_path(video_value)
    if not video_path or not os.path.exists(video_path):
        raise gr.Error("🎬 Movie / clip ကိုအရင် Upload လုပ်ပါ။")

    eta_low, eta_high = _auto_recap_eta_window(
        video_value, recap_length, voice_engine, render_mode, voxcpm_steps
    )
    now = time.time()
    _set_process_status(
        session_id,
        state="running", started=now, progress=1,
        stage="🚀 Request လက်ခံပြီး processing စတင်နေသည်…",
        eta_low=eta_low, eta_high=eta_high, error=""
    )

    eta_html = estimate_auto_recap_eta(
        video_value, recap_length, voice_engine, render_mode, voxcpm_steps
    )
    status = (
        "### 🚀 AUTO RECAP STARTED\n"
        "Button click ကိုလက်ခံပြီးပါပြီ။  \n"
        "အောက်က **Live Processing** card မှာ loading, လက်ရှိအဆင့်, %, elapsed နဲ့ remaining time ကိုကြည့်နိုင်ပါတယ်။"
    )
    return eta_html, status, _processing_status_html(session_id)

def _subtitle_size_preview_html(size_value):
    """Tiny live visual confirmation that the size slider is really changing."""
    try:
        s = max(1.0, min(10.0, float(size_value)))
    except Exception:
        s = 5.5
    # UI preview px only; final ASS uses output-frame mapping in build_ass_subtitles().
    preview_px = int(round(18 + ((s - 1.0) / 9.0) * 28))
    return f"""
    <div class='sub-size-preview'>
      <div class='sub-size-meta'><span>LIVE SIZE PREVIEW</span><b>{s:g} / 10</b></div>
      <div class='sub-size-stage'><span style='font-size:{preview_px}px'>စာတန်းထိုး နမူနာ</span></div>
      <small>ဒီ slider value ကို Final ASS subtitle render မှာ တိုက်ရိုက်အသုံးပြုပါတယ်။</small>
    </div>
    """

def create_app():
    css = r"""
    :root{--bg:#050812;--card:#0d1424;--card2:#111b31;--line:#263755;--cyan:#22d3ee;--blue:#2563eb;--violet:#7c3aed;--green:#34d399;--text:#f8fafc;--muted:#91a1bd;--gold:#facc15}
    html,body{overflow-x:hidden!important;background:#050812!important}*{box-sizing:border-box}
    body,.gradio-container{background:radial-gradient(circle at 12% 0,#142655 0,transparent 30%),radial-gradient(circle at 95% 3%,#32145c 0,transparent 27%),linear-gradient(180deg,#080d19,#050812)!important}
    .gradio-container{max-width:980px!important;margin:0 auto!important;padding:10px 12px 80px!important;color:var(--text)!important}
    .wiz-hero{position:relative;overflow:hidden;border:1px solid #2b3c60;border-radius:26px;background:linear-gradient(145deg,#0c1428ee,#111a36f5);padding:24px;margin:4px 0 14px;box-shadow:0 22px 65px #0007}
    .wiz-hero:after{content:"";position:absolute;width:230px;height:230px;right:-90px;top:-110px;border-radius:50%;background:radial-gradient(circle,#22d3ee2d,transparent 68%)}
    .wiz-brand{display:flex;align-items:center;gap:13px;position:relative;z-index:2}.wiz-logo{width:58px;height:58px;flex:0 0 58px;display:grid;place-items:center;border-radius:18px;background:linear-gradient(135deg,#7c3aed,#0891b2);font-weight:950;font-size:22px;box-shadow:0 12px 35px #22d3ee2e}.wiz-name{font-size:27px;font-weight:950;letter-spacing:-.02em}.wiz-sub{color:#8fa2c2;font-size:11px;margin-top:2px}.wiz-note{position:relative;z-index:2;color:#b5c1d8;font-size:11px;line-height:1.55;margin-top:13px}.wiz-note b{color:#67e8f9}
    .wiz-progress-wrap{position:sticky;top:0;z-index:90;padding:5px 0 8px;background:linear-gradient(180deg,#050812 75%,transparent)}
    .wiz-progress{position:relative;display:grid;grid-template-columns:repeat(6,1fr);align-items:start;padding:10px 4px 4px}.wiz-line{position:absolute;height:2px;background:#253653;left:8.3%;right:8.3%;top:24px}.wiz-node{position:relative;z-index:2;text-align:center;color:#60708f}.wiz-node span{margin:auto;width:30px;height:30px;display:grid;place-items:center;border-radius:50%;background:#0b1221;border:2px solid #33435f;font-size:11px;font-weight:950}.wiz-node small{display:block;margin-top:5px;font-size:8px;font-weight:800;white-space:nowrap}.wiz-node.active{color:#bae6fd}.wiz-node.active span{border-color:#22d3ee;background:linear-gradient(135deg,#0e7490,#2563eb);color:white;box-shadow:0 0 20px #22d3ee55}.wiz-node.done{color:#86efac}.wiz-node.done span{border-color:#34d399;background:#065f46;color:#fff}.wiz-step-label{text-align:center;color:#7dd3fc;font-size:9px;font-weight:900;letter-spacing:.14em;margin-top:3px}
    .wizard-card{border:1px solid var(--line)!important;background:linear-gradient(180deg,#0f172bd9,#091020f4)!important;border-radius:22px!important;padding:18px!important;box-shadow:0 15px 45px #0004!important}.wizard-title{font-size:20px;font-weight:950;margin-bottom:4px}.wizard-copy{font-size:11px;color:#8fa0bf;line-height:1.55;margin-bottom:14px}.wizard-badge{display:inline-flex;align-items:center;gap:6px;padding:5px 9px;border-radius:999px;border:1px solid #22d3ee40;background:#22d3ee0c;color:#a5f3fc;font-size:9px;font-weight:900;margin-bottom:10px}
    .wiz-nav{margin-top:13px!important}.wiz-next,.wiz-back{min-height:50px!important;border-radius:13px!important;font-weight:900!important}.wiz-next{background:linear-gradient(90deg,#6d28d9,#2563eb,#0891b2)!important;color:#fff!important;border:0!important}.wiz-back{background:#111827!important;border:1px solid #334155!important;color:#cbd5e1!important}
    .login-shell-pro{max-width:600px;margin:24px auto!important}.login-card-pro{border:1px solid #334166!important;background:#0d142cf5!important;border-radius:22px!important;padding:24px!important}.login-head{text-align:center;font-size:23px;font-weight:950}.login-copy{text-align:center;color:#8f9abb;font-size:11px;margin:6px 0 14px}.member-strip{padding:11px 14px;border:1px solid #34d39945;background:#34d3990d;border-radius:14px;margin-bottom:9px}.member-name{font-weight:900}.member-small{font-size:9px;color:#7dd3fc}.quota-badge{font-size:9px;color:#fde68a}
    .engine-panel{border:1px solid #334268!important;background:#0a1229aa!important;border-radius:16px!important;padding:12px!important;margin-top:8px!important}.clone-panel{border-color:#8b5cf65c!important;background:linear-gradient(180deg,#3a1d6a26,#0a1229d9)!important}.clone-title{font-weight:950;color:#ddd6fe;margin-bottom:4px}.clone-copy,.hint{font-size:10px;color:#91a1bd;line-height:1.5}.voice-mode-title{font-weight:950;color:#e0f2fe}.font-ok,.font-warn{font-size:10px;line-height:1.45;padding:8px 10px;border-radius:10px;margin-top:6px}.font-ok{color:#a7f3d0;background:#34d39912;border:1px solid #34d39935}.font-warn{color:#fde68a;background:#f59e0b12;border:1px solid #f59e0b35}
    #subtitle-font-picker{position:relative;z-index:35}#subtitle-font-picker [role="listbox"]{padding:7px!important;border:1px solid #465779!important;border-radius:14px!important;background:#080d18f7!important;box-shadow:0 20px 55px #000c!important;max-height:300px!important}#subtitle-font-picker [role="option"]{min-height:38px!important;padding:9px 11px!important;margin:2px 0!important;border-radius:9px!important;color:#e5edf9!important;font-size:12px!important;border:1px solid transparent!important}#subtitle-font-picker [role="option"]:hover,#subtitle-font-picker [role="option"][aria-selected="true"]{background:linear-gradient(90deg,#7c3aed35,#0891b22a)!important;border-color:#67e8f944!important;color:#fff!important}
    .process-card{display:flex;align-items:flex-start;gap:12px;width:100%;padding:14px;border-radius:16px;margin:10px 0;border:1px solid #22d3ee46;background:linear-gradient(110deg,#061426e8,#111738ed);box-shadow:inset 0 1px #ffffff08,0 12px 34px #0003}.process-card.idle{border-color:#47556966;background:#0a1020cc}.process-card.done{border-color:#34d39966;background:linear-gradient(110deg,#05251ce8,#092034ed)}.process-card.error{border-color:#fb718566;background:linear-gradient(110deg,#2b0b14e8,#1c1022ed)}.process-spinner{width:34px;height:34px;flex:0 0 34px;border-radius:50%;border:3px solid #22d3ee2f;border-top-color:#67e8f9;border-right-color:#818cf8;animation:yfspin .8s linear infinite;margin-top:1px}.process-icon{width:34px;height:34px;flex:0 0 34px;border-radius:11px;display:grid;place-items:center;border:1px solid #47556966;color:#94a3b8;font-weight:950}.done-icon{border-color:#34d39966;color:#6ee7b7;background:#10b98118}.error-icon{border-color:#fb718566;color:#fda4af;background:#fb718518}.process-main{min-width:0;flex:1}.process-top{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}.process-top b{font-size:12px;line-height:1.35;color:#f8fafc;overflow-wrap:anywhere}.process-top strong{font-size:11px;color:#67e8f9;white-space:nowrap}.process-main>span{display:block;color:#a9b9d3;font-size:10px;margin-top:4px;line-height:1.45}.process-main>small{display:block;color:#facc15;font-size:9px;margin-top:7px;line-height:1.4}.process-track{height:8px;width:100%;border-radius:999px;background:#020617cc;border:1px solid #33415588;overflow:hidden;margin-top:9px}.process-track i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#7c3aed,#2563eb,#22d3ee);box-shadow:0 0 14px #22d3ee66;transition:width .55s ease}@keyframes yfspin{to{transform:rotate(360deg)}}.eta-card{display:flex;align-items:center;gap:11px;width:100%;padding:12px 13px;border-radius:15px;margin:10px 0}.eta-card.ready{border:1px solid #22d3ee44;background:linear-gradient(90deg,#06b6d414,#7c3aed13)}.eta-card.waiting{border:1px solid #64748b45;background:#1118277d}.eta-icon{width:36px;height:36px;flex:0 0 36px;border-radius:11px;display:grid;place-items:center;background:#22d3ee17;border:1px solid #22d3ee33}.eta-card b{display:block;font-size:12px}.eta-card span,.eta-card small{display:block;color:#9fb0cd;font-size:10px;margin-top:2px}.eta-card small{color:#facc15}
    .clean-audio-badge{padding:10px;border-radius:12px;background:#34d3990c;border:1px solid #34d39935;color:#a7f3d0;font-size:10px;font-weight:850}.generate-summary{padding:12px;border-radius:14px;background:#07111f;border:1px solid #243852;color:#9fb0cb;font-size:10px;line-height:1.7;margin-bottom:12px}.generate-summary b{color:#e0f2fe}
    #auto-recap-btn{min-height:64px!important;border:0!important;border-radius:16px!important;font-size:17px!important;font-weight:950!important;background:linear-gradient(100deg,#6d28d9,#2563eb 50%,#0891b2)!important;box-shadow:0 14px 40px #2563eb40!important;color:white!important}.final-stage{border-color:#22d3ee42!important;background:linear-gradient(155deg,#0b1327,#0e1932)!important}.final-badge{display:inline-flex;padding:6px 9px;border-radius:999px;background:#22c55e12;border:1px solid #22c55e40;color:#86efac;font-size:9px;font-weight:950}.final-copy{font-size:10px;color:#93a4c5;line-height:1.5;margin-bottom:10px}#yf-download-btn{min-height:58px!important;border-radius:15px!important;border:1px solid #67e8f944!important;background:linear-gradient(100deg,#059669,#0891b2,#2563eb)!important;color:white!important;font-weight:950!important;font-size:15px!important;margin-top:10px!important}.download-note{padding:9px 10px;border-radius:11px;background:#07111f99;border:1px solid #334155;color:#8fa3c5;font-size:9px;line-height:1.45;margin-top:8px}.footer-note{text-align:center;color:#52617d;font-size:9px;padding:16px 0}
    input,textarea,select{max-width:100%!important}.gradio-container video{max-height:56vh!important}
    @media(max-width:720px){.gradio-container{padding:5px 6px 74px!important}.wiz-hero{padding:17px 13px;border-radius:19px;margin-top:2px}.wiz-logo{width:48px;height:48px;flex-basis:48px;border-radius:15px;font-size:18px}.wiz-name{font-size:21px}.wiz-sub{font-size:9px}.wiz-note{font-size:10px;margin-top:10px}.wiz-progress{padding-left:0;padding-right:0}.wiz-node small{font-size:7px}.wiz-node span{width:27px;height:27px;font-size:9px}.wiz-line{top:22px}.wizard-card{padding:12px!important;border-radius:17px!important}.wizard-title{font-size:17px}.wizard-copy{font-size:10px}.mobile-stack{display:flex!important;flex-direction:column!important;gap:9px!important}.mobile-stack>*{width:100%!important;min-width:0!important}button{min-height:48px!important}input,textarea,select{font-size:16px!important}.wiz-nav{display:flex!important;flex-direction:row!important;gap:8px!important}.wiz-nav>*{min-width:0!important;flex:1!important}#auto-recap-btn{position:sticky!important;bottom:8px!important;z-index:85!important;box-shadow:0 10px 34px #000b,0 0 24px #2563eb55!important}.gradio-container video{max-height:47vh!important}#yf-download-btn{min-height:55px!important}#yf-conn{right:7px!important;bottom:72px!important}}
    @media(max-width:390px){.wiz-node small{display:none}.wiz-progress{padding-bottom:0}.wizard-card{padding:10px!important}.wiz-name{font-size:19px}}
    """
    # V6.8.3 — complete Aurora UI redesign. This intentionally overrides the
    # older V6.8.2 palette while keeping all backend/component IDs intact.
    css += r"""
    :root{
      --aurora-bg:#05060b;--aurora-panel:#0d1019cc;--aurora-panel2:#111725d9;
      --aurora-line:#28354d;--aurora-mint:#56f2c7;--aurora-cyan:#43d9ff;
      --aurora-purple:#9b6cff;--aurora-pink:#ff5fb7;--aurora-text:#f7fbff;
      --aurora-muted:#96a6be;--aurora-warning:#ffd166;--aurora-danger:#ff6b83;
    }
    html,body{background:#05060b!important}
    body,.gradio-container{
      background:
        radial-gradient(900px 460px at -5% -5%,#00d4a91f 0%,transparent 62%),
        radial-gradient(820px 430px at 105% 2%,#9b6cff20 0%,transparent 60%),
        radial-gradient(650px 360px at 50% 105%,#ff5fb714 0%,transparent 70%),
        linear-gradient(180deg,#070913 0%,#05060b 60%,#04050a 100%)!important;
      color:var(--aurora-text)!important;
    }
    .gradio-container{max-width:1020px!important;padding:12px 14px 88px!important}

    /* Hero */
    .wiz-hero{
      border:1px solid #ffffff12!important;
      border-radius:30px!important;
      background:linear-gradient(145deg,#111522e8,#0a0d16e8)!important;
      box-shadow:0 28px 90px #0009,inset 0 1px #ffffff0d!important;
      backdrop-filter:blur(22px)!important;
      padding:25px!important;
    }
    .wiz-hero:before{content:"";position:absolute;inset:-2px;border-radius:31px;padding:1px;background:linear-gradient(125deg,#56f2c780,#43d9ff30,#9b6cff60,#ff5fb730);-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
    .wiz-hero:after{width:300px!important;height:300px!important;right:-100px!important;top:-150px!important;background:radial-gradient(circle,#9b6cff2a,transparent 67%)!important}
    .wiz-logo{position:relative!important;isolation:isolate;width:62px!important;height:62px!important;flex-basis:62px!important;border-radius:20px!important;background:#0c1019!important;border:1px solid #56f2c744!important;box-shadow:0 0 0 5px #56f2c70a,0 14px 45px #43d9ff20!important;overflow:hidden}
    .wiz-logo:before{content:"";position:absolute;inset:-45%;z-index:-1;background:conic-gradient(from 0deg,#56f2c7,#43d9ff,#9b6cff,#ff5fb7,#56f2c7);animation:yfLogoSpin 7s linear infinite}
    .wiz-logo:after{content:"";position:absolute;inset:2px;z-index:-1;border-radius:18px;background:#0a0d14}
    .wiz-logo span{font-weight:1000;letter-spacing:-.06em;background:linear-gradient(120deg,#fff,#b9fff0 45%,#d9c8ff);-webkit-background-clip:text;background-clip:text;color:transparent}
    @keyframes yfLogoSpin{to{transform:rotate(360deg)}}
    .wiz-name{font-size:29px!important;letter-spacing:-.04em!important;background:linear-gradient(90deg,#fff,#c9fff2 43%,#d5c7ff 80%);-webkit-background-clip:text;background-clip:text;color:transparent}
    .wiz-sub{color:#7f91aa!important;letter-spacing:.13em!important;font-size:9px!important;font-weight:850!important}
    .wiz-note{color:#a6b4c8!important}.wiz-note b{color:#72f7d4!important}

    /* Wizard progress */
    .wiz-progress-wrap{background:linear-gradient(180deg,#05060bf2 72%,transparent)!important;backdrop-filter:blur(16px)!important}
    .wiz-line{background:linear-gradient(90deg,#223047,#33415b)!important}
    .wiz-node span{background:#0b0f18!important;border-color:#31405a!important;color:#71829c!important;transition:.25s ease!important}
    .wiz-node.active span{background:linear-gradient(135deg,#0f6c64,#336bd8 55%,#7652d1)!important;border-color:#72f7d4!important;box-shadow:0 0 0 5px #56f2c70d,0 0 25px #43d9ff32!important;transform:scale(1.08)}
    .wiz-node.done span{background:linear-gradient(135deg,#087a61,#0aa487)!important;border-color:#56f2c7!important;box-shadow:0 0 18px #56f2c725!important}
    .wiz-step-label{color:#72f7d4!important}

    /* Glass cards / fields */
    .wizard-card,.login-card-pro{
      border:1px solid #ffffff12!important;
      background:linear-gradient(180deg,#101520d9,#090d15e8)!important;
      box-shadow:0 24px 70px #0008,inset 0 1px #ffffff0b!important;
      backdrop-filter:blur(22px)!important;
      border-radius:25px!important;
    }
    .wizard-badge{border-color:#56f2c73d!important;background:linear-gradient(90deg,#56f2c711,#43d9ff0d)!important;color:#8dffe1!important;letter-spacing:.08em!important}
    .wizard-title{color:#f8fbff!important;letter-spacing:-.025em!important}
    .wizard-copy,.hint,.clone-copy{color:#95a6bd!important}
    .engine-panel{background:linear-gradient(180deg,#0b1019d9,#0a0d15dd)!important;border-color:#2b3950!important}
    .clone-panel{background:linear-gradient(145deg,#25153b8c,#0a1018dc)!important;border-color:#9b6cff52!important}
    .generate-summary,.download-note{background:#070b12d9!important;border-color:#26354c!important;color:#9eacc0!important}
    .clean-audio-badge{background:#56f2c70a!important;border-color:#56f2c738!important;color:#8affe0!important}

    /* Gradio form controls */
    .gradio-container input,.gradio-container textarea,.gradio-container select{
      border-radius:13px!important;
    }
    .gradio-container input:focus,.gradio-container textarea:focus,.gradio-container select:focus{
      outline:none!important;box-shadow:0 0 0 2px #56f2c72c,0 0 22px #43d9ff16!important;border-color:#56f2c778!important;
    }
    input[type=range]{accent-color:#56f2c7!important}

    /* Subtitle live size preview */
    .sub-size-preview{margin:8px 0 13px;padding:12px;border-radius:16px;border:1px solid #2b3a50;background:linear-gradient(145deg,#080c13,#0e1420);box-shadow:inset 0 1px #ffffff08}
    .sub-size-meta{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
    .sub-size-meta span{font-size:8px;font-weight:950;letter-spacing:.14em;color:#72839b}.sub-size-meta b{font-size:11px;color:#72f7d4}
    .sub-size-stage{min-height:78px;border-radius:12px;display:grid;place-items:center;text-align:center;padding:12px;background:radial-gradient(circle at 50% 120%,#9b6cff22,transparent 58%),#05070c;border:1px solid #ffffff0b;overflow:hidden}
    .sub-size-stage span{font-family:"Noto Sans Myanmar",sans-serif;font-weight:900;line-height:1.3;color:#ffe66d;text-shadow:-2px -2px 0 #000,2px -2px 0 #000,-2px 2px 0 #000,2px 2px 0 #000;transition:font-size .22s ease}
    .sub-size-preview small{display:block;margin-top:7px;color:#76879e;font-size:9px;line-height:1.45}

    /* Live process card */
    .process-card{border-color:#43d9ff35!important;background:linear-gradient(135deg,#07121ae8,#121326e8)!important;box-shadow:0 18px 46px #0006,inset 0 1px #ffffff09!important}
    .process-spinner{border-color:#56f2c725!important;border-top-color:#56f2c7!important;border-right-color:#9b6cff!important;box-shadow:0 0 20px #43d9ff20!important}
    .process-top strong{color:#72f7d4!important}.process-track{height:9px!important;background:#03060b!important;border-color:#243249!important}.process-track i{background:linear-gradient(90deg,#56f2c7,#43d9ff,#9b6cff,#ff5fb7)!important;background-size:220% 100%!important;animation:yfProgressFlow 2s linear infinite!important;box-shadow:0 0 18px #43d9ff54!important}
    @keyframes yfProgressFlow{to{background-position:220% 0}}
    .eta-card.ready{border-color:#56f2c732!important;background:linear-gradient(105deg,#56f2c70d,#43d9ff0c,#9b6cff0d)!important}.eta-icon{background:#56f2c70e!important;border-color:#56f2c72b!important}

    /* Button system — hover lift + glow + press feedback + shimmer */
    .gradio-container button,#yf-download-btn{
      position:relative!important;overflow:hidden!important;isolation:isolate!important;
      transition:transform .18s ease,box-shadow .22s ease,border-color .22s ease,filter .22s ease!important;
      -webkit-tap-highlight-color:transparent!important;
    }
    .gradio-container button:hover,#yf-download-btn:hover{transform:translateY(-2px) scale(1.006)!important;filter:brightness(1.08)!important}
    .gradio-container button:active,#yf-download-btn:active{transform:translateY(1px) scale(.985)!important;transition-duration:.07s!important}
    .wiz-next{background:linear-gradient(105deg,#0e9f82,#178fb6 48%,#6f50d7)!important;border:1px solid #78f9d745!important;box-shadow:0 10px 28px #43d9ff1b!important}
    .wiz-next:hover{box-shadow:0 15px 38px #43d9ff2d,0 0 0 1px #56f2c72c inset!important}
    .wiz-back{background:linear-gradient(180deg,#121824,#0b1019)!important;border-color:#34425a!important;color:#c7d1df!important}.wiz-back:hover{border-color:#71839d!important;box-shadow:0 10px 26px #0005!important}

    #auto-recap-btn{
      min-height:68px!important;border-radius:18px!important;font-size:16px!important;letter-spacing:.015em!important;
      background:linear-gradient(105deg,#0eaa87 0%,#158eb2 35%,#6651d6 67%,#d34b9b 100%)!important;
      background-size:220% 100%!important;
      border:1px solid #ffffff24!important;
      box-shadow:0 18px 46px #43d9ff24,0 0 0 1px #56f2c71f inset!important;
      animation:yfButtonFlow 5s ease infinite!important;
    }
    #auto-recap-btn:before,#yf-download-btn:before{content:"";position:absolute;z-index:-1;top:-100%;left:-40%;width:35%;height:300%;transform:rotate(20deg);background:linear-gradient(90deg,transparent,#ffffff35,transparent);animation:yfShine 3.6s ease-in-out infinite}
    #auto-recap-btn:hover{box-shadow:0 22px 58px #43d9ff38,0 0 30px #9b6cff24!important}
    @keyframes yfButtonFlow{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
    @keyframes yfShine{0%,65%{left:-55%;opacity:0}72%{opacity:1}100%{left:125%;opacity:0}}

    #yf-download-btn{background:linear-gradient(105deg,#079b78,#0b8ba8,#4e61d8)!important;border-color:#56f2c74a!important;box-shadow:0 15px 38px #56f2c71d!important}
    #yf-download-btn:hover{box-shadow:0 20px 48px #56f2c72d!important}

    .final-stage{border-color:#56f2c72e!important;background:linear-gradient(145deg,#0a1417d9,#0d1020e8)!important}.final-badge{background:#56f2c70c!important;border-color:#56f2c738!important;color:#8affe0!important}
    .footer-note{color:#4d5c72!important;letter-spacing:.05em!important}

    @media(max-width:720px){
      .gradio-container{padding:6px 7px 82px!important}.wiz-hero{padding:18px 14px!important;border-radius:22px!important}.wiz-logo{width:50px!important;height:50px!important;flex-basis:50px!important;border-radius:16px!important}.wiz-logo:after{border-radius:14px!important}.wiz-name{font-size:22px!important}.wizard-card{padding:13px!important;border-radius:19px!important}.wizard-title{font-size:18px!important}
      #auto-recap-btn{min-height:64px!important;bottom:10px!important;border-radius:16px!important;font-size:15px!important}
      .sub-size-stage{min-height:70px}.process-card{padding:12px!important}.process-main>span{font-size:9.5px!important}

      /* Voice Clone: prevent the radio choices and uploaded-audio player from
         widening the whole page on narrow Android/iPhone screens. */
      html,body,.gradio-container,.wizard-card,.engine-panel,.voice-clone-card{max-width:100%!important;min-width:0!important}
      .voice-engine-radio,.voice-engine-radio fieldset,.voice-engine-radio [role="radiogroup"],.voice-engine-radio .wrap{width:100%!important;max-width:100%!important;min-width:0!important}
      .voice-engine-radio fieldset,.voice-engine-radio [role="radiogroup"],.voice-engine-radio .wrap{display:grid!important;grid-template-columns:minmax(0,1fr)!important;gap:8px!important}
      .voice-engine-radio label,.voice-engine-radio label.wrap{width:100%!important;min-width:0!important;max-width:100%!important}
      .voice-engine-radio label span{min-width:0!important;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      /* Gradio creates the waveform player only after an audio file is
         selected.  Constrain both the original upload block and that dynamic
         player so neither can push the mobile page sideways. */
      #clone-reference-upload,#clone-reference-upload *,
      .voice-clone-card,.voice-clone-card *{box-sizing:border-box!important}
      #clone-reference-upload,.clone-audio-input,
      #clone-reference-upload .wrap,#clone-reference-upload .block,
      #clone-reference-upload [data-testid="audio"],
      #clone-reference-upload .audio-container,
      #clone-reference-upload .audio-waveform,
      #clone-reference-upload .waveform,
      #clone-reference-upload .audio-player,
      #clone-reference-upload audio,
      .clone-audio-input .wrap,.clone-audio-input .audio-container,
      .clone-audio-input .audio-waveform,.clone-audio-input audio{
        width:100%!important;max-width:100%!important;min-width:0!important;
      }
      #clone-reference-upload,.clone-audio-input{overflow:hidden!important}
      #clone-reference-upload [data-testid="audio"],
      #clone-reference-upload .audio-container,.clone-audio-input .audio-container,
      #clone-reference-upload .audio-waveform,.clone-audio-input .audio-waveform{
        overflow:hidden!important;flex:1 1 0!important;
      }
      #clone-reference-upload canvas,#clone-reference-upload svg{
        max-width:100%!important;min-width:0!important;
      }
      /* Compact the tall WaveSurfer view Gradio shows after uploading. */
      #clone-reference-upload [class*="waveform"],
      #clone-reference-upload [class*="Waveform"]{
        height:92px!important;min-height:92px!important;max-height:92px!important;
      }
      #clone-reference-upload [class*="waveform"]>*,
      #clone-reference-upload [class*="Waveform"]>*{
        max-height:92px!important;
      }
      #clone-reference-upload audio{height:38px!important;display:block!important}

      /* Keep the Voice Clone card at the same height before and after a file
         is chosen.  Gradio turns the tall drop area into one short file row
         after upload, which used to make the whole mobile page jump upward. */
      .clone-upload-stable-slot{
        height:122px!important;min-height:122px!important;max-height:122px!important;
        overflow:hidden!important;
      }
      .clone-upload-stable-slot #clone-reference-upload{
        height:122px!important;min-height:122px!important;max-height:122px!important;
      }
      .clone-upload-stable-slot #clone-reference-upload .wrap,
      .clone-upload-stable-slot #clone-reference-upload .wrap > *{
        height:72px!important;min-height:0!important;max-height:72px!important;
        overflow:hidden!important;
      }
      /* UploadButton never swaps itself for Gradio's large file preview.
         It therefore has the exact same mobile size before and after upload. */
      #clone-reference-upload button{
        width:100%!important;min-height:56px!important;height:56px!important;
        border-radius:12px!important;font-weight:900!important;
      }
      .clone-reference-status-slot{
        min-height:54px!important;max-height:54px!important;overflow:hidden!important;
      }

      /* Dropdown pop-up should stay tap-friendly and above the card on phones. */
      #subtitle-font-picker,#subtitle-font-picker *{min-width:0!important;box-sizing:border-box!important}
      #subtitle-font-picker [role="listbox"]{max-width:calc(100vw - 26px)!important;z-index:1000!important}
    }

    /* V6.8.6 — Midnight Emerald + Champagne Gold full UI refresh. */
    :root{--bg:#06110f;--card:#0b1b17;--card2:#10251f;--line:#31584f;--cyan:#2dd4bf;--blue:#0f766e;--violet:#b98a3d;--green:#34d399;--text:#fffaf0;--muted:#9db8ae;--gold:#e7bd68}
    html,body{background:#06110f!important}
    body,.gradio-container{background:radial-gradient(circle at 8% -5%,#16483c 0,transparent 34%),radial-gradient(circle at 96% 2%,#5b401c66 0,transparent 29%),linear-gradient(180deg,#0a1814,#06110f 48%,#040b09)!important}
    .wiz-hero{border-color:#d6ad5b66!important;background:linear-gradient(145deg,#102a23f2,#091713f7)!important}.wiz-logo{background:linear-gradient(135deg,#0f766e,#d6ad5b)!important;color:#fff8e7!important}.wiz-sub,.wizard-copy,.clone-copy,.hint,.login-copy{color:#9db8ae!important}.wiz-note{color:#c6d9d2!important}.wiz-note b,.wiz-step-label{color:#ffe2a3!important}
    .wiz-progress-wrap{background:linear-gradient(180deg,#06110ff2 72%,transparent)!important}.wiz-line{background:#31584f!important}.wiz-node span{background:#091713!important;border-color:#3d665d!important}.wiz-node.active{color:#ffe2a3!important}.wiz-node.active span{border-color:#e7bd68!important;background:linear-gradient(135deg,#0f766e,#b98a3d)!important}
    .wizard-card,.login-card-pro{border-color:#31584f!important;background:linear-gradient(180deg,#0e211ce8,#07130ff7)!important}.wizard-badge{border-color:#e7bd6855!important;background:#d6ad5b12!important;color:#ffe5ad!important}
    .wiz-next,#auto-recap-btn,#yf-download-btn{background:linear-gradient(100deg,#0f766e,#159a86 52%,#b98a3d)!important;color:#fffdf5!important}.wiz-back{background:#10231e!important;border-color:#3a6259!important;color:#c9ddd6!important}
    .engine-panel,.generate-summary,.sub-size-preview,.eta-card,.download-note{border-color:#31584f!important;background:linear-gradient(180deg,#10251fcc,#091713e8)!important}.clone-panel{border-color:#d6ad5b66!important;background:linear-gradient(180deg,#5b401c2e,#0a1915e8)!important}.clone-title,.voice-mode-title{color:#ffe6b3!important}
    input,textarea,[role="listbox"],.gradio-container select{border-color:#355f55!important;background:#081713!important;color:#fffaf0!important}.footer-note{color:#78998e!important}.member-strip{border-color:#34d39955!important;background:#0f6b5020!important}
    @media(prefers-reduced-motion:reduce){.wiz-logo:before,.process-track i,#auto-recap-btn,#auto-recap-btn:before,#yf-download-btn:before{animation:none!important}.gradio-container button,#yf-download-btn{transition:none!important}}
    """
    theme = gr.themes.Soft(primary_hue="emerald", secondary_hue="violet", neutral_hue="slate")
    connection_js = r"""
    (()=>{if(document.getElementById('yf-conn'))return;const d=document.createElement('div');d.id='yf-conn';d.style='position:fixed;right:10px;bottom:10px;z-index:99999;background:#07111be8;color:#86efac;border:1px solid #34d39955;border-radius:999px;padding:7px 10px;font:700 9px Arial;backdrop-filter:blur(8px)';d.textContent='● YF Connected';document.body.appendChild(d);})();
    """

    with gr.Blocks(title="YF Recap V6.8.3 • Aurora Studio") as app:
        app._yf_theme = theme
        app._yf_css = css
        app._yf_js = connection_js
        session_id_state = gr.State(lambda: str(uuid.uuid4()))
        vip_access_state = gr.State({"authenticated": False})
        analysis_state = gr.State({})
        # BrowserState survives a temporary Cloudflare/Gradio reconnect. This
        # prevents a long render from visually jumping back to Step 1.
        wizard_step = gr.BrowserState(1, storage_key="yf_recap_wizard_step_v687")

        gr.HTML("""
        <section class='wiz-hero'>
          <div class='wiz-brand'>
            <div class='wiz-logo'><span>YF</span></div>
            <div><div class='wiz-name'>YF Recap</div><div class='wiz-sub'>AURORA • STEP-BY-STEP AI RECAP STUDIO</div></div>
          </div>
          <div class='wiz-note'>Clean wizard flow • <b>တစ်ဆင့်ပြီးမှ တစ်ဆင့်</b> • Mobile touch controls • Live render status</div>
        </section>
        """)

        with gr.Column(visible=True, elem_classes=["login-shell-pro"]) as login_panel:
            with gr.Column(elem_classes=["login-card-pro"]):
                gr.HTML("<div class='login-head'>YF Recap Access</div><div class='login-copy'>Admin Portal မှ ထုတ်ထားသော Video Recap VIP Code ကို ထည့်ပါ</div>")
                vip_code_input = gr.Textbox(label="VIP ACCESS CODE", placeholder="VIP-XXXX-XXXX-XXXX", type="password")
                unlock_btn = gr.Button("🔓 ENTER YF RECAP", variant="primary")
                login_status = gr.HTML()

        with gr.Column(visible=False) as main_panel:
            with gr.Row(elem_classes=["mobile-stack"]):
                with gr.Column(scale=9):
                    member_status_html = gr.HTML()
                with gr.Column(scale=1, min_width=95):
                    logout_btn = gr.Button("Logout")

            with gr.Column(elem_classes=["wiz-progress-wrap"]):
                wizard_progress = gr.HTML(_wizard_progress_html(1))

            # Internal hidden components retained for backend compatibility.
            analysis_status = gr.Markdown(visible=False)
            scene_table = gr.Dataframe(headers=["Scene", "Start", "End", "Speech / Context"], datatype=["number", "str", "str", "str"], interactive=False, wrap=True, value=[], visible=False)
            script_editor = gr.Textbox(visible=False)

            # ---------------- STEP 1 ----------------
            with gr.Column(visible=True, elem_classes=["wizard-card"]) as step1_panel:
                gr.HTML("<div class='wizard-badge'>STEP 1 • SOURCE</div><div class='wizard-title'>🎬 Upload Movie</div><div class='wizard-copy'>Recap လုပ်မယ့် movie / clip ကိုအရင် upload လုပ်ပါ။ မူရင်း video duration ကို Auto mode မှာ final duration အဖြစ်ထိန်းထားပါတယ်။</div>")
                video_input = gr.Video(label="Original Movie / Clip", sources=["upload"])
                with gr.Row(elem_classes=["wiz-nav"]):
                    step1_next = gr.Button("NEXT  →", variant="primary", elem_classes=["wiz-next"])

            # ---------------- STEP 2 ----------------
            with gr.Column(visible=False, elem_classes=["wizard-card"]) as step2_panel:
                gr.HTML("<div class='wizard-badge'>STEP 2 • STORY</div><div class='wizard-title'>🧠 Recap Settings</div><div class='wizard-copy'>AI script ကို user မမြင်ရအောင် backend မှာ auto analyze + generate လုပ်ပါမယ်။ Viral Story Recap ကို default ထားထားပါတယ်။</div>")
                user_api_key = gr.Textbox(label="Gemini API Key", type="password", placeholder="Gemini Flash models auto fallback")
                tone_style = gr.Dropdown(choices=["Viral Story Recap", "Thriller", "Comedy", "Dramatic", "Action/Epic", "Neutral"], value="Viral Story Recap", label="Narrative Tone")
                recap_length = gr.Dropdown(
                    choices=[
                        "🎞 မသတ်မှတ် (မူရင်း Video အရှည်အတိုင်း)",
                        "⚡ 1 Minute Short",
                        "🎬 3 Minute Recap",
                        "🔥 5 Minute Recap",
                        "🍿 10 Minute Recap",
                    ],
                    value="🎞 မသတ်မှတ် (မူရင်း Video အရှည်အတိုင်း)",
                    label="Target Recap Length",
                    info="မသတ်မှတ် = upload လုပ်ထားတဲ့ video duration ကို target အဖြစ်ထိန်းထားမယ်။",
                )
                with gr.Row(elem_classes=["wiz-nav"]):
                    step2_back = gr.Button("←  BACK", elem_classes=["wiz-back"])
                    step2_next = gr.Button("NEXT  →", variant="primary", elem_classes=["wiz-next"])

            # ---------------- STEP 3 ----------------
            with gr.Column(visible=False, elem_classes=["wizard-card"]) as step3_panel:
                gr.HTML("<div class='wizard-badge'>STEP 3 • NARRATION</div><div class='wizard-title'>🎙 Choose Voice</div><div class='wizard-copy'>Fast Burmese voice သို့ VoxCPM2 Voice Clone ရွေးပါ။ Voice Clone ရွေးမှသာ reference controls ပေါ်ပါမယ်။</div>")
                voice_engine = gr.Radio(
                    choices=["⚡ Edge TTS • Fast", "🎙️ VoxCPM2 Voice Clone"],
                    value="⚡ Edge TTS • Fast",
                    label="Narration Voice",
                    elem_classes=["voice-engine-radio"],
                )
                with gr.Column(visible=True, elem_classes=["engine-panel"]) as edge_voice_panel:
                    gr.HTML("<div class='voice-mode-title'>⚡ Fast Burmese Voice</div><div class='hint'>Edge TTS fail ဖြစ်ရင် gTTS Burmese fallback ကို backend က auto သုံးပါတယ်။</div>")
                    edge_voice_select = gr.Dropdown(choices=list(EDGE_VOICES.keys()), value="👩 Myanmar Female • Nilar", label="Voice")

                voice_preset = gr.State("")
                custom_voice_description = gr.State("")

                with gr.Column(visible=False, elem_classes=["engine-panel", "clone-panel", "voice-clone-card"]) as voxcpm_clone_panel:
                    gr.HTML("<div class='clone-title'>🎙 VoxCPM2 Voice Clone</div><div class='clone-copy'>အသုံးပြုခွင့်ရှိတဲ့ 5–15 sec reference MP3/WAV ကိုထည့်ပါ။</div>")
                    # UploadButton stays visually identical after selecting a
                    # file.  Unlike gr.File it does not replace the drop area
                    # with a filename preview, so mobile layout never jumps.
                    clone_reference = gr.State("")
                    clone_upload_button = gr.UploadButton(
                        "📤  UPLOAD REFERENCE MP3 / WAV",
                        file_types=["audio"], file_count="single", type="filepath",
                        variant="primary", elem_id="clone-reference-upload",
                    )
                    with gr.Column(elem_classes=["clone-reference-status-slot"]):
                        clone_reference_status = gr.HTML("<div class='hint'>Reference voice မထည့်ရသေးပါ။</div>")
                    clone_transcript = gr.Textbox(label="Reference Transcript (Optional)", lines=2, placeholder="Reference audio ထဲက စကားကို အတိအကျရေးနိုင်ပါတယ်။")
                    clone_consent = gr.Checkbox(label="ဒီ reference အသံကို clone အသုံးပြုရန် ခွင့်ပြုချက်ရှိပါသည်")

                desired_speed = gr.Slider(0.9, 1.1, value=1.0, step=.05, label="Voice Pace • Normal (Fixed)", interactive=False)
                with gr.Column(visible=False, elem_classes=["engine-panel"]) as voxcpm_quality_panel:
                    with gr.Accordion("⚙️ VoxCPM2 Quality", open=False):
                        voxcpm_cfg = gr.Slider(1.0, 3.0, value=2.0, step=.1, label="CFG")
                        voxcpm_steps = gr.Slider(4, 20, value=10, step=1, label="Steps")
                        voxcpm_seed = gr.Number(value=42, precision=0, label="Seed")
                with gr.Row(elem_classes=["wiz-nav"]):
                    step3_back = gr.Button("←  BACK", elem_classes=["wiz-back"])
                    step3_next = gr.Button("NEXT  →", variant="primary", elem_classes=["wiz-next"])

            # ---------------- STEP 4 ----------------
            with gr.Column(visible=False, elem_classes=["wizard-card"]) as step4_panel:
                gr.HTML("<div class='wizard-badge'>STEP 4 • LOOK</div><div class='wizard-title'>✨ Subtitle + Blur</div><div class='wizard-copy'>Yellow subtitle guide နဲ့ blur band ကို preview ပေါ်မှာ finger/mouse နဲ့ drag လုပ်ပါ။ Final render မှာ exact position sync ဖြစ်ပါတယ်။</div>")
                layout_editor = gr.HTML(value=video_first_frame_data_uri, inputs=[video_input], html_template=LAYOUT_EDITOR_TEMPLATE, css_template=LAYOUT_EDITOR_CSS, js_on_load=LAYOUT_EDITOR_JS, apply_default_css=False, container=False)
                blur_y_percent = gr.Textbox(value='[{"x":0,"y":72,"w":100,"h":12}]', visible=False)
                blur_height_percent = gr.Number(value=12, visible=False)
                sub_pos_percent = gr.Number(value=82, visible=False)
                with gr.Row(elem_classes=["mobile-stack"]):
                    text_color = gr.ColorPicker(label="Subtitle Text", value="#FFFF00")
                    stroke_color = gr.ColorPicker(label="Outline", value="#000000")
                subtitle_size = gr.Slider(1.0, 10.0, value=5.5, step=.5, label="Subtitle Size • 1 Small — 10 Large")
                subtitle_size_preview = gr.HTML(_subtitle_size_preview_html(5.5))
                subtitle_font_style = gr.Dropdown(
                    choices=list(FONT_STYLE_FILES.keys()),
                    value="Noto Sans Myanmar (Default)",
                    label="Subtitle Font Style",
                    filterable=False,
                    allow_custom_value=False,
                    elem_id="subtitle-font-picker",
                )
                blur_strength = gr.Slider(5, 151, value=51, step=2, label="Blur Strength")
                font_style_status = gr.HTML(subtitle_font_status("Noto Sans Myanmar (Default)"))
                with gr.Accordion("📁 Custom Myanmar Font", open=False):
                    gr.HTML(f"<div class='hint'>Unicode Myanmar TTF/OTF font ကို upload လုပ်နိုင်ပါတယ်။ Premium Font ZIP တင်ရင် ZIP ထဲက font အားလုံးကို dropdown မှာ search/ရွေးလို့ရပါတယ်။ လက်ရှိ auto-loaded premium fonts: <b>{PREMIUM_FONT_COUNT}</b></div>")
                    premium_font_zip_upload = gr.File(label="Premium Font ZIP • Add All Fonts", file_types=[".zip"], type="filepath")
                    premium_font_status = gr.HTML("<div class='hint'>Premium Font ZIP မတင်ရသေးပါ။</div>")
                    subtitle_font_upload = gr.File(label="Upload Font (.ttf / .otf)", file_count="multiple", file_types=[".ttf", ".otf"], type="filepath")
                    font_upload_status = gr.HTML("<div class='hint'>Custom font မတင်ရသေးပါ။</div>")
                with gr.Row(elem_classes=["wiz-nav"]):
                    step4_back = gr.Button("←  BACK", elem_classes=["wiz-back"])
                    step4_next = gr.Button("NEXT  →", variant="primary", elem_classes=["wiz-next"])

            # Hidden audio states: narration only, no original sound, no BGM.
            bgm_file = gr.State(None)
            original_vol = gr.State(0)
            bgm_vol = gr.State(0)
            auto_duck = gr.State(False)

            # ---------------- STEP 5 ----------------
            with gr.Column(visible=False, elem_classes=["wizard-card"]) as step5_panel:
                gr.HTML("<div class='wizard-badge'>STEP 5 • GENERATE</div><div class='wizard-title'>🚀 Ready to Auto Recap</div><div class='wizard-copy'>ဒီအဆင့်မှာ output settings ကိုနောက်ဆုံးစစ်ပြီး AUTO RECAP တစ်ချက်ပဲနှိပ်ပါ။ Original movie audio နဲ့ BGM မပါဘဲ narration only ထွက်ပါမယ်။</div>")
                gr.HTML("<div class='generate-summary'><b>✓ Narration only</b> · No original movie audio · No BGM<br><b>✓ Smart subtitles</b> · 25–35 visible characters · phrase-safe split<br><b>✓ Final duration</b> · Auto mode = source video duration</div>")
                narration_vol = gr.Slider(70, 130, value=100, step=1, label="Narration Volume %")
                with gr.Row(elem_classes=["mobile-stack"]):
                    ratio_select = gr.Dropdown(choices=["9:16 (TikTok/Reels)", "16:9 (Landscape)"], value="9:16 (TikTok/Reels)", label="Output Ratio")
                    render_mode = gr.Radio(choices=["⚡ Turbo 24 FPS (Recommended)", "🎬 Balanced 30 FPS"], value="⚡ Turbo 24 FPS (Recommended)", label="Render Mode")
                background_fill = gr.Radio(choices=["Blur Background", "Black Background"], value="Blur Background", label="Background")
                with gr.Row(elem_classes=["mobile-stack"]):
                    logo_file = gr.File(label="Brand Logo PNG (Optional)", file_types=["image"])
                    filter_color = gr.Dropdown(choices=["None", "Chrome Cool", "Warm Cinema"], value="None", label="Color Look")
                enable_zoom = gr.Checkbox(label="Zoom & Crop", value=False)
                zoom_level = gr.Slider(1.0, 3.0, value=1.0, step=.1, label="Zoom")
                mirror_flip = gr.Checkbox(label="Mirror Flip", value=False)
                eta_card = gr.HTML("<div class='eta-card waiting'><div class='eta-icon'>⏱</div><div><b>Ready</b><span>Video + settings အဆင်သင့်ဖြစ်ရင် AUTO RECAP တစ်ခုပဲနှိပ်ပါ။</span></div></div>")
                processing_card = gr.HTML(_processing_status_html(None))
                auto_recap_btn = gr.Button("✨  AUTO RECAP — GENERATE VIDEO", variant="primary", elem_id="auto-recap-btn")
                render_status = gr.Markdown()
                with gr.Row(elem_classes=["wiz-nav"]):
                    step5_back = gr.Button("←  BACK", elem_classes=["wiz-back"])

            # ---------------- STEP 6 ----------------
            with gr.Column(visible=False, elem_classes=["wizard-card", "final-stage"]) as step6_panel:
                gr.HTML("<div class='wizard-badge'>STEP 6 • COMPLETE</div><div class='wizard-title'>🎬 Final YF Recap</div><div class='final-copy'>Video preview ကိုကြည့်ပြီး အောက်က Download button နဲ့ Final MP4 ကိုယူပါ။</div><span class='final-badge'>● READY OUTPUT</span>")
                final_video = gr.Video(label="Final YF Recap", buttons=[], autoplay=False)
                fast_download = gr.DownloadButton("⬇  DOWNLOAD FINAL VIDEO", value=None, variant="primary", elem_id="yf-download-btn")
                gr.HTML("<div class='download-note'><b>Direct final-file download</b><br>Final MP4 ကို stable output path ကနေ serve လုပ်ပါတယ်။</div>")
                srt_file = gr.File(visible=False)
                mp3_file = gr.File(visible=False)
                script_file = gr.File(visible=False)
                with gr.Row(elem_classes=["wiz-nav"]):
                    step6_back = gr.Button("←  SETTINGS", elem_classes=["wiz-back"])

            gr.HTML(f"<div class='footer-note'>YF RECAP {YF_BUILD} • AURORA UI • LIVE ETA • MOBILE FIRST • NO BGM • NO ORIGINAL AUDIO</div>")

        wizard_outputs = [wizard_progress, step1_panel, step2_panel, step3_panel, step4_panel, step5_panel, step6_panel, wizard_step]

        # Restore the last active wizard page when the browser reconnects. The
        # VIP login state is intentionally still server-side and is not stored
        # in the browser.
        app.load(
            _restore_wizard_after_reconnect,
            inputs=[wizard_step],
            outputs=wizard_outputs,
            queue=False,
            show_progress="hidden",
        )

        unlock_btn.click(unlock_vip, [vip_code_input], [vip_access_state, login_panel, main_panel, login_status, member_status_html])
        vip_code_input.submit(unlock_vip, [vip_code_input], [vip_access_state, login_panel, main_panel, login_status, member_status_html])
        logout_btn.click(logout_vip, [], [vip_access_state, login_panel, main_panel, login_status, member_status_html, vip_code_input])

        # Wizard navigation.
        step1_next.click(_wizard_after_upload, [video_input], wizard_outputs, queue=False, show_progress="hidden")
        step2_back.click(lambda: _wizard_payload(1), outputs=wizard_outputs, queue=False, show_progress="hidden")
        step2_next.click(lambda: _wizard_payload(3), outputs=wizard_outputs, queue=False, show_progress="hidden")
        step3_back.click(lambda: _wizard_payload(2), outputs=wizard_outputs, queue=False, show_progress="hidden")
        step3_next.click(_wizard_validate_voice, [voice_engine, clone_reference, clone_consent], wizard_outputs, queue=False, show_progress="hidden")
        step4_back.click(lambda: _wizard_payload(3), outputs=wizard_outputs, queue=False, show_progress="hidden")
        step4_next.click(lambda: _wizard_payload(5), outputs=wizard_outputs, queue=False, show_progress="hidden")
        step5_back.click(lambda: _wizard_payload(4), outputs=wizard_outputs, queue=False, show_progress="hidden")
        step6_back.click(lambda: _wizard_payload(5), outputs=wizard_outputs, queue=False, show_progress="hidden")

        voice_engine.change(update_voice_engine_panels_v6, [voice_engine], [edge_voice_panel, voxcpm_clone_panel, voxcpm_quality_panel], queue=False, show_progress="hidden")
        clone_upload_button.upload(
            accept_clone_upload,
            inputs=[clone_upload_button],
            outputs=[clone_reference, clone_reference_status],
            queue=False,
            show_progress="hidden",
        )
        layout_editor.change(sync_layout_editor, outputs=[blur_y_percent, blur_height_percent, sub_pos_percent], queue=False, show_progress="hidden")
        subtitle_size.change(_subtitle_size_preview_html, [subtitle_size], [subtitle_size_preview], queue=False, show_progress="hidden")
        subtitle_font_style.change(subtitle_font_status, [subtitle_font_style], [font_style_status], queue=False, show_progress="hidden")
        subtitle_font_upload.change(
            install_uploaded_subtitle_fonts,
            inputs=[subtitle_font_upload, subtitle_font_style],
            outputs=[font_upload_status, font_style_status, subtitle_font_style],
            queue=False,
            show_progress="hidden",
        )
        premium_font_zip_upload.change(
            install_premium_font_bundle,
            inputs=[premium_font_zip_upload],
            outputs=[premium_font_status, subtitle_font_style, font_style_status],
            queue=False,
            show_progress="hidden",
        )

        # IMPORTANT: update the UI first.  In V6.8 the long backend started
        # immediately, but no component changed until it finished, so on mobile
        # the button looked as if it did nothing.
        start_evt = auto_recap_btn.click(
            _start_auto_recap_feedback,
            inputs=[video_input, recap_length, voice_engine, render_mode, voxcpm_steps, session_id_state],
            outputs=[eta_card, render_status, processing_card],
            queue=False,
            show_progress="hidden",
        )

        auto_evt = start_evt.then(
            auto_recap_pipeline_v5,
            inputs=[video_input, user_api_key, tone_style, recap_length,
                    ratio_select, background_fill, enable_zoom, zoom_level, logo_file,
                    bgm_file, narration_vol, original_vol, bgm_vol, auto_duck, mirror_flip, filter_color,
                    voice_engine, edge_voice_select, voice_preset, custom_voice_description, clone_reference, clone_transcript, clone_consent,
                    voxcpm_cfg, voxcpm_steps, voxcpm_seed, text_color, stroke_color, blur_y_percent, blur_height_percent, blur_strength,
                    sub_pos_percent, subtitle_size, subtitle_font_style, desired_speed, render_mode, session_id_state, vip_access_state],
            outputs=[final_video, fast_download, srt_file, mp3_file, script_file, render_status],
            trigger_mode="once",
            concurrency_limit=1,
            concurrency_id="yf_auto_recap",
            show_progress="full",
        )
        # Result page must open only when the long render actually succeeds.
        auto_evt.success(lambda: _wizard_payload(6), outputs=wizard_outputs, queue=False, show_progress="hidden")
        auto_evt.success(
            refresh_member_quota,
            inputs=[vip_access_state],
            outputs=[member_status_html],
            queue=False,
            show_progress="hidden",
        )

        for _eta_trigger in [video_input, recap_length, voice_engine, render_mode, voxcpm_steps]:
            _eta_trigger.change(
                estimate_auto_recap_eta,
                inputs=[video_input, recap_length, voice_engine, render_mode, voxcpm_steps],
                outputs=eta_card,
                queue=False,
                show_progress="hidden",
            )

        # Poll the per-session live state every second. queue=False keeps this
        # responsive even while the heavy AUTO RECAP event owns the render queue.
        live_status_timer = gr.Timer(value=1.0, active=True)
        live_status_timer.tick(
            _processing_status_html,
            inputs=[session_id_state],
            outputs=[processing_card],
            queue=False,
            show_progress="hidden",
        )

    return app

# ================================================================
# 11) COLAB PUBLIC LAUNCH — DUAL LINKS (Cloudflare + gradio.live)
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
    """Create a Quick Tunnel with protocol/route fallback and health checks.

    Colab backends do not all have the same egress route. V6 therefore tries
    several cloudflared transports instead of declaring Cloudflare unavailable
    after one HTTP/2 attempt.
    """
    import threading

    binary = ensure_cloudflared()
    local_url = str(origin_url).rstrip("/")
    url_pattern = re.compile(r"https://[-a-zA-Z0-9]+\.trycloudflare\.com")

    # Different Colab VMs behave differently. Try TCP first, then auto, then QUIC.
    attempts = [
        ("HTTP/2 + IPv4", ["--protocol", "http2", "--edge-ip-version", "4"]),
        ("AUTO + IPv4", ["--edge-ip-version", "4"]),
        ("HTTP/2 + Auto IP", ["--protocol", "http2"]),
        ("QUIC + IPv4", ["--protocol", "quic", "--edge-ip-version", "4"]),
    ]

    last_error = ""
    for attempt_no, (label, transport_args) in enumerate(attempts, 1):
        print(f"☁️ Cloudflare attempt {attempt_no}/{len(attempts)} • {label}")
        cmd = [
            binary, "tunnel", "--no-autoupdate",
            *transport_args,
            "--loglevel", "info",
            "--url", local_url,
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        state = {"url": None, "last_error": ""}

        def _drain():
            try:
                if process.stdout is None:
                    return
                for raw in iter(process.stdout.readline, ""):
                    if not raw:
                        break
                    clean = raw.strip()
                    m = url_pattern.search(clean)
                    if m and not state["url"]:
                        state["url"] = m.group(0)
                    low = clean.lower()
                    if (
                        "context canceled" in low
                        or "failed to serve incoming request" in low
                        or "receive buffer size" in low
                    ):
                        continue
                    if any(k in low for k in (" err ", " error=", "failed", "connection refused", "timeout")):
                        state["last_error"] = clean
            except Exception as exc:
                state["last_error"] = str(exc)

        log_thread = threading.Thread(target=_drain, name=f"cloudflared-{attempt_no}", daemon=True)
        log_thread.start()

        deadline = time.time() + 38
        while time.time() < deadline:
            if state["url"]:
                public_url = state["url"]
                # Give the edge a moment to register the route. A failed health
                # check does not immediately discard the URL because Gradio may
                # still be starting its first HTTP response.
                healthy = False
                for _ in range(6):
                    try:
                        req = urllib.request.Request(public_url, headers={"User-Agent": "YF-Recap/6"})
                        with urllib.request.urlopen(req, timeout=5) as response:
                            healthy = 200 <= int(getattr(response, "status", 200)) < 500
                        if healthy:
                            break
                    except Exception:
                        time.sleep(1.0)
                if process.poll() is None:
                    print(f"✅ Cloudflare ONLINE • {label}")
                    return process, public_url, log_thread

            if process.poll() is not None:
                break
            time.sleep(0.25)

        last_error = state["last_error"] or f"{label} did not produce a usable URL"
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=4)
                except Exception:
                    process.kill()
        except Exception:
            pass
        time.sleep(1.0)

    raise RuntimeError(
        "Cloudflare Quick Tunnel retries အားလုံး မအောင်မြင်ပါ။ "
        + (last_error or "This Colab backend cannot currently reach Cloudflare Tunnel edge.")
    )

def _start_gradio_share_tunnel(demo):
    """Create a gradio.live tunnel for the already-running local server."""
    try:
        import gradio.networking as gr_networking
        import gradio.tunneling as gr_tunneling

        url = gr_networking.setup_tunnel(
            local_host="127.0.0.1",
            local_port=PUBLIC_PORT,
            share_token=demo.share_token,
            share_server_address=getattr(demo, "share_server_address", None),
            share_server_tls_certificate=getattr(demo, "share_server_tls_certificate", None),
        )
        tunnel_obj = gr_tunneling.CURRENT_TUNNELS[-1] if gr_tunneling.CURRENT_TUNNELS else None
        return url, tunnel_obj, ""
    except Exception as exc:
        return "", None, str(exc)


def _display_dual_links(cloudflare_url, gradio_url, cloudflare_error="", gradio_error=""):
    """Show Cloudflare + Gradio Live links. Either one may be unavailable."""
    try:
        from IPython.display import clear_output, display, HTML
        clear_output(wait=True)

        def card(title, url, accent, note):
            if url:
                status = '<span style="color:#34d399;font-weight:800;">● ONLINE</span>'
                link = (
                    f'<a href="{url}" target="_blank" '
                    f'style="font-size:17px;font-weight:900;word-break:break-all;color:{accent};">'
                    f'{url}</a>'
                )
            else:
                status = '<span style="color:#f87171;font-weight:800;">● UNAVAILABLE</span>'
                link = (
                    '<div style="color:#94a3b8;font-size:13px;">'
                    'ဒီ tunnel ကို အခုမဖန်တီးနိုင်သေးပါ။ အခြား link ကိုသုံးနိုင်ပါတယ်။'
                    '</div>'
                )
            return (
                '<div style="padding:16px 18px;border:1px solid rgba(148,163,184,.22);'
                'border-radius:16px;background:rgba(15,23,42,.84);margin:10px 0;">'
                '<div style="display:flex;justify-content:space-between;gap:12px;align-items:center;'
                'margin-bottom:8px;">'
                f'<div style="font-weight:900;color:#f8fafc;">{title}</div>{status}</div>'
                f'{link}'
                f'<div style="margin-top:8px;color:#94a3b8;font-size:12px;">{note}</div>'
                '</div>'
            )

        html = (
            '<div style="font-family:Arial,sans-serif;max-width:820px;padding:16px 0;">'
            '<div style="font-size:22px;font-weight:950;color:#111827;margin-bottom:4px;">'
            'YF RECAP LIVE LINKS</div>'
            '<div style="font-size:13px;color:#64748b;margin-bottom:12px;">'
            'တစ်ခုအဆင်မပြေရင် နောက်တစ်ခုကိုသုံးပါ။ Colab cell ကို Stop မလုပ်ပါနဲ့။</div>'
            + card('☁️ Cloudflare Link', cloudflare_url, '#2563eb', 'Primary link • trycloudflare.com')
            + card('🟣 Gradio Live Link', gradio_url, '#7c3aed', 'Backup link • gradio.live')
            + '</div>'
        )
        display(HTML(html))
    except Exception:
        print("\nYF RECAP LIVE LINKS")
        print("Cloudflare:", cloudflare_url or f"Unavailable ({cloudflare_error})")
        print("Gradio Live:", gradio_url or f"Unavailable ({gradio_error})")


def launch_yf_recap_dual_links():
    """Run one local YF Recap server with Cloudflare + Gradio Live tunnels."""
    import gradio.utils as gr_utils
    import gradio.networking as gr_networking

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
            status_update_rate=5.0,
            api_open=False,
            max_size=6,
            default_concurrency_limit=1,
        ).launch(
            server_name="127.0.0.1",
            server_port=PUBLIC_PORT,
            share=False,
            inline=False,
            inbrowser=False,
            debug=False,
            prevent_thread_lock=True,
            show_error=True,
            quiet=True,
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

    local_origin = f"http://127.0.0.1:{PUBLIC_PORT}"
    if not _wait_for_port("127.0.0.1", PUBLIC_PORT, timeout=60):
        raise RuntimeError(
            f"YF Recap local server did not start on port {PUBLIC_PORT}. "
            "Check the Python traceback above."
        )

    # A) Cloudflare tunnel
    cloudflare_process = None
    cloudflare_url = ""
    cloudflare_error = ""
    try:
        cloudflare_process, cloudflare_url, _cf_log_thread = start_cloudflare_tunnel(local_origin)
    except Exception as exc:
        cloudflare_error = str(exc)

    # B) Gradio share tunnel
    gradio_url, gradio_tunnel, gradio_error = _start_gradio_share_tunnel(demo)

    if not cloudflare_url and not gradio_url:
        try:
            demo.close()
        except Exception:
            pass
        raise RuntimeError(
            "Cloudflare နှင့် Gradio Live tunnel နှစ်ခုလုံး မဖန်တီးနိုင်ပါ။\n"
            f"Cloudflare: {cloudflare_error}\nGradio: {gradio_error}"
        )

    _display_dual_links(
        cloudflare_url,
        gradio_url,
        cloudflare_error=cloudflare_error,
        gradio_error=gradio_error,
    )

    last_state = None
    local_server_misses = 0
    try:
        while True:
            if not _wait_for_port("127.0.0.1", PUBLIC_PORT, timeout=2):
                # A long FFmpeg/VoxCPM generation can briefly delay a health
                # check.  Do not close a render that is still running because
                # of one missed port probe.
                local_server_misses += 1
                if local_server_misses < 6:
                    time.sleep(5)
                    continue
                raise RuntimeError(
                    "YF Recap local server stopped responding for too long. "
                    "The Colab runtime may have restarted or run out of RAM/VRAM."
                )
            local_server_misses = 0

            cf_alive = bool(
                cloudflare_url
                and cloudflare_process is not None
                and cloudflare_process.poll() is None
            )
            gr_alive = bool(
                gradio_url
                and gradio_tunnel is not None
                and getattr(gradio_tunnel, "proc", None) is not None
                and gradio_tunnel.proc.poll() is None
            )

            state = (cf_alive, gr_alive)
            if state != last_state:
                _display_dual_links(
                    cloudflare_url if cf_alive else "",
                    gradio_url if gr_alive else "",
                    cloudflare_error=(
                        "Tunnel disconnected" if cloudflare_url and not cf_alive else cloudflare_error
                    ),
                    gradio_error=(
                        "Tunnel disconnected" if gradio_url and not gr_alive else gradio_error
                    ),
                )
                last_state = state

            # Tunnel services can disconnect while a long video is rendering.
            # Keep the local Gradio server alive and retry the tunnels instead
            # of ending the Colab cell and killing the user's render.
            if not cf_alive:
                try:
                    cloudflare_process, cloudflare_url, _cf_log_thread = start_cloudflare_tunnel(local_origin)
                    cloudflare_error = ""
                    cf_alive = True
                except Exception as exc:
                    cloudflare_error = f"Reconnect pending: {exc}"

            if not gr_alive:
                try:
                    gradio_url, gradio_tunnel, gradio_error = _start_gradio_share_tunnel(demo)
                    gr_alive = bool(gradio_url and gradio_tunnel is not None)
                except Exception as exc:
                    gradio_error = f"Reconnect pending: {exc}"

            if not cf_alive and not gr_alive:
                _display_dual_links(
                    "", "",
                    cloudflare_error=cloudflare_error or "Reconnecting…",
                    gradio_error=gradio_error or "Reconnecting…",
                )
                time.sleep(8)
                continue

            time.sleep(12)

    except KeyboardInterrupt:
        pass
    finally:
        if cloudflare_process is not None and cloudflare_process.poll() is None:
            cloudflare_process.terminate()
        if gradio_tunnel is not None:
            try:
                gradio_tunnel.kill()
            except Exception:
                pass
        try:
            demo.close()
        except Exception:
            pass

    return cloudflare_url, gradio_url


if __name__ == "__main__":
    launch_yf_recap_dual_links()

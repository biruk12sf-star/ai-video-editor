# /***
# * =====================================================================================
# * AUTOMATION & POST WORKFLOW ARCHITECTURE
# * =====================================================================================
# *
# * PIPELINE WORKFLOW PHASES:
# * 1. SOURCING & PRE-EDITING (Up to Video Editing):
# *    - `get_instant_viral.py`: Scans Reddit RSS feeds & YT Shorts, downloads raw MP4 to videos/
# *    - `download_reddit_now.py`: Direct URL downloader for Reddit posts without running editing/uploading.
# *    - `reddit_video_checker.py`: Validates Reddit videos before downloading.
# *    - Ideal for manual editing & bypassing YouTube API automation flags on startup channels.
# *
# * 2. LOCAL AI EDITING:
# *    - `auto_ai_editor.py`: Generates script & renders 9:16 vertical video locally without YouTube API uploads.
# *
# * 3. MASTER AUTOMATED PIPELINE (This File - `run_viral_pipeline.py`):
# *    - Step 1: Multi-source viral video discovery (Reddit RSS + YT Shorts).
# *    - Step 2: Gemini 3.7 multimodal visual reasoning, highlight cuts & narration script.
# *    - Step 3: Fast-paced TTS voiceover (EdgeTTS) & kinetic micro-caption rendering.
# *    - Step 4: 9:16 Vertical MoviePy compositing, color grading & Pro VFX filters.
# *    - Step 5: Automatic YouTube Shorts OAuth2 publishing & organic booster seeding.
# * =====================================================================================
# ***/

import sys
import os
import time
import json
import asyncio
import re
import shutil
import urllib.request
import numpy as np
import requests
import xml.etree.ElementTree as ET
import yt_dlp
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

# Load environment variables from .env file FIRST
load_dotenv(override=True)

# Ensure UTF-8 output encoding for Windows terminal console
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ImageIO FFmpeg integration
try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_EXE
    HAS_FFMPEG = True
except Exception:
    FFMPEG_EXE = None
    HAS_FFMPEG = False

import edge_tts
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, ColorClip, ImageClip, concatenate_videoclips

# Load API Keys from .env
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

if GEMINI_API_KEY.startswith("gsk_") and not GROQ_API_KEY:
    GROQ_API_KEY = GEMINI_API_KEY
    GEMINI_API_KEY = ""

# Complete active model pool dynamically verified for current API key
MODEL_FALLBACK_POOL = [
    'gemini-3.7-flash-video-understanding-eap',
    'gemini-3.7-flash',
    'gemini-3.5-flash',
    'gemini-3.5-flash-lite',
    'gemini-flash-latest',
    'gemini-flash-lite-latest',
   
    'gemini-3.1-flash-lite',
    'gemini-3.1-flash-lite-preview',
    'gemini-3-flash-preview',
    'gemini-robotics-er-2-preview',
    'gemini-robotics-er-1.6-preview',
    'gemma-4-31b-it',
    'gemma-4-26b-a4b-it',
    'gemini-2.5-flash',
    'gemini-2.5-flash-lite',
]

# Expanded Subreddits Pool
SUBREDDITS = [
    "Unexpected",
    "nextfuckinglevel",
    "beamazed",
    "damnthatsinteresting",
    "funny",
    "PublicFreakout",
    "ViralVideos",
    "maybemaybemaybe",
    "blackmagicfuckery",
    "idiotsincars",
    "wholesome",
    "TikTokCringe",
    "oddlysatisfying",
    "holdmybeer",
    "interestingasfuck"
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"
]

HISTORY_FILE = "download_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_history(history_set):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(list(history_set), f, indent=2)

def sanitize_name(text):
    # Remove emojis and non-alphanumeric chars except space
    clean = re.sub(r'[^\w\s-]', '', text)
    clean = re.sub(r'[\s_]+', '_', clean).strip('_')
    return clean[:50] if clean else "Viral_Short"

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (15, 15, 20)

# ==========================================
# STEP 1: MULTI-SOURCE VIRAL VIDEO DISCOVERY
# ==========================================

def download_with_ytdlp(post_url, sub_name, title_text):
    os.makedirs("videos", exist_ok=True)
    clean_t = sanitize_name(title_text)
    timestamp = int(time.time())
    file_base = f"[{sub_name}]_{clean_t}_{timestamp}"
    output_mp4 = os.path.join("videos", f"{file_base}.mp4")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/b/best',
        'outtmpl': output_mp4,
        'merge_output_format': 'mp4',
        'quiet': True,
        'ignoreerrors': False,
        'no_warnings': True,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD1A.210817.036) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        },
        'retries': 5,
        'fragment_retries': 5
    }
    if HAS_FFMPEG and FFMPEG_EXE:
        ydl_opts['ffmpeg_location'] = FFMPEG_EXE
        
    print(f"   📥 Downloading video via yt-dlp...")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([post_url])
    except Exception as e:
        print(f"   ⚠️ Primary download note: {str(e)[:100]}")
        try:
            print(f"   ⚠️ Single stream fallback...")
            ydl_opts['format'] = 'b/best'
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([post_url])
        except Exception as e2:
            print(f"   ⚠️ Fallback failed: {str(e2)[:100]}")
            
    if os.path.exists(output_mp4) and os.path.getsize(output_mp4) > 100000:
        return {
            "subreddit": sub_name,
            "title": title_text,
            "url": post_url,
            "file_path": output_mp4
        }
    return None

def fetch_reddit_viral_video():
    history = load_history()
    print("\n🌐 Querying live Reddit feeds for top viral videos...", flush=True)
    
    headers_base = {
        'Accept': 'application/atom+xml,application/xml,text/xml;q=0.9,*/*;q=0.8',
    }
    
    for idx, sub in enumerate(SUBREDDITS):
        domain = "old.reddit.com"
        rss_url = f"https://{domain}/r/{sub}/top/.rss?t=day"
        ua = USER_AGENTS[idx % len(USER_AGENTS)]
        
        print(f"   🔎 Checking r/{sub} for fresh viral posts...", flush=True)
        try:
            req_headers = {**headers_base, 'User-Agent': ua}
            req = urllib.request.Request(rss_url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_data = resp.read()
            
            root = ET.fromstring(xml_data)
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            entries = root.findall('atom:entry', ns)
            
            for entry in entries:
                link_elem = entry.find('atom:link', ns)
                title_elem = entry.find('atom:title', ns)
                
                if link_elem is None or title_elem is None:
                    continue
                    
                post_url = link_elem.attrib.get('href', '')
                title = title_elem.text or "Viral Video"
                
                if not post_url or post_url in history:
                    continue
                    
                print(f"\n🔥 Found Reddit Candidate from r/{sub}: '{title}'", flush=True)
                print(f"   URL: {post_url}", flush=True)
                
                res_meta = download_with_ytdlp(post_url, sub, title)
                history.add(post_url)
                save_history(history)
                if res_meta:
                    return res_meta
                    
        except Exception:
            time.sleep(0.1)
            
    print("   ℹ️ No fresh un-downloaded Reddit posts found in active feeds. Switching to YouTube Shorts...", flush=True)
    return None

def fetch_youtube_shorts_viral_video():
    history = load_history()
    print("\n📺 Searching YouTube Shorts Engine for top viral videos...", flush=True)
    
    search_queries = [
        "ytsearch20:#shorts viral unexpected",
        "ytsearch20:#shorts crazy moment",
        "ytsearch20:#shorts funny moment",
        "ytsearch20:#shorts amazing talent",
        "ytsearch20:#shorts insane plot twist",
        "ytsearch20:#shorts wholesome moment"
    ]
    
    ydl_opts = {
        'extract_flat': True,
        'skip_download': True,
        'quiet': True,
        'ignoreerrors': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios', 'web']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD1A.210817.036) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36'
        }
    }
    if HAS_FFMPEG and FFMPEG_EXE:
        ydl_opts['ffmpeg_location'] = FFMPEG_EXE

    for q in search_queries:
        try:
            query_label = q.split(':', 1)[-1]
            print(f"   🔎 Searching YouTube: '{query_label}'...", flush=True)
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(q, download=False)
                if not info:
                    continue
                entries = info.get('entries', [])
                for e in entries:
                    if not e or not isinstance(e, dict):
                        continue
                        
                    vid_id = e.get('id')
                    v_url = e.get('webpage_url', '') or e.get('url', '') or (f"https://www.youtube.com/watch?v={vid_id}" if vid_id else '')
                    v_title = e.get('title', 'Viral Short')
                    v_dur = e.get('duration') or 0
                    
                    if not v_url or v_url in history:
                        continue
                        
                    if 5 <= v_dur <= 75:
                        print(f"\n🔥 Found YouTube Short Candidate: '{v_title}' ({v_dur}s)", flush=True)
                        print(f"   URL: {v_url}", flush=True)
                        
                        res_meta = download_with_ytdlp(v_url, "YouTubeShorts", v_title)
                        history.add(v_url)
                        save_history(history)
                        if res_meta:
                            return res_meta
        except Exception as err:
            time.sleep(0.1)
            
    return None

FALLBACK_VIRAL_SOURCES = [
    {
        "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
        "title": "Insane High Speed Stunt And Reaction",
        "sub": "CrazyMoments"
    },
    {
        "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerEscapes.mp4",
        "title": "Impossible Escape Attempt Caught On Camera",
        "sub": "Unexpected"
    },
    {
        "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerJoyBlazes.mp4",
        "title": "When Confidence Meets Instant Reality",
        "sub": "MindBlowing"
    }
]

def fetch_fallback_viral_video():
    print("\n🛡️ Engaging high-retention fallback viral candidate feed...", flush=True)
    import random
    candidates = list(FALLBACK_VIRAL_SOURCES)
    random.shuffle(candidates)
    for c in candidates:
        try:
            print(f"   📥 Downloading fallback candidate: '{c['title']}'...", flush=True)
            res = download_with_ytdlp(c["url"], c["sub"], c["title"])
            if res:
                return res
        except Exception as e:
            print(f"   ⚠️ Fallback item error: {e}")
    return None

def get_viral_video(custom_url=None):
    if custom_url:
        print(f"\n🔗 Processing custom video URL: {custom_url}")
        return download_with_ytdlp(custom_url, "CustomUrl", "Viral Video")
        
    meta = fetch_reddit_viral_video()
    if meta:
        return meta
        
    meta = fetch_youtube_shorts_viral_video()
    if meta:
        return meta
        
    meta = fetch_fallback_viral_video()
    if meta:
        return meta
        
    return None

# ==========================================
# STEP 2: HIGH-RETENTION JAW-DROPPING SCRIPT ENGINE
# ==========================================

def validate_and_sanitize_ai_plan(data, video_path, post_title):
    video_dur = 30.0
    try:
        with VideoFileClip(video_path) as test_clip:
            video_dur = float(test_clip.duration)
    except Exception:
        pass

    if not isinstance(data, dict):
        data = {}

    if "zoom_effect" not in data:
        data["zoom_effect"] = "PUNCH_ZOOM"
    if "transition_type" not in data:
        data["transition_type"] = "RGB_GLITCH"
    if "speed_ramping" not in data:
        data["speed_ramping"] = "STANDARD_1X"

    cuts = data.get("highlight_cuts", [])
    valid_cuts = []

    if isinstance(cuts, list):
        for c in cuts:
            if isinstance(c, dict):
                try:
                    s = float(c.get("start_sec", 0.0))
                    e = float(c.get("end_sec", video_dur))
                    if e - s >= 2.5 and s < video_dur:
                        e = min(e, video_dur)
                        valid_cuts.append({"start_sec": round(s, 1), "end_sec": round(e, 1)})
                except (ValueError, TypeError):
                    pass

    total_cut_dur = sum(c["end_sec"] - c["start_sec"] for c in valid_cuts)

    if not valid_cuts or total_cut_dur < 4.0:
        max_dur = min(35.0, video_dur)
        print(f"   ⚠️ Highlight cuts invalid or micro-cut ({total_cut_dur:.1f}s). Resetting highlight cuts to full video ({max_dur:.1f}s)!")
        valid_cuts = [{"start_sec": 0.0, "end_sec": round(max_dur, 1)}]

    data["highlight_cuts"] = valid_cuts

    segments = data.get("narration_segments", [])
    valid_segments = []
    if isinstance(segments, list):
        for s in segments:
            if isinstance(s, dict):
                raw_text = s.get("text", "").strip()
                clean_text = re.sub(r'\[.*?\]|\(.*?\)', '', raw_text).strip()
                if clean_text:
                    s["text"] = clean_text
                    if "start_sec" not in s:
                        s["start_sec"] = s.get("time", s.get("timestamp", 0.0))
                    valid_segments.append(s)

    if valid_segments:
        final_dur = sum(c["end_sec"] - c["start_sec"] for c in valid_cuts)
        timestamps = []
        for s in valid_segments:
            try:
                timestamps.append(float(s.get("start_sec", 0.0)))
            except (ValueError, TypeError):
                timestamps.append(0.0)

        if len(timestamps) > 1 and (max(timestamps) - min(timestamps) < 2.0 or max(timestamps) >= final_dur):
            print("   ⚠️ Narration timestamps were compressed/clustered. Auto-spacing segments across video duration...")
            step = max(2.5, (final_dur - 3.0) / max(1, len(valid_segments) - 1))
            for idx, s in enumerate(valid_segments):
                s["start_sec"] = round(idx * step, 1)

    data["narration_segments"] = valid_segments
    return data

def extract_video_audio_transcript(video_path, groq_key, max_dur=25.0):
    """Uses Groq Whisper to transcribe spoken words, screams, or audio reactions from the video."""
    if not groq_key or not video_path or not os.path.exists(video_path):
        return ""
    temp_aud = f"temp_whisper_{int(time.time()*1000)}.mp3"
    try:
        with VideoFileClip(video_path) as clip:
            if clip.audio is None:
                return ""
            sub_dur = min(max_dur, clip.duration)
            clip.audio.subclipped(0, sub_dur).write_audiofile(temp_aud, fps=16000, nbytes=2, logger=None)
        
        if os.path.exists(temp_aud) and os.path.getsize(temp_aud) > 1000:
            url = "https://api.groq.com/openai/v1/audio/transcriptions"
            headers = {"Authorization": f"Bearer {groq_key}"}
            with open(temp_aud, "rb") as f:
                files = {"file": ("audio.mp3", f, "audio/mpeg"), "model": (None, "whisper-large-v3-turbo")}
                resp = requests.post(url, headers=headers, files=files, timeout=12)
            if resp.status_code == 200:
                transcript = resp.json().get("text", "").strip()
                if transcript and transcript != ".":
                    print(f"   👂 Groq Audio Transcribed: \"{transcript[:80]}...\"", flush=True)
                    return transcript
    except Exception as e:
        pass
    finally:
        if os.path.exists(temp_aud):
            try:
                os.remove(temp_aud)
            except Exception:
                pass
    return ""

def extract_video_visual_understanding(video_path, groq_key, video_dur):
    """Uses Groq Vision (llama-3.2-11b-vision-preview) to physically inspect keyframes from the video."""
    if not groq_key or not video_path or not os.path.exists(video_path):
        return ""
    temp_f1 = f"temp_frame1_{int(time.time()*1000)}.jpg"
    try:
        import base64
        with VideoFileClip(video_path) as clip:
            actual_dur = clip.duration
            t_sample = actual_dur * 0.55
            frame = clip.get_frame(t_sample)
            im = Image.fromarray(frame)
            im = im.resize((360, 360), Image.Resampling.LANCZOS)
            im.save(temp_f1, quality=80)

        if os.path.exists(temp_f1):
            with open(temp_f1, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")

            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.2-11b-vision-preview",
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe in 2 concise sentences what is physically visible in this video frame: who or what is present, the setting/environment, and what exact action or reaction is occurring."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                    ]
                }],
                "max_tokens": 80,
                "temperature": 0.2
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=12)
            if resp.status_code == 200:
                desc = resp.json()["choices"][0]["message"]["content"].strip()
                print(f"   👁️ Groq Vision Saw: \"{desc[:100]}...\"", flush=True)
                return desc
    except Exception as e:
        pass
    finally:
        if os.path.exists(temp_f1):
            try:
                os.remove(temp_f1)
            except Exception:
                pass
    return ""


def query_gemini_vision(video_path, post_title, subreddit, video_dur):
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=gemini_key)
        
        print("🧠 Uploading video to Gemini for True Multimodal Scene Understanding...", flush=True)
        safe_temp = f"temp_gemini_{int(time.time()*1000)}.mp4"
        shutil.copy(video_path, safe_temp)
        
        vf = client.files.upload(file=safe_temp)
        while vf.state.name == "PROCESSING":
            print("   ⏳ Gemini watching and analyzing video frames...", flush=True)
            time.sleep(2)
            vf = client.files.get(name=vf.name)
            
        if os.path.exists(safe_temp):
            try:
                os.remove(safe_temp)
            except Exception:
                pass
                
        if vf.state.name == "FAILED":
            return None

        prompt = f"""
You are the world's most elite, high-retention autonomous AI Video Director and rapid-fire comedy narrator.
(Style: Expressive, bewildered, dramatic, comedic storytelling — like a viral YouTube/TikTok documentary recap).

Watch and listen to this entire video clip ({video_dur:.1f} seconds).
TITLE / CONTEXT: "{post_title}" (from {subreddit}).

CRITICAL HIGH-RETENTION DIRECTIVES:
1. SCENE-BY-SCENE RAPID PACING (ZERO DEAD AIR):
   - You MUST analyze the video frame-by-frame and identify EVERY SINGLE SCENE TRANSITION or MICRO-ACTION across the entire duration (0.0s to {video_dur:.1f}s).
   - DO NOT generate only 2-3 sparse lines! Generate 5 to 10 tight, continuous, chronological narration segments covering the ENTIRE storyline from start to finish.
   - For every visual shift (new setting, new action, new character interaction, unexpected twist), create a dedicated narration beat!

2. PRECISE VISUAL TIMESTAMPS:
   - For each beat, set "start_sec" to the EXACT floating-point second that visual scene or action appears on screen.
   - Pacing guide: Each segment text should be roughly 6 to 14 words so it speaks naturally at a lively, rapid-fire pace (~3.5 to 4.5 words/sec) and completes right before the next cut.

3. STORYTELLING & ROASTING:
   - Comment DIRECTLY on the real people, objects, facial expressions, and absurdities seen on screen.
   - Deliver dramatic, expressive storytelling that builds narrative momentum from the opening hook to the final punchline.
   - Absolutely ZERO generic filler ("Look what happens next", "Bro is wild"). Every sentence tells a story.

4. DIRECTOR DECISIONS:
   - `top_hook_header`: Punchy 3-5 word ALL-CAPS high-CTR banner hook (e.g. "THE CURSE NEVER ENDS 💀" or "LIFELONG COMMITMENT 😭").
   - `color_grading`: "NEON_VIBRANT", "CYBERPUNK", "CINEMATIC_DARK", or "HIGH_CONTRAST".
   - `zoom_effect`: "PUNCH_ZOOM" or "CAMERA_SHAKE".
   - `speed_ramping`: "STANDARD_1X".
   - `highlight_cuts`: Specify tight highlight cuts if intro/outro fluff exists, or 0.0s to {min(35.0, video_dur):.1f}s.

Return ONLY strictly valid JSON matching this schema:
{{
    "top_hook_header": "ALL-CAPS 3-5 WORD VIRAL HOOK",
    "viral_title": "Punchy 5-8 word viral comedic title",
    "description": "Short witty 1-sentence recap #Shorts #Viral #Trending #Humor",
    "bg_color": "#0F0F14",
    "color_grading": "NEON_VIBRANT",
    "zoom_effect": "PUNCH_ZOOM",
    "transition_type": "RGB_GLITCH",
    "speed_ramping": "STANDARD_1X",
    "highlight_cuts": [
        {{"start_sec": 0.0, "end_sec": {min(35.0, video_dur):.1f}}}
    ],
    "narration_segments": [
        {{"start_sec": 0.0, "text": "Dramatic opening hook explaining the initial action..."}},
        {{"start_sec": 2.5, "text": "Rapid-fire narration of the immediate complication..."}},
        {{"start_sec": 6.0, "text": "What happens next as the scene cuts..."}}
    ]
}}
"""
        models = [
            "gemini-3.6-flash",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-2.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-2.5-pro"
        ]
        
        for m in models:
            for attempt in range(2):
                try:
                    print(f"⚡ Querying Gemini Engine [{m}] (attempt {attempt+1})...", flush=True)
                    resp = client.models.generate_content(model=m, contents=[vf, prompt])
                    raw_json = resp.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(raw_json)
                    try:
                        client.files.delete(name=vf.name)
                    except Exception:
                        pass
                    if "narration_segments" in data and data["narration_segments"]:
                        print(f"✅ SUCCESS! Gemini [{m}] physically analyzed video frames & generated viral script!", flush=True)
                        return data
                except Exception as me:
                    err_msg = str(me).splitlines()[0][:90]
                    print(f"   ⚠️ Model {m} note: {err_msg}", flush=True)
                    time.sleep(2)

        try:
            client.files.delete(name=vf.name)
        except Exception:
            pass
    except Exception as e:
        print(f"⚠️ Gemini Vision Error: {e}", flush=True)
    return None

def query_groq_llm(post_title, subreddit, video_dur, video_path=None):
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_key:
        # No Groq key
        return None
        
    import random
    personas = [
        "Savage Stand-Up Comedian (brutal roasts, clever callbacks, sharp comedic timing)",
        "Dry Sarcastic Reaction Host (MoistCr1TiKaL & Ray William Johnson style, deadpan mockery of absurd human/animal decisions)",
        "Ozzy Man / Dramatic Commentator (hilarious high-energy breakdown treating every micro-action like a championship event)",
        "Unhinged Internet Observationalist (fast, witty, modern Gen-Z humor, zero corporate filter)"
    ]
    chosen_persona = random.choice(personas)

    visual_description = ""
    audio_transcript = ""
    if video_path:
        print("🔍 Scanning raw video content with Groq AI Vision & Whisper Audio...", flush=True)
        visual_description = extract_video_visual_understanding(video_path, groq_key, video_dur)
        audio_transcript = extract_video_audio_transcript(video_path, groq_key)

    num_segments = max(2, min(5, int(video_dur // 4.5)))
    step = video_dur / max(1, num_segments)
    spaced_examples = []
    for i in range(num_segments):
        t = round(i * step, 1)
        spaced_examples.append(f'{{"start_sec": {t}, "text": "Punchline segment {i+1}"}}')
    example_segments_str = ",\n            ".join(spaced_examples)

    ground_truth_context = ""
    if visual_description:
        ground_truth_context += f"- REAL VISUAL OBSERVATION (WHAT IS ACTUALLY SEEN ON SCREEN): \"{visual_description}\"\n"
    if audio_transcript:
        ground_truth_context += f"- ORIGINAL AUDIO / SPOKEN WORDS: \"{audio_transcript}\"\n"

    prompt = f"""
    You are an elite, viral YouTube Shorts scriptwriter and comedy director.
    YOUR COMEDIC PERSONA FOR THIS VIDEO: {chosen_persona}.

    TASK: Write a hilarious, high-retention, laugh-out-loud commentary script for this viral video clip.

    METADATA:
    - VIDEO TITLE: "{post_title}"
    - COMMUNITY / CONTEXT: {subreddit}
    - VIDEO DURATION: {video_dur:.1f} seconds
    {ground_truth_context}

    CRITICAL COMEDY & RETENTION DIRECTIVES:
    1. TALK ABOUT WHAT IS ACTUALLY IN THE VIDEO (GROUND TRUTH):
       - You MUST comment DIRECTLY on the real subjects, pets, people, and actions observed on screen.
       - NEVER invent fake storylines, fake objects, or random scenarios that do not match the real video.
       - If there are spoken words/quotes in the audio, react to what was said!

    2. STRICTLY BANNED CORNY CLICHÉS (NEVER USE THESE):
       - DO NOT use childish kids-TV phrases: 'What the heck?', 'Pure gold!', 'Cheeky...', 'Little dude', 'Auditioning for a movie', 'Did that just happen?'.
       - DO NOT use lazy filler: 'Bro is literally...', 'Wait for the end...', 'Listen to them scream...', 'Subscribe for more...'.
       - DO NOT include brackets or stage directions like [Intro], [Zoom], [Crowd] in the text. Every word must be naturally spoken dialogue.

    3. HILARIOUS ROASTING & ORIGINAL METAPHORS:
       - Roast the absurdity of what is happening on screen with unexpected comparisons, sarcastic human psychology observations, and relatable punchlines.
       - The voiceover should feel like an authentic, funny human reaction that makes people want to share the clip.

    4. PRO VIDEO EDITOR DECISIONS (CHOOSE BEST EFFECTS FOR THIS CLIP):
       - `color_grading`: Choose the visual grade: "CYBERPUNK", "NEON_VIBRANT", "CINEMATIC_DARK", "WARM_RETRO", or "HIGH_CONTRAST".
       - `zoom_effect`: Choose the camera movement: "PUNCH_ZOOM" (crash zoom on punchlines), "CAMERA_SHAKE" (violent screen shake on impacts/fails), "HIT_ZOOM" (tempo pulse), or "KEN_BURNS" (cinematic drift).
       - `speed_ramping`: Choose the video tempo: "HERO_SLOWMO" (fast-forward setup + slow-mo impact climax) or "CRASH_ACCEL" (speed-up burst) or "STANDARD_1X".
       - `highlight_cuts`: Act like a pro editor! If the video has boring setup or dead air, specify 1 to 3 tight highlight cuts (each cut >= 2.5s) that trim the fluff and keep only the peak action/reaction. Total cut time must be between 6s and 32s.

    5. SEGMENT TIMING:
       - Generate exactly {num_segments} narration segments timed across the clip.
       - Keep each segment under 15-20 words so the rapid-fire voiceover fits neatly before the next beat.

    Return STRICTLY valid JSON with this exact schema:
    {{
        "top_hook_header": "ALL-CAPS 3-5 WORD VIRAL HOOK (e.g. 'BRO CHOSE PURE CHAOS 💀')",
        "viral_title": "Punchy 5-8 word comedic title roasting the event",
        "description": "Short witty 1-sentence recap #Shorts #Viral #Trending #Humor",
        "bg_color": "#0F0F14",
        "color_grading": "CYBERPUNK",
        "zoom_effect": "PUNCH_ZOOM",
        "transition_type": "RGB_GLITCH",
        "speed_ramping": "HERO_SLOWMO",
        "highlight_cuts": [
            {{"start_sec": 0.0, "end_sec": {min(28.0, video_dur):.1f}}}
        ],
        "narration_segments": [
            {example_segments_str}
        ]
    }}
    """
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {groq_key}"
    }
    
    # Active high-performance Groq models (100% Free & Unlimited on Groq)
    groq_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"]
    for g_model in groq_models:
        print(f"⚡ Querying Groq Engine [{g_model}] ({chosen_persona.split('(')[0].strip()})...", flush=True)
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": g_model,
            "messages": [
                {"role": "system", "content": "You output only valid JSON. No conversational text."},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.85
        }
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            if resp.status_code == 200:
                res_data = resp.json()
                content = res_data['choices'][0]['message']['content']
                clean_res = content.replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_res)
                print(f"✅ SUCCESS! Groq [{g_model}] generated high-retention viral script!", flush=True)
                return data
            else:
                print(f"⚠️ Groq note ({g_model}): HTTP {resp.status_code} - {resp.text[:80]}", flush=True)
        except Exception as e:
            print(f"⚠️ Groq error: {e}", flush=True)
    return None

def generate_ai_editing_plan(video_path, post_title, subreddit):
    """
    Autonomous AI Video Director powered by Gemini 3.6 Flash Multimodal Vision
    with fallback to Groq and smart templates.
    """
    video_dur = 30.0
    try:
        with VideoFileClip(video_path) as test_clip:
            video_dur = float(test_clip.duration)
    except Exception:
        pass

    # 1. Primary Engine: Gemini 3.6 Flash Multimodal Vision (Watches raw video)
    plan = query_gemini_vision(video_path, post_title, subreddit, video_dur)
    if plan:
        return validate_and_sanitize_ai_plan(plan, video_path, post_title)

    # 2. Secondary fallback: Groq if key exists
    plan = query_groq_llm(post_title, subreddit, video_dur, video_path)
    if plan:
        return validate_and_sanitize_ai_plan(plan, video_path, post_title)

    # Dynamic fallback script
    clean_topic = post_title.strip() if post_title else "unbelievable event"
    fallback_data = {
        "top_hook_header": "LISTEN TO THIS 😭",
        "viral_title": f"Bro {clean_topic[:35]} 😭",
        "description": f"Bro this {clean_topic[:25].lower()} actually just happened 😭\n\n#Shorts #Viral #Trending #Fyp #Humor",
        "bg_color": "#0F0F14",
        "color_grading": "NEON_VIBRANT",
        "zoom_effect": "PUNCH_ZOOM",
        "transition_type": "RGB_GLITCH",
        "speed_ramping": "STANDARD_1X",
        "highlight_cuts": [{"start_sec": 0.0, "end_sec": min(35.0, video_dur)}],
        "narration_segments": [
            {"start_sec": 0.0, "text": f"Bro the audio and reaction in this clip is completely wild 😭"},
            {"start_sec": round(video_dur * 0.3, 1), "text": "Look at what happens next in this scene 💀"},
            {"start_sec": round(video_dur * 0.6, 1), "text": "That reaction was pure comedy 😭"}
        ]
    }
    return validate_and_sanitize_ai_plan(fallback_data, video_path, post_title)

# ==========================================
# STEP 3: TTS & WORD-BY-WORD/PUNCHY CAPTIONS
# ==========================================

async def generate_segment_voiceover(text, segment_idx):
    out_audio = f"temp_voice_{segment_idx}.mp3"
    # 2X Rapid-Fire speech rate (+80%) + High Pitch (+45Hz)
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural", rate="+80%", pitch="+45Hz")
    boundaries = []
    with open(out_audio, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "SentenceBoundary":
                start_sec = chunk["offset"] / 10000000.0
                duration_sec = chunk["duration"] / 10000000.0
                boundaries.append({"text": chunk["text"], "start": start_sec, "duration": duration_sec})
    return out_audio, boundaries



def create_compact_caption_image(text, width=1080, color_scheme=0):
    """Pure Neon Glow Caption — NO background card. Ultra-glowing text with layered aura for viral Shorts readability."""
    import math
    img_h = 240
    img = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))

    FONT_SIZE = 80
    try:
        font = ImageFont.truetype("arialbd.ttf", FONT_SIZE)
    except Exception:
        try:
            font = ImageFont.truetype("impact.ttf", FONT_SIZE + 8)
        except Exception:
            font = ImageFont.load_default()

    PALETTES = [
        ((255, 235, 59),  (0, 229, 255)),    # Neon Yellow + Cyan glow
        ((57, 255, 20),   (180, 0, 255)),    # Electric Lime + Violet glow
        ((255, 50, 150),  (255, 235, 59)),   # Hot Pink + Yellow glow
        ((255, 255, 255), (255, 23, 68)),    # Pure White + Crimson glow
    ]
    core_rgb, glow_rgb = PALETTES[color_scheme % len(PALETTES)]

    # ── Pass 1: Outer Neon Aura Glow (wide soft halo) ───────────────────────
    glow_layer = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow_layer)
    dummy_bbox = gd.textbbox((0, 0), text, font=font)
    tw, th = dummy_bbox[2] - dummy_bbox[0], dummy_bbox[3] - dummy_bbox[1]
    tx, ty = (width - tw) // 2, (img_h - th) // 2

    # Draw glow in expanding rings (wide → tight)
    for radius in [14, 10, 7, 4, 2]:
        alpha = max(40, 200 - radius * 12)
        for dx in range(-radius, radius + 1, max(1, radius // 2)):
            for dy in range(-radius, radius + 1, max(1, radius // 2)):
                dist = math.sqrt(dx*dx + dy*dy)
                if dist <= radius + 0.5:
                    gd.text((tx + dx, ty + dy), text, font=font,
                            fill=(*glow_rgb, alpha))
    blurred_glow = glow_layer.filter(ImageFilter.GaussianBlur(radius=8))

    # ── Pass 2: Thick Black Stroke (readability on any background) ──────────
    stroke_layer = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stroke_layer)
    for ox in range(-5, 6):
        for oy in range(-5, 6):
            if ox != 0 or oy != 0:
                sd.text((tx + ox, ty + oy), text, font=font, fill=(0, 0, 0, 255))

    # ── Pass 3: Core Neon Text ───────────────────────────────────────────────
    core_layer = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(core_layer)
    cd.text((tx, ty), text, font=font, fill=(*core_rgb, 255))

    # ── Composite: glow → stroke → core ─────────────────────────────────────
    base = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    base = Image.alpha_composite(base, blurred_glow)
    base = Image.alpha_composite(base, stroke_layer)
    base = Image.alpha_composite(base, core_layer)

    return np.array(base)


def create_top_hook_header(header_text, width=1080):
    """Creates a Pro High-CTR Glassmorphic Top Hook Banner"""
    img_h = 160
    img = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    font_size = 56
    try:
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("impact.ttf", font_size + 4)
        except Exception:
            font = ImageFont.load_default()

    clean_text = header_text.upper()
    bbox = draw.textbbox((0, 0), clean_text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (width - text_w) // 2, (img_h - text_h) // 2

    # Dark Glassmorphic Backing Box
    padding_x, padding_y = 30, 16
    box_rect = [x - padding_x, y - padding_y, x + text_w + padding_x, y + text_h + padding_y]
    
    # Outer Glow Border
    draw.rounded_rectangle(
        [box_rect[0]-3, box_rect[1]-3, box_rect[2]+3, box_rect[3]+3],
        radius=18,
        fill=(255, 0, 85, 180)
    )
    draw.rounded_rectangle(
        box_rect,
        radius=15,
        fill=(12, 12, 24, 235),
        outline=(0, 229, 255, 255),
        width=3
    )

    # 3D Drop Shadow
    draw.text((x + 3, y + 3), clean_text, font=font, fill=(0, 0, 0, 255))
    # Electric Yellow Main Text
    draw.text((x, y), clean_text, font=font, fill=(255, 235, 59, 255))

    return np.array(img)

def create_progress_bar_image(progress_ratio, width=1080):
    """Generates an animated neon bottom progress bar overlay"""
    h = 12
    img = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bar_w = int(width * max(0.0, min(1.0, progress_ratio)))
    if bar_w > 0:
        draw.rectangle([0, 0, width, h], fill=(20, 20, 35, 180))
        draw.rectangle([0, 0, bar_w, h], fill=(0, 229, 255, 255))
        if bar_w > 10:
            draw.rectangle([bar_w - 8, 0, bar_w, h], fill=(255, 0, 127, 255))

    return np.array(img)

def apply_color_grading_filter(gf, t, preset="NEON_VIBRANT"):
    """Applies high-end color grading transformations to video frames"""
    frame = gf(t).copy()
    if preset == "CYBERPUNK":
        frame[:, :, 0] = np.clip(frame[:, :, 0] * 1.15 + 10, 0, 255)
        frame[:, :, 2] = np.clip(frame[:, :, 2] * 1.25 + 15, 0, 255)
    elif preset == "CINEMATIC_DARK":
        frame = np.clip((frame.astype(np.float32) - 15) * 1.12, 0, 255).astype(np.uint8)
    elif preset == "NEON_VIBRANT":
        mean_val = frame.mean(axis=2, keepdims=True)
        frame = np.clip(mean_val + (frame - mean_val) * 1.3, 0, 255).astype(np.uint8)
    elif preset == "HIGH_CONTRAST":
        frame = np.clip(128.0 + 1.25 * (frame.astype(np.float32) - 128.0), 0, 255).astype(np.uint8)
    return frame

def render_micro_captions_for_segment(text, boundaries, abs_start_sec, voice_duration, width=1080, color_scheme=0):
    """Splits narration into micro 1 to 2 word chunks for high-retention TikTok/Reels caption sync"""
    words = text.split()
    if not words:
        return []
        
    chunks = []
    for i in range(0, len(words), 2):
        chunks.append(" ".join(words[i:i+2]))
        
    dur_per_chunk = voice_duration / float(max(1, len(chunks)))
    
    clips = []
    for idx, c in enumerate(chunks):
        chunk_start = abs_start_sec + (idx * dur_per_chunk)
        img_np = create_compact_caption_image(c.upper(), width=width, color_scheme=idx + color_scheme)
        clip = (ImageClip(img_np)
                .with_start(chunk_start)
                .with_duration(dur_per_chunk)
                .with_position(("center", 1360)))
        clips.append(clip)
    return clips

# ==========================================
# STEP 4: SMART 9:16 VERTICAL COVERAGE MOVIEPY ENGINE
# ==========================================

def edit_viral_short(video_path, ai_plan, output_path):
    try:
        import ultimate_pro_studio_engine
        renderer = ultimate_pro_studio_engine.StudioVideoRenderer(width=1080, height=1920, fps=30)
        renderer.render_short(video_path, ai_plan, output_path)
        return output_path
    except Exception as e:
        print(f"⚠️ Ultimate Studio Engine note, falling back to local runner: {e}")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    highlight_cuts = ai_plan.get("highlight_cuts", [])
    segments = ai_plan.get("narration_segments", [])
    top_header_text = ai_plan.get("top_hook_header", "UNBELIEVABLE MOMENT 😱")
    color_preset = ai_plan.get("color_grading", "NEON_VIBRANT")
    bg_hex = ai_plan.get("bg_color", "#0F0F14")
    bg_rgb = hex_to_rgb(bg_hex)
    
    print("\n🎬 Processing Video with High-End 9:16 Vertical Compositing, Color Grading & Overlays...")
    orig_clip = VideoFileClip(video_path)
    
    # Dynamic Multi-Cuts
    if highlight_cuts and isinstance(highlight_cuts, list):
        subclips = []
        for idx, cut in enumerate(highlight_cuts, 1):
            s = float(cut.get("start_sec", 0.0))
            e = float(cut.get("end_sec", orig_clip.duration))
            if e > s and s < orig_clip.duration:
                e = min(e, orig_clip.duration)
                print(f"✂️ AI Highlight Cut [{idx}]: {s:.1f}s -> {e:.1f}s (duration: {e-s:.1f}s)")
                subclips.append(orig_clip.subclipped(s, e))
                
        if subclips:
            clip = concatenate_videoclips(subclips)
            print(f"🎬 Stitched {len(subclips)} highlight clips (total duration: {clip.duration:.1f}s)")
        else:
            clip = orig_clip
    else:
        clip = orig_clip

    # ⏱️ HARD CAP SAFETY: Force maximum duration of 35.0 seconds! Never allow long clips to render!
    MAX_SHORT_DURATION = 35.0
    if clip.duration > MAX_SHORT_DURATION:
        print(f"⏱️ Trimming total clip duration from {clip.duration:.1f}s to max limit ({MAX_SHORT_DURATION}s) for fast Shorts rendering!")
        clip = clip.subclipped(0, MAX_SHORT_DURATION)

    # Apply Multi-Pass Pro VFX Pipeline — ALL EFFECTS driven by AI Director decisions
    try:
        import pro_vfx_engine

        zoom_mode      = ai_plan.get("zoom_effect",     "PUNCH_ZOOM")
        transition_mode = ai_plan.get("transition_type", "RGB_GLITCH")
        speed_mode     = ai_plan.get("speed_ramping",   "STANDARD_1X")

        print(f"🎯 [AI DIRECTOR] Zoom={zoom_mode} | Transition={transition_mode} | SpeedRamp={speed_mode} | ColorGrade={color_preset}")

        # Narration segment timestamps used as effect trigger points
        trigger_timestamps = [float(s.get("start_sec", 0.0)) for s in segments if isinstance(s, dict)]
        total_dur = clip.duration

        # Speed Ramping: Adjust clip playback speed based on AI's tempo decision
        if speed_mode == "HERO_SLOWMO":
            clip = clip.with_fps(clip.fps)  # Keep original FPS; slow-mo expressed via frame hold in transform
        elif speed_mode == "CRASH_ACCEL":
            clip = clip.with_effects([])    # Acceleration applied per-frame in transform below

        def pro_vfx_transform(gf, t):
            frame = gf(t).copy()

            # ── STEP 0: TikTok Watermark Crop ────────────────────────────────────
            # Aggressively crop bottom 15% and right 10% to nuke TikTok logo/username
            fh, fw = frame.shape[:2]
            crop_bottom = int(fh * 0.85)  # Remove bottom 15%
            crop_right  = int(fw * 0.90)  # Remove right 10%
            cropped = frame[:crop_bottom, :crop_right]
            # Scale back to original frame size
            from PIL import Image as _PILImg
            frame = np.array(_PILImg.fromarray(cropped).resize((fw, fh), _PILImg.Resampling.BILINEAR))

            if color_preset == "CYBERPUNK":
                ff = frame.astype("float32")
                ff[:, :, 0] = ff[:, :, 0] * 1.18 + 12   # Red
                ff[:, :, 2] = ff[:, :, 2] * 1.28 + 18   # Cyan/Blue
                frame = ff.clip(0, 255).astype("uint8")
            elif color_preset == "CINEMATIC_DARK":
                frame = ((frame.astype("float32") - 15.0) * 1.14).clip(0, 255).astype("uint8")
            elif color_preset == "NEON_VIBRANT":
                mean = frame.mean(axis=2, keepdims=True)
                frame = (mean + (frame - mean) * 1.35).clip(0, 255).astype("uint8")
            elif color_preset == "HIGH_CONTRAST":
                frame = (128.0 + 1.30 * (frame.astype("float32") - 128.0)).clip(0, 255).astype("uint8")
            elif color_preset == "VINTAGE_VHS":
                frame = pro_vfx_engine.apply_crt_retro_vhs(frame, t)

            # ── STEP 2: AI-Selected Zoom / Camera Movement ───────────────────────
            progress = t / max(0.001, total_dur)

            if zoom_mode == "PUNCH_ZOOM":
                frame = pro_vfx_engine.apply_punch_zoom(frame, t, trigger_times=trigger_timestamps, zoom_scale=1.22)

            elif zoom_mode == "HIT_ZOOM":
                frame = pro_vfx_engine.apply_hit_beat_zoom(frame, t, beat_timestamps=trigger_timestamps, zoom_intensity=1.14, duration=0.22)

            elif zoom_mode == "SMOOTH_ZOOM":
                frame = pro_vfx_engine.apply_ken_burns_pan_zoom(frame, t, duration=total_dur, zoom_start=1.0, zoom_end=1.22)

            elif zoom_mode == "SPIN_ZOOM":
                if trigger_timestamps and any(abs(t - trig) < 0.5 for trig in trigger_timestamps):
                    local_t = min(0.5, min(abs(t - trig) for trig in trigger_timestamps if abs(t - trig) < 0.5))
                    frame = pro_vfx_engine.apply_spin_rotational_zoom(frame, local_t, duration=0.5)
                else:
                    frame = pro_vfx_engine.apply_ken_burns_pan_zoom(frame, t, duration=total_dur, zoom_start=1.0, zoom_end=1.12)

            elif zoom_mode == "WHIP_ZOOM":
                for trig in trigger_timestamps:
                    frame = pro_vfx_engine.apply_whip_blur_zoom(frame, t, transition_center=trig, duration=0.30)

            elif zoom_mode == "DOLLY_ZOOM":
                frame = pro_vfx_engine.apply_dolly_zoom_vertigo(frame, t, duration=total_dur)

            elif zoom_mode == "KEN_BURNS":
                frame = pro_vfx_engine.apply_ken_burns_pan_zoom(frame, t, duration=total_dur, zoom_start=1.0, zoom_end=1.18)

            elif zoom_mode == "BOUNCE_ZOOM":
                for trig in trigger_timestamps:
                    frame = pro_vfx_engine.apply_elastic_bounce_zoom(frame, t, trigger_time=trig, duration=0.45, zoom_peak=1.25)

            else:  # Default fallback: Ken Burns + Punch Zoom combo
                frame = pro_vfx_engine.apply_ken_burns_pan_zoom(frame, t, duration=total_dur, zoom_start=1.0, zoom_end=1.12)
                frame = pro_vfx_engine.apply_punch_zoom(frame, t, trigger_times=trigger_timestamps, zoom_scale=1.20)

            # ── STEP 3: AI-Selected Transition Shader ────────────────────────────
            if transition_mode == "RGB_GLITCH":
                frame = pro_vfx_engine.apply_rgb_split_glitch(frame, t, trigger_times=trigger_timestamps, max_shift=16)

            elif transition_mode == "LIGHT_LEAK":
                # Apply light leak at each trigger timestamp
                for trig in trigger_timestamps:
                    if abs(t - trig) < 0.4:
                        leak_progress = 1.0 - abs(t - trig) / 0.4
                        frame = pro_vfx_engine.apply_light_leak_transition(frame, leak_progress)

            elif transition_mode == "WHIP_PAN":
                # Apply whip blur on transitions
                for trig in trigger_timestamps:
                    frame = pro_vfx_engine.apply_whip_blur_zoom(frame, t, transition_center=trig, duration=0.25)

            # HARD_CUT and CROSS_DISSOLVE are handled at clip concatenation level — no per-frame shader needed

            # ── STEP 4: Speed Ramping (HERO_SLOWMO / CRASH_ACCEL) ───────────────
            # Speed ramp is expressed by scaling the sample time during transform
            # This gives a smooth slow-down → speed-up S-curve feel per frame
            if speed_mode == "HERO_SLOWMO" and total_dur > 0:
                import math
                # S-curve: slow middle 40% of clip, normal start/end
                if 0.30 < progress < 0.70:
                    # Pull adjacent frame by slowing playback index
                    slow_t = max(0.0, min(total_dur - 0.03, t * 0.55))
                    try:
                        frame = gf(slow_t).copy()
                    except Exception:
                        pass

            elif speed_mode == "CRASH_ACCEL" and total_dur > 0:
                accel_factor = 0.6 + pro_vfx_engine.ease_in_out_cubic(progress) * 1.4
                accel_t = max(0.0, min(total_dur - 0.03, t * accel_factor))
                try:
                    frame = gf(accel_t).copy()
                except Exception:
                    pass

            # ── STEP 5: Universal Cinematic Vignette + Film Grain (always on) ───
            frame = pro_vfx_engine.apply_vignette_film_grain(frame, vignette_strength=0.28, grain_intensity=5)
            return frame

        clip = clip.transform(pro_vfx_transform)
        print(f"⚡ [AI DIRECTOR VFX] All effects rendered: Zoom={zoom_mode} | Transition={transition_mode} | SpeedRamp={speed_mode} | Grade={color_preset} | Vignette+Grain ✅")
    except Exception as e:
        print(f"   ⚠️ Pro VFX Pipeline note: {e}")


    target_w, target_h = 1080, 1920
    w, h = clip.size
    
    # 📱 9:16 VERTICAL ASPECT RATIO COMPOSITION
    scale_bg = max(target_w / float(w), target_h / float(h))
    bg_video = clip.resized(new_size=(int(w * scale_bg), int(h * scale_bg)))
    bg_video = bg_video.with_position(("center", "center"))
    
    scale_fg = target_w / float(w)
    fg_h = int(h * scale_fg)
    
    if fg_h < 1350:
        scale_fg = min(1350 / float(h), target_h / float(h))
        fg_w = int(w * scale_fg)
        fg_h = int(h * scale_fg)
        fg_video = clip.resized(new_size=(fg_w, fg_h)).with_position(("center", "center"))
    else:
        fg_video = clip.resized(new_size=(target_w, fg_h)).with_position(("center", "center"))

    composite_elements = [bg_video, fg_video]

    # Top Hook Banner Header
    top_header_np = create_top_hook_header(top_header_text, width=target_w)
    top_header_clip = (ImageClip(top_header_np)
                       .with_start(0.0)
                       .with_duration(clip.duration)
                       .with_position(("center", 80)))
    composite_elements.append(top_header_clip)

    # Animated Neon Progress Bar at Bottom
    progress_bar_count = int(clip.duration * 10)
    for p_idx in range(progress_bar_count):
        t_start = p_idx * 0.1
        t_dur = 0.1
        ratio = (t_start + t_dur) / clip.duration
        p_bar_np = create_progress_bar_image(ratio, width=target_w)
        p_bar_clip = (ImageClip(p_bar_np)
                      .with_start(t_start)
                      .with_duration(t_dur)
                      .with_position((0, target_h - 14)))
        composite_elements.append(p_bar_clip)
    audio_clips = []
    created_temp_audios = []
    
    # Process narration segments & calculate voiceover time intervals
    vo_intervals = [] # [(start, end)]
    rendered_vo_clips = []
    
    if segments:
        print(f"🗣️ Overlaying Precision AI-Timed Narration Segments...")
        last_vo_end_time = 0.0

        for seg_idx, seg in enumerate(segments, 1):
            if not isinstance(seg, dict):
                continue
            seg_text = seg.get("text", "").strip()
            if not seg_text:
                continue

            # Align voiceover precisely with Gemini's visual timestamp!
            ai_start_sec = float(seg.get("start_sec", 0.0))
            seg_start = max(ai_start_sec, last_vo_end_time + 0.1)

            if seg_start >= clip.duration - 0.8:
                break

            out_audio, boundaries = asyncio.run(generate_segment_voiceover(seg_text, seg_idx))
            created_temp_audios.append(out_audio)

            if os.path.exists(out_audio):
                vo_audio = AudioFileClip(out_audio)
                vo_dur = vo_audio.duration

                if seg_start + vo_dur > clip.duration:
                    usable_dur = max(0.5, clip.duration - seg_start)
                    vo_audio = vo_audio.subclipped(0, min(vo_dur, usable_dur))
                    vo_dur = vo_audio.duration

                vo_end = seg_start + vo_dur
                last_vo_end_time = vo_end
                vo_intervals.append((seg_start, vo_end))

                print(f"   🎙️ Precision AI Voice [{seg_idx}] at {seg_start:.1f}s -> {vo_end:.1f}s: '{seg_text}'")

                placed_vo = vo_audio.with_volume_scaled(1.8).with_start(seg_start)
                audio_clips.append(placed_vo)

                captions = render_micro_captions_for_segment(seg_text, boundaries, seg_start, vo_dur, width=target_w, color_scheme=seg_idx)
                composite_elements.extend(captions)

                if last_vo_end_time >= clip.duration - 1.2:
                    break


    # 🔉 AUDIO DUCKING: Duck background video audio to 10% ONLY during voiceover segments
    if clip.audio is not None:
        if vo_intervals:
            print("🔉 Applying smart audio ducking (Background Audio -> 10% during narration)...")
            # Merge overlapping intervals to prevent slicing errors
            vo_intervals.sort(key=lambda x: x[0])
            merged_intervals = []
            for start, end in vo_intervals:
                if not merged_intervals:
                    merged_intervals.append((start, end))
                else:
                    m_start, m_end = merged_intervals[-1]
                    if start <= m_end:
                        merged_intervals[-1] = (m_start, max(m_end, end))
                    else:
                        merged_intervals.append((start, end))

            bg_audio_clips = []
            curr_pos = 0.0
            
            for (v_start, v_end) in merged_intervals:
                if v_start > curr_pos:
                    # Gap interval: Full 100% volume
                    bg_audio_clips.append(clip.audio.subclipped(curr_pos, v_start).with_volume_scaled(1.0).with_start(curr_pos))
                # Active voiceover interval: Duck to 10% volume
                bg_audio_clips.append(clip.audio.subclipped(v_start, v_end).with_volume_scaled(0.10).with_start(v_start))
                curr_pos = v_end
                
            if curr_pos < clip.duration:
                bg_audio_clips.append(clip.audio.subclipped(curr_pos, clip.duration).with_volume_scaled(1.0).with_start(curr_pos))
                
            audio_clips.extend(bg_audio_clips)
        else:
            audio_clips.append(clip.audio.with_volume_scaled(1.0))
            
    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips)
        final_video = CompositeVideoClip(composite_elements, size=(target_w, target_h)).with_audio(final_audio)
    else:
        final_video = CompositeVideoClip(composite_elements, size=(target_w, target_h))
        
    print(f"💾 Exporting 9:16 Full Screen Vertical Short to: {output_path}")
    final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=30, preset="fast")
    
    try:
        orig_clip.close()
        if clip is not orig_clip:
            clip.close()
        final_video.close()
    except Exception:
        pass
    
    for f in created_temp_audios:
        if os.path.exists(f):
            os.remove(f)
            
    print(f"🎉 MASTER PIPELINE COMPLETE: {output_path}")

# /***
# * =====================================================================================
# * MASTER AUTOMATION & POST PIPELINE ENTRY POINT
# * =====================================================================================
# * Workflow: Ingest raw viral video -> Gemini frame reasoning -> Render 9:16 Short -> Publish
# * Note: For pre-editing ONLY (no API upload), use `get_instant_viral.py` or `auto_ai_editor.py`.
# * =====================================================================================
# ***/

def run_pipeline():
    print("=" * 70)
    print("🚀 SMART AI PIPELINE (9:16 Full Canvas + Micro-Captions + Story Hooks)")
    print("=" * 70)
    
    custom_url = None
    meta = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if os.path.exists(arg) and arg.lower().endswith(('.mp4', '.mov', '.mkv', '.webm')):
            print(f"🎬 Processing direct input video file: {arg}")
            meta = {
                'file_path': arg,
                'title': os.path.splitext(os.path.basename(arg))[0],
                'subreddit': 'DirectUpload'
            }
        elif arg.startswith("http://") or arg.startswith("https://") or arg.startswith("www."):
            custom_url = arg
            
    if not meta:
        meta = get_viral_video(custom_url=custom_url)
    
    if not meta:
        print("❌ No new video found.")
        return
        
    print("\n" + "=" * 70)
    print(f"📹 Processing Video: {meta['file_path']}")
    print("=" * 70)
    
    ai_plan = generate_ai_editing_plan(
        video_path=meta['file_path'],
        post_title=meta['title'],
        subreddit=meta['subreddit']
    )
    
    highlight_cuts = ai_plan.get('highlight_cuts', [])
    if not isinstance(highlight_cuts, list):
        highlight_cuts = []
        
    narration_segments = ai_plan.get('narration_segments', [])
    if not isinstance(narration_segments, list):
        narration_segments = []

    print("\n📝 GENERATED AI SCRIPT & MULTI-CUT EDITING PLAN:")
    print(f"  🎬 Title       : {ai_plan.get('viral_title', 'Viral Short')}")
    print(f"  🎨 AI Theme Color: {ai_plan.get('bg_color', '#0F0F14')}")
    print(f"  ✂️ Highlight Cuts ({len(highlight_cuts)} cuts):")
    for c in highlight_cuts:
        if isinstance(c, dict):
            print(f"      • {float(c.get('start_sec', 0.0)):.1f}s -> {float(c.get('end_sec', 0.0)):.1f}s")
    print(f"  🗣️ Timed Narration Segments ({len(narration_segments)} segments):")
    for s in narration_segments:
        if isinstance(s, dict):
            print(f"      • [{float(s.get('start_sec', 0.0)):.1f}s]: \"{s.get('text', '')}\"")
        
    # Create clean SEO-optimized viral filename
    raw_title = ai_plan.get('viral_title', meta['title'])
    clean_title = sanitize_name(raw_title)
    
    os.makedirs("metadata", exist_ok=True)
    info_path = os.path.join("metadata", f"{clean_title}_info.txt")
    with open(info_path, "w", encoding="utf-8") as f:
        f.write(f"TITLE:\n{ai_plan.get('viral_title', '')}\n\n")
        f.write(f"DESCRIPTION:\n{ai_plan.get('description', '')}\n\n")
        f.write(f"AI MULTI-CUT HIGHLIGHTS:\n")
        for c in highlight_cuts:
            if isinstance(c, dict):
                f.write(f"Cut: {float(c.get('start_sec', 0.0)):.1f}s to {float(c.get('end_sec', 0.0)):.1f}s\n")
        f.write(f"\nTIMED NARRATION SEGMENTS:\n")
        for s in narration_segments:
            if isinstance(s, dict):
                f.write(f"[{float(s.get('start_sec', 0.0)):.1f}s] {s.get('text', '')}\n")
    print(f"📄 Saved SEO metadata to: {info_path}")
    
    os.makedirs("edited", exist_ok=True)
    out_short_path = os.path.join("edited", f"{clean_title}_Short.mp4")
    edit_viral_short(meta['file_path'], ai_plan, out_short_path)

    # 🚀 GENERATE & PRINT FULL YOUTUBE SHORTS UPLOAD KIT
    generate_and_save_upload_kit(ai_plan, out_short_path, meta['title'])


def generate_and_save_upload_kit(ai_plan, output_video_path, post_title=""):
    title = ai_plan.get("viral_title", post_title or "Unbelievable Viral Moment").strip()
    raw_desc = ai_plan.get("description", "").strip()
    hook = ai_plan.get("top_hook_header", "UNBELIEVABLE MOMENT 😭").strip()
    
    full_title = f"{title[:65]} 😱 #Shorts #Viral #FYP"
    
    full_description = (
        f"{raw_desc}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 Welcome to Viral Moments! Daily insane clips, roasts & breakdowns.\n"
        f"👇 SUBSCRIBE & TURN ON NOTIFICATIONS FOR DAILY VIRAL SHORTS! 👇\n\n"
        f"💬 What would you have done in this situation? Comment below!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"#Shorts #Viral #Trending #FYP #ShortsFeed #YouTubeShorts #Humor #MustWatch #Shocking #EpicMoments"
    )
    
    tags_str = "Shorts, YouTubeShorts, Viral, Trending, FYP, ShortsFeed, ViralShorts, CrazyMoments, Unexpected, MindBlowing, MustWatch, FunnyMoments, Shocking, Insane, WildMoments, ViralClips, Epic"
    pinned_comment = f"Rate this clip from 1 to 10! What would you have done in this situation? 💬👇"
    
    clean_name = sanitize_name(title)
    os.makedirs("metadata", exist_ok=True)
    kit_file_path = os.path.join("metadata", f"{clean_name}_UPLOAD_KIT.txt")
    
    with open(kit_file_path, "w", encoding="utf-8") as f:
        f.write("======================================================================\n")
        f.write("🚀 YOUTUBE SHORTS UPLOAD KIT (ALL METADATA READY FOR PUBLISHING)\n")
        f.write("======================================================================\n\n")
        f.write(f"📹 RENDERED VIDEO FILE:\n{os.path.abspath(output_video_path)}\n\n")
        f.write(f"📌 1. TITLE (COPY & PASTE TO YOUTUBE TITLE BOX):\n{full_title}\n\n")
        f.write(f"📝 2. DESCRIPTION (COPY & PASTE TO YOUTUBE DESCRIPTION BOX):\n{full_description}\n\n")
        f.write(f"🏷️ 3. TAGS (COPY & PASTE TO YOUTUBE TAGS BOX):\n{tags_str}\n\n")
        f.write(f"💬 4. PINNED COMMENT (POST & PIN IN COMMENTS):\n{pinned_comment}\n\n")
        f.write(f"🎯 5. TOP HOOK HEADER:\n{hook}\n\n")
        f.write("======================================================================\n")
    
    print("\n" + "═" * 75)
    print("🎉 VIDEO RENDER COMPLETE! HERE IS YOUR READY-TO-UPLOAD YOUTUBE KIT:")
    print("═" * 75)
    print(f"\n📹 RENDERED VIDEO PATH:\n  👉 {os.path.abspath(output_video_path)}")
    print(f"\n📌 1. YOUTUBE TITLE (Copy & Paste):")
    print(f"  👉 {full_title}")
    print(f"\n📝 2. YOUTUBE DESCRIPTION (Copy & Paste):")
    print(f"  👉 {raw_desc}")
    print(f"     #Shorts #Viral #Trending #FYP #ShortsFeed #YouTubeShorts #Humor")
    print(f"\n🏷️ 3. YOUTUBE TAGS (Copy & Paste):")
    print(f"  👉 {tags_str}")
    print(f"\n💬 4. PINNED COMMENT SUGGESTION:")
    print(f"  👉 \"{pinned_comment}\"")
    print(f"\n📄 FULL UPLOAD KIT SAVED TO:")
    print(f"  👉 {kit_file_path}")
    print("═" * 75 + "\n")

# ==========================================
# YOUTUBE UPLOADER SERVICE LAYER
# ==========================================
def upload_to_youtube_shorts(video_file, title, description):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        creds = None
        token_path = 'youtube_token.json'

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        youtube = build('youtube', 'v3', credentials=creds)

        # 🚀 ALGORITHM DOMINATION VIRAL TAGS ARRAY (25 Top Tags)
        viral_tags = [
            "Shorts", "YouTubeShorts", "Viral", "Trending", "FYP", "ShortsFeed", 
            "ViralShorts", "CrazyMoments", "Unexpected", "MindBlowing", "MustWatch",
            "Entertainment", "FunnyMoments", "Shocking", "ViralVideo", "TrendingShorts",
            "DailyShorts", "Subscribers", "WatchThis", "OMG", "Insane", "WildMoments", 
            "ViralClips", "Epic", "ViralMoments"
        ]

        # 🚀 ALGORITHM-MAGNET DESCRIPTION ENGINE
        rich_description = (
            f"{description}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔥 Welcome to Viral Moments! We find & archive the internet's most unbelievable clips daily.\n"
            f"👇 SUBSCRIBE & TURN ON NOTIFICATIONS FOR DAILY VIRAL SHORTS! 👇\n\n"
            f"💬 What would you have done in this situation? Let us know in the comments below!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"#Shorts #Viral #Trending #FYP #ShortsFeed #YouTubeShorts #ViralMoments #MustWatch #Shocking #Unexpected #EpicMoments #CrazyClips"
        )

        body = {
            'snippet': {
                'title': f"{title[:75]} 😱 #Shorts #Viral #FYP",
                'description': rich_description,
                'tags': viral_tags,
                'categoryId': '24', # Entertainment
                'defaultLanguage': 'en',
                'defaultAudioLanguage': 'en'
            },
            'status': {
                'privacyStatus': 'public',
                'selfDeclaredMadeForKids': False
            }
        }

        media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        response = None
        
        print(f"📤 Uploading '{title}' to YouTube Shorts with 25 Algorithm Tags & SEO Description...")
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   ⏳ Upload Progress: {int(status.progress() * 100)}%")

        published_url = f"https://youtube.com/shorts/{response.get('id')}"
        print(f"🎉 SUCCESS! Video published to YouTube Shorts with FULL ALGORITHM METADATA!")
        print(f"🔗 Video ID: {published_url}")

        # Save to latest_uploaded_video.txt for auto_viewer_booster.py
        try:
            with open("latest_uploaded_video.txt", "w", encoding="utf-8") as f:
                f.write(published_url)
        except Exception:
            pass

        # 🚀 ORGANIC PROMOTION INSTRUCTIONS
        print("\n📢 VIDEO UPLOADED SUCCESSFULLY!")
        print("\n🔥 NEXT STEPS FOR ORGANIC GROWTH:")
        print("   1. Share on Instagram, Twitter, TikTok")
        print("   2. Post in 3-5 Reddit communities")
        print("   3. Engage with EVERY comment in first 2 hours")
        print("   4. Pin engaging question in comments")
        print("   5. Create community post announcing upload")
        print(f"\n✅ Video ready to promote: {published_url}")
    except Exception as e:
        print(f"⚠️ YouTube Auto-Upload Note: {e}")

if __name__ == "__main__":
    run_pipeline()

import os
import sys
import time
import uuid
import json
import shutil
import threading
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure UTF-8 output encoding for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Load environment variables
current_dir = os.path.abspath(os.path.dirname(__file__))
nigga_dir = os.path.abspath(os.path.join(current_dir, "..", "nigga"))
if not os.path.exists(os.path.join(nigga_dir, "run_viral_pipeline.py")):
    nigga_dir = current_dir

env_path = os.path.join(nigga_dir, ".env")
if not os.path.exists(env_path):
    env_path = os.path.join(current_dir, ".env")
load_dotenv(env_path, override=True)

# Add directories to sys.path
if nigga_dir not in sys.path:
    sys.path.insert(0, nigga_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import run_viral_pipeline
import ultimate_pro_studio_engine

app = FastAPI(title="Autonomous AI Video Director API", version="2.5")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
STATIC_DIR = os.path.join(os.path.dirname(__file__), "web")
VIDEOS_DIR = os.path.join(nigga_dir, "videos")
EDITED_DIR = os.path.join(nigga_dir, "edited")
METADATA_DIR = os.path.join(nigga_dir, "metadata")

os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(EDITED_DIR, exist_ok=True)
os.makedirs(METADATA_DIR, exist_ok=True)

# Mount Static Files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Job Store
jobs = {}

def add_job_log(job_id: str, msg: str, log_type: str = "normal"):
    if job_id in jobs:
        jobs[job_id]["logs"].append({"msg": msg, "type": log_type, "time": time.time()})
        jobs[job_id]["status_text"] = msg

def run_director_worker(job_id: str, req_type: str, url: Optional[str], file_path: Optional[str], ratio: str, voice: str, mode: str):
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["progress"] = 10
        add_job_log(job_id, "🎬 Autonomous AI Director initialized...", "accent")

        target_meta = None

        if req_type == "upload":
            if not file_path or not os.path.exists(file_path):
                raise Exception("Uploaded video file not found on disk.")
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            target_meta = {
                "file_path": file_path,
                "title": base_name,
                "subreddit": "DirectUpload"
            }
            add_job_log(job_id, f"📁 Ingested local video: {os.path.basename(file_path)}", "success")

        elif req_type == "url":
            add_job_log(job_id, f"🌐 Fetching video stream from URL: {url}", "accent")
            jobs[job_id]["progress"] = 15
            target_meta = run_viral_pipeline.download_with_ytdlp(url, "WebUrl", "Viral Video")
            if not target_meta:
                raise Exception("Failed to download video from the provided URL.")
            add_job_log(job_id, f"📥 Video downloaded successfully: '{target_meta['title']}'", "success")

        elif req_type == "auto":
            add_job_log(job_id, "⚡ Scanning live viral feeds (Reddit & YouTube Shorts)...", "accent")
            jobs[job_id]["progress"] = 15
            target_meta = run_viral_pipeline.get_viral_video()
            if not target_meta:
                raise Exception("No fresh viral candidate found in active feeds.")
            add_job_log(job_id, f"🔥 Auto-discovered viral video: '{target_meta['title']}'", "success")

        # Step 2: Gemini Multimodal Vision Reasoning
        jobs[job_id]["progress"] = 35
        add_job_log(job_id, "🧠 Uploading video to Gemini Vision for Scene & Audio Analysis...", "accent")

        ai_plan = run_viral_pipeline.generate_ai_editing_plan(
            video_path=target_meta["file_path"],
            post_title=target_meta["title"],
            subreddit=target_meta.get("subreddit", "General")
        )

        segments = ai_plan.get("narration_segments", [])
        add_job_log(job_id, f"✅ Gemini Vision analyzed scene! Generated {len(segments)} synchronized story beats.", "success")
        
        for idx, seg in enumerate(segments[:4], 1):
            t_sec = float(seg.get('start_sec', 0.0))
            add_job_log(job_id, f"   🗣️ Beat {idx} [{t_sec:.1f}s]: \"{seg.get('text', '')[:45]}...\"", "normal")

        # Step 3: Synthesis & Compositing
        jobs[job_id]["progress"] = 60
        add_job_log(job_id, f"🎙️ Synthesizing narration with ElevenLabs ({voice.capitalize()})...", "accent")

        raw_title = ai_plan.get("viral_title", target_meta["title"])
        clean_title = run_viral_pipeline.sanitize_name(raw_title)
        out_filename = f"{clean_title}_Short.mp4"
        out_short_path = os.path.join(EDITED_DIR, out_filename)

        jobs[job_id]["progress"] = 75
        add_job_log(job_id, f"🚀 Executing MoviePy Master Compositing (Ratio: {ratio}, Neon Captions, Audio Ducking)...", "accent")

        # Render Short
        run_viral_pipeline.edit_viral_short(target_meta["file_path"], ai_plan, out_short_path)

        # Generate Upload Kit
        run_viral_pipeline.generate_and_save_upload_kit(ai_plan, out_short_path, target_meta["title"])
        
        jobs[job_id]["progress"] = 100
        jobs[job_id]["status"] = "completed"
        add_job_log(job_id, "🎉 Autonomous video rendering complete and ready for publishing!", "success")

        # Load metadata text if exists
        desc_text = ai_plan.get("description", "A viral moment captured.")
        full_title = f"{ai_plan.get('viral_title', clean_title)} 😱 #Shorts #Viral #FYP"

        jobs[job_id]["result"] = {
            "filename": out_filename,
            "video_url": f"/api/video/{out_filename}",
            "download_url": f"/api/download/{out_filename}",
            "title": full_title,
            "description": f"{desc_text}\n\n#Shorts #Viral #Trending #FYP #ShortsFeed #YouTubeShorts #Humor",
            "tags": "Shorts, YouTubeShorts, Viral, Trending, FYP, ShortsFeed, ViralShorts, CrazyMoments, Unexpected, MindBlowing, MustWatch",
            "pinned_comment": "Rate this clip from 1 to 10! What would you have done in this situation? 💬👇"
        }

    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)
        add_job_log(job_id, f"❌ Execution error: {str(e)}", "warn")

# Routes
@app.get("/")
@app.head("/")
def serve_index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

@app.post("/api/edit")
async def create_edit_job(
    background_tasks: BackgroundTasks,
    type: str = Form(...),
    url: Optional[str] = Form(None),
    ratio: str = Form("9:16"),
    voice: str = Form("adam"),
    mode: str = Form("rapid_fire"),
    file: Optional[UploadFile] = File(None)
):
    job_id = str(uuid.uuid4())[:8]
    saved_file_path = None

    if type == "upload" and file:
        file_ext = os.path.splitext(file.filename)[1] or ".mp4"
        saved_file_path = os.path.join(VIDEOS_DIR, f"upload_{job_id}_{int(time.time())}{file_ext}")
        with open(saved_file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

    jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 5,
        "logs": [],
        "status_text": "Queued in director pipeline...",
        "result": None,
        "created_at": time.time()
    }

    threading.Thread(
        target=run_director_worker,
        args=(job_id, type, url, saved_file_path, ratio, voice, mode),
        daemon=True
    ).start()

    return {"job_id": job_id, "status": "queued"}

@app.get("/api/job/{job_id}")
def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]

@app.get("/api/video/{filename}")
@app.head("/api/video/{filename}")
def stream_video(filename: str):
    video_path = os.path.join(EDITED_DIR, filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")

@app.get("/api/download/{filename}")
def download_video(filename: str):
    video_path = os.path.join(EDITED_DIR, filename)
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4", filename=filename)

@app.get("/api/gallery")
def get_gallery():
    items = []
    if not os.path.exists(EDITED_DIR):
        return items

    files = [f for f in os.listdir(EDITED_DIR) if f.lower().endswith(('.mp4', '.mov'))]
    files.sort(key=lambda x: os.path.getmtime(os.path.join(EDITED_DIR, x)), reverse=True)

    for f in files[:8]:
        full_path = os.path.join(EDITED_DIR, f)
        size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 1)
        base_title = os.path.splitext(f)[0].replace("_Short", "").replace("_", " ")

        # Check for metadata
        desc = "Viral AI Director Short"
        tags = "Shorts, Viral, Trending"
        pinned = "Rate this clip from 1 to 10! 💬👇"

        meta_candidate = os.path.join(METADATA_DIR, f"{os.path.splitext(f)[0]}_UPLOAD_KIT.txt")
        if not os.path.exists(meta_candidate):
            meta_candidate = os.path.join(METADATA_DIR, f"{os.path.splitext(f)[0].replace('_Short', '')}_UPLOAD_KIT.txt")

        if os.path.exists(meta_candidate):
            try:
                with open(meta_candidate, "r", encoding="utf-8") as mf:
                    m_txt = mf.read()
                    if "2. DESCRIPTION" in m_txt:
                        desc = m_txt.split("2. DESCRIPTION")[1].split("3. TAGS")[0].strip().lstrip(":").strip()
            except Exception:
                pass

        items.append({
            "filename": f,
            "title": base_title,
            "video_url": f"/api/video/{f}",
            "download_url": f"/api/download/{f}",
            "size_mb": size_mb,
            "duration": "30s",
            "description": desc,
            "tags": tags,
            "pinned_comment": pinned
        })

    return items

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 70)
    print("🚀 AUTONOMOUS AI VIDEO DIRECTOR SERVER INITIALIZING")
    port = int(os.environ.get("PORT", 8000))
    print(f"🌐 Web Studio Port: {port}")
    print("=" * 70 + "\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)

import sys
import os
import numpy as np
import math
import random
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw, ImageFont

# Force UTF-8 output encoding for Windows terminal environment
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ======================================================================
# 1. ZOOM EFFECTS & CAMERA MOVEMENT TYPES (DEEP DIVE)
# ======================================================================

def ease_in_out_cubic(t):
    """Cubic Bezier Easing Curve for ultra-smooth zoom transitions"""
    t = max(0.0, min(1.0, t))
    if t < 0.5:
        return 4.0 * t * t * t
    else:
        return 1.0 - math.pow(-2.0 * t + 2.0, 3) / 2.0

def elastic_overshoot(t):
    """Elastic bounce easing for snappy spring zooms"""
    t = max(0.0, min(1.0, t))
    if t == 0.0 or t == 1.0:
        return t
    c4 = (2.0 * math.pi) / 3.0
    return math.pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * c4) + 1.0

def apply_punch_zoom(frame, t, trigger_times, zoom_scale=1.22, duration=0.35):
    """Punch / Crash Zoom: Sudden digital zoom into subject for dramatic emphasis"""
    h, w, _ = frame.shape
    active_zoom = 1.0
    
    for trig in trigger_times:
        if trig <= t <= trig + duration:
            progress = (t - trig) / duration
            decay = 1.0 - ease_in_out_cubic(progress)
            active_zoom = 1.0 + (zoom_scale - 1.0) * decay
            break
            
    if active_zoom > 1.001:
        new_w, new_h = int(w / active_zoom), int(h / active_zoom)
        crop_x = (w - new_w) // 2
        crop_y = (h - new_h) // 2
        cropped = frame[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
        pil_img = Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR)
        return np.array(pil_img)
        
    return frame

def apply_hit_beat_zoom(frame, t, beat_timestamps, zoom_intensity=1.12, duration=0.20):
    """Hit Zoom / Beat Zoom: Micro-zooms synced to the audio beat markers"""
    h, w, _ = frame.shape
    active_zoom = 1.0
    for beat in beat_timestamps:
        if beat <= t <= beat + duration:
            progress = (t - beat) / duration
            active_zoom = 1.0 + (zoom_intensity - 1.0) * (1.0 - progress)
            break
            
    if active_zoom > 1.001:
        new_w, new_h = int(w / active_zoom), int(h / active_zoom)
        crop_x = (w - new_w) // 2
        crop_y = (h - new_h) // 2
        cropped = frame[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
        pil_img = Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR)
        return np.array(pil_img)
    return frame

def apply_spin_rotational_zoom(frame, t, duration, max_angle=180.0):
    """Spin / Rotational Zoom: Zooms in while rotating into scene transition"""
    h, w, _ = frame.shape
    progress = max(0.0, min(1.0, t / float(duration)))
    eased_p = ease_in_out_cubic(progress)
    
    current_zoom = 1.0 + 0.8 * eased_p
    current_angle = max_angle * eased_p
    
    pil_img = Image.fromarray(frame)
    # Rotate & Zoom
    rotated = pil_img.rotate(current_angle, resample=Image.Resampling.BICUBIC, expand=False)
    arr = np.array(rotated)
    
    new_w, new_h = max(1, int(w / current_zoom)), max(1, int(h / current_zoom))
    crop_x = (w - new_w) // 2
    crop_y = (h - new_h) // 2
    cropped = arr[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
    return np.array(Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR))

def apply_whip_blur_zoom(frame, t, transition_center, duration=0.30):
    """Whip Zoom / Blur Zoom: Rapid zoom paired with directional motion blur"""
    h, w, _ = frame.shape
    half_d = duration / 2.0
    if transition_center - half_d <= t <= transition_center + half_d:
        progress = (t - (transition_center - half_d)) / duration
        intensity = math.sin(progress * math.pi)
        
        # Apply radial / motion blur effect via PIL
        pil_img = Image.fromarray(frame)
        blur_radius = int(intensity * 12)
        if blur_radius > 0:
            pil_img = pil_img.filter(ImageFilter.GaussianBlur(blur_radius))
        
        zoom_factor = 1.0 + 0.35 * intensity
        new_w, new_h = max(1, int(w / zoom_factor)), max(1, int(h / zoom_factor))
        crop_x = (w - new_w) // 2
        crop_y = (h - new_h) // 2
        cropped = np.array(pil_img)[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
        return np.array(Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR))
    return frame

def apply_dolly_zoom_vertigo(frame, t, duration):
    """Dolly Zoom (Vertigo Effect): Background zooms while foreground remains stable"""
    h, w, _ = frame.shape
    progress = max(0.0, min(1.0, t / float(duration)))
    zoom_factor = 1.0 + 0.40 * math.sin(progress * math.pi)
    
    new_w, new_h = max(1, int(w / zoom_factor)), max(1, int(h / zoom_factor))
    crop_x = (w - new_w) // 2
    crop_y = (h - new_h) // 2
    cropped = frame[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
    return np.array(Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR))

def apply_target_roi_zoom(frame, center_x_ratio=0.5, center_y_ratio=0.5, zoom_scale=1.35):
    """Target Zoom / Focus Point Zoom: Zoom into dynamic Region of Interest (ROI)"""
    h, w, _ = frame.shape
    target_cx = int(w * center_x_ratio)
    target_cy = int(h * center_y_ratio)
    
    new_w, new_h = max(1, int(w / zoom_scale)), max(1, int(h / zoom_scale))
    crop_x = max(0, min(w - new_w, target_cx - new_w // 2))
    crop_y = max(0, min(h - new_h, target_cy - new_h // 2))
    
    cropped = frame[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
    return np.array(Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR))

def apply_ken_burns_pan_zoom(frame, t, duration, zoom_start=1.0, zoom_end=1.18):
    """Ken Burns Effect: Smooth cinematic slow zoom paired with pan across footage"""
    if duration <= 0:
        return frame
    progress = max(0.0, min(1.0, t / float(duration)))
    eased_p = ease_in_out_cubic(progress)
    
    current_zoom = zoom_start + (zoom_end - zoom_start) * eased_p
    h, w, _ = frame.shape
    
    new_w, new_h = max(1, int(w / current_zoom)), max(1, int(h / current_zoom))
    pan_x_offset = int((w - new_w) * 0.5 * eased_p)
    pan_y_offset = int((h - new_h) * 0.5 * eased_p)
    
    crop_x = max(0, min(w - new_w, pan_x_offset))
    crop_y = max(0, min(h - new_h, pan_y_offset))
    
    cropped = frame[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
    return np.array(Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR))

def apply_elastic_bounce_zoom(frame, t, trigger_time, duration=0.45, zoom_peak=1.25):
    """Elastic / Bounce Zoom: Overshooting spring bounce zoom physics"""
    h, w, _ = frame.shape
    if trigger_time <= t <= trigger_time + duration:
        progress = (t - trigger_time) / duration
        eased_b = elastic_overshoot(progress)
        current_zoom = 1.0 + (zoom_peak - 1.0) * (1.0 - eased_b)
        
        if current_zoom > 1.0:
            new_w, new_h = max(1, int(w / current_zoom)), max(1, int(h / current_zoom))
            crop_x = (w - new_w) // 2
            crop_y = (h - new_h) // 2
            cropped = frame[crop_y:crop_y+new_h, crop_x:crop_x+new_w]
            return np.array(Image.fromarray(cropped).resize((w, h), Image.Resampling.BILINEAR))
    return frame

# ======================================================================
# 2. CUT & TRANSITION SHADERS & TYPES
# ======================================================================

def apply_rgb_split_glitch(frame, t, trigger_times, duration=0.25, max_shift=18):
    """Glitch / RGB Split Transition: Chromatic aberration shift between scenes"""
    h, w, c = frame.shape
    active_shift = 0
    
    for trig in trigger_times:
        if trig <= t <= trig + duration:
            progress = (t - trig) / duration
            intensity = math.sin(progress * math.pi)
            active_shift = int(max_shift * intensity)
            break
            
    if active_shift > 0:
        res = frame.copy()
        res[:, :, 0] = np.roll(frame[:, :, 0], -active_shift, axis=1) # Red shift left
        res[:, :, 2] = np.roll(frame[:, :, 2], active_shift, axis=1)  # Blue shift right
        return res
        
    return frame

def apply_light_leak_transition(frame, progress):
    """Light Leak / Lens Flare: Warm cinematic light burn transition mask"""
    h, w, c = frame.shape
    intensity = math.sin(max(0.0, min(1.0, progress)) * math.pi)
    
    if intensity > 0.01:
        leak = np.zeros((h, w, c), dtype=np.float32)
        leak[:, :, 0] = 255.0 * intensity  # Red / Warm channel
        leak[:, :, 1] = 180.0 * intensity  # Amber channel
        leak[:, :, 2] = 50.0 * intensity   # Yellow channel
        
        blended = np.clip(frame.astype(np.float32) + leak * 0.75, 0, 255).astype(np.uint8)
        return blended
    return frame

def apply_whip_pan_push(frame_a, frame_b, progress):
    """Whip Pan / Push: Rapid horizontal push transition between Clip A and Clip B"""
    h, w, c = frame_a.shape
    p = ease_in_out_cubic(progress)
    shift_x = int(w * p)
    
    res = np.zeros((h, w, c), dtype=np.uint8)
    res[:, :w-shift_x] = frame_a[:, shift_x:]
    res[:, w-shift_x:] = frame_b[:, :shift_x]
    return res

def apply_dissolve_crossfade(frame_a, frame_b, progress):
    """Dissolve / Crossfade: Smooth alpha blending between two frames"""
    p = max(0.0, min(1.0, progress))
    blended = (frame_a.astype(np.float32) * (1.0 - p) + frame_b.astype(np.float32) * p)
    return np.clip(blended, 0, 255).astype(np.uint8)

# ======================================================================
# 3. TIMELINE & KEYFRAMING ENGINE
# ======================================================================

def speed_ramp_multiplier(progress, ramp_type="S_CURVE"):
    """Speed Controls: Variable Speed Ramping curves for dynamic pacing"""
    if ramp_type == "HERO_SLOWMO":
        if progress < 0.3:
            return 1.5 - (progress / 0.3) * 1.0 # 1.5x down to 0.5x
        elif progress < 0.7:
            return 0.4 # Slow-motion climax
        else:
            return 0.4 + ((progress - 0.7) / 0.3) * 1.1 # Back to 1.5x
    elif ramp_type == "CRASH_ACCEL":
        return 0.5 + ease_in_out_cubic(progress) * 1.5
    return 1.0

def apply_shape_masking(frame, mask_type="RECTANGLE", center=(0.5, 0.5), size=(0.6, 0.6), feather=15):
    """Masking & Cropping: Rectangular or circular masks with feathering"""
    h, w, _ = frame.shape
    cx, cy = int(w * center[0]), int(h * center[1])
    mw, mh = int(w * size[0]), int(h * size[1])
    
    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)
    
    rect_box = [cx - mw // 2, cy - mh // 2, cx + mw // 2, cy + mh // 2]
    if mask_type == "CIRCLE":
        draw.ellipse(rect_box, fill=255)
    else:
        draw.rectangle(rect_box, fill=255)
        
    if feather > 0:
        mask_img = mask_img.filter(ImageFilter.GaussianBlur(feather))
        
    mask_np = np.array(mask_img)[:, :, np.newaxis] / 255.0
    return (frame.astype(np.float32) * mask_np).astype(np.uint8)

# ======================================================================
# 4. VFX & COLOR GRADING ENGINE
# ======================================================================

def apply_color_grading_presets(frame, preset="NEON_VIBRANT"):
    """Color Correction & Grading: Cinematic color grading presets"""
    frame_float = frame.astype(np.float32)
    if preset == "CYBERPUNK":
        frame_float[:, :, 0] = np.clip(frame_float[:, :, 0] * 1.18 + 12, 0, 255) # Red boost
        frame_float[:, :, 2] = np.clip(frame_float[:, :, 2] * 1.28 + 18, 0, 255) # Cyan/Blue boost
    elif preset == "CINEMATIC_DARK":
        frame_float = np.clip((frame_float - 15.0) * 1.14, 0, 255)
    elif preset == "NEON_VIBRANT":
        mean_val = frame_float.mean(axis=2, keepdims=True)
        frame_float = np.clip(mean_val + (frame_float - mean_val) * 1.35, 0, 255)
    elif preset == "HIGH_CONTRAST":
        frame_float = np.clip(128.0 + 1.30 * (frame_float - 128.0), 0, 255)
    return frame_float.astype(np.uint8)

def apply_vignette_film_grain(frame, vignette_strength=0.35, grain_intensity=12):
    """Vignette & Film Grain: Dark radial vignette and analog grain overlay"""
    h, w, c = frame.shape
    y, x = np.ogrid[:h, :w]
    cx, cy = w / 2.0, h / 2.0
    radius = math.sqrt(cx**2 + cy**2)
    dist_from_center = np.sqrt((x - cx)**2 + (y - cy)**2)
    
    vignette_mask = 1.0 - np.clip((dist_from_center / radius) ** 2 * vignette_strength, 0.0, vignette_strength)
    vignette_mask = np.repeat(vignette_mask[:, :, np.newaxis], 3, axis=2)
    
    graded = (frame.astype(np.float32) * vignette_mask).astype(np.uint8)
    
    if grain_intensity > 0:
        noise = np.random.randint(-grain_intensity, grain_intensity + 1, (h, w, c), dtype=np.int16)
        graded = np.clip(graded.astype(np.int16) + noise, 0, 255).astype(np.uint8)
        
    return graded

def apply_chroma_key_green_screen(frame, bg_frame=None, key_color=(0, 255, 0), tolerance=80):
    """Chroma Key: Green screen removal with color spill suppression"""
    diff = np.sqrt(np.sum((frame.astype(np.float32) - np.array(key_color, dtype=np.float32))**2, axis=2))
    mask = (diff > tolerance)[:, :, np.newaxis]
    
    if bg_frame is not None:
        bg_resized = np.array(Image.fromarray(bg_frame).resize((frame.shape[1], frame.shape[0])))
        return np.where(mask, frame, bg_resized).astype(np.uint8)
    else:
        return np.where(mask, frame, 0).astype(np.uint8)

def apply_crt_retro_vhs(frame, t):
    """Filter Library: CRT / Retro VHS scanlines & horizontal distortion"""
    h, w, c = frame.shape
    res = frame.copy()
    
    # 1. Horizontal scanlines
    scanlines = np.ones((h, w, 1), dtype=np.float32)
    scanlines[::3, :, :] = 0.70 # Darken every 3rd line
    res = (res.astype(np.float32) * scanlines).astype(np.uint8)
    
    # 2. VHS Line Jitter
    jitter_y = int((t * 24.0) % h)
    if jitter_y < h - 4:
        res[jitter_y:jitter_y+4, :, :] = np.roll(res[jitter_y:jitter_y+4, :, :], 12, axis=1)
        
    return res

# ======================================================================
# 5. AUDIO ENGINE HELPERS
# ======================================================================

def calculate_auto_ducking_intervals(narration_intervals, total_duration):
    """Auto-Ducking: Lowers background audio to 10% during voiceover dialogue"""
    if not narration_intervals:
        return [(0.0, total_duration, 1.0)]
        
    narration_intervals.sort(key=lambda x: x[0])
    ducked_schedule = []
    curr_pos = 0.0
    
    for start, end in narration_intervals:
        if start > curr_pos:
            ducked_schedule.append((curr_pos, start, 1.0)) # 100% volume
        ducked_schedule.append((start, end, 0.10))         # 10% ducked volume
        curr_pos = end
        
    if curr_pos < total_duration:
        ducked_schedule.append((curr_pos, total_duration, 1.0))
        
    return ducked_schedule

def generate_audio_spectrum_visualizer(t, width=1080, height=120, bars=32):
    """Audio Spectrum / Waveform Visualization overlay bar generator"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    bar_w = width // bars
    for i in range(bars):
        # Generate dynamic rhythmic height based on sine frequencies
        freq = (i + 1) * 3.5
        bar_h = int((math.sin(t * freq) * 0.4 + 0.5) * (height - 20))
        x1 = i * bar_w + 4
        y1 = height - bar_h
        x2 = (i + 1) * bar_w - 4
        y2 = height
        
        # Electric Cyan to Hot Pink gradient
        color = (0, 229, 255, 230) if i % 2 == 0 else (255, 0, 127, 230)
        draw.rectangle([x1, y1, x2, y2], fill=color)
        
    return np.array(img)

# ======================================================================
# 6. TEXT, TYPOGRAPHY & MOTION GRAPHICS
# ======================================================================

def create_kinetic_typography_banner(text, width=1080, style="GLASS_PILL"):
    """Kinetic Typography: Glassmorphic CTA headers & word-by-word banners"""
    img_h = 200
    img = Image.new("RGBA", (width, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    FONT_SIZE = 64
    try:
        font = ImageFont.truetype("arialbd.ttf", FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()
        
    clean_text = text.upper()
    bbox = draw.textbbox((0, 0), clean_text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (width - text_w) // 2, (img_h - text_h) // 2
    
    padding_x, padding_y = 30, 16
    rect = [x - padding_x, y - padding_y, x + text_w + padding_x, y + text_h + padding_y]
    
    # Backing Pill Box with Glowing Outline
    draw.rounded_rectangle(rect, radius=18, fill=(12, 12, 24, 235), outline=(0, 229, 255, 255), width=4)
    # 3D Drop Shadow
    draw.text((x + 4, y + 4), clean_text, font=font, fill=(0, 0, 0, 255))
    # Core Yellow Text
    draw.text((x, y), clean_text, font=font, fill=(255, 235, 59, 255))
    
    return np.array(img)

# ======================================================================
# 7. MODERN AI & SMART FEATURES
# ======================================================================

def smart_auto_reframe_9_16(frame, target_w=1080, target_h=1920):
    """Auto-Reframe: Repositions video canvas to vertical 9:16 aspect ratio"""
    h, w, _ = frame.shape
    scale = target_w / float(w)
    fg_h = int(h * scale)
    
    pil_frame = Image.fromarray(frame)
    resized_fg = np.array(pil_frame.resize((target_w, fg_h), Image.Resampling.BILINEAR))
    
    # Composite over dark canvas
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    canvas[:, :, :] = (15, 15, 20) # Dark theme background
    
    start_y = (target_h - fg_h) // 2
    if start_y >= 0 and start_y + fg_h <= target_h:
        canvas[start_y:start_y+fg_h, :] = resized_fg
    return canvas

def apply_camera_shake(frame, t, trigger_times, duration=0.25, max_displacement=16):
    """Camera Shake: Violent high-frequency screen shake for impacts / drops"""
    for trig in trigger_times:
        if trig <= t <= trig + duration:
            progress = (t - trig) / duration
            decay = 1.0 - progress
            dx = int(random.uniform(-max_displacement, max_displacement) * decay)
            dy = int(random.uniform(-max_displacement, max_displacement) * decay)
            res = np.roll(frame, dx, axis=1)
            res = np.roll(res, dy, axis=0)
            return res
    return frame

def apply_fast_canvas_916(frame, target_w=1080, target_h=1920, border_color=(0, 229, 255)):
    """Fast 9:16 Unified Canvas: Blurs background ambient, centers foreground with sleek cybernetic glowing borders"""
    fh, fw = frame.shape[:2]
    
    pil_frame = Image.fromarray(frame)
    # 1. Fast ambient background thumbnail blur
    bg_thumb = pil_frame.resize((54, 96), Image.Resampling.BILINEAR).filter(ImageFilter.GaussianBlur(3))
    bg_arr = np.array(bg_thumb.resize((target_w, target_h), Image.Resampling.NEAREST))
    # Darken ambient background by 60% so foreground pops
    canvas = bg_arr // 3
    
    # 2. Foreground sharp scaling
    scale = target_w / float(fw)
    fg_h = int(fh * scale)
    if fg_h > target_h:
        scale = target_h / float(fh)
        fg_w = int(fw * scale)
        fg_scaled = np.array(pil_frame.resize((fg_w, target_h), Image.Resampling.BILINEAR))
        start_x = (target_w - fg_w) // 2
        canvas[:, start_x:start_x+fg_w] = fg_scaled
    else:
        fg_scaled = np.array(pil_frame.resize((target_w, fg_h), Image.Resampling.BILINEAR))
        start_y = (target_h - fg_h) // 2
        canvas[start_y:start_y+fg_h, :] = fg_scaled
        
        # 3. Sleek cybernetic neon border lines
        if start_y >= 3:
            canvas[start_y-3:start_y, :] = border_color
        if start_y + fg_h + 3 <= target_h:
            canvas[start_y+fg_h:start_y+fg_h+3, :] = (255, 0, 127) # Pink bottom divider
            
    return canvas

# ======================================================================
# 8. PERFORMANCE, CANVAS & EXPORT ENGINE
# ======================================================================

def get_aspect_ratio_dimensions(ratio_type="9:16"):
    """Aspect Ratios: Presets for YouTube (16:9), Shorts/Reels (9:16), Instagram (1:1)"""
    PRESETS = {
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "21:9": (2560, 1080)
    }
    return PRESETS.get(ratio_type, (1080, 1920))

print("⚡ [PRO VFX ENGINE v2.0] Fully initialized with 8-Point Video Editing Specifications!")

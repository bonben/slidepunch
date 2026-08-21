#!/usr/bin/env python3
"""
SlidePunch — Standalone, zero-dependency slide-by-slide presentation recording studio.
Features:
- Multi-project management
- PDF slide set import (automatic extraction via pdftoppm)
- Slide-by-slide audio recording with live waveform & punch-in repair
- Real-time editable teleprompter with auto-save
- 1-click 1080p MP4 video rendering via ffmpeg
"""

import os
import sys
import json
import re
import shutil
import subprocess
import webbrowser
import urllib.parse
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8080
BASE_DIR = Path(__file__).resolve().parent
PROJECTS_DIR = BASE_DIR / "projects"
WEB_DIR = BASE_DIR / "web"

def ensure_base_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_DIR.mkdir(parents=True, exist_ok=True)

def get_all_projects():
    ensure_base_dirs()
    projects = []
    for p in sorted(PROJECTS_DIR.iterdir()):
        if p.is_dir() and not p.name.startswith('.'):
            meta_file = p / "metadata.json"
            title = p.name.replace('_', ' ').title()
            if meta_file.exists():
                try:
                    meta = json.loads(meta_file.read_text(encoding="utf-8"))
                    title = meta.get("title", title)
                except Exception:
                    pass
            
            slide_imgs = list((p / "slide_images").glob("slide-*.png")) if (p / "slide_images").exists() else []
            recordings = list((p / "recordings").glob("slide_*.wav")) if (p / "recordings").exists() else []
            
            # Calculate total duration
            total_duration = 0.0
            for wav in recordings:
                try:
                    res = subprocess.run([
                        "ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(wav)
                    ], capture_output=True, text=True, check=True)
                    total_duration += float(res.stdout.strip())
                except Exception:
                    pass
                    
            projects.append({
                "id": p.name,
                "title": title,
                "slideCount": len(slide_imgs),
                "recordedCount": len(recordings),
                "totalDuration": total_duration,
                "hasVideo": (p / "presentation_complete.mp4").exists()
            })
    return projects

def find_slide_image(proj_dir, idx):
    slide_dir = proj_dir / "slide_images"
    if not slide_dir.exists():
        return None
    candidates = [
        slide_dir / f"slide-{idx:02d}.png",
        slide_dir / f"slide-{idx}.png",
        slide_dir / f"slide-{idx:03d}.png",
        slide_dir / f"slide_{idx:02d}.png",
        slide_dir / f"slide_{idx}.png",
        slide_dir / f"slide_{idx:03d}.png",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

def parse_project_slides(project_id):
    proj_dir = PROJECTS_DIR / project_id
    if not proj_dir.exists():
        return []
    
    notes_file = proj_dir / "notes.md"
    content = notes_file.read_text(encoding="utf-8") if notes_file.exists() else ""
    
    timings = {}
    table_match = re.findall(r'\|\s*\*\*(\d+)\*\*\s*\|\s*([^|]+)\|\s*([0-9:]+)\s*\|\s*([0-9:]+)\s*\|', content)
    for num, topic, target, cum in table_match:
        timings[int(num)] = {"topic": topic.strip(), "target": target.strip(), "cumulative": cum.strip()}
    
    slide_images_dir = proj_dir / "slide_images"
    recordings_dir = proj_dir / "recordings"
    slide_images = sorted(slide_images_dir.glob("slide-*.png")) if slide_images_dir.exists() else []
    
    # Parse slide script blocks: ### Slide X or ### Slide X: Title
    script_by_num = {}
    topic_by_num = {}
    
    matches = list(re.finditer(r'###\s+Slide\s+(\d+)(?::\s*([^\n]*))?\n(.*?)(?=(?:###\s+Slide|\Z))', content, re.DOTALL))
    for m in matches:
        slide_num = int(m.group(1))
        raw_title = (m.group(2) or "").strip()
        body = m.group(3).split('---')[0].strip()
        
        cleaned_lines = []
        for line in body.split('\n'):
            l = line.strip()
            while l.startswith('>'):
                l = l[1:].strip()
            if l.startswith('*') and l.endswith('*') and len(l) > 1:
                l = l[1:-1].strip()
            if l.startswith('"') and l.endswith('"') and len(l) > 1:
                l = l[1:-1].strip()
            cleaned_lines.append(l)
        clean_script = "\n".join(cleaned_lines).strip()
        clean_script = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_script)
        clean_script = re.sub(r'\*(.*?)\*', r'\1', clean_script)
        
        script_by_num[slide_num] = clean_script
        if raw_title and raw_title.lower() != f"slide {slide_num}" and raw_title.lower() != "slide":
            topic_by_num[slide_num] = raw_title
        else:
            topic_by_num[slide_num] = ""

    slides = []
    num_to_iterate = max(len(slide_images), len(script_by_num))
    
    for idx in range(1, num_to_iterate + 1):
        custom_topic = topic_by_num.get(idx, "")
        timing_info = timings.get(idx, {"topic": custom_topic, "target": "1:00", "cumulative": ""})
        clean_script = script_by_num.get(idx, "")
        
        slide_img = find_slide_image(proj_dir, idx)
        img_name = slide_img.name if slide_img else f"slide-{idx:02d}.png"
        wav_name = f"slide_{idx:02d}.wav"
        has_audio = (recordings_dir / wav_name).exists()
        
        audio_duration = 0.0
        if has_audio:
            try:
                res = subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(recordings_dir / wav_name)
                ], capture_output=True, text=True, check=True)
                audio_duration = float(res.stdout.strip())
            except Exception:
                pass

        slides.append({
            "number": idx,
            "title": custom_topic or f"Slide {idx}",
            "topic": custom_topic,
            "targetTime": timing_info.get("target", "1:00"),
            "cumulative": timing_info.get("cumulative", ""),
            "script": clean_script,
            "image": f"/api/slide_image?project={project_id}&file={img_name}",
            "hasAudio": has_audio,
            "audioUrl": f"/api/audio?project={project_id}&file={wav_name}" if has_audio else None,
            "audioDuration": audio_duration
        })
    
    return slides

def update_slide_script_in_project(project_id, slide_num, new_text):
    proj_dir = PROJECTS_DIR / project_id
    notes_file = proj_dir / "notes.md"
    if not notes_file.exists():
        initial_content = f"# Speaker Notes - {project_id}\n\n"
        notes_file.write_text(initial_content, encoding="utf-8")
    
    content = notes_file.read_text(encoding="utf-8")
    
    pattern = rf'(###\s+Slide\s+{slide_num}(?::[^\n]*)?\n)(.*?)(?=(?:###\s+Slide|\Z))'
    match = re.search(pattern, content, flags=re.DOTALL)
    
    cleaned_lines = []
    for line in new_text.split('\n'):
        l = line.strip()
        while l.startswith('>'):
            l = l[1:].strip()
        cleaned_lines.append(l)
    
    formatted_body = "> " + "\n> ".join(cleaned_lines) + "\n"
    
    if match:
        new_content = re.sub(pattern, rf'\g<1>{formatted_body}', content, flags=re.DOTALL)
    else:
        new_content = content.rstrip() + f"\n\n---\n\n### Slide {slide_num}\n{formatted_body}"
        
    notes_file.write_text(new_content, encoding="utf-8")
    return True

def create_project_from_pdf(project_name, pdf_bytes, title=None):
    safe_id = re.sub(r'[^a-zA-Z0-9_-]', '_', project_name.lower().strip())
    if not safe_id:
        safe_id = "project_demo"
        
    if not pdf_bytes or len(pdf_bytes) == 0:
        raise ValueError("Le fichier PDF reçu est vide (0 octet).")

    proj_dir = PROJECTS_DIR / safe_id
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "slide_images").mkdir(exist_ok=True)
    (proj_dir / "recordings").mkdir(exist_ok=True)
    
    pdf_path = proj_dir / "slides.pdf"
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes)
        
    # Extract images with pdftoppm
    subprocess.run(["pdftoppm", "-png", "-r", "150", str(pdf_path), str(proj_dir / "slide_images" / "slide")], check=True)
    slide_images = sorted((proj_dir / "slide_images").glob("slide-*.png"))
    
    # Save metadata
    meta = {
        "id": safe_id,
        "title": title or project_name,
        "slideCount": len(slide_images)
    }
    (proj_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    
    # Create clean starter notes.md
    notes_path = proj_dir / "notes.md"
    if not notes_path.exists():
        notes_lines = [f"# {title or project_name}\n\n## Speaker Script\n\n"]
        for idx in range(1, len(slide_images) + 1):
            notes_lines.append(f"### Slide {idx}\n> Enter your speech script for Slide {idx} here...\n\n---\n\n")
        notes_path.write_text("".join(notes_lines), encoding="utf-8")
        
    return safe_id

def render_project_video(project_id):
    proj_dir = PROJECTS_DIR / project_id
    slides = parse_project_slides(project_id)
    if not slides:
        return False, "Aucune diapositive trouvée pour ce projet."
    
    temp_dir = proj_dir / "temp_segments"
    temp_dir.mkdir(parents=True, exist_ok=True)
    segment_files = []
    
    for s in slides:
        num = s["number"]
        img = find_slide_image(proj_dir, num)
        wav = proj_dir / "recordings" / f"slide_{num:02d}.wav"
        seg_mp4 = temp_dir / f"seg_{num:02d}.mp4"
        
        if not img or not img.exists():
            return False, f"Image manquante: slide-{num:02d}.png"
        
        if not wav.exists():
            return False, f"Audio manquant pour la Slide {num}. Veuillez l'enregistrer d'abord."
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-framerate", "30", "-i", str(img),
            "-i", str(wav),
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:white,format=yuv420p",
            "-c:v", "libx264", "-tune", "stillimage", "-preset", "fast",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(seg_mp4)
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode != 0:
            return False, f"Erreur ffmpeg segment {num}: {res.stderr.decode('utf-8')}"
        segment_files.append(seg_mp4)
        
    concat_txt = temp_dir / "concat_list.txt"
    with open(concat_txt, "w") as f:
        for seg in segment_files:
            f.write(f"file '{seg.resolve()}'\n")
            
    output_video = proj_dir / "presentation_complete.mp4"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-c", "copy",
        str(output_video)
    ]
    res = subprocess.run(concat_cmd, capture_output=True)
    if res.returncode != 0:
        return False, f"Erreur concaténation finale: {res.stderr.decode('utf-8')}"
    
    # Cleanup
    for seg in segment_files:
        if seg.exists(): seg.unlink()
    if concat_txt.exists(): concat_txt.unlink()
    if temp_dir.exists(): temp_dir.rmdir()
    
    return True, f"Vidéo générée avec succès : {output_video.name}"

class SlidePunchHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        
        if path == "/api/projects":
            projects = get_all_projects()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(projects, ensure_ascii=False).encode("utf-8"))
            return
            
        elif path == "/api/slides":
            proj_id = params.get("project", ["hdr_demo"])[0]
            slides = parse_project_slides(proj_id)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(json.dumps(slides, ensure_ascii=False).encode("utf-8"))
            return
            
        elif path == "/api/slide_image":
            proj_id = params.get("project", ["hdr_demo"])[0]
            filename = params.get("file", ["slide-01.png"])[0]
            file_path = PROJECTS_DIR / proj_id / "slide_images" / filename
            if not file_path.exists():
                m = re.search(r'(\d+)', filename)
                if m:
                    alt = find_slide_image(PROJECTS_DIR / proj_id, int(m.group(1)))
                    if alt and alt.exists():
                        file_path = alt
            if file_path.exists():
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Slide image not found")
                return

        elif path == "/api/audio":
            proj_id = params.get("project", ["hdr_demo"])[0]
            filename = params.get("file", ["slide_01.wav"])[0]
            file_path = PROJECTS_DIR / proj_id / "recordings" / filename
            if not file_path.exists():
                m = re.search(r'(\d+)', filename)
                if m:
                    idx = int(m.group(1))
                    for alt_name in [f"slide_{idx:02d}.wav", f"slide_{idx}.wav", f"slide_{idx:03d}.wav"]:
                        alt = PROJECTS_DIR / proj_id / "recordings" / alt_name
                        if alt.exists():
                            file_path = alt
                            break
            if not file_path.exists():
                self.send_error(404, "Audio file not found")
                return

            file_size = file_path.stat().st_size
            range_header = self.headers.get("Range")

            if range_header:
                m = re.match(r"bytes=(\d+)-(\d*)", range_header)
                if m:
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1

                    self.send_response(206)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()

                    with open(file_path, "rb") as f:
                        f.seek(start)
                        self.wfile.write(f.read(length))
                    return

            self.send_response(200)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        elif path == "/api/video":
            proj_id = params.get("project", ["hdr_demo"])[0]
            video_file = PROJECTS_DIR / proj_id / "presentation_complete.mp4"
            if video_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.end_headers()
                with open(video_file, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_error(404, "Video not yet generated")
                return

        elif path == "/" or path == "/index.html":
            html_file = WEB_DIR / "index.html"
            if html_file.exists():
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                with open(html_file, "rb") as f:
                    self.wfile.write(f.read())
                return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        content_length = int(self.headers.get("Content-Length", 0))
        
        if path == "/api/delete_audio":
            proj_id = params.get("project", [""])[0]
            slide_idx = int(params.get("slide", [1])[0])
            wav_file = PROJECTS_DIR / proj_id / "recordings" / f"slide_{slide_idx:02d}.wav"
            if wav_file.exists():
                wav_file.unlink()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
            return

        elif path == "/api/save_audio":
            post_data = self.rfile.read(content_length)
            proj_id = params.get("project", ["hdr_demo"])[0]
            slide_idx = int(params.get("slide", [1])[0])
            
            proj_dir = PROJECTS_DIR / proj_id
            rec_dir = proj_dir / "recordings"
            rec_dir.mkdir(parents=True, exist_ok=True)
            
            temp_input = rec_dir / f"temp_upload_{slide_idx}.dat"
            target_wav = rec_dir / f"slide_{slide_idx:02d}.wav"
            
            with open(temp_input, "wb") as f:
                f.write(post_data)
                
            try:
                subprocess.run([
                    "ffmpeg", "-y", "-i", str(temp_input),
                    "-c:a", "pcm_s16le", "-ar", "48000", str(target_wav)
                ], check=True, capture_output=True)
                if temp_input.exists(): temp_input.unlink()
                
                res = subprocess.run([
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(target_wav)
                ], capture_output=True, text=True, check=True)
                duration = float(res.stdout.strip())
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": True,
                    "slide": slide_idx,
                    "duration": duration,
                    "audioUrl": f"/api/audio?project={proj_id}&file=slide_{slide_idx:02d}.wav"
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        elif path == "/api/save_script":
            post_data = self.rfile.read(content_length).decode("utf-8")
            proj_id = params.get("project", ["hdr_demo"])[0]
            slide_idx = int(params.get("slide", [1])[0])
            
            try:
                data = json.loads(post_data)
                new_text = data.get("script", "")
            except Exception:
                new_text = post_data
                
            success = update_slide_script_in_project(proj_id, slide_idx, new_text)
            self.send_response(200 if success else 500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "slide": slide_idx}).encode("utf-8"))
            return

        elif path == "/api/projects/new":
            proj_name = params.get("name", ["Mon Projet"])[0]
            title = params.get("title", [proj_name])[0]
            pdf_bytes = self.rfile.read(content_length)
            
            try:
                safe_id = create_project_from_pdf(proj_name, pdf_bytes, title)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "projectId": safe_id}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        elif path == "/api/generate_video":
            proj_id = params.get("project", ["hdr_demo"])[0]
            try:
                success, msg = render_project_video(proj_id)
                self.send_response(200 if success else 500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": success,
                    "message": msg,
                    "videoUrl": f"/api/video?project={proj_id}"
                }).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": str(e)}).encode("utf-8"))
            return

        self.send_error(404)

def main():
    ensure_base_dirs()
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, SlidePunchHandler)
    url = f"http://localhost:{PORT}"
    print("\n" + "="*70)
    print("🎙️  SlidePunch — Studio d'Enregistrement Présentation Slide-par-Slide")
    print(f"👉 Interface Web : {url}")
    print(f"📁 Dossier Projets : {PROJECTS_DIR}")
    print("="*70 + "\n")
    print("Appuyez sur Ctrl+C pour arrêter le serveur.")
    
    try:
        webbrowser.open(url)
    except Exception:
        pass
        
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[SlidePunch] Arrêt du serveur.")
        httpd.server_close()

if __name__ == "__main__":
    main()

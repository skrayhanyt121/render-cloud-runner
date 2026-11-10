import os
import subprocess
import logging
import urllib.request
import json
import re
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger("VideoEngine")
TMP_DIR = "/tmp/ai_bot_videos"
os.makedirs(TMP_DIR, exist_ok=True)

class VideoEngine:
    @staticmethod
    def download_video(url: str, dest_path: str) -> bool:
        """Download video from URL (Messenger CDN or external link)."""
        logger.info(f"Downloading video from {url[:80]}... to {dest_path}")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(dest_path, "wb") as f:
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            size_mb = os.path.getsize(dest_path) / (1024 * 1024)
            logger.info(f"Downloaded video successfully: {size_mb:.2f} MB")
            return True
        except Exception as e:
            logger.error(f"Failed to download video: {e}")
            return False

    @staticmethod
    def edit_video(input_path: str, output_path: str, instruction: str = "") -> Tuple[bool, str]:
        """
        Executes FFmpeg operations based on user instruction:
        - 9:16 vertical crop with aesthetic blurred background (Reels/TikTok/Shorts)
        - Speed adjustments (1.25x, 1.5x, 2x)
        - Trimming / cut
        - High-quality H.264 compression with AAC audio
        """
        inst_lower = instruction.lower() if instruction else ""
        logger.info(f"Editing video {input_path} -> {output_path} with instruction: '{instruction}'")

        # 1. Check if user wants 9:16 reels / vertical format (default if reels or vertical mentioned)
        is_reels = any(k in inst_lower for k in ("reels", "reel", "9:16", "vertical", "tiktok", "shorts", "crop")) or not instruction

        if is_reels:
            # 9:16 vertical canvas with blurred background and centered crisp video
            vf = (
                "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:1[bg];"
                "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2"
            )
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex", vf,
                "-c:v", "libx264", "-preset", "fast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]
        elif "speed" in inst_lower or "2x" in inst_lower or "fast" in inst_lower:
            # Speed up 1.5x
            speed = 1.5
            if "2x" in inst_lower:
                speed = 2.0
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-filter_complex", f"[0:v]setpts=PTS/{speed}[v];[0:a]atempo={speed}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "26",
                output_path
            ]
        else:
            # General clean compression / remux
            cmd = [
                "ffmpeg", "-y", "-i", input_path,
                "-c:v", "libx264", "-preset", "fast", "-crf", "26",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path
            ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info("FFmpeg processing succeeded!")
                return True, "Video editing complete."
            else:
                err_msg = res.stderr[-500:] if res.stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg error: {err_msg}")
                return False, f"FFmpeg error: {err_msg}"
        except subprocess.TimeoutExpired:
            return False, "FFmpeg operation timed out after 120s."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def upload_to_catbox(file_path: str) -> Optional[str]:
        """Upload to catbox.moe for ultra-fast direct link hosting."""
        try:
            cmd = [
                "curl", "-s",
                "-F", "reqtype=fileupload",
                "-F", f"fileToUpload=@{file_path}",
                "https://catbox.moe/user/api.php"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            out = res.stdout.strip()
            if out.startswith("https://files.catbox.moe/"):
                return out
        except Exception as e:
            logger.error(f"Catbox upload failed: {e}")
        return None

    @staticmethod
    def upload_to_tmpfiles(file_path: str) -> Optional[str]:
        """Upload to tmpfiles.org as reliable fallback."""
        try:
            cmd = [
                "curl", "-s",
                "-F", f"file=@{file_path}",
                "https://tmpfiles.org/api/v1/upload"
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
            data = json.loads(res.stdout)
            if data.get("status") == "success":
                url = data.get("data", {}).get("url", "")
                # Convert view url https://tmpfiles.org/123/name to direct download url https://tmpfiles.org/dl/123/name
                if "tmpfiles.org/" in url:
                    url = url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
                return url
        except Exception as e:
            logger.error(f"Tmpfiles upload failed: {e}")
        return None

    @classmethod
    def deliver_video_decision(cls, output_path: str) -> Dict[str, Any]:
        """
        Decision engine:
        - If size <= 25MB: Send directly into Messenger chat
        - If size > 25MB: Upload to Catbox / Tmpfiles and deliver high-speed download link
        """
        size_bytes = os.path.getsize(output_path)
        size_mb = size_bytes / (1024 * 1024)
        logger.info(f"Processed video size: {size_mb:.2f} MB")

        if size_mb <= 25.0:
            return {
                "delivery": "direct",
                "file_path": output_path,
                "size_mb": round(size_mb, 2)
            }
        else:
            logger.info("Video is > 25MB. Uploading to high-speed file hosting...")
            url = cls.upload_to_catbox(output_path) or cls.upload_to_tmpfiles(output_path)
            return {
                "delivery": "link",
                "download_url": url,
                "size_mb": round(size_mb, 2)
            }

video_engine = VideoEngine()

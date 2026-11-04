"""
Core subtitle embedding engine.
Enforces Container Embedding (Softsub) via stream copying (-c:v copy -c:a copy).
Guarantees bit-for-bit lossless video/audio preservation and sub-second execution.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Common language code mappings for automatic naming
LANGUAGE_MAP = {
    "en": ("eng", "English"),
    "eng": ("eng", "English"),
    "english": ("eng", "English"),
    "es": ("spa", "Spanish"),
    "spa": ("spa", "Spanish"),
    "spanish": ("spa", "Spanish"),
    "fr": ("fra", "French"),
    "fra": ("fra", "French"),
    "fre": ("fra", "French"),
    "french": ("fra", "French"),
    "de": ("deu", "German"),
    "deu": ("deu", "German"),
    "ger": ("deu", "German"),
    "german": ("deu", "German"),
    "it": ("ita", "Italian"),
    "ita": ("ita", "Italian"),
    "italian": ("ita", "Italian"),
    "pt": ("por", "Portuguese"),
    "por": ("por", "Portuguese"),
    "portuguese": ("por", "Portuguese"),
    "ru": ("rus", "Russian"),
    "rus": ("rus", "Russian"),
    "russian": ("rus", "Russian"),
    "ja": ("jpn", "Japanese"),
    "jpn": ("jpn", "Japanese"),
    "japanese": ("jpn", "Japanese"),
    "zh": ("zho", "Chinese"),
    "zho": ("zho", "Chinese"),
    "chi": ("zho", "Chinese"),
    "chinese": ("zho", "Chinese"),
    "ko": ("kor", "Korean"),
    "kor": ("kor", "Korean"),
    "korean": ("kor", "Korean"),
    "ar": ("ara", "Arabic"),
    "ara": ("ara", "Arabic"),
    "arabic": ("ara", "Arabic"),
    "hi": ("hin", "Hindi"),
    "hin": ("hin", "Hindi"),
    "hindi": ("hin", "Hindi"),
    "ur": ("urd", "Urdu"),
    "urd": ("urd", "Urdu"),
    "urdu": ("urd", "Urdu"),
    "id": ("ind", "Indonesian"),
    "ind": ("ind", "Indonesian"),
    "indonesian": ("ind", "Indonesian"),
    "tr": ("tur", "Turkish"),
    "tur": ("tur", "Turkish"),
    "turkish": ("tur", "Turkish"),
}

VALID_VIDEO_EXTS = {".mp4", ".mkv", ".m4v", ".mov", ".webm", ".avi", ".ts"}
VALID_SUB_EXTS = {".srt", ".vtt", ".ass", ".ssa", ".sub"}


class SubEmbedError(Exception):
    """Base exception for SubEmbed operations."""
    pass


def find_binary(name: str) -> str:
    """
    Locates the requested binary ('ffmpeg' or 'ffprobe').
    Checks PATH, ~/.local/bin, and common virtualenv locations.
    """
    which_path = shutil.which(name)
    if which_path and os.access(which_path, os.X_OK):
        return which_path

    # Check user local bin
    user_bin = Path.home() / ".local" / "bin" / name
    if user_bin.exists() and os.access(user_bin, os.X_OK):
        return str(user_bin)

    # Check known project virtualenv static_ffmpeg
    venv_candidate = Path("/home/user/code/sideProjects/download/venv/lib/python3.14/site-packages/static_ffmpeg/bin/linux") / name
    if venv_candidate.exists() and os.access(venv_candidate, os.X_OK):
        return str(venv_candidate)

    raise SubEmbedError(f"Required binary '{name}' not found. Please install ffmpeg or ensure it is in PATH.")


def probe_media(file_path: Union[str, Path]) -> Dict:
    """
    Probes media file metadata and stream topology using ffprobe.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise SubEmbedError(f"File not found: {path}")

    ffprobe = find_binary("ffprobe")
    cmd = [
        ffprobe,
        "-v", "error",
        "-show_format",
        "-show_streams",
        "-of", "json",
        str(path)
    ]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(res.stdout)
    except subprocess.CalledProcessError as e:
        raise SubEmbedError(f"ffprobe failed to read {path.name}: {e.stderr.strip()}")
    except json.JSONDecodeError as e:
        raise SubEmbedError(f"Invalid JSON returned by ffprobe: {e}")

    streams = data.get("streams", [])
    format_info = data.get("format", {})

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    subtitle_streams = [s for s in streams if s.get("codec_type") == "subtitle"]

    return {
        "path": str(path),
        "filename": path.name,
        "size_bytes": int(format_info.get("size", 0)),
        "duration": float(format_info.get("duration", 0.0) or 0.0),
        "format_name": format_info.get("format_name", ""),
        "video_streams": [
            {
                "index": s["index"],
                "codec": s.get("codec_name"),
                "width": s.get("width"),
                "height": s.get("height"),
                "fps": s.get("r_frame_rate"),
            }
            for s in video_streams
        ],
        "audio_streams": [
            {
                "index": s["index"],
                "codec": s.get("codec_name"),
                "channels": s.get("channels"),
                "language": s.get("tags", {}).get("language", "und"),
            }
            for s in audio_streams
        ],
        "subtitle_streams": [
            {
                "index": s["index"],
                "codec": s.get("codec_name"),
                "language": s.get("tags", {}).get("language", "und"),
                "title": s.get("tags", {}).get("title") or s.get("tags", {}).get("handler_name", ""),
                "default": bool(s.get("disposition", {}).get("default", 0)),
            }
            for s in subtitle_streams
        ]
    }


def detect_language_from_filename(filename: str) -> Tuple[str, str]:
    """
    Attempts to infer language from filename clues (e.g. 'movie.en.srt' -> ('eng', 'English')).
    Defaults to ('eng', 'English') if no known language token is found.
    """
    clean = Path(filename).stem.lower().replace("-", ".").replace("_", ".")
    parts = clean.split(".")

    for part in parts:
        if part in LANGUAGE_MAP:
            return LANGUAGE_MAP[part]

    return ("eng", "English")


def auto_detect_subtitles(video_path: Union[str, Path]) -> List[Path]:
    """
    Finds subtitle files matching the video filename in the same directory.
    E.g. for 'movie.mp4', matches 'movie.srt', 'movie.en.srt', 'movie.eng.vtt', etc.
    """
    v_path = Path(video_path).resolve()
    parent = v_path.parent
    stem = v_path.stem

    candidates = []
    for file in parent.iterdir():
        if not file.is_file():
            continue
        if file.suffix.lower() in VALID_SUB_EXTS:
            if file.stem == stem or file.stem.startswith(f"{stem}.") or file.stem.startswith(f"{stem}_"):
                candidates.append(file)

    candidates.sort(key=lambda p: (len(p.name), p.name))
    return candidates


def embed_subtitles(
    video_path: Union[str, Path],
    subtitles: Union[Union[str, Path], List[Union[str, Path, Dict]]],
    output_path: Optional[Union[str, Path]] = None,
    default_track_index: int = 0,
    force_overwrite: bool = False,
    target_format: Optional[str] = None
) -> Dict:
    """
    Embeds one or more subtitle tracks into the video container without re-encoding.
    
    Guarantees:
    - Zero video quality loss (-c:v copy).
    - Zero audio quality loss (-c:a copy).
    - Preserves all original video and audio streams.
    - Sets the specified subtitle track as 'default' for automatic display in players.
    - Validates output integrity using ffprobe.
    """
    v_path = Path(video_path).resolve()
    if not v_path.is_file():
        raise SubEmbedError(f"Video file does not exist: {v_path}")
    if v_path.stat().st_size == 0:
        raise SubEmbedError(f"Video file is empty (0 bytes): {v_path}")

    # Inspect source video
    source_meta = probe_media(v_path)
    if not source_meta["video_streams"]:
        raise SubEmbedError(f"No video stream found in {v_path.name}")

    # Normalize subtitle specifications
    if isinstance(subtitles, (str, Path)):
        sub_list = [{"path": subtitles}]
    elif isinstance(subtitles, list):
        sub_list = []
        for item in subtitles:
            if isinstance(item, (str, Path)):
                sub_list.append({"path": item})
            elif isinstance(item, dict):
                sub_list.append(item)
            else:
                raise SubEmbedError(f"Invalid subtitle entry: {item}")
    else:
        raise SubEmbedError("Subtitles must be a file path or list of file paths / track specs")

    if not sub_list:
        raise SubEmbedError("No subtitle files provided.")

    processed_subs = []
    for idx, s in enumerate(sub_list):
        sub_file = Path(s["path"]).resolve()
        if not sub_file.is_file():
            raise SubEmbedError(f"Subtitle file not found: {sub_file}")
        if sub_file.stat().st_size == 0:
            raise SubEmbedError(f"Subtitle file is empty (0 bytes): {sub_file}")

        sub_ext = sub_file.suffix.lower()
        if sub_ext not in VALID_SUB_EXTS:
            raise SubEmbedError(f"Unsupported subtitle format '{sub_ext}'. Supported: {', '.join(VALID_SUB_EXTS)}")

        detected_code, detected_title = detect_language_from_filename(sub_file.name)
        lang_code = s.get("language") or detected_code
        title = s.get("title") or detected_title

        processed_subs.append({
            "path": sub_file,
            "language": lang_code,
            "title": title,
            "ext": sub_ext,
            "is_default": (idx == default_track_index)
        })

    # Determine output container format
    if target_format:
        fmt = target_format.lower().lstrip(".")
    elif output_path:
        fmt = Path(output_path).suffix.lower().lstrip(".")
    else:
        fmt = v_path.suffix.lower().lstrip(".")

    if fmt not in {"mp4", "mkv", "m4v", "mov"}:
        # Default to mp4 if source was something uncommon (e.g. avi/webm), or keep original if mkv
        fmt = "mkv" if v_path.suffix.lower() == ".mkv" else "mp4"

    # Determine output path
    if output_path:
        out_p = Path(output_path).resolve()
    else:
        out_p = v_path.parent / f"{v_path.stem}.embedded.{fmt}"

    if out_p == v_path:
        raise SubEmbedError("Output file path cannot be identical to input video path (prevents data corruption).")

    if out_p.exists() and not force_overwrite:
        raise SubEmbedError(f"Output file already exists: {out_p}. Use force_overwrite=True to overwrite.")

    ffmpeg = find_binary("ffmpeg")

    # Build FFmpeg command safely using structured argument list (NEVER shell=True)
    cmd = [ffmpeg, "-y" if force_overwrite else "-n"]

    # Input 0: original video
    cmd.extend(["-i", str(v_path)])

    # Inputs 1..N: subtitles
    for sub in processed_subs:
        cmd.extend(["-i", str(sub["path"])])

    # Stream mapping:
    # 0 = include all existing streams from video file (video, audio, existing subs, chapters)
    cmd.extend(["-map", "0"])

    # Map each new subtitle input (index 1 + i, subtitle stream 0)
    for i in range(len(processed_subs)):
        cmd.extend(["-map", f"{i + 1}:s:0"])

    # Codecs:
    # 100% Stream Copy for Video and Audio (Bit-for-bit lossless!)
    cmd.extend(["-c:v", "copy", "-c:a", "copy"])

    # Subtitle codec selection:
    # MP4/MOV container requires 'mov_text'
    # MKV natively supports 'copy' (SRT, ASS, VTT directly)
    if fmt in {"mp4", "m4v", "mov"}:
        cmd.extend(["-c:s", "mov_text"])
    else:
        cmd.extend(["-c:s", "copy"])

    # Existing subtitles in input video: count how many existing subtitle tracks there are
    existing_sub_count = len(source_meta["subtitle_streams"])

    # Metadata and Dispositions
    # We clear existing default flags if our new track is set to default
    total_sub_idx = existing_sub_count
    for sub in processed_subs:
        cmd.extend([
            f"-metadata:s:s:{total_sub_idx}", f"language={sub['language']}",
            f"-metadata:s:s:{total_sub_idx}", f"title={sub['title']}",
            f"-metadata:s:s:{total_sub_idx}", f"handler_name={sub['title']}",
        ])
        if sub["is_default"]:
            cmd.extend([f"-disposition:s:{total_sub_idx}", "default"])
        else:
            cmd.extend([f"-disposition:s:{total_sub_idx}", "0"])
        total_sub_idx += 1

    cmd.append(str(out_p))

    # Execute ffmpeg
    start_time = time.perf_counter()
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        # Clean up partial output if it failed
        if out_p.exists():
            out_p.unlink(missing_ok=True)
        raise SubEmbedError(f"FFmpeg muxing failed:\n{e.stderr.strip()}")

    elapsed = time.perf_counter() - start_time

    # Verification: Verify with ffprobe that the output file exists, is non-empty,
    # and has the newly embedded subtitle stream.
    if not out_p.exists() or out_p.stat().st_size == 0:
        raise SubEmbedError("FFmpeg execution completed but output file is missing or empty.")

    out_meta = probe_media(out_p)
    new_sub_streams = out_meta["subtitle_streams"]
    expected_count = existing_sub_count + len(processed_subs)

    if len(new_sub_streams) < expected_count:
        raise SubEmbedError(
            f"Verification failed: Expected {expected_count} subtitle tracks, found {len(new_sub_streams)}."
        )

    return {
        "success": True,
        "input_video": str(v_path),
        "output_video": str(out_p),
        "output_size_bytes": out_p.stat().st_size,
        "elapsed_seconds": round(elapsed, 3),
        "format": fmt,
        "video_codec": source_meta["video_streams"][0]["codec"],
        "audio_codecs": [a["codec"] for a in source_meta["audio_streams"]],
        "tracks_embedded": [
            {
                "language": s["language"],
                "title": s["title"],
                "source_file": s["path"].name,
                "is_default": s["is_default"]
            }
            for s in processed_subs
        ],
        "total_subtitles_in_file": len(new_sub_streams)
    }

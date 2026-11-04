"""
Command-Line Interface for SubEmbed.
Fast, lossless container softsub muxer (in-place embedding, zero quality loss).
"""

import argparse
import sys
from pathlib import Path

from .core import (
    SubEmbedError,
    auto_detect_subtitles,
    detect_language_from_filename,
    embed_subtitles,
    probe_media,
)

# ANSI terminal formatting
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"


def format_size(bytes_val: int) -> str:
    """Formats bytes into human readable MB/GB string."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_val < 1024.0:
            return f"{bytes_val:3.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


def print_info(video_path: Path):
    """Prints media stream details in a clean format."""
    try:
        info = probe_media(video_path)
    except SubEmbedError as e:
        print(f"{RED}Error probing file:{RESET} {e}")
        return 1

    print(f"\n{BOLD}File:{RESET} {CYAN}{info['filename']}{RESET}")
    print(f"{BOLD}Size:{RESET} {format_size(info['size_bytes'])}  |  {BOLD}Duration:{RESET} {info['duration']:.2f}s  |  {BOLD}Container:{RESET} {info['format_name']}")

    print(f"\n{BOLD}Video Streams:{RESET}")
    for v in info["video_streams"]:
        print(f"  • #{v['index']} [Video]: Codec={v['codec']}  Resolution={v['width']}x{v['height']}  FPS={v['fps']}")

    print(f"\n{BOLD}Audio Streams:{RESET}")
    for a in info["audio_streams"]:
        print(f"  • #{a['index']} [Audio]: Codec={a['codec']}  Channels={a['channels']}  Lang={a['language']}")

    print(f"\n{BOLD}Embedded Subtitle Tracks:{RESET}")
    if info["subtitle_streams"]:
        for s in info["subtitle_streams"]:
            default_marker = f"{GREEN}[DEFAULT]{RESET}" if s["default"] else ""
            title = f" '{s['title']}'" if s['title'] else ""
            print(f"  • #{s['index']} [Sub]: Codec={s['codec']}  Lang={s['language']}{title} {default_marker}")
    else:
        print(f"  {DIM}(No embedded subtitle tracks found){RESET}")
    print()
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="subembed",
        description="SubEmbed: Lossless Container Subtitle Embedder (embeds directly into video with zero quality loss)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  subembed movie.mp4 subtitles.srt             # Embeds directly into movie.mp4 (in-place)
  subembed movie.mp4                           # Auto-detects movie.srt in the same directory
  subembed movie.mp4 subtitles.srt -l eng -t "English"
  subembed movie.mp4 subtitles.srt -o new.mp4  # Save to separate file instead of in-place
  subembed --batch *.mp4                       # In-place embed subtitles for all videos
  subembed --info movie.mp4                    # Inspect streams and existing subtitles
        """
    )

    parser.add_argument("video", nargs="?", help="Path to video file (.mp4, .mkv, .mov, etc.)")
    parser.add_argument("subtitles", nargs="*", help="Path to subtitle file(s) (.srt, .vtt, .ass)")
    parser.add_argument("-o", "--output", help="Optional output path (default: in-place, replaces original video)")
    parser.add_argument("-l", "--lang", help="Subtitle language code (e.g. eng, spa, fra, jpn)")
    parser.add_argument("-t", "--title", help="Subtitle track title (e.g. 'English', 'Full Subtitles')")
    parser.add_argument("-f", "--format", choices=["mp4", "mkv", "mov"], help="Force specific container format")
    parser.add_argument("-y", "--force", action="store_true", help="Force overwrite output file if writing to new file")
    parser.add_argument("--info", action="store_true", help="Show stream & subtitle info for the input video and exit")
    parser.add_argument("--batch", action="store_true", help="Batch mode: process multiple videos with auto-detected subtitles")

    args = parser.parse_args()

    if not args.video:
        parser.print_help()
        return 1

    video_path = Path(args.video)

    # Info Mode
    if args.info:
        return print_info(video_path)

    # Batch Mode
    if args.batch:
        videos_to_process = [video_path]
        if args.subtitles:
            videos_to_process.extend([Path(p) for p in args.subtitles])

        print(f"\n{BOLD}{CYAN}=== SubEmbed Batch Processing (In-Place) ==={RESET}\n")
        success_count = 0
        for v in videos_to_process:
            if not v.is_file():
                continue
            candidates = auto_detect_subtitles(v)
            if not candidates:
                print(f"[{YELLOW}SKIP{RESET}] {v.name}: No matching subtitle file found in directory.")
                continue

            sub_target = candidates[0]
            print(f"[{CYAN}EMBEDDING{RESET}] {v.name} + {sub_target.name}...")
            try:
                res = embed_subtitles(
                    video_path=v,
                    subtitles=[sub_target],
                    output_path=args.output,
                    force_overwrite=args.force,
                    target_format=args.format
                )
                print(f"[{GREEN}DONE{RESET}] Updated: {BOLD}{Path(res['output_video']).name}{RESET} in {res['elapsed_seconds']}s ({format_size(res['output_size_bytes'])})")
                success_count += 1
            except SubEmbedError as e:
                print(f"[{RED}FAILED{RESET}] {v.name}: {e}")

        print(f"\n{BOLD}Batch finished:{RESET} {success_count} video(s) updated in-place.\n")
        return 0

    # Single Video Mode
    subs = list(args.subtitles)
    if not subs:
        # Attempt auto-detection in same directory
        candidates = auto_detect_subtitles(video_path)
        if candidates:
            subs = [candidates[0]]
            print(f"{DIM}Auto-detected subtitle file:{RESET} {CYAN}{candidates[0].name}{RESET}")
        else:
            print(f"{RED}Error:{RESET} No subtitle file provided, and no matching subtitle found in {video_path.parent}")
            return 1

    # Prepare subtitle track metadata
    sub_specs = []
    for s_path in subs:
        s_p = Path(s_path)
        det_code, det_name = detect_language_from_filename(s_p.name)
        sub_specs.append({
            "path": s_p,
            "language": args.lang or det_code,
            "title": args.title or det_name
        })

    print(f"\n{BOLD}{CYAN}SubEmbed{RESET} - Embedding subtitles into container...")
    print(f"  • Video:     {video_path.name}")
    for spec in sub_specs:
        print(f"  • Subtitle:  {spec['path'].name} [Lang: {spec['language']}, Title: '{spec['title']}']")

    try:
        result = embed_subtitles(
            video_path=video_path,
            subtitles=sub_specs,
            output_path=args.output,
            force_overwrite=args.force,
            target_format=args.format
        )
    except SubEmbedError as e:
        print(f"\n{RED}Error:{RESET} {e}\n")
        return 1

    out_file = Path(result["output_video"])
    action_text = "Updated original video in-place" if result["in_place"] else "Saved to output"
    print(f"\n{GREEN}{BOLD}✓ Subtitles embedded successfully!{RESET}")
    print(f"  • Target:       {BOLD}{out_file}{RESET} ({action_text})")
    print(f"  • File size:    {format_size(result['output_size_bytes'])}")
    print(f"  • Elapsed time: {result['elapsed_seconds']}s (Zero quality loss, stream-copied)")
    print(f"  • Video codec:  {result['video_codec']} (untouched)")
    print(f"  • Total subs:   {result['total_subtitles_in_file']} tracks in container\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

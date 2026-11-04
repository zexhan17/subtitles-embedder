# SubEmbed

**Lossless Container Subtitle Embedder (Softsub)**  
Zero quality loss, 100% stream copy, sub-second execution.

SubEmbed embeds subtitle tracks (`.srt`, `.vtt`, `.ass`, `.ssa`) directly into video containers (`.mp4`, `.mkv`, `.mov`) so your subtitles travel with the video as a single standalone file.

---

## Key Highlights

- **100% Original Video & Audio Quality**: Uses FFmpeg stream copying (`-c:v copy -c:a copy`). The video is **never re-encoded**, preserving original bitrate, frame rate, resolution, and HDR/color space.
- **Blazing Fast**: Processes a full 4 GB movie in **under 1–2 seconds** (limited only by your SSD/disk speed).
- **Auto-Play Subtitles**: Configures the embedded subtitle track as the **Default** stream (`disposition:default`), so players like VLC, MPV, QuickTime, and TV media centers display subtitles automatically upon playback.
- **Auto-Detection**: Select a video file, and SubEmbed automatically searches for matching `.srt` or `.vtt` files in the same directory.
- **Zero Third-Party Dependencies**: Pure Python standard library + static FFmpeg.
- **Dual Interface**:
  - **Native Desktop GUI**: Modern, clean, dark-themed interface with browse buttons and instant feedback.
  - **Terminal CLI**: One-liner commands, auto-detection, stream inspection, and batch processing.

---

## How to Use

### 1. Launching the GUI

Launch it from your terminal or application launcher:

```bash
subembed --gui
# or simply:
subembed-gui
```

- Select your video file.
- It will automatically detect any matching subtitle file in the same folder (or click "Browse Sub..." to pick one).
- Click **⚡ Embed Subtitles Losslessly**.
- In less than a second, you get a `.embedded.mp4` (or `.mkv`) file with the subtitle track baked into the container.

---

### 2. Command-Line Usage (CLI)

#### Basic (Auto-detects matching subtitle):
```bash
subembed movie.mp4
# Finds movie.srt or movie.en.srt in the same directory and embeds it!
```

#### Explicit video + subtitle:
```bash
subembed movie.mp4 subtitles.srt
```

#### Specify Language & Track Title:
```bash
subembed movie.mp4 subtitles.srt -l eng -t "English [SDH]"
```

#### Choose MKV container:
```bash
subembed movie.mp4 subtitles.srt -o movie.mkv
```

#### Inspect streams in a video:
```bash
subembed --info movie.mp4
```

#### Batch process all videos in a folder:
```bash
subembed --batch *.mp4
```

---

## Supported Formats

- **Video Containers**: `.mp4`, `.mkv`, `.mov`, `.m4v`, `.webm`, `.avi`
- **Subtitle Formats**: `.srt`, `.vtt`, `.ass`, `.ssa`, `.sub`

---

## Running Tests

```bash
python3 -m unittest discover -s tests
```

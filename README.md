# SubEmbed

**Fast, Lossless Container Subtitle Embedder (In-Place Softsub)**  
Zero video/audio re-encoding, 100% original quality, embeds directly into the original file.

SubEmbed embeds subtitle tracks (`.srt`, `.vtt`, `.ass`, `.ssa`) directly into video containers (`.mp4`, `.mkv`, `.mov`) so your subtitles travel with the video as a single standalone file.

---

## Key Highlights

- **In-Place Replacement**: Replaces the original video file directly. No leftover `.embedded.mp4` duplicates.
- **Safe & Atomic**: Performs muxing to a temporary staging file on the same filesystem and verifies all streams with `ffprobe` before atomically replacing the original. If anything goes wrong, the original file is left completely untouched.
- **100% Original Video & Audio Quality**: Stream copied (`-c:v copy -c:a copy`). Zero compression artifacts, preserves original bitrate, frame rate, resolution, and HDR metadata.
- **Sub-Second Execution**: Embeds into a full-length 4 GB video in ~1 second.
- **Auto-Play Subtitles**: Configures the embedded subtitle track as the **Default** stream (`disposition:default`), so players like VLC, MPV, and QuickTime display subtitles automatically upon playback.
- **Auto-Detection**: Give it just the video name (`subembed movie.mp4`), and it automatically finds the matching `.srt` in the same directory!

---

## How to Use

### 1. Basic In-Place Embedding
Embeds `subtitles.srt` directly into `movie.mp4`:
```bash
subembed movie.mp4 subtitles.srt
```

### 2. Auto-Detect Subtitles
If your subtitle file has a matching name (e.g., `movie.srt` or `movie.en.srt`), just give the video:
```bash
subembed movie.mp4
```

### 3. Set Custom Language & Track Title
```bash
subembed movie.mp4 subtitles.srt -l eng -t "English [SDH]"
```

### 4. Batch Process All Videos in a Folder
Embeds matching subtitles into each video in-place:
```bash
subembed --batch *.mp4
```

### 5. Inspect Streams
Check video codecs, audio codecs, and embedded subtitle tracks:
```bash
subembed --info movie.mp4
```

### 6. Optional: Save to a New File
If you ever want to keep the original and write to a new file instead:
```bash
subembed movie.mp4 subtitles.srt -o output.mp4
```

---

## Running Tests

```bash
python3 -m unittest discover -s tests
```

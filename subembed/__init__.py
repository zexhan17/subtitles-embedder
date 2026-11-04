"""
SubEmbed - Lossless Container Subtitle Embedder.
Embeds subtitles into video containers (MP4, MKV) without re-encoding.
"""

from .core import (
    SubEmbedError,
    probe_media,
    auto_detect_subtitles,
    embed_subtitles,
    detect_language_from_filename
)

__version__ = "1.0.0"
__all__ = [
    "SubEmbedError",
    "probe_media",
    "auto_detect_subtitles",
    "embed_subtitles",
    "detect_language_from_filename"
]


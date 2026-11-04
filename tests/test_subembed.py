"""
Test suite for SubEmbed.
Includes in-place embedding verification, positive functional tests,
stream integrity checks, and mandatory adversarial/refusal tests.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from subembed.core import (
    SubEmbedError,
    auto_detect_subtitles,
    detect_language_from_filename,
    embed_subtitles,
    probe_media,
)


class TestSubEmbed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_dir = Path(tempfile.mkdtemp(prefix="subembed_test_"))
        cls.sample_video = cls.test_dir / "sample_video.mp4"
        cls.sample_sub_srt = cls.test_dir / "sample_video.srt"
        cls.sample_sub_vtt = cls.test_dir / "sample_video.en.vtt"

        # Generate a lightweight 2-second valid MP4 file (H.264 + AAC)
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=15",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-c:a", "aac",
            str(cls.sample_video)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # Generate sample SRT
        cls.sample_sub_srt.write_text(
            "1\n00:00:00,100 --> 00:00:01,000\nHello World\n\n"
            "2\n00:00:01,100 --> 00:00:01,900\nSubEmbed Test Subtitle\n",
            encoding="utf-8"
        )

        # Generate sample VTT
        cls.sample_sub_vtt.write_text(
            "WEBVTT\n\n00:00.100 --> 00:01.000\nHello WebVTT\n",
            encoding="utf-8"
        )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_probe_media(self):
        info = probe_media(self.sample_video)
        self.assertEqual(info["filename"], "sample_video.mp4")
        self.assertGreater(len(info["video_streams"]), 0)
        self.assertGreater(len(info["audio_streams"]), 0)
        self.assertEqual(info["video_streams"][0]["codec"], "h264")
        self.assertEqual(info["audio_streams"][0]["codec"], "aac")

    def test_detect_language_from_filename(self):
        self.assertEqual(detect_language_from_filename("movie.en.srt"), ("eng", "English"))
        self.assertEqual(detect_language_from_filename("film.es.vtt"), ("spa", "Spanish"))
        self.assertEqual(detect_language_from_filename("show.ja.ass"), ("jpn", "Japanese"))
        self.assertEqual(detect_language_from_filename("series.french.srt"), ("fra", "French"))
        self.assertEqual(detect_language_from_filename("generic.srt"), ("eng", "English"))

    def test_auto_detect_subtitles(self):
        candidates = auto_detect_subtitles(self.sample_video)
        candidate_names = [c.name for c in candidates]
        self.assertIn("sample_video.srt", candidate_names)
        self.assertIn("sample_video.en.vtt", candidate_names)

    def test_embed_in_place_mp4(self):
        """Tests that omitting output_path embeds directly into the original file."""
        target_video = self.test_dir / "target_inplace.mp4"
        shutil.copy(self.sample_video, target_video)

        # Before embedding, verify 0 subtitle streams
        before_info = probe_media(target_video)
        self.assertEqual(len(before_info["subtitle_streams"]), 0)

        res = embed_subtitles(
            video_path=target_video,
            subtitles=self.sample_sub_srt
        )

        self.assertTrue(res["success"])
        self.assertTrue(res["in_place"])
        self.assertEqual(res["output_video"], str(target_video))

        # After embedding, target_video itself now contains the subtitle stream
        after_info = probe_media(target_video)
        self.assertEqual(after_info["video_streams"][0]["codec"], "h264")
        self.assertEqual(after_info["audio_streams"][0]["codec"], "aac")
        self.assertEqual(len(after_info["subtitle_streams"]), 1)
        self.assertEqual(after_info["subtitle_streams"][0]["codec"], "mov_text")
        self.assertTrue(after_info["subtitle_streams"][0]["default"])

        # Ensure no temporary staging files were left behind
        temp_files = list(self.test_dir.glob("*__subembed_tmp__*"))
        self.assertEqual(len(temp_files), 0)

    def test_convert_mkv_to_mp4_in_place(self):
        """Tests converting MKV to MP4 container in-place with target_format='mp4'."""
        mkv_target = self.test_dir / "movie_convert.mkv"
        cmd = [
            "ffmpeg", "-y",
            "-i", str(self.sample_video),
            "-c:v", "copy", "-c:a", "copy",
            str(mkv_target)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        res = embed_subtitles(
            video_path=mkv_target,
            subtitles=self.sample_sub_srt,
            target_format="mp4"
        )
        self.assertTrue(res["success"])
        self.assertFalse(mkv_target.exists(), "Old MKV should be deleted")
        mp4_target = mkv_target.with_suffix(".mp4")
        self.assertTrue(mp4_target.exists(), "New MP4 should exist")
        out_info = probe_media(mp4_target)
        self.assertEqual(len(out_info["subtitle_streams"]), 1)

    def test_embed_mp4_lossless_custom_output(self):
        out_file = self.test_dir / "output_custom.mp4"
        if out_file.exists():
            out_file.unlink()

        res = embed_subtitles(
            video_path=self.sample_video,
            subtitles=self.sample_sub_srt,
            output_path=out_file,
            force_overwrite=True
        )

        self.assertTrue(res["success"])
        self.assertFalse(res["in_place"])
        self.assertTrue(out_file.exists())
        self.assertGreater(out_file.stat().st_size, 0)
        self.assertEqual(res["video_codec"], "h264")

        out_info = probe_media(out_file)
        self.assertEqual(out_info["video_streams"][0]["codec"], "h264")
        self.assertEqual(out_info["audio_streams"][0]["codec"], "aac")
        self.assertEqual(len(out_info["subtitle_streams"]), 1)
        self.assertEqual(out_info["subtitle_streams"][0]["codec"], "mov_text")

    def test_embed_mkv_container(self):
        out_file = self.test_dir / "output_test.mkv"
        if out_file.exists():
            out_file.unlink()

        res = embed_subtitles(
            video_path=self.sample_video,
            subtitles=self.sample_sub_srt,
            output_path=out_file,
            target_format="mkv",
            force_overwrite=True
        )

        self.assertTrue(res["success"])
        self.assertTrue(out_file.exists())
        out_info = probe_media(out_file)
        self.assertEqual(out_info["video_streams"][0]["codec"], "h264")
        self.assertEqual(len(out_info["subtitle_streams"]), 1)
        self.assertEqual(out_info["subtitle_streams"][0]["codec"], "subrip")

    def test_special_characters_in_filenames(self):
        """Ensures safe argument boundary isolation without shell injection."""
        tricky_video = self.test_dir / "movie [2026] (HD) 'director$cut' #1.mp4"
        tricky_sub = self.test_dir / "movie [2026] (HD) 'director$cut' #1.en.srt"
        shutil.copy(self.sample_video, tricky_video)
        shutil.copy(self.sample_sub_srt, tricky_sub)

        res = embed_subtitles(
            video_path=tricky_video,
            subtitles=tricky_sub
        )
        self.assertTrue(res["success"])
        self.assertTrue(tricky_video.exists())

    # --- Refusal / Negative Adversarial Tests ---

    def test_refuse_nonexistent_video(self):
        with self.assertRaises(SubEmbedError) as ctx:
            embed_subtitles(self.test_dir / "ghost_video.mp4", self.sample_sub_srt)
        self.assertIn("does not exist", str(ctx.exception))

    def test_refuse_empty_video(self):
        empty_v = self.test_dir / "zero_byte.mp4"
        empty_v.write_bytes(b"")
        with self.assertRaises(SubEmbedError) as ctx:
            embed_subtitles(empty_v, self.sample_sub_srt)
        self.assertIn("empty", str(ctx.exception))

    def test_refuse_nonexistent_subtitle(self):
        with self.assertRaises(SubEmbedError) as ctx:
            embed_subtitles(self.sample_video, self.test_dir / "ghost_sub.srt")
        self.assertIn("not found", str(ctx.exception))

    def test_refuse_empty_subtitle(self):
        empty_s = self.test_dir / "zero_byte.srt"
        empty_s.write_bytes(b"")
        with self.assertRaises(SubEmbedError) as ctx:
            embed_subtitles(self.sample_video, empty_s)
        self.assertIn("empty", str(ctx.exception))

    def test_refuse_unsupported_subtitle_format(self):
        bad_sub = self.test_dir / "bad.txt"
        bad_sub.write_text("Not a sub")
        with self.assertRaises(SubEmbedError) as ctx:
            embed_subtitles(self.sample_video, bad_sub)
        self.assertIn("Unsupported subtitle format", str(ctx.exception))

    def test_refuse_overwrite_when_not_forced(self):
        existing_out = self.test_dir / "pre_existing.mp4"
        existing_out.write_bytes(b"123")
        with self.assertRaises(SubEmbedError) as ctx:
            embed_subtitles(
                video_path=self.sample_video,
                subtitles=self.sample_sub_srt,
                output_path=existing_out,
                force_overwrite=False
            )
        self.assertIn("already exists", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

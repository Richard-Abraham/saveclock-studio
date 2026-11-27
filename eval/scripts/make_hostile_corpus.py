"""A deterministic corpus of hostile "audio" files for the security pass (plan 008, T-2.14).

Every file is generated here, never downloaded, and goes under `.data/hostile/` (git-ignored); the
HLS playlists name a listener on 127.0.0.1 whose port is given at run time. The JSON manifest it
prints lists every file with its category and how to upload it: `upload_name` is the `X-Filename`
(hostile names cannot be written to disk), `content_type` the upload's Content-Type.

usage: make_hostile_corpus.py OUT_DIR [--port 9] [--ffmpeg .data/ffmpeg/ffmpeg]

The few files that need a muxer (five streams, a 3 MB embedded picture, a video stream) are made by
the pinned FFmpeg from synthetic inputs; without it the script stops instead of writing fewer files.
"""

import argparse
import json
import random
import struct
import subprocess
import sys
import wave
import zlib
from pathlib import Path
from typing import Any

SEED = 8
MIN_FILES = 60
Entry = dict[str, Any]


def wav_header(
    data_len: int, *, channels: int = 1, rate: int = 8000, bits: int = 16, riff_len: int | None = None
) -> bytes:
    block = channels * bits // 8
    riff = riff_len if riff_len is not None else 36 + data_len
    return (
        b"RIFF"
        + struct.pack("<I", riff & 0xFFFFFFFF)
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * block, block, bits)
        + b"data"
        + struct.pack("<I", data_len & 0xFFFFFFFF)
    )


def silent_wav(path: Path, seconds: int = 16, rate: int = 8000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * rate * seconds)


def flac_header(total_samples: int) -> bytes:
    packed = (44100 << 44) | (1 << 41) | (15 << 36) | total_samples
    info = struct.pack(">HH", 4096, 4096) + b"\x00\x00\x00\x00\x00\x00" + struct.pack(">Q", packed)
    return b"fLaC" + bytes([0x80, 0, 0, 34]) + info + bytes(16)


def ogg_pages(n: int) -> bytes:
    page = b"OggS" + bytes([0, 0]) + bytes(8) + struct.pack("<III", 1, 0, 0) + bytes([0])
    return b"".join(page[:18] + struct.pack("<I", i) + page[22:] for i in range(n))


def adts(frames: int, profile: int) -> bytes:
    header = bytes([0xFF, 0xF1, (profile << 6) | 0x10, 0x80, 0x0B, 0xFF, 0xFC])
    return (header + bytes(range(64))) * frames


def noise_png(rng: random.Random, size: int) -> bytes:
    """A PNG of incompressible bytes, about `size` bytes: the embedded-picture bomb."""
    side = int((size / 3) ** 0.5)
    raw = b"".join(b"\x00" + rng.randbytes(side * 3) for _ in range(side))

    def chunk(tag: bytes, body: bytes) -> bytes:
        crc = zlib.crc32(tag + body) & 0xFFFFFFFF
        return struct.pack(">I", len(body)) + tag + body + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", side, side, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def ffmpeg(binary: str, *args: str) -> None:
    done = subprocess.run(  # noqa: S603 - fixed argument list, the pinned binary
        [binary, "-v", "error", "-y", *args], capture_output=True, check=False, timeout=120
    )
    if done.returncode != 0:
        sys.exit(f"ffmpeg failed: {done.stderr.decode(errors='replace')[:300]}")


class Writer:
    def __init__(self, out: Path) -> None:
        self.out, self.entries = out, []
        out.mkdir(parents=True, exist_ok=True)

    def add(
        self,
        category: str,
        name: str,
        data: bytes | None = None,
        *,
        upload_name: str | None = None,
        content_type: str = "audio/wav",
    ) -> Path:
        path = self.out / name
        if data is not None:
            path.write_bytes(data)
        self.entries.append(
            {
                "category": category,
                "path": name,
                "upload_name": upload_name or name,
                "content_type": content_type,
                "bytes": path.stat().st_size,
            }
        )
        return path


def generate(out: Path, *, port: int = 9, ffmpeg_bin: str = ".data/ffmpeg/ffmpeg") -> list[Entry]:  # noqa: PLR0915
    rng = random.Random(SEED)
    w = Writer(out)
    http = f"http://127.0.0.1:{port}/seg.ts"

    # 1. HLS playlists that name a listener or a local file
    for i, (ext, ctype) in enumerate((("wav", "audio/wav"), ("mp3", "audio/mpeg"))):
        w.add("hls_playlist", f"hls_http_{i}.{ext}",
              f"#EXTM3U\n#EXT-X-VERSION:3\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\n{http}\n#EXT-X-ENDLIST\n".encode(),
              content_type=ctype)
        w.add("hls_playlist", f"hls_file_{i}.{ext}",
              b"#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nfile:///etc/passwd\n#EXT-X-ENDLIST\n",
              content_type=ctype)
    # 2. concat lists
    w.add("concat", "ffconcat_file.wav", b"ffconcat version 1.0\nfile '/etc/passwd'\n")
    w.add("concat", "ffconcat_http.wav", f"ffconcat version 1.0\nfile '{http}'\n".encode())
    w.add("concat", "concat_proto.mp3", b"concat:/etc/passwd|/etc/hostname", content_type="audio/mpeg")
    w.add("concat", "concat_proto2.flac", f"concat:{http}|/etc/hostname".encode(), content_type="audio/flac")
    # 3. text protocols
    w.add("text_protocol", "stream.sdp", b"v=0\no=- 0 0 IN IP4 127.0.0.1\ns=x\nc=IN IP4 127.0.0.1\nm=audio 9 RTP/AVP 0\n", content_type="audio/wav")
    w.add("text_protocol", "stream.rtsp", b"rtsp://127.0.0.1:9/live\n", content_type="audio/wav")
    w.add("text_protocol", "plain.mp3", b"this is a text file, not an mp3\n", content_type="audio/mpeg")
    # 4. renamed binaries
    png = b"\x89PNG\r\n\x1a\n" + rng.randbytes(64)
    w.add("renamed_binary", "image.wav", png)
    w.add("renamed_binary", "archive.flac", b"PK\x03\x04" + rng.randbytes(64), content_type="audio/flac")
    w.add("renamed_binary", "program.m4a", b"\x7fELF\x02\x01\x01" + rng.randbytes(64), content_type="audio/mp4")
    w.add("renamed_binary", "document.wav", b"%PDF-1.4\n" + rng.randbytes(64))
    # 5. valid containers with the wrong extension
    valid = w.out / "_valid.wav"
    silent_wav(valid)
    body = valid.read_bytes()
    valid.unlink()
    w.add("wrong_extension", "wav_as.mp3", body, content_type="audio/mpeg")
    w.add("wrong_extension", "wav_as.flac", body, content_type="audio/flac")
    w.add("wrong_extension", "wav_as.m4a", body, content_type="audio/mp4")
    # 6. raw ADTS AAC (not accepted: unsupported_media)
    for profile in (0, 1, 2):
        # named .mp3: with an .m4a name the extension check refuses it before the sniff matters
        w.add("adts_aac", f"adts_{profile}.mp3", adts(200, profile), content_type="audio/mpeg")
    # 7. WAV size bombs
    w.add("wav_bomb", "declares_4gb.wav", wav_header(0xFFFFFFF0) + bytes(1024))
    w.add("wav_bomb", "declares_10h.wav", wav_header(8000 * 2 * 36000) + bytes(1024))
    for rate in (192000, 193000):
        data_len = 16 * rate * 8 * 2
        path = w.add("wav_bomb", f"eight_channels_{rate}.wav", wav_header(data_len, channels=8, rate=rate))
        with path.open("ab") as fh:
            fh.truncate(44 + data_len)  # sparse zeros: a valid 16 s file without writing 49 MB
        w.entries[-1]["bytes"] = path.stat().st_size
    # 8. MP4 with an unreasonable moov size
    ftyp = struct.pack(">I", 20) + b"ftypM4A " + bytes(4) + b"M4A "
    w.add("mp4_bad_box", "moov_huge.m4a", ftyp + struct.pack(">I", 0x7FFFFFFF) + b"moov" + bytes(32), content_type="audio/mp4")
    w.add("mp4_bad_box", "moov_64bit.m4a", ftyp + struct.pack(">I", 1) + b"moov" + struct.pack(">Q", 1 << 62) + bytes(32), content_type="audio/mp4")
    w.add("mp4_bad_box", "moov_tiny.m4a", ftyp + struct.pack(">I", 4) + b"moov" + bytes(32), content_type="audio/mp4")
    # 9. FLAC claiming far too many samples
    for i, total in enumerate((10**9, 2**36 - 1, 10**10)):
        w.add("flac_claim", f"flac_claim_{i}.flac", flac_header(total) + rng.randbytes(256), content_type="audio/flac")
    # 10. Ogg made of empty pages
    for i, n in enumerate((200, 1000, 5000)):
        w.add("ogg_pages", f"ogg_empty_{i}.ogg", ogg_pages(n), content_type="audio/ogg")
    # 11. many streams, an embedded picture, a video stream (made by the pinned FFmpeg)
    sine = ["-f", "lavfi", "-i", "sine=frequency=440:duration=16"]
    five = [arg for _ in range(5) for arg in sine]
    maps = [arg for i in range(5) for arg in ("-map", str(i))]
    ffmpeg(ffmpeg_bin, *five, *maps, "-c:a", "aac", "-f", "mp4", str(w.out / "five_streams.m4a"))
    ffmpeg(ffmpeg_bin, *five, *maps, "-c:a", "aac", "-f", "matroska", str(w.out / "five_streams_mkv.m4a"))
    ffmpeg(ffmpeg_bin, *five, *maps, "-c:a", "aac", "-f", "mpegts", str(w.out / "five_streams_ts.mp3"))
    for name, ctype in (("five_streams.m4a", "audio/mp4"), ("five_streams_mkv.m4a", "audio/mp4"), ("five_streams_ts.mp3", "audio/mpeg")):
        w.add("many_streams", name, None, content_type=ctype)
    pic = w.out / "_pic.png"
    pic.write_bytes(noise_png(rng, 3 * 1024 * 1024))
    ffmpeg(ffmpeg_bin, *sine, "-i", str(pic), "-map", "0", "-map", "1", "-c:a", "libmp3lame",
           "-c:v", "copy", "-id3v2_version", "3", str(w.out / "picture_3mb.mp3"))
    ffmpeg(ffmpeg_bin, *sine, "-f", "lavfi", "-i", "color=c=red:s=64x64:d=16", "-c:a", "aac",
           "-c:v", "libx264", "-shortest", str(w.out / "with_video.m4a"))
    ffmpeg(ffmpeg_bin, *sine, "-f", "lavfi", "-i", "color=c=blue:s=64x64:d=16", "-c:a", "aac",
           "-c:v", "libx264", "-shortest", "-f", "matroska", str(w.out / "video_as.flac"))
    pic.unlink()
    w.add("embedded_media", "picture_3mb.mp3", None, content_type="audio/mpeg")
    w.add("embedded_media", "with_video.m4a", None, content_type="audio/mp4")
    w.add("embedded_media", "video_as.flac", None, content_type="audio/flac")
    # 12. truncated files
    header = wav_header(16 * 8000 * 2) + bytes(16 * 8000 * 2)
    for n in (1, 16, 100, 4096):
        w.add("truncated", f"truncated_{n}.wav", header[:n])
    # 13. zero bytes
    for ext, ctype in (("wav", "audio/wav"), ("mp3", "audio/mpeg"), ("flac", "audio/flac")):
        w.add("zero_byte", f"empty.{ext}", b"", content_type=ctype)
    # 14. an MP3 of pure 0xFF
    for i, n in enumerate((4096, 65536, 1 << 20)):
        w.add("ff_mp3", f"all_ff_{i}.mp3", b"\xff" * n, content_type="audio/mpeg")
    # 15. hostile names (the on-disk name is safe; the name goes in X-Filename)
    names = [
        "../../etc/passwd.wav", "a\x00b.wav", "‮gpj.wav", "a" * 300 + ".wav", "....",
        "x;touch pwned.wav", "`id`.wav", "$(id).wav", "dir/sub\\name.wav", "-rf .wav",
    ]
    for i, name in enumerate(names):
        w.add("hostile_name", f"named_{i}.wav", body, upload_name=name)
    # 16. odd content types
    for i, ctype in enumerate((
        "audio/wav; charset=evil", "application/x-evil", "text/html", "audio/",
        "AUDIO/WAV", "multipart/form-data; boundary=x",
    )):
        w.add("content_type", f"ctype_{i}.wav", body, content_type=ctype)

    (w.out / "manifest.json").write_text(json.dumps(w.entries, indent=1))
    missing = [e["path"] for e in w.entries if not (w.out / e["path"]).exists()]
    if missing or len(w.entries) < MIN_FILES:
        sys.exit(f"corpus incomplete: {len(w.entries)} files, missing {missing}")
    return w.entries


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--port", type=int, default=9)
    parser.add_argument("--ffmpeg", default=".data/ffmpeg/ffmpeg")
    args = parser.parse_args()
    entries = generate(args.out, port=args.port, ffmpeg_bin=args.ffmpeg)
    categories: dict[str, int] = {}
    for e in entries:
        categories[e["category"]] = categories.get(e["category"], 0) + 1
    print(json.dumps({"files": len(entries), "categories": categories}, indent=1))  # noqa: T201
    print(f"hostile files: {len(entries)}")  # noqa: T201
    return 0


if __name__ == "__main__":
    sys.exit(main())

import subprocess


def mux_streams(video_path, audio_path, output_path, container):
    if container not in ("mp4", "webm"):
        raise ValueError("نوع الحاوية غير مدعوم")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c", "copy",
        output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or "فشل في FFmpeg أثناء الدمج")

    return output_path

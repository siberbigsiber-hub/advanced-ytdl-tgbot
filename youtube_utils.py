import yt_dlp


def estimate_size_mb(fmt):
    if fmt.get("filesize_approx"):
        return round(fmt["filesize_approx"] / 1024 / 1024, 2)

    if fmt.get("filesize"):
        return round(fmt["filesize"] / 1024 / 1024, 2)

    bitrate = fmt.get("tbr") or 0
    duration = fmt.get("duration") or 0
    if bitrate and duration:
        return round((bitrate * duration) / (8 * 1024), 2)

    return 0


def normalize_codec(value):
    if not value or value in ("none", "None"):
        return "-"
    return str(value).split(".")[0].upper()


def normalize_resolution(fmt):
    height = fmt.get("height")
    if height:
        return f"{height}p"
    return "-"


def clean_langs(subtitles=None, auto_caps=None):
    subtitles = subtitles or {}
    auto_caps = auto_caps or {}
    langs = []

    for lang in subtitles:
        langs.append(str(lang))

    for lang in auto_caps:
        langs.append(f"{lang} (auto)")

    out = []
    seen = set()
    for lang in langs:
        if lang not in seen:
            out.append(lang)
            seen.add(lang)
    return out


def is_mp4_compatible_video(fmt):
    vcodec = (fmt.get("vcodec") or "").lower()
    ext = (fmt.get("ext") or "").lower()
    if ext in ("mp4", "m4v", "m4a"):
        return True
    if any(token in vcodec for token in ["h264", "avc", "hevc", "av1"]):
        return True
    return False


def is_mp4_compatible_audio(fmt):
    acodec = (fmt.get("acodec") or "").lower()
    ext = (fmt.get("ext") or "").lower()
    if ext in ("m4a", "mp3", "aac"):
        return True
    if any(token in acodec for token in ["aac", "mp3"]):
        return True
    return False


def is_webm_compatible_video(fmt):
    vcodec = (fmt.get("vcodec") or "").lower()
    ext = (fmt.get("ext") or "").lower()
    if ext == "webm":
        return True
    if any(token in vcodec for token in ["vp9", "av1"]):
        return True
    return False


def is_webm_compatible_audio(fmt):
    acodec = (fmt.get("acodec") or "").lower()
    ext = (fmt.get("ext") or "").lower()
    if ext == "webm":
        return True
    if "opus" in acodec:
        return True
    return False


def filter_compatible_formats(formats):
    mp4_video = []
    mp4_audio = []
    webm_video = []
    webm_audio = []

    for fmt in formats:
        format_id = fmt.get("format_id")
        if not format_id:
            continue

        vcodec = fmt.get("vcodec") or "none"
        acodec = fmt.get("acodec") or "none"

        if vcodec != "none":
            if is_mp4_compatible_video(fmt):
                mp4_video.append({
                    "format_id": format_id,
                    "codec": normalize_codec(vcodec),
                    "resolution": normalize_resolution(fmt),
                    "ext": fmt.get("ext", "-"),
                    "size_mb": estimate_size_mb(fmt),
                    "height": fmt.get("height"),
                    "width": fmt.get("width"),
                })

            if is_webm_compatible_video(fmt):
                webm_video.append({
                    "format_id": format_id,
                    "codec": normalize_codec(vcodec),
                    "resolution": normalize_resolution(fmt),
                    "ext": fmt.get("ext", "-"),
                    "size_mb": estimate_size_mb(fmt),
                    "height": fmt.get("height"),
                    "width": fmt.get("width"),
                })

        if acodec != "none":
            if is_mp4_compatible_audio(fmt):
                mp4_audio.append({
                    "format_id": format_id,
                    "codec": normalize_codec(acodec),
                    "ext": fmt.get("ext", "-"),
                    "size_mb": estimate_size_mb(fmt),
                    "abr": fmt.get("abr"),
                })

            if is_webm_compatible_audio(fmt):
                webm_audio.append({
                    "format_id": format_id,
                    "codec": normalize_codec(acodec),
                    "ext": fmt.get("ext", "-"),
                    "size_mb": estimate_size_mb(fmt),
                    "abr": fmt.get("abr"),
                })

    mp4_video.sort(key=lambda x: ((x["height"] or 0), x["size_mb"]), reverse=True)
    webm_video.sort(key=lambda x: ((x["height"] or 0), x["size_mb"]), reverse=True)
    mp4_audio.sort(key=lambda x: (x["size_mb"], x["format_id"]), reverse=True)
    webm_audio.sort(key=lambda x: (x["size_mb"], x["format_id"]), reverse=True)

    return {
        "mp4_video": mp4_video,
        "mp4_audio": mp4_audio,
        "webm_video": webm_video,
        "webm_audio": webm_audio,
    }


def extract_metadata(url):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", [])
    grouped = filter_compatible_formats(formats)

    return {
        "title": info.get("title", "فيديو"),
        "duration": info.get("duration"),
        "audio": grouped,
        "subtitles": clean_langs(info.get("subtitles"), info.get("automatic_captions")),
    }

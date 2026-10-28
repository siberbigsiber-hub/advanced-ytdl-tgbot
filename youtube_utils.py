import os
import random
from typing import Dict, Optional

import yt_dlp


DEVICE_CLIENTS = {
    "ios": {
        "user_agent": [
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.7 Mobile/15E148 Safari/604.1",
        ],
        "player_client": "ios",
    },
    "android": {
        "user_agent": [
            "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A.240205.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0.6613.146 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 13; SM-G998B Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/125.0.6422.165 Mobile Safari/537.36",
            "Mozilla/5.0 (Linux; Android 14; Pixel 7 Build/UP1A.231005.007; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.6478.122 Mobile Safari/537.36",
        ],
        "player_client": "android",
    },
    "android_tv": {
        "user_agent": [
            "Mozilla/5.0 (Linux; Android 13; Fire TV Stick Build/TP1A.220624.014; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/127.0.6533.80 Television Safari/537.36",
            "Mozilla/5.0 (Linux; Android 12; TCL Android TV Build/SP1A.210812.016; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/122.0.6261.119 Television Safari/537.36",
        ],
        "player_client": "android",
    },
}

DEFAULT_HEADERS = {
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
}

COOKIES_PATH = os.getenv("YT_COOKIES_FILE")


class BotProtectedVideoError(RuntimeError):
    pass


def random_user_agent_for(device_hint: str = "ios") -> str:
    device_hint = (device_hint or "ios").lower()
    device = DEVICE_CLIENTS.get(device_hint, DEVICE_CLIENTS["ios"])
    return random.choice(device["user_agent"])


def build_http_headers(device_hint: str = "ios", override_ua: Optional[str] = None) -> Dict[str, str]:
    headers = DEFAULT_HEADERS.copy()
    ua = override_ua or random_user_agent_for(device_hint)
    headers["User-Agent"] = ua
    headers["X-Requested-With"] = "com.google.android.youtube"
    headers["Sec-Fetch-Mode"] = "navigate"
    headers["Sec-Fetch-Site"] = "none"
    headers["Sec-Fetch-User"] = "?1"
    headers["Sec-CH-UA-Platform"] = '"Android"' if device_hint.lower().startswith("android") else '"iOS"'
    headers["Sec-CH-UA-Mobile"] = "?1" if "android" in device_hint.lower() else "?0"
    return headers


def build_yt_dlp_options(cookies_path: Optional[str] = None, device_hint: str = "ios") -> Dict:
    ua = random_user_agent_for(device_hint)
    headers = build_http_headers(device_hint, ua)

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extractor_args": {
            "youtube": [
                f"player_client={device_hint}",
                "player_skip=webpage,configs",
            ]
        },
        "http_headers": headers,
        "ignore_no_formats_error": True,
        "socket_timeout": 20,
        "retries": 2,
        "fragment_retries": 2,
    }

    if cookies_path and os.path.exists(cookies_path):
        opts["cookies"] = cookies_path

    return opts


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


def detect_protected_video_error(message: str) -> bool:
    msg = (message or "").lower()
    protected_keywords = [
        "sign in to confirm you’re not a bot",
        "sign in to confirm you are not a bot",
        "use --cookies-from-browser",
        "cookies",
        "login required",
        "this video is unavailable",
        "not available in your country",
        "requires authentication",
        "verify you are human",
        "bot detection",
    ]
    return any(keyword in msg for keyword in protected_keywords)


def extract_metadata(url: str, cookies_path: Optional[str] = None, device_hint: str = "ios"):
    cookies_path = cookies_path or COOKIES_PATH
    device_hint = (device_hint or "ios").lower()
    if device_hint not in DEVICE_CLIENTS:
        device_hint = "ios"

    ydl_opts = build_yt_dlp_options(cookies_path=cookies_path, device_hint=device_hint)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as exc:
            message = str(exc)
            if detect_protected_video_error(message):
                raise BotProtectedVideoError(
                    "هذا الفيديو محمي بنظام أمان يوتيوب أو يحتاج كوكيز جديدة من المتصفح/الحساب."
                ) from exc
            raise

    formats = info.get("formats", [])
    grouped = filter_compatible_formats(formats)

    return {
        "title": info.get("title", "فيديو"),
        "duration": info.get("duration"),
        "audio": grouped,
        "subtitles": clean_langs(info.get("subtitles"), info.get("automatic_captions")),
    }


__all__ = [
    "BotProtectedVideoError",
    "build_yt_dlp_options",
    "build_http_headers",
    "random_user_agent_for",
    "extract_metadata",
]


""" end """


""" end """


""" end """


""" end """


""" end """


""" end """


""" end """


""" end """


""" end """ 

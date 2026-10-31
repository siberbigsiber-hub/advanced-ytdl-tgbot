import os
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder=".", static_url_path="")

COOKIES_PATH = os.getenv("YT_COOKIES_FILE", "/app/cookies.txt")
os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/upload-cookies", methods=["POST"])
def upload_cookies():
    try:
        text = request.get_data(as_text=True)
        if not text or len(text.strip()) < 20:
            return jsonify({"error": "ملف cookies فارغ أو غير صالح."}), 400

        with open(COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(text)

        return jsonify({
            "status": "ok",
            "path": COOKIES_PATH,
            "message": "تم حفظ ملف cookies بنجاح."
        }), 200

    except Exception as exc:
        return jsonify({"error": f"خطأ: {str(exc)}"}), 500


@app.route("/status-cookies", methods=["GET"])
def status_cookies():
    if os.path.exists(COOKIES_PATH):
        stat = os.stat(COOKIES_PATH)
        return jsonify({
            "exists": True,
            "path": COOKIES_PATH,
            "size": stat.st_size
        })
    return jsonify({"exists": False, "path": COOKIES_PATH})


@app.route("/clear-cookies", methods=["POST"])
def clear_cookies():
    try:
        if os.path.exists(COOKIES_PATH):
            os.remove(COOKIES_PATH)
        return jsonify({"status": "ok", "message": "تم حذف ملف cookies بنجاح."})
    except Exception as exc:
        return jsonify({"error": f"خطأ: {str(exc)}"}), 500

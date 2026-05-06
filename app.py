
from pathlib import Path
from datetime import datetime
import json, socket, io, hashlib, secrets, re
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort, flash, jsonify, send_file, session

APP_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = APP_DIR / "uploads"
DATA_DIR = APP_DIR / "data"
CACHE_DIR = APP_DIR / "static" / "cache"
USERS_FILE = DATA_DIR / "users.json"
HISTORY_FILE = DATA_DIR / "history.json"
CHAT_FILE = DATA_DIR / "chat.json"

app = Flask(__name__)
app.secret_key = "seleznev-local-share-v2"
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024 * 1024

ROOM_NAMES = {
    "general": "Общие файлы",
    "wb": "Wildberries",
    "jewelry": "Ювелирка",
    "stl": "STL модели",
    "renders": "Рендеры",
}

def slugify(v):
    v = (v or "").strip().lower()
    v = re.sub(r"[^a-zа-я0-9_-]+", "-", v, flags=re.I).strip("-_")
    return v[:60] or "general"

def hpass(password, salt):
    return hashlib.sha256((salt + password).encode()).hexdigest()

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def init():
    UPLOAD_DIR.mkdir(exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for r in ROOM_NAMES:
        (UPLOAD_DIR / r).mkdir(exist_ok=True)
    if not USERS_FILE.exists():
        salt = secrets.token_hex(16)
        save_json(USERS_FILE, {"admin": {"salt": salt, "password_hash": hpass("1234", salt), "role": "admin"}})
    if not HISTORY_FILE.exists(): save_json(HISTORY_FILE, [])
    if not CHAT_FILE.exists(): save_json(CHAT_FILE, [])

def user():
    return session.get("user")

@app.before_request
def auth():
    init()
    if request.endpoint in ["login", "static", "manifest", "sw"] or request.path.startswith("/static/"):
        return
    if not user():
        return redirect(url_for("login"))

def ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        x = s.getsockname()[0]
        s.close()
        return x
    except Exception:
        return "127.0.0.1"

def hostname():
    try: return socket.gethostname()
    except Exception: return "localhost"

def room_path(room):
    room = slugify(room)
    p = UPLOAD_DIR / room
    p.mkdir(exist_ok=True)
    return p

def safe_file(room, filename):
    return room_path(room) / Path(filename).name

def size_h(n):
    if n < 1024: return f"{n} Б"
    if n < 1024**2: return f"{n/1024:.1f} КБ"
    if n < 1024**3: return f"{n/1024**2:.2f} МБ"
    return f"{n/1024**3:.2f} ГБ"

def kind(name):
    e = Path(name).suffix.lower()
    if e in [".jpg",".jpeg",".png",".webp",".gif",".bmp"]: return "image"
    if e == ".stl": return "stl"
    if e == ".pdf": return "pdf"
    if e in [".xlsx",".xls",".csv"]: return "table"
    if e in [".zip",".rar",".7z"]: return "archive"
    return "file"

def icon(k):
    return {"image":"🖼️","stl":"💍","pdf":"📕","table":"📊","archive":"🗜️","file":"📄"}.get(k,"📄")

def history(action, room, filename):
    h = load_json(HISTORY_FILE, [])
    h.append({"time": datetime.now().strftime("%d.%m.%Y %H:%M:%S"), "user": user() or "system", "action": action, "room": room, "filename": filename})
    save_json(HISTORY_FILE, h[-1000:])

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username","").strip()
        p = request.form.get("password","")
        users = load_json(USERS_FILE, {})
        rec = users.get(u)
        if rec and hpass(p, rec["salt"]) == rec["password_hash"]:
            session["user"] = u
            return redirect(url_for("index"))
        flash("Неверный логин или пароль")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    r = slugify(request.args.get("room") or "general")
    q = (request.args.get("q") or "").strip().lower()
    files, total = [], 0
    for f in sorted(room_path(r).iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not f.is_file() or f.name == ".gitkeep": continue
        if q and q not in f.name.lower(): continue
        st = f.stat(); total += st.st_size; k = kind(f.name)
        files.append({"name": f.name, "size": size_h(st.st_size), "date": datetime.fromtimestamp(st.st_mtime).strftime("%d.%m.%Y %H:%M"), "kind": k, "icon": icon(k)})
    rooms = [{"id": p.name, "title": ROOM_NAMES.get(p.name, p.name)} for p in sorted(UPLOAD_DIR.iterdir()) if p.is_dir()]
    return render_template("index.html", files=files, rooms=rooms, selected_room=r, selected_room_title=ROOM_NAMES.get(r,r),
                           file_count=len(files), total_size=size_h(total), local_url=f"http://{ip()}:8000",
                           host_url=f"http://{hostname()}:8000", user=user(), search=q)

@app.route("/room/create", methods=["POST"])
def create_room():
    title = request.form.get("title","").strip()
    r = slugify(title)
    if not title:
        flash("Введите название комнаты")
        return redirect(url_for("index"))
    room_path(r)
    flash(f"Комната создана: {title}")
    return redirect(url_for("index", room=r))

@app.route("/upload/<room>", methods=["POST"])
def upload(room):
    room = slugify(room)
    saved = 0
    for file in request.files.getlist("files"):
        if not file or not file.filename: continue
        target = safe_file(room, file.filename)
        if target.exists():
            stem, suf, i = target.stem, target.suffix, 1
            while True:
                cand = room_path(room) / f"{stem}_{i}{suf}"
                if not cand.exists():
                    target = cand; break
                i += 1
        file.save(target)
        history("upload", room, target.name)
        saved += 1
    flash(f"Загружено файлов: {saved}" if saved else "Файлы не выбраны")
    return redirect(url_for("index", room=room))

@app.route("/download/<room>/<path:filename>")
def download(room, filename):
    fp = safe_file(room, filename)
    if not fp.exists(): abort(404)
    history("download", room, fp.name)
    return send_from_directory(room_path(room), fp.name, as_attachment=True)

@app.route("/view/<room>/<path:filename>")
def view(room, filename):
    fp = safe_file(room, filename)
    if not fp.exists(): abort(404)
    return send_from_directory(room_path(room), fp.name, as_attachment=False)

@app.route("/delete/<room>/<path:filename>", methods=["POST"])
def delete(room, filename):
    fp = safe_file(room, filename)
    if fp.exists() and fp.is_file():
        fp.unlink()
        history("delete", room, fp.name)
        flash(f"Удалено: {fp.name}")
    return redirect(url_for("index", room=room))

@app.route("/preview/stl/<room>/<path:filename>")
def preview_stl(room, filename):
    fp = safe_file(room, filename)
    if not fp.exists() or fp.suffix.lower() != ".stl": abort(404)
    cached = CACHE_DIR / (slugify(room) + "_" + fp.stem + "_preview.png")
    if not cached.exists() or cached.stat().st_mtime < fp.stat().st_mtime:
        try:
            import trimesh, matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d.art3d import Poly3DCollection
            model = trimesh.load(str(fp), force="mesh")
            fig = plt.figure(figsize=(7,7)); ax = fig.add_subplot(111, projection="3d")
            faces = model.vertices[model.faces]
            col = Poly3DCollection(faces, linewidths=.02, alpha=1)
            col.set_facecolor((.86,.70,.20)); col.set_edgecolor((.52,.39,.10))
            ax.add_collection3d(col); s = model.vertices.flatten(); ax.auto_scale_xyz(s,s,s)
            ax.view_init(elev=22, azim=42); ax.set_axis_off()
            fig.patch.set_facecolor((.96,.94,.90)); ax.set_facecolor((.96,.94,.90))
            plt.savefig(cached, dpi=180, bbox_inches="tight", pad_inches=.02); plt.close(fig)
        except Exception as e:
            return f"Не удалось создать STL превью: {e}", 500
    return send_file(cached, mimetype="image/png")

@app.route("/stl-viewer")
def stl_viewer():
    room = slugify(request.args.get("room") or "stl")
    filename = Path(request.args.get("file") or "").name
    fp = safe_file(room, filename)
    if not fp.exists() or fp.suffix.lower() != ".stl": abort(404)
    return render_template("stl_viewer.html", room=room, filename=filename)


def is_admin():
    users = load_json(USERS_FILE, {})
    rec = users.get(user() or "")
    return bool(rec and rec.get("role") == "admin")

@app.route("/users", methods=["GET", "POST"])
def users_page():
    if not is_admin():
        abort(403)

    users = load_json(USERS_FILE, {})

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "user")

            if not username or not password:
                flash("Введите логин и пароль")
            elif username in users:
                flash("Такой пользователь уже существует")
            else:
                salt = secrets.token_hex(16)
                users[username] = {
                    "salt": salt,
                    "password_hash": hpass(password, salt),
                    "role": role if role in ["admin", "user"] else "user"
                }
                save_json(USERS_FILE, users)
                flash(f"Пользователь создан: {username}")

        elif action == "password":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")

            if username not in users:
                flash("Пользователь не найден")
            elif not password:
                flash("Введите новый пароль")
            else:
                salt = secrets.token_hex(16)
                users[username]["salt"] = salt
                users[username]["password_hash"] = hpass(password, salt)
                save_json(USERS_FILE, users)
                flash(f"Пароль изменён: {username}")

        elif action == "delete":
            username = request.form.get("username", "").strip()

            if username == "admin":
                flash("Пользователя admin удалять нельзя")
            elif username == user():
                flash("Нельзя удалить самого себя")
            elif username in users:
                del users[username]
                save_json(USERS_FILE, users)
                flash(f"Пользователь удалён: {username}")
            else:
                flash("Пользователь не найден")

        return redirect(url_for("users_page"))

    safe_users = []
    for username, rec in users.items():
        safe_users.append({"username": username, "role": rec.get("role", "user")})

    return render_template("users.html", users=safe_users, user=user())

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    users = load_json(USERS_FILE, {})
    username = user()

    if request.method == "POST":
        old_password = request.form.get("old_password", "")
        new_password = request.form.get("new_password", "")
        rec = users.get(username)

        if not rec or hpass(old_password, rec["salt"]) != rec["password_hash"]:
            flash("Старый пароль неверный")
        elif not new_password:
            flash("Введите новый пароль")
        else:
            salt = secrets.token_hex(16)
            users[username]["salt"] = salt
            users[username]["password_hash"] = hpass(new_password, salt)
            save_json(USERS_FILE, users)
            flash("Пароль изменён")

    return render_template("change_password.html", user=username)


@app.route("/history")
def history_page():
    return render_template("history.html", history=list(reversed(load_json(HISTORY_FILE, [])[-300:])), user=user())

@app.route("/chat", methods=["GET"])
def chat_get():
    return jsonify(load_json(CHAT_FILE, []))

@app.route("/chat", methods=["POST"])
def chat_post():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()[:1000]
    if not text: return jsonify({"ok": False}), 400
    msgs = load_json(CHAT_FILE, [])
    msgs.append({"name": user(), "text": text, "time": datetime.now().strftime("%d.%m %H:%M")})
    save_json(CHAT_FILE, msgs[-200:])
    return jsonify({"ok": True})

@app.route("/qr")
def qr():
    try:
        import qrcode
        img = qrcode.make(f"http://{ip()}:8000")
        buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
        return send_file(buf, mimetype="image/png")
    except Exception as e:
        return f"QR недоступен: {e}", 500

@app.route("/manifest.json")
def manifest():
    return jsonify({"name":"SELEZNEV Local Share","short_name":"SELEZNEV","start_url":"/","display":"standalone","background_color":"#f8f3ea","theme_color":"#b48a3c","icons":[]})

@app.route("/sw.js")
def sw():
    return app.response_class("self.addEventListener('install',e=>self.skipWaiting());", mimetype="application/javascript")

if __name__ == "__main__":
    init()
    app.run(host="0.0.0.0", port=8000, debug=False)

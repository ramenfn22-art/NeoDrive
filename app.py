import os
import json
import mimetypes
from io import BytesIO
from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === Persistent data folder (Render-safe) ===
os.makedirs("data", exist_ok=True)
USER_FILE = os.path.join("data", "users.json")

# === Ensure users.json exists ===
if not os.path.exists(USER_FILE):
    with open(USER_FILE, "w") as f:
        json.dump({}, f)

# === Ensure uploads folder exists ===
os.makedirs("uploads", exist_ok=True)

# === App-level encryption key ===
if not os.path.exists("secret.key"):
    app_key = Fernet.generate_key()
    with open("secret.key", "wb") as f:
        f.write(app_key)
else:
    with open("secret.key", "rb") as f:
        app_key = f.read()

app_cipher = Fernet(app_key)


# === User storage helpers ===
def load_users():
    with open(USER_FILE, "r") as f:
        return json.load(f)


def save_users(users):
    with open(USER_FILE, "w") as f:
        json.dump(users, f)


# === Routes ===

@app.route("/")
def index():
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    os.makedirs(user_folder, exist_ok=True)

    files = os.listdir(user_folder)
    return render_template("index.html", username=session["username"], files=files)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        if username in users:
            return "Username already exists", 400

        # Per-user encryption key (ASCII-safe)
        user_key = Fernet.generate_key().decode("ascii")

        users[username] = {
            "password": password,
            "key": user_key
        }
        save_users(users)

        return redirect("/login")

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        if username in users and users[username]["password"] == password:
            session["username"] = username
            return redirect("/")

        return "Invalid login", 400

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        return redirect("/login")

    if request.method == "POST":
        if "file" not in request.files:
            return "No file part", 400

        file = request.files["file"]

        if file.filename == "":
            return "No selected file", 400

        filename = secure_filename(file.filename)

        user_folder = os.path.join("uploads", session["username"])
        os.makedirs(user_folder, exist_ok=True)

        file_bytes = file.read()

        users = load_users()
        user_info = users.get(session["username"])
        if not user_info:
            return "User not found", 400

        user_cipher = Fernet(user_info["key"].encode("ascii"))

        # Double encryption
        encrypted_user = user_cipher.encrypt(file_bytes)
        encrypted_final = app_cipher.encrypt(encrypted_user)

        with open(os.path.join(user_folder, filename), "wb") as f:
            f.write(encrypted_final)

        return redirect("/viewer")

    return render_template("upload.html")


@app.route("/viewer")
def viewer():
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    os.makedirs(user_folder, exist_ok=True)

    files = os.listdir(user_folder)
    return render_template("viewer.html", username=session["username"], files=files)


@app.route("/view/<filename>")
def view_file(filename):
    if "username" not in session:
        return redirect("/login")

    return render_template("view.html", filename=filename)


def decrypt_file(username, filename):
    user_folder = os.path.join("uploads", username)
    file_path = os.path.join(user_folder, filename)

    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        encrypted_final = f.read()

    # First decrypt with app key
    encrypted_user = app_cipher.decrypt(encrypted_final)

    users = load_users()
    user_info = users.get(username)
    if not user_info:
        return None

    user_cipher = Fernet(user_info["key"].encode("ascii"))

    # Then decrypt with user key
    decrypted = user_cipher.decrypt(encrypted_user)

    return decrypted


@app.route("/download/<filename>")
def download(filename):
    if "username" not in session:
        return redirect("/login")

    decrypted = decrypt_file(session["username"], filename)
    if decrypted is None:
        return "File not found", 404

    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type is None:
        mime_type = "application/octet-stream"

    return send_file(
        BytesIO(decrypted),
        download_name=filename,
        mimetype=mime_type,
        as_attachment=False
    )


@app.route("/delete/<filename>")
def delete(filename):
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    file_path = os.path.join(user_folder, filename)

    if os.path.exists(file_path):
        os.remove(file_path)

    return redirect("/viewer")


if __name__ == "__main__":
    app.run(debug=True)

import os
import json
import mimetypes
from io import BytesIO
from flask import Flask, render_template, request, redirect, session, send_file
from werkzeug.utils import secure_filename
from cryptography.fernet import Fernet

app = Flask(__name__)
app.secret_key = "supersecretkey"

# === Ensure base folders/files exist ===
os.makedirs("uploads", exist_ok=True)

if not os.path.exists("users.json"):
    with open("users.json", "w") as f:
        json.dump({}, f)

if not os.path.exists("secret.key"):
    # App-level encryption key (only generated once)
    app_key = Fernet.generate_key()
    with open("secret.key", "wb") as f:
        f.write(app_key)
else:
    with open("secret.key", "rb") as f:
        app_key = f.read()

app_cipher = Fernet(app_key)


# === User storage helpers ===
def load_users():
    with open("users.json", "r") as f:
        return json.load(f)


def save_users(users):
    with open("users.json", "w") as f:
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

        # Per-user encryption key
        user_key = Fernet.generate_key().decode("utf-8")

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

        # Read raw bytes
        file_bytes = file.read()

        # Get user key
        users = load_users()
        user_info = users.get(session["username"])
        if not user_info:
            return "User not found", 400

        user_cipher = Fernet(user_info["key"].encode("utf-8"))

        # Double encryption: first user key, then app key
        user_encrypted = user_cipher.encrypt(file_bytes)
        fully_encrypted = app_cipher.encrypt(user_encrypted)

        with open(os.path.join(user_folder, filename), "wb") as f:
            f.write(fully_encrypted)

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

    user_folder = os.path.join("uploads", session["username"])
    file_path = os.path.join(user_folder, filename)

    if not os.path.exists(file_path):
        return "File not found", 404

    # Decrypt for viewing (used by view.html via /download)
    return render_template("view.html", filename=filename)


def decrypt_file_for_user(username, filename):
    user_folder = os.path.join("uploads", username)
    file_path = os.path.join(user_folder, filename)

    if not os.path.exists(file_path):
        return None

    with open(file_path, "rb") as f:
        fully_encrypted = f.read()

    # First decrypt with app key
    user_encrypted = app_cipher.decrypt(fully_encrypted)

    # Then decrypt with user key
    users = load_users()
    user_info = users.get(username)
    if not user_info:
        return None

    user_cipher = Fernet(user_info["key"].encode("utf-8"))
    decrypted = user_cipher.decrypt(user_encrypted)

    return decrypted


@app.route("/download/<filename>")
def download(filename):
    if "username" not in session:
        return redirect("/login")

    decrypted = decrypt_file_for_user(session["username"], filename)
    if decrypted is None:
        return "File not found", 404

    # Guess mimetype for better viewing
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

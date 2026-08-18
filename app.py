import os
import sqlite3
from flask import Flask, render_template, request, redirect, session, send_from_directory, jsonify

app = Flask(__name__)
app.secret_key = "supersecretkey"  # change later

UPLOAD_ROOT = "uploads"
os.makedirs(UPLOAD_ROOT, exist_ok=True)


# -----------------------------
# Database Helper
# -----------------------------
def get_db():
    return sqlite3.connect("users.db")


# -----------------------------
# Create User Folder
# -----------------------------
def user_folder(username):
    path = os.path.join(UPLOAD_ROOT, username)
    os.makedirs(path, exist_ok=True)
    return path


# -----------------------------
# Signup
# -----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            return "Please enter a username and password"

        conn = get_db()
        c = conn.cursor()

        # Check if username exists
        c.execute("SELECT id FROM users WHERE username=?", (username,))
        if c.fetchone():
            return "Username already exists"

        # Insert new user
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

        # Create user folder
        user_folder(username)

        return redirect("/login")

    return render_template("signup.html")


# -----------------------------
# Login
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        conn = get_db()
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["username"] = username
            return redirect("/")
        else:
            return "Invalid username or password"

    return render_template("login.html")


# -----------------------------
# Logout
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -----------------------------
# Home (User Files)
# -----------------------------
@app.route("/")
def index():
    if "username" not in session:
        return redirect("/login")

    folder = user_folder(session["username"])
    files = os.listdir(folder)

    return render_template("index.html", files=files, username=session["username"])


# -----------------------------
# Upload (AJAX)
# -----------------------------
@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "username" not in session:
        return redirect("/login")

    folder = user_folder(session["username"])

    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return jsonify({"error": "No file"}), 400

        file.save(os.path.join(folder, file.filename))
        return jsonify({"status": "ok"})

    return render_template("upload.html")


# -----------------------------
# Download
# -----------------------------
@app.route("/download/<filename>")
def download(filename):
    folder = user_folder(session["username"])
    return send_from_directory(folder, filename, as_attachment=True)


# -----------------------------
# Delete
# -----------------------------
@app.route("/delete/<filename>")
def delete(filename):
    folder = user_folder(session["username"])
    path = os.path.join(folder, filename)

    if os.path.exists(path):
        os.remove(path)

    return redirect("/")


# -----------------------------
# Run
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)

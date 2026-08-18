import os
import json
from flask import Flask, render_template, request, redirect, session, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Ensure uploads folder exists
os.makedirs("uploads", exist_ok=True)

# Ensure users.json exists
if not os.path.exists("users.json"):
    with open("users.json", "w") as f:
        json.dump({}, f)


def load_users():
    with open("users.json", "r") as f:
        return json.load(f)


def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f)


# Home Page
@app.route("/")
def index():
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    os.makedirs(user_folder, exist_ok=True)

    files = os.listdir(user_folder)
    return render_template("index.html", username=session["username"], files=files)


# Signup Page
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        if username in users:
            return "Username already exists", 400

        users[username] = password
        save_users(users)

        return redirect("/login")

    return render_template("signup.html")


# Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        users = load_users()

        if username in users and users[username] == password:
            session["username"] = username
            return redirect("/")

        return "Invalid login", 400

    return render_template("login.html")


# Logout
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# Upload Page
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

        file.save(os.path.join(user_folder, filename))

        return redirect("/viewer")

    return render_template("upload.html")


# File Viewer Grid Page
@app.route("/viewer")
def viewer():
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    os.makedirs(user_folder, exist_ok=True)

    files = os.listdir(user_folder)
    return render_template("viewer.html", username=session["username"], files=files)


# Fullscreen File Viewer
@app.route("/view/<filename>")
def view_file(filename):
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    file_path = os.path.join(user_folder, filename)

    if not os.path.exists(file_path):
        return "File not found", 404

    return render_template("view.html", filename=filename)


# Download File
@app.route("/download/<filename>")
def download(filename):
    if "username" not in session:
        return redirect("/login")

    user_folder = os.path.join("uploads", session["username"])
    return send_from_directory(user_folder, filename, as_attachment=False)


# Delete File
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

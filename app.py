import os
import json
import shutil
from collections import defaultdict

from flask import Flask, request, jsonify, send_from_directory, abort
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename


app = Flask(__name__, static_folder="static")


print("Debug Mode: ", app.debug)
# Config paths
DATABASE_FOLDER = "database"
UPLOADS_FOLDER = os.path.join(DATABASE_FOLDER, "uploads")
SESSIONS_FILE = os.path.join(DATABASE_FOLDER, "sessions.json")
PACKAGES_FILE = os.path.join(DATABASE_FOLDER, "packages.json")
PACKAGE_TASKS_FILE = os.path.join(DATABASE_FOLDER, "package_tasks.json")
FEEDBACK_FILE = os.path.join(DATABASE_FOLDER, "feedback.jsonl")
TASK_FOLDER = "tasks"
INSTRUCTIONS_FILE = "task_instruction.md"
LOCK_TIMEOUT_HOURS = 2
MAX_EVALUATIONS_PER_PACKAGE = 3

# Ensure folders and files exist
os.makedirs(DATABASE_FOLDER, exist_ok=True)
os.makedirs(UPLOADS_FOLDER, exist_ok=True)
os.makedirs(TASK_FOLDER, exist_ok=True)
for file_path in [SESSIONS_FILE, PACKAGES_FILE, PACKAGE_TASKS_FILE]:
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump({}, f)
if not os.path.exists(FEEDBACK_FILE):
    open(FEEDBACK_FILE, "a").close()


# Utilities
def now():
    return datetime.utcnow()


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def cleanup_expired_locks(packages):
    now_time = now()
    for entry in packages.values():
        assigned = entry.get("assigned_to", {})
        if isinstance(assigned, dict):
            active = {
                k: v for k, v in assigned.items()
                if datetime.fromisoformat(v) > now_time
            }
            entry["assigned_to"] = active


def assign_package(user_id, email):
    user_key = f"{user_id}|{email}"
    packages = load_json(PACKAGES_FILE)
    cleanup_expired_locks(packages)

    # Step 1: Get eligible packages (user not assigned or evaluated, and < 3 evaluations)
    eligible = []
    for pkg_id, entry in packages.items():
        assigned_to = entry.get("assigned_to", {})
        evaluated_by = entry.get("evaluated_by", [])

        if user_key in assigned_to or user_key in evaluated_by:
            continue
        if len(evaluated_by) >= MAX_EVALUATIONS_PER_PACKAGE:
            continue
        eligible.append((pkg_id, entry))

    # Step 2: Sort eligible by current load
    if eligible:
        eligible.sort(key=lambda x: len(x[1].get("assigned_to", {})) + len(x[1].get("evaluated_by", [])))
        pkg_id, entry = eligible[0]
        entry.setdefault("assigned_to", {})[user_key] = (
            now() + timedelta(hours=LOCK_TIMEOUT_HOURS)
        ).isoformat()
        save_json(PACKAGES_FILE, packages)
        return pkg_id

    # Step 3: Fallback — assign any package user hasn't evaluated
    candidates = [
        (pkg_id, entry)
        for pkg_id, entry in packages.items()
        if user_key not in entry.get("evaluated_by", [])
    ]
    if candidates:
        candidates.sort(key=lambda x: len(x[1].get("assigned_to", {})) + len(x[1].get("evaluated_by", [])))
        pkg_id, entry = candidates[0]
        entry.setdefault("assigned_to", {})[user_key] = (
            now() + timedelta(hours=LOCK_TIMEOUT_HOURS)
        ).isoformat()
        save_json(PACKAGES_FILE, packages)
        return pkg_id

    return None

@app.route("/instructions")
def instructions():
    if os.path.exists(INSTRUCTIONS_FILE):
        with open(INSTRUCTIONS_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "No instructions available."


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    user_id = data.get("user_id")
    email = data.get("email")
    background = data.get("background")

    if not user_id or not email:
        return jsonify(success=False, error="Missing user ID or email"), 400

    sessions = load_json(SESSIONS_FILE)
    session = sessions.get(user_id)
    # ok lets allow user to re-login
    if session and session["email"] == email and datetime.fromisoformat(session["locked_until"]) > now():
        return jsonify(success=True, package_id=session["task_id"], resumed=True)

    pkg_id = assign_package(user_id, email)
    if not pkg_id:
        return jsonify(success=False, error="No packages available"), 403


    sessions[user_id] = {
        "email": email,
        "background": background,
        "task_id": pkg_id,
        "locked_until": (now() + timedelta(hours=LOCK_TIMEOUT_HOURS)).isoformat()
    }
    save_json(SESSIONS_FILE, sessions)
    return jsonify(success=True, package_id=pkg_id, resumed=False)


@app.route("/quit", methods=["POST"])
def quit():
    data = request.get_json()
    user_id = data.get("user_id")

    sessions = load_json(SESSIONS_FILE)
    packages = load_json(PACKAGES_FILE)

    session = sessions.pop(user_id, None)
    if session:
        pkg_id = session["task_id"]
        email = session.get("email")
        user_key = f"{user_id}|{email}"

        if pkg_id in packages:
            assigned = packages[pkg_id].get("assigned_to", {})
            if isinstance(assigned, dict):
                assigned.pop(user_key, None)

    save_json(SESSIONS_FILE, sessions)
    save_json(PACKAGES_FILE, packages)
    return jsonify(success=True)



@app.route("/package/<package_id>")
def get_package_tasks(package_id):
    taskmap = load_json(PACKAGE_TASKS_FILE)
    return jsonify(success=True, tasks=taskmap.get(package_id, []))




@app.route("/submit-rating", methods=["POST"])
def submit_rating():
    data = request.get_json()
    user_id = data.get("user_id")
    email = data.get("email")
    package_id = data.get("package_id")
    ratings = data.get("ratings")

    user_key = f"{user_id}|{email}"

    sessions = load_json(SESSIONS_FILE)
    packages = load_json(PACKAGES_FILE)

    background = ""
    if user_id in sessions:
        background = sessions[user_id].get("background", "not_found")


    # Remove session (user finished their work)
    sessions.pop(user_id, None)

    # Update package
    if package_id in packages:
        pkg = packages[package_id]
        if user_key not in pkg.get("evaluated_by", []):
            pkg.setdefault("evaluated_by", []).append(user_key)
        if isinstance(pkg.get("assigned_to"), dict):
            pkg["assigned_to"].pop(user_key, None)

    # Save all changes
    save_json(SESSIONS_FILE, sessions)
    save_json(PACKAGES_FILE, packages)

    # Log feedback
    # with open(FEEDBACK_FILE, "a") as f:
    #     f.write(json.dumps(data) + "\n")
    with open(FEEDBACK_FILE, "a") as f:
        log_entry = data.copy()
        log_entry["background"] = background
        f.write(json.dumps(log_entry) + "\n")

    return jsonify(success=True)

# @app.route("/mark-complete", methods=["POST"])
# def mark_complete():
#     data = request.get_json()
#     user_id = data.get("user_id")
#     email = data.get("email")
#     package_id = data.get("package_id")
#
#     if not user_id or not email or not package_id:
#         return jsonify(success=False, error="Missing required fields"), 400
#
#     user_key = f"{user_id}|{email}"
#
#     packages = load_json(PACKAGES_FILE)
#     sessions = load_json(SESSIONS_FILE)
#
#     if package_id not in packages:
#         return jsonify(success=False, error="Package not found"), 404
#
#     pkg = packages[package_id]
#
#     # Mark as evaluated
#     if user_key not in pkg.get("evaluated_by", []):
#         pkg.setdefault("evaluated_by", []).append(user_key)
#
#     # Remove assignment
#     if isinstance(pkg.get("assigned_to"), dict):
#         pkg["assigned_to"].pop(user_key, None)
#
#     # Remove session
#     sessions.pop(user_id, None)
#
#     save_json(PACKAGES_FILE, packages)
#     save_json(SESSIONS_FILE, sessions)
#
#     return jsonify(success=True, message="Evaluation marked complete")
#

@app.route("/tasks/<task_id>")
def get_task(task_id):
    path = os.path.join(TASK_FOLDER, task_id)
    if not os.path.exists(path):
        abort(404)

    files = os.listdir(path)
    translation_file = next((f for f in files if f.endswith(".pdf")), "")
    # original_image = next((f for f in files if f.startswith("original_petri_net") and f.endswith(".png")), "")
    original_image = next(
        (f for f in files if f.lower().startswith("id") and f.lower().endswith(".png")), "")

    print(f"[DEBUG] Files in task folder: {files}")
    print(f"[DEBUG] Selected original image: {original_image}")

    activity_md = next((f for f in files if f.endswith(".md")), "")
    activity_text = ""
    if activity_md:
        with open(os.path.join(path, activity_md), "r") as f:
            activity_text = f.read()

    return jsonify({
        "id": task_id,
        "title": task_id.replace("task_id_", "Task ").replace("_", "."),
        "translation_file_url": f"/tasks/{task_id}/{translation_file}",
        "original_image_url": f"/tasks/{task_id}/{original_image}",
        "activity_md": activity_text,
    })


@app.route("/tasks/<task_id>/<filename>")
def get_task_file(task_id, filename):
    return send_from_directory(os.path.join(TASK_FOLDER, task_id), filename)



@app.route("/")
@app.route("/<path:path>")
def serve_static(path="login.html"):
    return send_from_directory(app.static_folder, path)


# def extract_user_key(task_id, filename):
#     """
#     Extracts user_id|email from the filename:
#     task_id_userid_safeemail[_non_Sound]_vX.pnml
#     """
#     if not filename.endswith(".pnml"):
#         return None
#
#     name = filename.replace(".pnml", "")
#     name = name.replace("_non_Sound", "")
#     prefix = f"{task_id}_"
#     if not name.startswith(prefix):
#         return None
#     rest = name[len(prefix):]
#
#     # Remove version suffix
#     if "_v" not in rest:
#         return None
#     rest = rest.rsplit("_v", 1)[0]
#
#     # Try to detect where safe_email starts
#     # This assumes email will contain at least "_at_" and "_dot_"
#     parts = rest.split("_")
#     for i in range(1, len(parts)):
#         maybe_email = "_".join(parts[i:])
#         if "_at_" in maybe_email and "_dot_" in maybe_email:
#             user_id = "_".join(parts[:i])
#             safe_email = maybe_email
#             email = safe_email.replace("_at_", "@").replace("_dot_", ".")
#             return f"{user_id}|{email}"
#     return None

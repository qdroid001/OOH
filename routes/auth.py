import os

from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

from database import get_db_connection

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "company_logos")
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def allowed_logo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


def save_company_logo(file_storage, email):
    if not file_storage or not file_storage.filename:
        return ""

    if not allowed_logo(file_storage.filename):
        raise ValueError("Company logo must be an image file: png, jpg, jpeg, gif, or webp")

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    original_filename = secure_filename(file_storage.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    email_slug = secure_filename(email.split("@")[0]) or "company"
    filename = f"{email_slug}_logo.{extension}"
    save_path = os.path.join(UPLOAD_FOLDER, filename)
    file_storage.save(save_path)
    return f"/static/uploads/company_logos/{filename}"

# REGISTER
@auth_bp.route("/register", methods=["POST"])
def register():
    if request.form:
        data = request.form
    else:
        data = request.get_json() or {}

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")
    key = data.get("key", "").strip()
    company_address = data.get("company_address", "").strip()
    company_hotline = data.get("company_hotline", "").strip()
    company_logo = ""

    if not username or not email or not password:
        return jsonify({"error": "Missing fields"}), 400

    if role not in ("client", "staff", "company"):
        return jsonify({"error": "Invalid account type"}), 400

    if role == "company":
        if not company_address or not company_hotline:
            return jsonify({"error": "Company address and hotline are required"}), 400

        try:
            company_logo = save_company_logo(request.files.get("company_logo"), email)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    company_id = None

    if role == "staff":
        if not key:
            conn.close()
            return jsonify({"error": "Company staff key is required"}), 400

        cursor.execute(
            """
            SELECT id FROM users
            WHERE role='company' AND staff_registration_key=?
            """,
            (key,)
        )
        company = cursor.fetchone()
        if not company:
            conn.close()
            return jsonify({"error": "Invalid company staff key"}), 400

        company_id = company["id"]

    # Check duplicates
    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    if cursor.fetchone():
        return jsonify({"error": "Email already exists"}), 400

    cursor.execute("SELECT * FROM users WHERE username=?", (username,))
    if cursor.fetchone():
        return jsonify({"error": "Username taken"}), 400

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")

    cursor.execute(
        """
        INSERT INTO users (
            username, email, password, role, company_logo, company_address, company_hotline, company_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (username, email, hashed, role, company_logo, company_address, company_hotline, company_id)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Registration successful"})


# LOGIN
@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()

    if not user:
        return jsonify({"error": "Invalid email"}), 401

    user = dict(user)

    if not bcrypt.check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid password"}), 401

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "email": user["email"],
        "company_logo": user["company_logo"],
        "company_address": user["company_address"],
        "company_hotline": user["company_hotline"],
        "company_id": user["company_id"],
        "staff_registration_key": user["staff_registration_key"],
        "is_prime_staff": user["is_prime_staff"]
    })


# COMPANY LOGIN
@auth_bp.route("/company-login", methods=["POST"])
def company_login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify({"error": "Invalid email"}), 401

    user = dict(user)

    if user["role"] != "company":
        return jsonify({"error": "This login is for company accounts only"}), 403

    if not bcrypt.check_password_hash(user["password"], password):
        return jsonify({"error": "Invalid password"}), 401

    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "email": user["email"],
        "company_logo": user["company_logo"],
        "company_address": user["company_address"],
        "company_hotline": user["company_hotline"],
        "company_id": user["company_id"],
        "staff_registration_key": user["staff_registration_key"],
        "is_prime_staff": user["is_prime_staff"]
    })

import os

from flask import Blueprint, request, jsonify
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename

from database import get_db_connection

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "company_logos")
STAFF_PIC_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "staff_pics")
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


def save_staff_profile_pic(file_storage, username):
    if not file_storage or not file_storage.filename:
        return ""

    if not allowed_logo(file_storage.filename):
        raise ValueError("Staff profile picture must be an image file: png, jpg, jpeg, gif, or webp")

    os.makedirs(STAFF_PIC_FOLDER, exist_ok=True)
    original_filename = secure_filename(file_storage.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    username_slug = secure_filename(username) or "staff"
    filename = f"{username_slug}_profile.{extension}"
    save_path = os.path.join(STAFF_PIC_FOLDER, filename)
    file_storage.save(save_path)
    return f"/static/uploads/staff_pics/{filename}"

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
    profile_pic = ""

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
    elif role == "staff":
        try:
            profile_pic = save_staff_profile_pic(request.files.get("profile_pic"), username)
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
            username, email, password, role, company_logo, company_address, company_hotline, company_id, profile_pic
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (username, email, hashed, role, company_logo, company_address, company_hotline, company_id, profile_pic)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Registration successful"})


@auth_bp.route("/staff-profile/<int:staff_id>", methods=["GET"])
def get_staff_profile(staff_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, email, profile_pic, company_id, is_prime_staff, staff_about, first_name, last_name, phone_number, address, department, skills FROM users WHERE id=? AND role='staff'",
        (staff_id,)
    )
    staff = cursor.fetchone()
    conn.close()

    if not staff:
        return jsonify({"error": "Staff not found"}), 404

    return jsonify({
        "id": staff["id"],
        "username": staff["username"],
        "email": staff["email"],
        "profile_pic": staff["profile_pic"],
        "company_id": staff["company_id"],
        "is_prime_staff": bool(staff["is_prime_staff"]),
        "staff_about": staff["staff_about"] or "",
        "first_name": staff["first_name"] or "",
        "last_name": staff["last_name"] or "",
        "phone_number": staff["phone_number"] or "",
        "address": staff["address"] or "",
        "department": staff["department"] or "",
        "skills": staff["skills"] or ""
    })


@auth_bp.route("/staff-profile/<int:staff_id>", methods=["POST"])
def update_staff_profile(staff_id):
    if request.form:
        data = request.form
    else:
        data = request.get_json() or {}

    user_id = data.get("user_id")
    if not user_id or int(user_id) != staff_id:
        return jsonify({"error": "User ID mismatch or missing"}), 403

    profile_pic = None
    staff_about = data.get("staff_about")
    delete_about = data.get("delete_about") in ("true", "True", "1", 1, True)
    first_name = data.get("first_name") if "first_name" in data else None
    last_name = data.get("last_name") if "last_name" in data else None
    phone_number = data.get("phone_number") if "phone_number" in data else None
    address = data.get("address") if "address" in data else None
    department = data.get("department") if "department" in data else None
    skills = data.get("skills") if "skills" in data else None

    if "profile_pic" in request.files:
        try:
            profile_pic = save_staff_profile_pic(request.files.get("profile_pic"), f"staff_{staff_id}")
        except ValueError as error:
            return jsonify({"error": str(error)}), 400

    if (
        profile_pic is None
        and staff_about is None
        and not delete_about
        and first_name is None
        and last_name is None
        and phone_number is None
        and address is None
        and department is None
        and skills is None
    ):
        return jsonify({"error": "No update data provided"}), 400

    updates = []
    params = []

    if profile_pic:
        updates.append("profile_pic=?")
        params.append(profile_pic)

    if staff_about is not None:
        updates.append("staff_about=?")
        params.append(staff_about)
    elif delete_about:
        updates.append("staff_about=?")
        params.append("")

    if first_name is not None:
        updates.append("first_name=?")
        params.append(first_name)
    if last_name is not None:
        updates.append("last_name=?")
        params.append(last_name)
    if phone_number is not None:
        updates.append("phone_number=?")
        params.append(phone_number)
    if address is not None:
        updates.append("address=?")
        params.append(address)
    if department is not None:
        updates.append("department=?")
        params.append(department)
    if skills is not None:
        updates.append("skills=?")
        params.append(skills)

    params.append(staff_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE users SET {', '.join(updates)} WHERE id=? AND role='staff'",
        tuple(params)
    )
    conn.commit()
    conn.close()

    response = {"message": "Profile updated"}
    if profile_pic:
        response["profile_pic"] = profile_pic
    if staff_about is not None:
        response["staff_about"] = staff_about
    if delete_about:
        response["staff_about"] = ""
    if first_name is not None:
        response["first_name"] = first_name
    if last_name is not None:
        response["last_name"] = last_name
    if phone_number is not None:
        response["phone_number"] = phone_number
    if address is not None:
        response["address"] = address
    if department is not None:
        response["department"] = department
    if skills is not None:
        response["skills"] = skills

    return jsonify(response)


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    conn.close()

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
        "profile_pic": user.get("profile_pic", ""),
        "staff_about": user.get("staff_about", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "phone_number": user.get("phone_number", ""),
        "address": user.get("address", ""),
        "department": user.get("department", ""),
        "skills": user.get("skills", ""),
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
        "profile_pic": user.get("profile_pic", ""),
        "staff_about": user.get("staff_about", ""),
        "staff_registration_key": user["staff_registration_key"],
        "is_prime_staff": user["is_prime_staff"]
    })

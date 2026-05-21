import secrets
import string
import json
import os

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename

from database import get_db_connection

company_bp = Blueprint("company", __name__)

VALID_STATUS = ["pending", "accepted", "processing", "done", "completed", "declined"]
STAFF_ALLOWED_STATUS = ["pending", "processing", "done", "completed"]
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COMPANY_MEDIA_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "company_media")
COMPANY_LOGO_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "company_logos")
ALLOWED_MEDIA_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "mp4", "webm", "mov"}
ALLOWED_LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def create_staff_key():
    alphabet = string.ascii_uppercase + string.digits
    return "COMP-" + "".join(secrets.choice(alphabet) for _ in range(10))


def allowed_media(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_MEDIA_EXTENSIONS


def media_type(filename):
    extension = filename.rsplit(".", 1)[1].lower()
    return "video" if extension in {"mp4", "webm", "mov"} else "image"


def allowed_logo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


def save_company_logo(file_storage, company_id):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_logo(file_storage.filename):
        raise ValueError("Company logo must be an image file: png, jpg, jpeg, gif, or webp")

    os.makedirs(COMPANY_LOGO_FOLDER, exist_ok=True)
    original_filename = secure_filename(file_storage.filename)
    extension = original_filename.rsplit(".", 1)[1].lower()
    filename = f"company_{company_id}_logo.{extension}"
    save_path = os.path.join(COMPANY_LOGO_FOLDER, filename)
    file_storage.save(save_path)
    return f"/static/uploads/company_logos/{filename}"


def can_edit_company_profile(cursor, company_id, user_id):
    cursor.execute("SELECT id, role, company_id, is_prime_staff FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        return False

    if user["role"] == "company" and int(user["id"]) == int(company_id):
        return True

    return (
        user["role"] == "staff"
        and user["company_id"] is not None
        and int(user["company_id"]) == int(company_id)
        and user["is_prime_staff"] == 1
    )


def can_view_company_profile(cursor, company_id, user_id):
    cursor.execute("SELECT id, role, company_id FROM users WHERE id=?", (user_id,))
    user = cursor.fetchone()

    if not user:
        return False

    if user["role"] == "company" and int(user["id"]) == int(company_id):
        return True

    return (
        user["role"] == "staff"
        and user["company_id"] is not None
        and int(user["company_id"]) == int(company_id)
    )


def save_company_media(files, company_id):
    saved = []
    os.makedirs(COMPANY_MEDIA_FOLDER, exist_ok=True)

    for file_storage in files:
        if not file_storage or not file_storage.filename:
            continue

        if not allowed_media(file_storage.filename):
            raise ValueError("Media must be an image or video file")

        original_filename = secure_filename(file_storage.filename)
        extension = original_filename.rsplit(".", 1)[1].lower()
        filename = f"company_{company_id}_{secrets.token_hex(8)}.{extension}"
        save_path = os.path.join(COMPANY_MEDIA_FOLDER, filename)
        file_storage.save(save_path)
        saved.append({
            "url": f"/static/uploads/company_media/{filename}",
            "type": media_type(filename),
            "name": original_filename,
        })

    return saved


# GENERATE COMPANY STAFF KEY
@company_bp.route("/generate-staff-key", methods=["POST"])
def generate_staff_key():
    data = request.get_json() or {}
    company_id = data.get("company_id")

    if not company_id:
        return jsonify({"error": "Company id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id=? AND role='company'", (company_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": "Invalid company account"}), 400

    while True:
        staff_key = create_staff_key()
        cursor.execute(
            "SELECT id FROM users WHERE staff_registration_key=?",
            (staff_key,)
        )
        if not cursor.fetchone():
            break

    cursor.execute(
        "UPDATE users SET staff_registration_key=? WHERE id=? AND role='company'",
        (staff_key, company_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"staff_registration_key": staff_key})


# PUBLIC COMPANY LIST FOR CLIENTS
@company_bp.route("/companies", methods=["GET"])
def companies():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, email, company_logo, company_address, company_hotline,
               company_about, company_media
        FROM users
        WHERE role='company'
        ORDER BY username
        """
    )

    result = []
    for row in cursor.fetchall():
        company = dict(row)
        company["company_media"] = json.loads(company["company_media"] or "[]")
        result.append(company)

    conn.close()
    return jsonify(result)


# COMPANY PROFILE
@company_bp.route("/company-profile/<int:company_id>", methods=["GET"])
def get_company_profile(company_id):
    user_id = request.args.get("user_id")

    if not user_id:
        return jsonify({"error": "User id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if not can_view_company_profile(cursor, company_id, user_id):
        conn.close()
        return jsonify({"error": "Not allowed to view this company profile"}), 403

    cursor.execute(
        """
        SELECT id, username, company_about, company_media
        FROM users
        WHERE id=? AND role='company'
        """,
        (company_id,)
    )
    company = cursor.fetchone()
    editable = can_edit_company_profile(cursor, company_id, user_id)
    conn.close()

    if not company:
        return jsonify({"error": "Company not found"}), 404

    return jsonify({
        "company_id": company["id"],
        "company_name": company["username"],
        "company_about": company["company_about"] or "",
        "company_media": json.loads(company["company_media"] or "[]"),
        "can_edit": editable,
    })


@company_bp.route("/company-profile/<int:company_id>", methods=["POST"])
def update_company_profile(company_id):
    data = request.form if request.form else (request.get_json() or {})
    user_id = data.get("user_id")
    company_about = data.get("company_about", "").strip()
    delete_profile = data.get("delete_profile") in ("true", "True", "1", 1, True)

    if not user_id:
        return jsonify({"error": "User id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    if not can_edit_company_profile(cursor, company_id, user_id):
        conn.close()
        return jsonify({"error": "Only the company or a prime staff member can edit this profile"}), 403

    cursor.execute(
        "SELECT company_media FROM users WHERE id=? AND role='company'",
        (company_id,)
    )
    company = cursor.fetchone()
    if not company:
        conn.close()
        return jsonify({"error": "Company not found"}), 404

    existing_media = json.loads(company["company_media"] or "[]")

    if delete_profile:
        company_media = []
        company_about = ""
        company_logo = None
    else:
        company_logo = None
        if request.files.get("company_logo"):
            try:
                company_logo = save_company_logo(request.files.get("company_logo"), company_id)
            except ValueError as error:
                conn.close()
                return jsonify({"error": str(error)}), 400

        try:
            new_media = save_company_media(request.files.getlist("company_media"), company_id)
        except ValueError as error:
            conn.close()
            return jsonify({"error": str(error)}), 400

        company_media = existing_media + new_media

    update_fields = ["company_about=?, company_media=?"]
    params = [company_about, json.dumps(company_media)]
    if company_logo is not None:
        update_fields.append("company_logo=?")
        params.append(company_logo)

    params.append(company_id)

    cursor.execute(
        f"UPDATE users SET {', '.join(update_fields)} WHERE id=? AND role='company'",
        tuple(params)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Company profile updated",
        "company_about": company_about,
        "company_media": company_media,
    })


@company_bp.route("/set-prime-staff", methods=["PUT"])
def set_prime_staff():
    data = request.get_json() or {}
    company_id = data.get("company_id")
    actor_id = data.get("actor_id")
    username = data.get("username")
    is_prime = 1 if data.get("is_prime") else 0

    if not company_id or not actor_id or not username:
        return jsonify({"error": "Company id, actor id, and staff username are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE id=? AND role='company'",
        (actor_id,)
    )
    actor = cursor.fetchone()
    if not actor or int(actor["id"]) != int(company_id):
        conn.close()
        return jsonify({"error": "Only the company account can assign prime staff"}), 403

    cursor.execute(
        "SELECT id FROM users WHERE username=? AND role='staff' AND company_id=?",
        (username, company_id)
    )
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        return jsonify({"error": "Staff not found in this company"}), 400

    cursor.execute(
        "UPDATE users SET is_prime_staff=? WHERE id=?",
        (is_prime, staff["id"])
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Prime staff updated"})

# UPDATE STATUS
@company_bp.route("/update-status/<int:ad_id>", methods=["PUT"])
def update_status(ad_id):
    data = request.get_json() or {}
    status = data.get("status")
    role = data.get("role")
    user_id = data.get("user_id")

    if status not in VALID_STATUS:
        return jsonify({"error": "Invalid status"}), 400

    if role not in ("company", "staff"):
        return jsonify({"error": "Account role is required"}), 400

    if not user_id:
        return jsonify({"error": "User id is required"}), 400

    if role == "staff" and status not in STAFF_ALLOWED_STATUS:
        return jsonify({"error": "Staff cannot accept or decline campaigns"}), 403

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT advertisements.id, advertisements.company_id, advertisements.assigned_staff,
               users.username, users.role, users.company_id AS staff_company_id
        FROM advertisements
        LEFT JOIN users ON users.id=?
        WHERE advertisements.id=?
        """,
        (user_id, ad_id)
    )
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Campaign not found"}), 404

    if role == "company":
        if row["role"] != "company" or int(row["company_id"]) != int(user_id):
            conn.close()
            return jsonify({"error": "Only the selected company can update this campaign"}), 403
    else:
        allowed_staff = (
            row["role"] == "staff"
            and row["staff_company_id"] is not None
            and int(row["staff_company_id"]) == int(row["company_id"])
            and row["assigned_staff"] == row["username"]
        )
        if not allowed_staff:
            conn.close()
            return jsonify({"error": "Only the assigned staff can update this campaign"}), 403

    cursor.execute(
        "UPDATE advertisements SET status=? WHERE id=?",
        (status, ad_id)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Status updated"})


# ASSIGN STAFF
@company_bp.route("/assign-staff/<int:ad_id>", methods=["PUT"])
def assign_staff(ad_id):
    data = request.get_json() or {}
    staff = data.get("assigned_staff")
    company_id = data.get("company_id")

    if not staff:
        return jsonify({"error": "Staff required"}), 400

    if not company_id:
        return jsonify({"error": "Company id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM advertisements WHERE id=? AND company_id=?",
        (ad_id, company_id)
    )
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": "Campaign not found for this company"}), 404

    # Validate staff exists
    cursor.execute(
        "SELECT * FROM users WHERE username=? AND role='staff' AND company_id=?",
        (staff, company_id)
    )

    if not cursor.fetchone():
        return jsonify({"error": "Invalid staff"}), 400

    cursor.execute(
        "UPDATE advertisements SET assigned_staff=? WHERE id=?",
        (staff, ad_id)
    )

    conn.commit()
    conn.close()

    return jsonify({"message": "Staff assigned"})


# STAFF LIST
@company_bp.route("/staff-list", methods=["GET"])
def staff_list():
    company_id = request.args.get("company_id")

    if not company_id:
        return jsonify({"error": "Company id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, username, profile_pic, is_prime_staff, first_name, last_name, phone_number, address, department, skills, staff_about FROM users WHERE role='staff' AND company_id=?",
        (company_id,)
    )
    staff = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return jsonify(staff)

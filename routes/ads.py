import os
import secrets
import json

from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from database import get_db_connection

ads_bp = Blueprint("ads", __name__)

# CREATE AD
@ads_bp.route("/create-ad", methods=["POST"])
def create_ad():
    data = request.get_json()

    user_id = data.get("user_id")
    company_id = data.get("company_id")
    product_name = data.get("product_name")
    quantity = data.get("quantity")
    ad_type = data.get("ad_type")
    description = data.get("description")
    location = data.get("location") or "Not specified"
    start_date = data.get("start_date")
    end_date = data.get("end_date")

    if not user_id or not company_id or not product_name or not ad_type:
        return jsonify({"error": "Missing required fields"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id=? AND role='company'", (company_id,))
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": "Please select a valid company"}), 400

    cursor.execute("""
        INSERT INTO advertisements
        (user_id, company_id, product_name, quantity, ad_type, description, location, start_date, end_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, company_id, product_name, quantity, ad_type, description, location, start_date, end_date))

    conn.commit()
    conn.close()

    return jsonify({"message": "Ad created successfully"})


# GET ALL ADS
@ads_bp.route("/ads", methods=["GET"])
def get_ads():
    company_id = request.args.get("company_id")
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT advertisements.*, users.username, companies.username AS company_name
        FROM advertisements
        JOIN users ON advertisements.user_id = users.id
        LEFT JOIN users AS companies ON advertisements.company_id = companies.id
    """
    params = []

    if company_id:
        query += " WHERE advertisements.company_id=?"
        params.append(company_id)

    query += " ORDER BY created_at DESC"
    cursor.execute(query, params)

    ads = []
    for row in cursor.fetchall():
        ad = dict(row)
        ad["completion_media"] = json.loads(ad["completion_media"]) if ad["completion_media"] else []
        ads.append(ad)

    conn.close()

    return jsonify(ads)


@ads_bp.route("/submit-completion/<int:ad_id>", methods=["POST"])
def submit_completion(ad_id):
    staff_id = request.form.get("staff_id")
    if not staff_id:
        return jsonify({"error": "Staff id is required"}), 400

    evidence_files = request.files.getlist("work_images")
    if not evidence_files and "work_image" in request.files:
        evidence_files = [request.files["work_image"]]

    evidence_files = [file for file in evidence_files if file and file.filename]
    if not evidence_files:
        return jsonify({"error": "At least one completion evidence image is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, is_prime_staff FROM users WHERE id=? AND role='staff'", (staff_id,))
    staff = cursor.fetchone()
    if not staff:
        conn.close()
        return jsonify({"error": "Staff account not found"}), 404

    cursor.execute("SELECT assigned_staff, completion_media FROM advertisements WHERE id=?", (ad_id,))
    ad = cursor.fetchone()
    if not ad:
        conn.close()
        return jsonify({"error": "Advertisement not found"}), 404

    if ad["assigned_staff"] != staff["username"]:
        conn.close()
        return jsonify({"error": "Only the assigned staff can submit completion evidence"}), 403

    upload_folder = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "completion_media")
    os.makedirs(upload_folder, exist_ok=True)

    existing_media = json.loads(ad["completion_media"]) if ad["completion_media"] else []
    for work_image in evidence_files:
        filename = secure_filename(work_image.filename)
        unique_name = f"completion_{secrets.token_hex(8)}_{filename}"
        save_path = os.path.join(upload_folder, unique_name)
        work_image.save(save_path)
        existing_media.append(f"/static/uploads/completion_media/{unique_name}")

    confirmed = 1 if staff["is_prime_staff"] else 0
    status = "completed" if confirmed else "done"

    cursor.execute(
        """
        UPDATE advertisements
        SET completion_media=?, completion_confirmed=?, completion_submitted_by=?,
            completion_submitted_at=CURRENT_TIMESTAMP, status=?
        WHERE id=?
        """,
        (json.dumps(existing_media), confirmed, staff_id, status, ad_id)
    )
    conn.commit()
    conn.close()

    return jsonify({
        "message": "Completion evidence uploaded",
        "status": status,
        "completion_confirmed": confirmed,
        "completion_media": existing_media
    })


@ads_bp.route("/work-done-evidence", methods=["GET"])
def work_done_evidence():
    role = request.args.get("role")
    user_id = request.args.get("user_id")

    if role not in ("company", "staff", "client") or not user_id:
        return jsonify({"error": "Role and user id are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, username FROM users WHERE id=? AND role=?", (user_id, role))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "Invalid account"}), 403

    query = """
        SELECT advertisements.*, clients.username AS client_name, companies.username AS company_name
        FROM advertisements
        LEFT JOIN users AS clients ON advertisements.user_id = clients.id
        LEFT JOIN users AS companies ON advertisements.company_id = companies.id
        WHERE advertisements.completion_media IS NOT NULL
          AND advertisements.completion_media != ''
    """
    params = []

    if role == "company":
        query += " AND advertisements.company_id=?"
        params.append(user_id)
    elif role == "client":
        query += " AND advertisements.user_id=? AND advertisements.completion_confirmed=1"
        params.append(user_id)
    else:
        query += " AND advertisements.assigned_staff=?"
        params.append(user["username"])

    query += " ORDER BY advertisements.completion_submitted_at DESC, advertisements.created_at DESC"
    cursor.execute(query, params)

    evidence = []
    for row in cursor.fetchall():
        item = dict(row)
        item["completion_media"] = json.loads(item["completion_media"] or "[]")
        evidence.append(item)

    conn.close()
    return jsonify(evidence)


@ads_bp.route("/confirm-completion/<int:ad_id>", methods=["POST"])
def confirm_completion(ad_id):
    data = request.get_json() or {}
    company_id = data.get("company_id")

    if not company_id:
        return jsonify({"error": "Company id is required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM advertisements WHERE id=? AND company_id=? AND completion_media IS NOT NULL AND completion_media != ''",
        (ad_id, company_id)
    )
    if not cursor.fetchone():
        conn.close()
        return jsonify({"error": "Evidence not found for this company"}), 404

    cursor.execute(
        "UPDATE advertisements SET completion_confirmed=1, status='completed' WHERE id=?",
        (ad_id,)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Work done evidence confirmed"})


# CLIENT ADS
@ads_bp.route("/my-ads/<int:user_id>", methods=["GET"])
def my_ads(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT advertisements.*, companies.username AS company_name
        FROM advertisements
        LEFT JOIN users AS companies ON advertisements.company_id = companies.id
        WHERE advertisements.user_id=?
        ORDER BY created_at DESC
    """, (user_id,))

    ads = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(ads)

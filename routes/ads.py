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

    if "work_image" not in request.files:
        return jsonify({"error": "Completion evidence image is required"}), 400

    work_image = request.files["work_image"]
    if work_image.filename == "":
        return jsonify({"error": "Invalid completion image"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE id=? AND role='staff'", (staff_id,))
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

    filename = secure_filename(work_image.filename)
    unique_name = f"completion_{secrets.token_hex(8)}_{filename}"
    upload_folder = os.path.join(os.path.dirname(__file__), "..", "static", "uploads", "completion_media")
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, unique_name)
    work_image.save(save_path)

    file_path = f"/static/uploads/completion_media/{unique_name}"

    existing_media = json.loads(ad["completion_media"]) if ad["completion_media"] else []
    existing_media.append(file_path)

    cursor.execute(
        "UPDATE advertisements SET completion_media=?, status='completed' WHERE id=?",
        (json.dumps(existing_media), ad_id)
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "Completion evidence uploaded", "status": "completed", "completion_media": existing_media})


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

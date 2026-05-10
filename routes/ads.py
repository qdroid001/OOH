from flask import Blueprint, request, jsonify
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

    ads = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify(ads)


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

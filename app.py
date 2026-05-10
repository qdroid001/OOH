from flask import Flask, redirect, render_template
from flask_cors import CORS

from models import init_db
from routes.auth import auth_bp
from routes.ads import ads_bp
from routes.company import company_bp

app = Flask(__name__)
CORS(app)

# INIT DB
init_db()

# REGISTER ROUTES
app.register_blueprint(auth_bp)
app.register_blueprint(ads_bp)
app.register_blueprint(company_bp)

# FRONTEND ROUTES
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/company.html")
def company():
    return render_template("company.html")

@app.route("/admin")
@app.route("/admin.html")
def legacy_admin():
    return redirect("/company.html")

@app.route("/staff.html")
def staff():
    return render_template("staff.html")

@app.route("/client.html")
def client():
    return render_template("client.html")


if __name__ == "__main__":
    app.run(debug=True)

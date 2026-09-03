from flask import Flask, render_template, request, send_file, session, redirect, url_for
import csv
import os
import pandas as pd
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "smart_irrigation_secret_key"

CSV_FILE = "irrigation_data.csv"
DATABASE = "users.db"


# =========================================================
# CREATE IRRIGATION CSV
# =========================================================

if not os.path.exists(CSV_FILE):

    with open(CSV_FILE, "w", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            "Field",
            "Crop Stage",
            "Soil Moisture",
            "Weather",
            "Water Available",
            "Priority",
            "Decision",
            "Reason",
            "Recommended Water",
            "Water Saved",
            "Fairness"
        ])


# =========================================================
# CREATE USER DATABASE
# =========================================================

def create_database():

    connection = sqlite3.connect(DATABASE)

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    connection.commit()

    connection.close()


create_database()


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        connection = sqlite3.connect(DATABASE)

        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name, username, password FROM users WHERE username = ?",
            (username,)
        )

        user = cursor.fetchone()

        connection.close()

        if user and check_password_hash(user[3], password):

            session["logged_in"] = True
            session["user_id"] = user[0]
            session["username"] = user[2]
            session["name"] = user[1]

            return redirect(url_for("dashboard"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:

            return render_template(
                "register.html",
                error="Passwords do not match"
            )

        connection = sqlite3.connect(DATABASE)

        cursor = connection.cursor()

        cursor.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            connection.close()

            return render_template(
                "register.html",
                error="Username already exists"
            )

        password_hash = generate_password_hash(password)

        cursor.execute(
            """
            INSERT INTO users (name, username, password)
            VALUES (?, ?, ?)
            """,
            (name, username, password_hash)
        )

        connection.commit()

        connection.close()

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if not session.get("logged_in"):

        return redirect(url_for("login"))

    return render_template(
        "dashboard.html",
        username=session.get("username"),
        name=session.get("name")
    )


# =========================================================
# RESULT
# =========================================================

@app.route("/result", methods=["POST"])
def result():

    if not session.get("logged_in"):

        return redirect(url_for("login"))

    field = request.form["field"]
    stage = request.form["stage"]
    moisture = int(request.form["moisture"])
    weather = request.form["weather"]
    water = int(request.form["water"])
    priority = request.form["priority"]


    # -----------------------------------------------------
    # IRRIGATION DECISION
    # -----------------------------------------------------

    if weather == "Rain":

        decision = "Do Not Irrigate"
        reason = "Rain is expected. Irrigation stopped."

    elif water == 0:

        decision = "Cannot Irrigate"
        reason = "No water available."

    elif moisture < 30:

        decision = "Irrigate Immediately"
        reason = "Soil moisture is critically low."

    elif stage == "Flowering":

        decision = "Irrigate"
        reason = "Flowering stage requires sufficient water."

    elif priority == "High" and water >= 100:

        decision = "Priority Irrigation"
        reason = "High priority field receives preference."

    elif water < 100:

        decision = "Limited Irrigation"
        reason = "Water is limited. Irrigate only essential fields."

    else:

        decision = "Normal Irrigation"
        reason = "Conditions are suitable."


    # -----------------------------------------------------
    # WATER CALCULATION
    # -----------------------------------------------------

    required_water = 200

    if weather == "Rain":

        recommended_water = 0

    elif moisture < 30:

        recommended_water = 180

    elif moisture < 50:

        recommended_water = 120

    else:

        recommended_water = 60

    if water < recommended_water:

        recommended_water = water

    water_saved = required_water - recommended_water

    if water_saved < 0:

        water_saved = 0


    # -----------------------------------------------------
    # FAIRNESS
    # -----------------------------------------------------

    if priority == "High":

        fairness = "Highest Priority Allocated"

    elif priority == "Medium":

        fairness = "Balanced Allocation"

    else:

        fairness = "Low Priority Allocation"


    # -----------------------------------------------------
    # SAVE DATA
    # -----------------------------------------------------

    with open(CSV_FILE, "a", newline="") as file:

        writer = csv.writer(file)

        writer.writerow([
            field,
            stage,
            moisture,
            weather,
            water,
            priority,
            decision,
            reason,
            recommended_water,
            water_saved,
            fairness
        ])


    return render_template(
        "result.html",
        field=field,
        stage=stage,
        moisture=moisture,
        weather=weather,
        water=water,
        priority=priority,
        decision=decision,
        reason=reason,
        recommended_water=recommended_water,
        water_saved=water_saved,
        fairness=fairness
    )


# =========================================================
# REPORT
# =========================================================

@app.route("/report")
def report():

    if not session.get("logged_in"):

        return redirect(url_for("login"))

    data = pd.read_csv(CSV_FILE)

    records = data.values.tolist()

    total = len(data)

    total_recommended_water = data["Recommended Water"].sum()

    total_water_saved = data["Water Saved"].sum()

    high_priority_fields = len(
        data[data["Priority"] == "High"]
    )

    if total > 0:

        fairness_score = round(
            (high_priority_fields / total) * 100,
            2
        )

    else:

        fairness_score = 0

    other_fields = total - high_priority_fields

    return render_template(
        "report.html",
        data=records,
        total=total,
        total_recommended_water=total_recommended_water,
        total_water_saved=total_water_saved,
        high_priority_fields=high_priority_fields,
        other_fields=other_fields,
        fairness_score=fairness_score
    )


# =========================================================
# ADMIN OVERRIDE
# =========================================================

@app.route("/override", methods=["GET", "POST"])
def override():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    if request.method == "POST":

        field = request.form["field"]
        decision = request.form["decision"]
        reason = request.form["reason"]

        if not os.path.exists(CSV_FILE):
            return render_template(
                "override.html",
                error="CSV file not found."
            )

        data = pd.read_csv(CSV_FILE)

        # Check whether field exists
        if field not in data["Field"].astype(str).values:
            return render_template(
                "override.html",
                error="Field not found in irrigation history."
            )

        # Find the selected field
        index = data[
            data["Field"].astype(str).str.lower() == field.lower()
        ].index[-1]

        # Update decision and reason
        data.loc[index, "Decision"] = decision
        data.loc[index, "Reason"] = reason

        # Update recommended water based on override decision
        if decision == "Do Not Irrigate" or decision == "Cannot Irrigate":
            recommended_water = 0
        elif decision == "Irrigate Immediately":
            recommended_water = 180
        elif decision == "Limited Irrigation":
            recommended_water = 50
        else:
            recommended_water = 60

        data.loc[index, "Recommended Water"] = recommended_water

        # Recalculate water saved
        required_water = 200
        water_saved = required_water - recommended_water

        if water_saved < 0:
            water_saved = 0

        data.loc[index, "Water Saved"] = water_saved

        # Save updated data back to CSV
        data.to_csv(CSV_FILE, index=False)

        return render_template(
            "override.html",
            success=True,
            field=field,
            decision=decision,
            reason=reason
        )

    return render_template("override.html")
# =========================================================
# DOWNLOAD REPORT
# =========================================================

@app.route("/download")
def download():

    if not session.get("logged_in"):

        return redirect(url_for("login"))

    return send_file(
        CSV_FILE,
        as_attachment=True,
        download_name="irrigation_report.csv",
        mimetype="text/csv"
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    print("===================================")
    print("🌱 Smart Irrigation Scheduler")
    print("===================================")
    print("🔐 Login: http://127.0.0.1:5000/login")
    print("===================================")

    app.run(debug=True)
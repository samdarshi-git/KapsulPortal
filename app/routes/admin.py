# app/routes/admin.py
# app/routes/admin.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, User, Device
from functools import wraps

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# --- Decorator ---
def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("🚫 Access restricted to admins only.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return wrapper

# --- DASHBOARD ---
@admin_bp.route("/dashboard", methods=["GET", "POST"])
@login_required
@admin_required
def dashboard():
    users = User.query.all()
    patients = [u for u in users if u.role == "patient"]
    doctors = [u for u in users if u.role == "doctor"]
    devices = Device.query.all()
    pending_users = [u for u in users if not u.approved]

    if request.method == "POST":
        # Add device
        if "add_device" in request.form:
            device_code = request.form.get("device_code")
            owner_id = request.form.get("owner_id") or None
            compartments = int(request.form.get("total_compartments", 8))
            if not device_code:
                flash("⚠️ Device code required.", "warning")
                return redirect(url_for("admin.dashboard"))
            if Device.query.filter_by(device_code=device_code).first():
                flash("❌ Device code already exists!", "danger")
                return redirect(url_for("admin.dashboard"))
            new_device = Device(device_code=device_code, owner_id=owner_id, total_compartments=compartments)
            db.session.add(new_device)
            db.session.commit()
            flash(f"✅ Added device {device_code} with {compartments} compartments.", "success")

        # Approve user
        if "approve_user" in request.form:
            user_id = int(request.form.get("user_id"))
            user = User.query.get(user_id)
            user.approved = True
            db.session.commit()
            flash(f"✅ Approved {user.name} ({user.role}).", "success")

        # Reject user
        if "reject_user" in request.form:
            user_id = int(request.form.get("user_id"))
            user = User.query.get(user_id)
            db.session.delete(user)
            db.session.commit()
            flash(f"❌ Rejected user {user.name}.", "danger")

        # Delete user
        if "delete_user" in request.form:
            user_id = int(request.form.get("user_id"))
            user = User.query.get(user_id)
            db.session.delete(user)
            db.session.commit()
            flash(f"🗑️ Deleted {user.name}.", "danger")

        # Delete device
        if "delete_device" in request.form:
            device_code = request.form.get("device_code")
            device = Device.query.filter_by(device_code=device_code).first()
            db.session.delete(device)
            db.session.commit()
            flash(f"🗑️ Device {device.device_code} removed.", "danger")

        # Change device owner
        if "update_device_owner" in request.form:
            device_code = request.form.get("device_code")
            owner_id = request.form.get("owner_id") or None
            device = Device.query.filter_by(device_code=device_code).first()
            device.owner_id = owner_id
            db.session.commit()
            flash(f"🔄 Device {device.device_code} ownership updated.", "info")

        return redirect(url_for("admin.dashboard"))

    return render_template(
        "admin/dashboard.html",
        patients=patients,
        doctors=doctors,
        devices=devices,
        pending_users=pending_users,
        total_users=len(users),
        total_patients=len(patients),
        total_doctors=len(doctors),
        total_devices=len(devices),
        title="Admin Dashboard"
    )

from datetime import datetime, timedelta
from flask import jsonify
import random

@admin_bp.route("/dashboard-data")
@login_required
@admin_required
def dashboard_data():
    # Simulate or compute weekly stats
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).strftime("%b %d") for i in reversed(range(7))]
    user_growth = [random.randint(1, 5) for _ in range(7)]
    device_growth = [random.randint(0, 3) for _ in range(7)]

    approval_rate = 0
    total_users = User.query.count()
    approved_users = User.query.filter_by(approved=True).count()
    if total_users > 0:
        approval_rate = round((approved_users / total_users) * 100, 2)

    return jsonify({
        "dates": dates,
        "user_growth": user_growth,
        "device_growth": device_growth,
        "approval_rate": approval_rate,
        "total_users": total_users,
        "approved_users": approved_users
    })

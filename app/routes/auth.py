# app/routes/auth.py
# app/routes/auth.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models import User

auth_bp = Blueprint("auth", __name__)


# ---------------- LOGIN ----------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in and approved → redirect to their dashboard
    if current_user.is_authenticated:
        if current_user.approved:
            if current_user.role == "admin":
                return redirect(url_for("admin.dashboard"))
            elif current_user.role == "doctor":
                return redirect(url_for("doctor.dashboard"))
            elif current_user.role == "patient":
                return redirect(url_for("patient.dashboard"))
        # If not approved yet → force logout
        else:
            logout_user()
            flash("⏳ Your account is pending admin approval. Please wait.", "warning")
            return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if not user:
            flash("❌ Invalid username or password.", "danger")
            return redirect(url_for("auth.login"))

        if not check_password_hash(user.password_hash, password):
            flash("❌ Invalid username or password.", "danger")
            return redirect(url_for("auth.login"))

        # Block unapproved users from logging in
        if not user.approved:
            flash("⏳ Your account is still awaiting admin approval.", "warning")
            return redirect(url_for("auth.login"))

        # ✅ Everything ok — log in
        login_user(user)
        flash(f"Welcome back, {user.name}!", "success")

        # Role-based redirects
        if user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        elif user.role == "doctor":
            return redirect(url_for("doctor.dashboard"))
        elif user.role == "patient":
            return redirect(url_for("patient.dashboard"))
        else:
            return redirect(url_for("auth.home"))

    return render_template("auth/login.html", title="Login")


# ---------------- SIGNUP ----------------
@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():
    # If someone already logged in → go to dashboard
    if current_user.is_authenticated and current_user.approved:
        if current_user.role == "admin":
            return redirect(url_for("admin.dashboard"))
        elif current_user.role == "doctor":
            return redirect(url_for("doctor.dashboard"))
        elif current_user.role == "patient":
            return redirect(url_for("patient.dashboard"))

    if request.method == "POST":
        name = request.form.get("name")
        username = request.form.get("username")
        email = request.form.get("email") or None
        password = request.form.get("password")
        role = request.form.get("role")

        if not (name and username and password and role):
            flash("⚠️ Please fill in all required fields.", "warning")
            return redirect(url_for("auth.signup"))

        if User.query.filter_by(username=username).first():
            flash("❌ Username already exists. Choose another.", "danger")
            return redirect(url_for("auth.signup"))

        hashed_pw = generate_password_hash(password)
        new_user = User(
            name=name,
            username=username,
            email=email,
            password_hash=hashed_pw,
            role=role,
            approved=False  # Wait for admin approval
        )
        db.session.add(new_user)
        db.session.commit()

        flash("🎉 Signup successful! Wait for admin approval before logging in.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/signup.html", title="Signup")


# ---------------- LOGOUT ----------------
@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.home"))


# ---------------- HOME ----------------
@auth_bp.route("/")
def home():
    """
    Public landing page — visible to everyone, even if not logged in.
    Approved users can go to login/dashboard separately.
    """
    return render_template("home.html", title="Welcome to Smart Pill Portal")

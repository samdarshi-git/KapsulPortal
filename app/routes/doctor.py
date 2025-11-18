# app/routes/doctor.py
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.models import db, User, Device, Medication, Dosage, Log, Alert, DoctorPatientLink
from datetime import datetime

doctor_bp = Blueprint("doctor", __name__, url_prefix="/doctor")


# =============================
# Doctor Dashboard
# =============================
from app.utils.analytics import compute_patient_analytics
from datetime import timedelta

@doctor_bp.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    links_active = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, active=True).all()
    links_pending = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, active=False).all()

    # ---- Prepare patient summaries ----
    summaries = []
    for link in links_active:
        patient = link.patient_link
        device = Device.query.filter_by(owner_id=patient.id).first()

        # Analytics summary
        stats = compute_patient_analytics(patient)
        adherence = stats["adherence"]
        missed = stats["missed"]
        total = stats["total"]

        # Important alerts
        alerts = Alert.query.filter_by(user_id=patient.id).order_by(Alert.created_at.desc()).limit(5).all()

        # Flag important medicine alerts
        expiring_meds = Medication.query.filter(
            Medication.patient_id == patient.id,
            Medication.expiry <= datetime.utcnow().date() + timedelta(days=7)
        ).all()
        low_stock = Medication.query.filter(
            Medication.patient_id == patient.id,
            Medication.quantity <= 5
        ).all()

        important_alerts = []
        if expiring_meds:
            important_alerts.append(f"⚠️ {len(expiring_meds)} medicine(s) expiring soon")
        if low_stock:
            important_alerts.append(f"💊 {len(low_stock)} low in stock")
        if missed > 2:
            important_alerts.append(f"❌ {missed} missed doses in last 7 days")

        summaries.append({
            "patient": patient,
            "device": device,
            "link": link,
            "adherence": adherence,
            "missed": missed,
            "total": total,
            "alerts": important_alerts,
            "recent_alerts": alerts
        })

    return render_template(
        "doctor/dashboard.html",
        summaries=summaries,
        pending=links_pending,
        title="Doctor Dashboard"
    )


# =============================
# Approve / Reject Link (Dashboard)
# =============================
@doctor_bp.route("/approve_link/<int:link_id>")
@login_required
def approve_link(link_id):
    link = DoctorPatientLink.query.get_or_404(link_id)
    if link.doctor_id != current_user.id:
        flash("⚠️ Unauthorized action.", "danger")
        return redirect(url_for("doctor.dashboard"))

    link.active = True
    link.approved_at = datetime.utcnow()
    db.session.commit()

    flash(f"✅ You approved {link.patient_link.name}'s request.", "success")
    return redirect(url_for("doctor.dashboard"))


@doctor_bp.route("/reject_link/<int:link_id>")
@login_required
def reject_link(link_id):
    link = DoctorPatientLink.query.get_or_404(link_id)
    if link.doctor_id != current_user.id:
        flash("⚠️ Unauthorized action.", "danger")
        return redirect(url_for("doctor.dashboard"))

    db.session.delete(link)
    db.session.commit()
    flash(f"❌ You rejected {link.patient_link.name}'s request.", "warning")
    return redirect(url_for("doctor.dashboard"))


# =============================
# View All Linked Patients
# =============================
@doctor_bp.route("/patients")
@login_required
def patients():
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    links = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, active=True).all()
    return render_template("doctor/patients.html", links=links, title="My Patients")


# =============================
# View Single Patient Detail
# =============================
@doctor_bp.route("/patient/<int:patient_id>")
@login_required
def view_patient(patient_id):
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    patient = User.query.get_or_404(patient_id)
    link = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, patient_id=patient_id, active=True).first()

    if not link:
        flash("⚠️ You are not linked with this patient.", "warning")
        return redirect(url_for("doctor.dashboard"))

    device = Device.query.filter_by(owner_id=patient.id).first()
    meds = Medication.query.filter_by(patient_id=patient.id).all()

    logs = []
    if device:
        logs = Log.query.filter_by(device_id=device.id).order_by(Log.taken_time.desc()).limit(10).all()

    return render_template(
        "doctor/patient_detail.html",
        patient=patient,
        device=device,
        meds=meds,
        logs=logs,
        permissions=link,
        title=f"Patient: {patient.name}"
    )


# =============================
# Send Alert to Patient
# =============================
@doctor_bp.route("/patient/<int:patient_id>/alert", methods=["POST"])
@login_required
def send_alert(patient_id):
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    link = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, patient_id=patient_id, active=True).first()
    if not link or not link.allow_alerts:
        flash("⚠️ You do not have permission to send alerts to this patient.", "warning")
        return redirect(url_for("doctor.view_patient", patient_id=patient_id))

    patient = User.query.get_or_404(patient_id)
    title = request.form.get("title")
    message = request.form.get("message")

    if not title or not message:
        flash("⚠️ Both title and message are required.", "warning")
        return redirect(url_for("doctor.view_patient", patient_id=patient_id))

    new_alert = Alert(
        user_id=patient.id,
        title=title,
        message=message,
        created_at=datetime.utcnow()
    )
    db.session.add(new_alert)
    db.session.commit()

    flash(f"📩 Alert sent to {patient.name}.", "success")
    return redirect(url_for("doctor.view_patient", patient_id=patient_id))


# =============================
# Pending Link Requests Page
# =============================
@doctor_bp.route("/requests")
@login_required
def link_requests():
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    pending_links = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, active=False).all()
    return render_template(
        "doctor/requests.html",
        pending_links=pending_links,
        title="Pending Link Requests"
    )


# =============================
# Handle Approve/Reject Request
# =============================
@doctor_bp.route("/requests/<int:link_id>/<action>")
@login_required
def handle_link_request(link_id, action):
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    link = DoctorPatientLink.query.get_or_404(link_id)
    if link.doctor_id != current_user.id:
        flash("⚠️ Unauthorized action.", "danger")
        return redirect(url_for("doctor.link_requests"))

    patient = User.query.get_or_404(link.patient_id)

    if action == "approve":
        link.active = True
        link.approved_at = datetime.utcnow()
        msg = f"✅ Dr. {current_user.name} approved your link request."
        flash(f"✅ {patient.name} linked successfully.", "success")
    elif action == "reject":
        db.session.delete(link)
        msg = f"❌ Dr. {current_user.name} rejected your link request."
        flash(f"❌ Request from {patient.name} rejected.", "danger")
    else:
        flash("⚠️ Invalid action.", "warning")
        return redirect(url_for("doctor.link_requests"))

    alert = Alert(user_id=patient.id, title="Doctor Link Update", message=msg, created_at=datetime.utcnow())
    db.session.add(alert)
    db.session.commit()

    return redirect(url_for("doctor.link_requests"))

# =============================
# Doctor Alert Center
# =============================
from sqlalchemy import and_
from datetime import datetime, timedelta

@doctor_bp.route("/alerts")
@login_required
def view_alerts():
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    links = DoctorPatientLink.query.filter_by(doctor_id=current_user.id, active=True).all()
    patients = [l.patient_link for l in links]

    combined_alerts = []
    now = datetime.utcnow()
    seven_days = now + timedelta(days=7)

    for p in patients:
        meds = Medication.query.filter_by(patient_id=p.id).all()
        device = Device.query.filter_by(owner_id=p.id).first()

        # ⚠️ Expiring
        expiring = [m for m in meds if m.expiry and m.expiry <= seven_days.date()]
        # 💊 Low stock
        low_stock = [m for m in meds if m.quantity and m.quantity <= 5]

        # ❌ Missed doses (approx.)
        logs = Log.query.filter(Log.device_id == (device.device_code if device else None)).all()
        week_missed = len([l for l in logs if l.missed])
        important = [m for m in meds if m.importance_level == "High"]

        patient_alerts = []
        if expiring:
            patient_alerts.append({
                "type": "expiry",
                "color": "danger",
                "msg": f"{len(expiring)} medicine(s) expiring soon"
            })
        if low_stock:
            patient_alerts.append({
                "type": "stock",
                "color": "warning",
                "msg": f"{len(low_stock)} medicine(s) low in stock"
            })
        if week_missed > 2:
            patient_alerts.append({
                "type": "missed",
                "color": "danger",
                "msg": f"{week_missed} doses missed this week"
            })
        if any(m.name for m in important if week_missed > 0):
            patient_alerts.append({
                "type": "important",
                "color": "warning",
                "msg": f"Missed important medicine doses"
            })

        combined_alerts.append({
            "patient": p,
            "device": device,
            "alerts": patient_alerts
        })

    return render_template(
        "doctor/alert_center.html",
        combined_alerts=combined_alerts,
        title="Doctor Alert Center"
    )

# =============================
# View Patient Analytics
# ===========================
from app.utils.analytics import compute_patient_analytics, get_adherence_trend
from datetime import datetime, timedelta
from flask import jsonify

@doctor_bp.route("/patient/<int:patient_id>/analytics")
@login_required
def view_analytics(patient_id):
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    link = DoctorPatientLink.query.filter_by(
        doctor_id=current_user.id,
        patient_id=patient_id,
        active=True
    ).first()

    if not link or not link.allow_analytics:
        flash("⚠️ You don't have permission to view this patient's analytics.", "warning")
        return redirect(url_for("doctor.view_patient", patient_id=patient_id))

    patient = User.query.get_or_404(patient_id)
    device = Device.query.filter_by(owner_id=patient.id).first()

    stats = compute_patient_analytics(patient)
    trend_data = get_adherence_trend(patient)  # returns list of {date, adherence}

    # Prepare chart-friendly data
    chart_labels = [t["date"] for t in trend_data]
    chart_values = [t["adherence"] for t in trend_data]

    return render_template(
        "doctor/patient_analytics.html",
        patient=patient,
        device=device,
        stats=stats,
        chart_labels=chart_labels,
        chart_values=chart_values,
        title=f"Analytics - {patient.name}"
    )


# =============================
# Doctor Manage Medicines (with permission)
# =============================
from datetime import date, time

@doctor_bp.route("/patient/<int:patient_id>/medicines", methods=["GET", "POST"])
@login_required
def manage_meds(patient_id):
    if current_user.role != "doctor":
        flash("🚫 Access restricted to doctors only.", "danger")
        return redirect(url_for("auth.login"))

    link = DoctorPatientLink.query.filter_by(
        doctor_id=current_user.id, patient_id=patient_id, active=True
    ).first()

    if not link or not link.allow_med_update:
        flash("⚠️ You don't have permission to modify this patient's medicines.", "warning")
        return redirect(url_for("doctor.view_patient", patient_id=patient_id))

    patient = User.query.get_or_404(patient_id)
    device = Device.query.filter_by(owner_id=patient.id).first()

    # Preload medicines
    meds = {i: None for i in range(1, 9)}
    for med in Medication.query.filter_by(patient_id=patient.id).all():
        meds[med.compartment] = med

    if request.method == "POST":
        comp = int(request.form.get("compartment"))
        name = request.form.get("name")
        composition = request.form.get("composition")
        importance = request.form.get("importance_level")
        quantity = int(request.form.get("quantity"))
        expiry_month = int(request.form.get("expiry_month"))
        expiry_year = int(request.form.get("expiry_year"))
        expiry_date = date(expiry_year, expiry_month, 1)

        existing = Medication.query.filter_by(patient_id=patient.id, compartment=comp).first()

        if existing:
            existing.name = name
            existing.composition = composition
            existing.importance_level = importance
            existing.quantity = quantity
            existing.expiry = expiry_date
            Dosage.query.filter_by(medication_id=existing.id).delete()
            med = existing
            flash(f"✅ Updated medicine in compartment {comp}", "success")
        else:
            med = Medication(
                patient_id=patient.id,
                doctor_id=current_user.id,
                name=name,
                composition=composition,
                importance_level=importance,
                quantity=quantity,
                expiry=expiry_date,
                compartment=comp,
            )
            db.session.add(med)
            db.session.flush()
            flash(f"💊 Added new medicine in compartment {comp}", "success")

        # --- Dosages ---
        starts = request.form.getlist("time_start[]")
        ampm = request.form.getlist("ampm[]")
        foods = request.form.getlist("food_status[]")
        remarks = request.form.getlist("remark[]")

        for i in range(len(starts)):
            try:
                hour = int(starts[i])
            except ValueError:
                continue

            if ampm[i] == "PM" and hour != 12:
                hour += 12
            elif ampm[i] == "AM" and hour == 12:
                hour = 0

            start_time = time(hour, 0)
            end_time = time((hour + 1) % 24, 0)

            db.session.add(Dosage(
                medication_id=med.id,
                time_range_start=start_time,
                time_range_end=end_time,
                food_status=foods[i],
                remark=remarks[i],
            ))

        db.session.commit()

        if device:
            device.pending_sync = True
            db.session.commit()

        flash(f"📡 Sync flag set for patient’s device ({device.device_code if device else 'no device'})", "info")
        return redirect(url_for("doctor.manage_meds", patient_id=patient.id))

    return render_template(
        "doctor/manage_meds.html",
        meds=meds,
        patient=patient,
        device=device,
        title=f"Manage Medicines - {patient.name}"
    )

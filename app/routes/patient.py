# app/routes/patient.py

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from datetime import datetime, date, time
from sqlalchemy import func

from app.models import (
    db, User, Device, Medication, Dosage, Alert,
    DoctorPatientLink, DeviceState, Log, DeviceCommandQueue
)

from app.utils.device_sync import (
    build_config_json,
    build_schedule_json,
    build_audio_manifest_cached
)

from app.utils.analytics import compute_patient_analytics

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")


# =============================================================
# DEVICE COMMAND QUEUE (dedupe)
# =============================================================
def push_device_cmd(device, cmd, data=None):

    exists = DeviceCommandQueue.query.filter_by(
        device_code=device.device_code,
        command=cmd,
        processed=False
    ).first()

    if exists:
        return

    q = DeviceCommandQueue(
        device_code=device.device_code,
        command=cmd,
        data=data or {}
    )
    db.session.add(q)
    db.session.commit()


# =============================================================
# DASHBOARD
# =============================================================
@patient_bp.route("/dashboard")
@login_required
def dashboard():

    if current_user.role != "patient":
        flash("Access restricted.", "danger")
        return redirect(url_for("auth.login"))

    device = Device.query.filter_by(owner_id=current_user.id).first()

    med_ids = [
        m.id for m in Medication.query.filter_by(patient_id=current_user.id).all()
    ]
    logs = Log.query.filter(Log.med_id.in_(med_ids)).order_by(
        Log.taken_time.desc()
    ).limit(5).all()

    alerts = Alert.query.filter_by(user_id=current_user.id).order_by(
        Alert.created_at.desc()
    ).limit(5).all()

    stats = compute_patient_analytics(current_user)

    return render_template(
        "patient/dashboard.html",
        device=device,
        logs=logs,
        alerts=alerts,
        stats=stats
    )


# =============================================================
# DOCTOR LINK
# =============================================================
@patient_bp.route("/link-doctor", methods=["GET", "POST"])
@login_required
def link_doctor():

    if current_user.role != "patient":
        flash("Patients only.", "danger")
        return redirect(url_for("auth.login"))

    doctors = User.query.filter_by(role="doctor", approved=True).all()
    links = DoctorPatientLink.query.filter_by(patient_id=current_user.id).all()

    if request.method == "POST":

        # New doctor request
        if "doctor_id" in request.form:
            doc_id = int(request.form.get("doctor_id"))
            doctor = User.query.get(doc_id)

            if not doctor:
                flash("Doctor not found", "danger")
                return redirect(url_for("patient.link_doctor"))

            existing = DoctorPatientLink.query.filter_by(
                patient_id=current_user.id,
                doctor_id=doc_id
            ).first()

            if existing:
                flash("Already requested or linked.", "info")
                return redirect(url_for("patient.link_doctor"))

            link = DoctorPatientLink(
                doctor_id=doc_id,
                patient_id=current_user.id,
                active=False
            )
            db.session.add(link)

            db.session.add(Alert(
                user_id=doc_id,
                title="New Patient Request",
                message=f"{current_user.name} wants to link with you.",
                created_at=datetime.utcnow()
            ))

            db.session.commit()
            flash("Request sent.", "success")
            return redirect(url_for("patient.link_doctor"))

        # Update permissions
        elif "save_permissions" in request.form:
            for link in links:
                link.allow_alerts = bool(request.form.get(f"alerts_{link.id}"))
                link.allow_analytics = bool(request.form.get(f"analytics_{link.id}"))
                link.allow_med_update = bool(request.form.get(f"update_{link.id}"))

            db.session.commit()
            flash("Permissions updated.", "success")
            return redirect(url_for("patient.link_doctor"))

    return render_template(
        "patient/link_doctor.html",
        doctors=doctors,
        links=links
    )


# =============================================================
# DEVICE PAGE
# =============================================================
@patient_bp.route("/device", methods=["GET", "POST"])
@login_required
def device():

    if current_user.role != "patient":
        flash("Access restricted.", "danger")
        return redirect(url_for("auth.login"))

    device = Device.query.filter_by(owner_id=current_user.id).first()
    if not device:
        flash("No device linked.", "warning")
        return redirect(url_for("patient.dashboard"))

    # POST: Commands
    if request.method == "POST":
        action = request.form.get("action")

        # Basic commands
        if action == "dispense_now":
            push_device_cmd(device, "dispense_now")
            flash("Dispense triggered.", "success")

        elif action == "dispense_med":
            med_name = request.form.get("medicine")
            med = Medication.query.filter_by(
                patient_id=current_user.id, name=med_name
            ).first()
            if med:
                push_device_cmd(device, "dispense_med", {
                    "med_id": med.id,
                    "compartment": med.compartment,
                    "dose": 1
                })
                flash("Requested dispense.", "success")

            else:
                flash("Medicine not found.", "danger")

        elif action == "snooze":
            minutes = int(request.form.get("minutes", 10))
            push_device_cmd(device, "snooze", {"minutes": minutes})
            flash("Snooze command sent.", "info")

        elif action == "skip":
            push_device_cmd(device, "skip")
            flash("Dose skipped.", "warning")

        elif action == "force_sync":
            push_device_cmd(device, "force_sync")
            flash("Sync requested.", "info")

        elif action == "play_audio":
            sound = request.form.get("sound")
            push_device_cmd(device, "play_audio", {"sound": sound})
            flash("Audio played.", "success")

        elif action == "start_alarm":
            push_device_cmd(device, "start_alarm")
            flash("Alarm triggered.", "danger")

        elif action == "stop_alarm":
            push_device_cmd(device, "stop_alarm")
            flash("Alarm stopped.", "success")

        elif action == "reboot":
            push_device_cmd(device, "reboot")
            flash("Rebooting device.", "info")

        elif action == "set_led":
            color = request.form.get("color")
            push_device_cmd(device, "set_led", {"color": color})
            flash("LED updated.", "info")

        elif action == "servo_test":
            push_device_cmd(device, "servo_test")
            flash("Servo test sent.", "info")

        # Language change → force full sync
        elif action == "change_language":
            device.language = request.form.get("language")
            device.data_dirty = True
            db.session.commit()
            push_device_cmd(device, "force_sync")
            flash("Language updated.", "success")

        return redirect(url_for("patient.device"))

    # GET: Preview data
    config_preview = build_config_json(current_user)
    schedule_preview = build_schedule_json(current_user)
    audio_manifest = build_audio_manifest_cached(current_user)

    med_ids = [m.id for m in Medication.query.filter_by(patient_id=current_user.id).all()]
    recent_logs = Log.query.filter(Log.med_id.in_(med_ids)).order_by(
        Log.taken_time.desc()
    ).limit(15).all()

    dev_state = DeviceState.query.filter_by(device_id=device.id).first()
    medications = Medication.query.filter_by(patient_id=current_user.id).all()

    return render_template(
        "patient/device.html",
        device=device,
        config_preview=config_preview,
        schedule_preview=schedule_preview,
        audio_manifest=audio_manifest,
        medications=medications,
        recent_logs=recent_logs,
        dev_state=dev_state
    )


# =============================================================
# MEDICATION PAGE
# =============================================================
@patient_bp.route("/medicine", methods=["GET", "POST"])
@login_required
def medicine():

    if current_user.role != "patient":
        flash("Access restricted.", "danger")
        return redirect(url_for("auth.login"))

    device = Device.query.filter_by(owner_id=current_user.id).first()

    # Prepare UI structure
    meds = {i: None for i in range(1, 9)}
    for m in Medication.query.filter_by(patient_id=current_user.id).all():
        meds[m.compartment] = m

    # POST: Save medicine
    if request.method == "POST":
        try:
            comp = int(request.form.get("compartment"))
            name = request.form.get("name")
            composition = request.form.get("composition")
            quantity = int(request.form.get("quantity"))

            expiry_month = int(request.form.get("expiry_month"))
            expiry_year = int(request.form.get("expiry_year"))
            expiry_date = date(expiry_year, expiry_month, 1)

            if comp < 1 or comp > 8:
                raise ValueError("Invalid compartment")

            # Validate time ranges
            starts = request.form.getlist("time_start[]")
            ends = request.form.getlist("time_end[]")

            clean_dosages = []
            for s, e in zip(starts, ends):
                if not s or not e:
                    continue

                sh = int(s)
                eh = int(e)
                if not (0 <= sh <= 23 and 0 <= eh <= 23):
                    raise ValueError("Invalid time range")
                if sh >= eh:
                    raise ValueError("Start must be before end")

                clean_dosages.append((sh, eh))

            # Look for overlapping times
            clean_sorted = sorted(clean_dosages)
            for i in range(len(clean_sorted) - 1):
                if clean_sorted[i][1] > clean_sorted[i+1][0]:
                    raise ValueError("Overlapping time windows")

            # Save / update medicine
            existing = Medication.query.filter_by(
                patient_id=current_user.id,
                compartment=comp
            ).first()

            if existing:
                med = existing
                med.name = name
                med.composition = composition
                med.quantity = quantity
                med.expiry = expiry_date

                # delete old dosages
                Dosage.query.filter_by(medication_id=med.id).delete()

                flash(f"Updated Compartment {comp}", "success")
            else:
                med = Medication(
                    patient_id=current_user.id,
                    name=name,
                    composition=composition,
                    quantity=quantity,
                    expiry=expiry_date,
                    compartment=comp
                )
                db.session.add(med)
                db.session.flush()
                flash(f"Saved to Compartment {comp}", "success")

            # Save dosages
            foods = request.form.getlist("food_status[]")
            remarks = request.form.getlist("remark[]")

            for (sh, eh), food, rm in zip(clean_dosages, foods, remarks):
                d = Dosage(
                    medication_id=med.id,
                    time_range_start=time(sh, 0),
                    time_range_end=time(eh, 0),
                    food_status=food,
                    remark=rm
                )
                db.session.add(d)

            # Mark data dirty → full sync needed
            if device:
                device.data_dirty = True

            db.session.commit()
            return redirect(url_for("patient.medicine"))

        except Exception as e:
            db.session.rollback()
            flash(f"Error: {e}", "danger")
            return redirect(url_for("patient.medicine"))

    return render_template(
        "patient/medicine.html",
        meds=meds,
        device=device
    )


# =============================================================
# ALERTS
# =============================================================
@patient_bp.route("/alerts")
@login_required
def alerts():

    if current_user.role != "patient":
        flash("Access restricted.", "danger")
        return redirect(url_for("auth.login"))

    alerts = Alert.query.filter_by(
        user_id=current_user.id
    ).order_by(Alert.created_at.desc()).all()

    for a in alerts:
        a.read = True

    db.session.commit()

    return render_template("patient/alerts.html", alerts=alerts)


# =============================================================
# LOG HISTORY
# =============================================================
@patient_bp.route("/history")
@login_required
def history():

    if current_user.role != "patient":
        flash("Access restricted.", "danger")
        return redirect(url_for("auth.login"))

    med_filter = request.args.get("medicine", "")
    date_filter = request.args.get("date", "")

    logs = Log.query
    med_ids = [
        m.id for m in Medication.query.filter_by(patient_id=current_user.id).all()
    ]
    logs = logs.filter(Log.med_id.in_(med_ids))

    if med_filter:
        logs = logs.filter(Log.med_name.ilike(f"%{med_filter}%"))

    if date_filter:
        try:
            dt = datetime.strptime(date_filter, "%Y-%m-%d").date()
            logs = logs.filter(func.date(Log.taken_time) == dt)
        except:
            flash("Invalid date format.", "warning")

    logs = logs.order_by(Log.taken_time.desc()).limit(200).all()

    med_names = [
        m[0] for m in db.session.query(Log.med_name)
              .filter(Log.med_id.in_(med_ids)).distinct().all()
    ]

    return render_template(
        "patient/history.html",
        logs=logs,
        med_filter=med_filter,
        date_filter=date_filter,
        med_names=med_names
    )


# =============================================================
# ANALYTICS
# =============================================================
@patient_bp.route("/analytics")
@login_required
def analytics():

    if current_user.role != "patient":
        flash("Access restricted.", "danger")
        return redirect(url_for("auth.login"))

    stats = compute_patient_analytics(current_user)
    meds = Medication.query.filter_by(patient_id=current_user.id).all()

    med_ids = [m.id for m in meds]
    recent_logs = Log.query.filter(
        Log.med_id.in_(med_ids)
    ).order_by(Log.taken_time.desc()).limit(20).all()

    return render_template(
        "patient/analytics.html",
        total_meds=len(meds),
        total_doses=sum(len(m.dosages) for m in meds),
        missed_doses=stats["missed"],
        adherence_rate=stats["adherence"],
        recent_logs=recent_logs
    )

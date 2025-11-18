# app/utils/analytics.py

from datetime import datetime, timedelta, date
from sqlalchemy import func
from app.models import db, Log, Medication, Dosage


# ===============================================================
# 🧮 COMPUTE PATIENT ANALYTICS
# ===============================================================

def compute_patient_analytics(patient):
    """
    Compute patient's analytics:
    - Taken, Missed, Not Eaten counts
    - Adherence %
    - Next dose prediction
    - 7-day adherence trend
    """

    now = datetime.utcnow()
    today = date.today()
    week_start = today - timedelta(days=6)

    # ------------------------------
    # 📜 Get logs (past 7 days)
    # ------------------------------
    logs = (
        Log.query.join(Medication, Log.med_name == Medication.name)
        .filter(Medication.patient_id == patient.id, Log.taken_time >= week_start)
        .all()
    )

    total_logs = len(logs)
    taken = len([l for l in logs if not l.missed])
    not_eaten = len([l for l in logs if l.missed and l.device_id is not None])
    missed = len([l for l in logs if l.missed and l.device_id is None])

    adherence = round((taken / total_logs) * 100, 1) if total_logs else 0
    not_eaten_rate = round((not_eaten / total_logs) * 100, 1) if total_logs else 0
    missed_rate = round((missed / total_logs) * 100, 1) if total_logs else 0

    # ------------------------------
    # 🕒 Next Dose (today)
    # ------------------------------
    upcoming = None
    next_med = None
    meds = Medication.query.filter_by(patient_id=patient.id).all()

    for med in meds:
        for d in med.dosages:
            t = datetime.combine(today, d.time_range_start)
            if t > now and (not upcoming or t < upcoming):
                upcoming = t
                next_med = med

    next_dose = {
        "medicine": next_med.name if next_med else None,
        "time": upcoming.strftime("%I:%M %p") if upcoming else "All done for today",
    }

    # ------------------------------
    # 📈 7-day Adherence Trend
    # ------------------------------
    trend_data = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_logs = [l for l in logs if l.taken_time.date() == day]
        if not day_logs:
            trend_data.append({"date": day.strftime("%d %b"), "adherence": 0})
        else:
            taken_day = len([l for l in day_logs if not l.missed])
            adherence_day = round((taken_day / len(day_logs)) * 100, 1)
            trend_data.append({"date": day.strftime("%d %b"), "adherence": adherence_day})
    trend_data.reverse()

    return {
        "taken": taken,
        "not_eaten": not_eaten,
        "missed": missed,
        "total": total_logs,
        "adherence": adherence,
        "not_eaten_rate": not_eaten_rate,
        "missed_rate": missed_rate,
        "next_dose": next_dose,
        "trend_data": trend_data,
    }


# ===============================================================
# 📊 WEEKLY ADHERENCE SUMMARY (used by doctors/admin)
# ===============================================================

def compute_doctor_view(patient_id):
    """
    Return summarized adherence for a given patient.
    Used in doctor analytics dashboard.
    """
    today = date.today()
    week_start = today - timedelta(days=6)

    logs = (
        Log.query.join(Medication, Log.med_name == Medication.name)
        .filter(Medication.patient_id == patient_id, Log.taken_time >= week_start)
        .all()
    )

    total = len(logs)
    taken = len([l for l in logs if not l.missed])
    adherence = round((taken / total) * 100, 1) if total else 0

    return {
        "patient_id": patient_id,
        "total_logs": total,
        "taken": taken,
        "adherence": adherence,
    }


# ===============================================================
# 🔁 DAILY UPDATE HOOK (called after every sync)
# ===============================================================

def update_patient_analytics(patient_id):
    """
    Lightweight summary updater after ESP sync.
    Only logs & adherence (no graphs) to save compute.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    logs = (
        Log.query.join(Medication, Log.med_name == Medication.name)
        .filter(Medication.patient_id == patient_id, Log.taken_time >= yesterday)
        .all()
    )

    total = len(logs)
    taken = len([l for l in logs if not l.missed])
    adherence = round((taken / total) * 100, 1) if total else 0

    print(f"[ANALYTICS] ✅ Updated for Patient {patient_id}: {adherence}% adherence today")

    return {
        "total_logs": total,
        "taken": taken,
        "adherence": adherence,
    }

def get_adherence_trend(patient):
    trend = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        logs = Log.query.filter(
            Log.device_id == (patient.devices[0].device_code if patient.devices else None),
            db.func.date(Log.taken_time) == day
        ).all()
        taken = len(logs)
        # For simplicity assume 3 doses/day
        adherence = round(min((taken / 3) * 100, 100), 1)
        trend.append({"date": day.strftime("%b %d"), "adherence": adherence})
    return trend
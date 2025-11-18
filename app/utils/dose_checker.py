# app/utils/dose_checker.py

from datetime import datetime, timedelta
from app.models import db, Medication, Dosage, Log, Alert


def detect_missed_doses(patient_id, window_hours=24):
    """
    Compare expected dosages vs actual taken logs 
    and automatically create:
      - missed dose logs
      - late dose alerts
      - missed dose alerts
    """

    now = datetime.utcnow()
    since = now - timedelta(hours=window_hours)

    medications = Medication.query.filter_by(patient_id=patient_id).all()

    missed_count = 0
    alerts_created = 0

    for med in medications:
        dosages = Dosage.query.filter_by(medication_id=med.id).all()

        for d in dosages:
            # Expected time window for TODAY
            today = now.date()
            expected_start = datetime.combine(today, d.time_range_start)
            expected_end = datetime.combine(today, d.time_range_end)

            # If dosage window is in the future → skip
            if expected_end > now:
                continue

            # If dosage window is older than our check window → skip
            if expected_end < since:
                continue

            # --------------------------------------------------------
            # Was this dose TAKEN?
            # --------------------------------------------------------
            taken_log = Log.query.filter(
                Log.med_id == med.id,
                Log.dose_id == d.id,
                Log.status == "taken",
                Log.taken_time.between(expected_start, expected_end)
            ).first()

            if taken_log:
                # Check for Late Dose
                delay = (taken_log.taken_time - expected_start).total_seconds() / 60
                if delay > 30:
                    db.session.add(Alert(
                        user_id=patient_id,
                        title="Late Dose",
                        message=f"You took {med.name} {int(delay)} minutes late.",
                        created_at=datetime.utcnow()
                    ))
                    alerts_created += 1

                continue  # Taken, no missed dose.

            # --------------------------------------------------------
            # MISSED DOSE
            # --------------------------------------------------------
            missed_count += 1

            # Create missed log
            missed_log = Log(
                device_id=None,  # Not from device
                med_name=med.name,
                med_id=med.id,
                dose_id=d.id,
                taken_time=expected_end,
                status="missed",
                mode="scheduled",
                delay_minutes=0,
                pill_sensor=False,
                dustbin_sensor=False
            )
            db.session.add(missed_log)

            # Create alert
            db.session.add(Alert(
                user_id=patient_id,
                title="Missed Dose",
                message=f"You missed your {med.name} dose scheduled at {d.time_range_start.strftime('%I:%M %p')}.",
                created_at=datetime.utcnow()
            ))
            alerts_created += 1

    db.session.commit()

    print(f"[DOSE CHECK] Missed={missed_count}, Alerts={alerts_created}")
    return {
        "missed": missed_count,
        "alerts": alerts_created
    }

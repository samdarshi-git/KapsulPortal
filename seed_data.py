from datetime import datetime, timedelta, time, date
from werkzeug.security import generate_password_hash
from app import create_app, db
from app.models import User, Device, Medication, Dosage, Log, Alert, DoctorPatientLink

app = create_app()

with app.app_context():
    print("🚀 Adding data for existing patient 'anku'...")

    # ----------------------------------------------------------------
    # 🧑‍⚕️ Find existing users
    # ----------------------------------------------------------------
    doctor1 = User.query.filter_by(username="amit").first()
    doctor2 = User.query.filter_by(username="mahi").first()
    patient = User.query.filter_by(username="anku").first()

    if not patient:
        print("❌ ERROR: Patient 'anku' not found. Cannot continue.")
        exit()

    # ----------------------------------------------------------------
    # 🔗 ADD DOCTOR–PATIENT LINKS (if not already linked)
    # ----------------------------------------------------------------
    def ensure_link(doc):
        existing = DoctorPatientLink.query.filter_by(
            doctor_id=doc.id, patient_id=patient.id
        ).first()
        if not existing:
            link = DoctorPatientLink(
                doctor_id=doc.id,
                patient_id=patient.id,
                active=True,
                allow_alerts=True,
                allow_analytics=True,
                allow_med_update=True,
                approved_at=datetime.utcnow()
            )
            db.session.add(link)
            print(f"✅ Linked doctor {doc.username} → anku")

    ensure_link(doctor1)
    ensure_link(doctor2)

    # ----------------------------------------------------------------
    # 📟 DEVICE (if not exists)
    # ----------------------------------------------------------------
    device = Device.query.filter_by(device_code="ANKU1001").first()
    if not device:
        device = Device(
            device_code="ANKU1001",
            owner_id=patient.id,
            language="en",
            alarm_tone="default",
            total_compartments=8,
            last_heartbeat=datetime.utcnow(),
            last_incoming_sync=datetime.utcnow(),
            last_outgoing_sync=datetime.utcnow(),
            data_dirty=False
        )
        db.session.add(device)
        db.session.flush()
        print("📟 Device created for patient 'anku'")
    else:
        print("📟 Device already exists, using existing ANKU1001")

    # ----------------------------------------------------------------
# 💊 MEDICATIONS (skip if compartment already occupied)
# ----------------------------------------------------------------
    med_list = [
        ("Paracetamol", "Acetaminophen 500mg", True, 25, 1, doctor1.id),
        ("Vitamin C", "Ascorbic Acid 1000mg", False, 10, 2, doctor2.id),
        ("Amoxicillin", "Amoxicillin 250mg", True, 5, 3, doctor1.id),
        ("Pantoprazole", "Pantoprazole 40mg", False, 18, 4, doctor1.id),
        ("Metformin", "Metformin 500mg", True, 30, 5, doctor2.id),
    ]

    meds = []

    for name, comp, crit, qty, comp_no, doc_id in med_list:

        # Check if this compartment already exists for patient
        existing_by_compartment = Medication.query.filter_by(
            patient_id=patient.id,
            compartment=comp_no
        ).first()

        if existing_by_compartment:
            print(f"⚠️ Compartment {comp_no} already occupied by {existing_by_compartment.name}. Skipping {name}.")
            meds.append(existing_by_compartment)  # so dosages/logs still link
            continue

        # If compartment is free → add medication
        med = Medication(
            patient_id=patient.id,
            doctor_id=doc_id,
            name=name,
            composition=comp,
            quantity=qty,
            expiry=date.today() + timedelta(days=15 + comp_no),
            critical=crit,
            compartment=comp_no
        )
        db.session.add(med)
        meds.append(med)
        print(f"💊 Added medication: {name} (Compartment {comp_no})")

    db.session.flush()


    # ----------------------------------------------------------------
    # ⏰ DOSAGES (add only if missing)
    # ----------------------------------------------------------------
    for med in meds:
        if len(med.dosages) == 0:
            db.session.add_all([
                Dosage(
                    medication_id=med.id,
                    time_range_start=time(9, 0),
                    time_range_end=time(10, 0),
                    food_status="After Food",
                    remark="Morning dose"
                ),
                Dosage(
                    medication_id=med.id,
                    time_range_start=time(20, 0),
                    time_range_end=time(21, 0),
                    food_status="Before Food",
                    remark="Evening dose"
                ),
            ])
            print(f"⏰ Added dosages for {med.name}")
        else:
            print(f"⏰ Dosages already present for {med.name}")

    db.session.flush()

    # ----------------------------------------------------------------
    # 🧾 LOGS (5 days of sample logs)
    # ----------------------------------------------------------------
    now = datetime.utcnow()

    for i in range(5):
        log_day = now - timedelta(days=i)
        for med in meds:
            taken_flag = ((i + med.id) % 3 != 0)

            db.session.add(Log(
                device_id=device.id,
                med_name=med.name,
                med_id=med.id,
                dose_id=None,
                taken_time=log_day.replace(hour=9, minute=10),

                status="taken" if taken_flag else "missed",
                mode="device",
                delay_minutes=0,
                pill_sensor=taken_flag,
                dustbin_sensor=taken_flag
            ))

    print("🧾 Added 5 days of logs")

    # ----------------------------------------------------------------
    # 🔔 Alerts
    # ----------------------------------------------------------------
    db.session.add_all([
        Alert(user_id=patient.id, title="Low Stock Alert", message="Amoxicillin is running low."),
        Alert(user_id=patient.id, title="Missed Dose", message="You missed your Metformin morning dose."),
        Alert(user_id=patient.id, title="Sensor Issue", message="Vitamin C was dispensed but not detected."),
    ])

    print("🔔 Alerts added")

    db.session.commit()
    print("✅ Done seeding data for patient 'anku'!")

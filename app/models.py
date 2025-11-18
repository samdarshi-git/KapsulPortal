# app/models.py

from datetime import datetime
from flask_login import UserMixin
from .extensions import db, login_manager


# ------------------------------------------------------
# LOGIN USER LOADER
# ------------------------------------------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ------------------------------------------------------
# USER MODEL
# ------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # patient / doctor / admin
    approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    devices = db.relationship(
        "Device",
        backref="owner",
        lazy=True,
        cascade="all, delete-orphan"
    )

    patient_medications = db.relationship(
        "Medication",
        foreign_keys="Medication.patient_id",
        backref="patient",
        lazy=True,
    )

    doctor_links = db.relationship(
        "DoctorPatientLink",
        foreign_keys="DoctorPatientLink.doctor_id",
        backref="doctor",
        lazy=True,
        cascade="all, delete"
    )

    patient_links = db.relationship(
        "DoctorPatientLink",
        foreign_keys="DoctorPatientLink.patient_id",
        backref="patient_link",
        lazy=True,
        cascade="all, delete"
    )

    alerts = db.relationship(
        "Alert",
        backref="user",
        lazy=True,
        cascade="all, delete"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class Device(db.Model):
    __tablename__ = "device"

    id = db.Column(db.Integer, primary_key=True)
    device_code = db.Column(db.String(50), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    last_heartbeat = db.Column(db.DateTime)
    last_incoming_sync = db.Column(db.DateTime)
    last_outgoing_sync = db.Column(db.DateTime)

    language = db.Column(db.String(20), default="en")
    alarm_tone = db.Column(db.String(50), default="default")
    total_compartments = db.Column(db.Integer, default=8)

    data_dirty = db.Column(db.Boolean, default=True)

    states = db.relationship("DeviceState", backref="device", lazy=True)
    logs = db.relationship("Log", backref="device", lazy=True)

    def is_online(self):
        if not self.last_heartbeat:
            return False
        return (datetime.utcnow() - self.last_heartbeat).total_seconds() < 120

    def __repr__(self):
        return f"<Device {self.device_code}>"



# ------------------------------------------------------
# MEDICATION MODEL
# ------------------------------------------------------
class Medication(db.Model):
    __tablename__ = "medication"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    name = db.Column(db.String(100), nullable=False)
    composition = db.Column(db.String(200))
    quantity = db.Column(db.Integer)
    expiry = db.Column(db.Date)

    critical = db.Column(db.Boolean, default=False)

    compartment = db.Column(db.Integer, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("patient_id", "compartment", name="unique_patient_compartment"),
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    dosages = db.relationship(
        "Dosage",
        backref="medicine",
        cascade="all, delete",
        lazy=True
    )

    def __repr__(self):
        return f"<Medication {self.name} (Critical={self.critical})>"


# ------------------------------------------------------
# DOSAGE MODEL
# ------------------------------------------------------
class Dosage(db.Model):
    __tablename__ = "dosage"

    id = db.Column(db.Integer, primary_key=True)
    medication_id = db.Column(db.Integer, db.ForeignKey("medication.id"), nullable=False)

    time_range_start = db.Column(db.Time, nullable=False)
    time_range_end = db.Column(db.Time, nullable=False)

    food_status = db.Column(db.String(50))
    remark = db.Column(db.String(200))

    def __repr__(self):
        return f"<Dosage {self.time_range_start}-{self.time_range_end}>"


# ------------------------------------------------------
# DOCTOR-PATIENT LINK
# ------------------------------------------------------
class DoctorPatientLink(db.Model):
    __tablename__ = "doctor_patient_link"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    active = db.Column(db.Boolean, default=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)

    allow_alerts = db.Column(db.Boolean, default=False)
    allow_analytics = db.Column(db.Boolean, default=False)
    allow_med_update = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Link D={self.doctor_id} P={self.patient_id} A={self.active}>"


# ------------------------------------------------------
# LOG MODEL
# ------------------------------------------------------
class Log(db.Model):
    __tablename__ = "log"

    id = db.Column(db.Integer, primary_key=True)

    device_id = db.Column(db.Integer, db.ForeignKey("device.id"))
    med_name = db.Column(db.String(100))
    med_id = db.Column(db.Integer)
    dose_id = db.Column(db.Integer)

    taken_time = db.Column(db.DateTime, default=datetime.utcnow)

    status = db.Column(db.String(20))   # taken / missed / skipped / taken_late
    mode = db.Column(db.String(20))     # scheduled / manual / portal / device
    delay_minutes = db.Column(db.Integer, default=0)

    pill_sensor = db.Column(db.Boolean, default=False)
    dustbin_sensor = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Log {self.med_name} {self.status} ({self.taken_time})>"


# ------------------------------------------------------
# ALERT MODEL
# ------------------------------------------------------
class Alert(db.Model):
    __tablename__ = "alert"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    title = db.Column(db.String(100))
    message = db.Column(db.Text)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Alert {self.title}>"


# ------------------------------------------------------
# DEVICE COMMAND QUEUE
# ------------------------------------------------------
class DeviceCommandQueue(db.Model):
    __tablename__ = "device_command_queue"

    id = db.Column(db.Integer, primary_key=True)
    device_code = db.Column(db.String(50), nullable=False)

    command = db.Column(db.String(50))  # dispense_now / snooze / skip / etc
    data = db.Column(db.JSON)

    processed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Cmd {self.device_code}: {self.command}>"


# ------------------------------------------------------
# DEVICE STATE
# ------------------------------------------------------
class DeviceState(db.Model):
    __tablename__ = "device_state"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"))

    files = db.Column(db.JSON)  # {"audio":[], "json":[], "logs":[]}
    storage_used = db.Column(db.Integer)
    storage_total = db.Column(db.Integer)

    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DeviceState Device={self.device_id}>"

class DeviceSyncStatus(db.Model):
    __tablename__ = "device_sync_status"

    id = db.Column(db.Integer, primary_key=True)
    device_id = db.Column(db.Integer, db.ForeignKey("device.id"))
    message = db.Column(db.String(200))
    progress = db.Column(db.Integer, default=0)   # 0–100
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

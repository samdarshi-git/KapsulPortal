# app/routes/device_api_bp.py

from flask import Blueprint, request, jsonify, send_file, abort
from datetime import datetime
import os

from app import db
from app.models import (
    Device,
    DeviceCommandQueue,
    Log,
    DeviceState,
)

from app.utils.device_sync import (
    build_config_json,
    build_schedule_json,
    build_audio_manifest_cached
)

from flask_socketio import emit
from app import socketio


device_api_bp = Blueprint("device_api", __name__, url_prefix="/api/device")


# =============================================================
# HEARTBEAT  (Device → Portal)
# =============================================================
@device_api_bp.route("/heartbeat/<device_code>", methods=["POST"])
def heartbeat(device_code):

    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    # Update heartbeat timestamp
    device.last_heartbeat = datetime.utcnow()
    db.session.commit()

    # ---- FETCH COMMANDS QUEUED FOR THIS DEVICE ----
    cmds = DeviceCommandQueue.query.filter_by(
        device_code=device_code,
        processed=False
    ).all()

    cmd_list = []
    for c in cmds:
        cmd_list.append({
            "command": c.command,
            "data": c.data or {}
        })

        c.processed = True  # mark processed

    db.session.commit()

    # ---- SEND BACK SYNC + COMMANDS ----
    return jsonify({
        "status": "ok",
        "sync": {
            "all": bool(device.data_dirty)
        },
        "commands": cmd_list
    })


# =============================================================
# SYNC DONE  (Device → Portal)
# =============================================================
@device_api_bp.route("/sync_done/<device_code>", methods=["POST"])
def sync_done(device_code):

    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    # Device finished downloading config/schedule/audio
    device.data_dirty = False
    device.last_incoming_sync = datetime.utcnow()

    db.session.commit()

    return jsonify({"status": "ok"})


# =============================================================
# DEVICE → PORTAL  :  SYNC PROGRESS UPDATE (via socket)
# =============================================================
@device_api_bp.route("/notify/<device_code>", methods=["POST"])
def device_progress(device_code):
    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    payload = request.json or {}

    socketio.emit(
        "device_progress",
        {
            "device": device_code,
            "msg": payload.get("msg", ""),
            "pct": payload.get("pct", 0),
        },
        room=device.owner_id
    )

    return jsonify({"status": "sent"})


# =============================================================
# CONFIG DOWNLOAD
# =============================================================
@device_api_bp.route("/download/config/<device_code>", methods=["GET"])
def download_config(device_code):
    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    cfg = build_config_json(device.owner)
    return jsonify(cfg)


# =============================================================
# SCHEDULE DOWNLOAD
# =============================================================
@device_api_bp.route("/download/schedule/<device_code>", methods=["GET"])
def download_schedule(device_code):
    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    sch = build_schedule_json(device.owner)
    return jsonify(sch)


# =============================================================
# AUDIO MANIFEST DOWNLOAD
# =============================================================
@device_api_bp.route("/download/audio_manifest/<device_code>", methods=["GET"])
def download_audio_manifest(device_code):

    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    manifest = build_audio_manifest_cached(device.owner)
    return jsonify(manifest)


# =============================================================
# SERVE AUDIO FILES
# =============================================================
@device_api_bp.route("/audio/<path:filepath>", methods=["GET"])
def serve_audio(filepath):

    base = os.path.join(os.getcwd(), "app", "static", "audio")
    full = os.path.join(base, filepath)
    full = os.path.normpath(full)

    if not os.path.exists(full):
        return abort(404)

    return send_file(full, mimetype="audio/wav")


# =============================================================
# LOG UPLOAD (Device → Portal)
# =============================================================
@device_api_bp.route("/upload_logs/<device_code>", methods=["POST"])
def upload_logs(device_code):

    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    logs = request.json or []

    for entry in logs:
        log = Log(
            device_id=device.id,
            med_name=entry.get("med_name"),
            med_id=entry.get("med_id"),
            dose_id=entry.get("dose_id"),
            status=entry.get("status"),
            taken_time=datetime.fromisoformat(entry["taken_time"]),
            mode=entry.get("mode", "device"),
            delay_minutes=entry.get("delay", 0),
            pill_sensor=entry.get("pill_sensor", False),
            dustbin_sensor=entry.get("dustbin_sensor", False)
        )
        db.session.add(log)

    db.session.commit()

    # VERY SIMPLE:
    # device may delete all logs after uploading
    return jsonify({"status": "ok", "delete": True})


# =============================================================
# DEVICE STATE UPLOAD
# =============================================================
@device_api_bp.route("/upload_state/<device_code>", methods=["POST"])
def upload_state(device_code):

    device = Device.query.filter_by(device_code=device_code).first()
    if not device:
        return jsonify({"error": "device not found"}), 404

    payload = request.json or {}

    files = payload.get("files", {})
    used = payload.get("storage_used", 0)
    total = payload.get("storage_total", 0)

    state = DeviceState.query.filter_by(device_code=device_code).first()

    if not state:
        state = DeviceState(
            device_code=device_code,
            files=files,
            storage_used=used,
            storage_total=total
        )
        db.session.add(state)
    else:
        state.files = files
        state.storage_used = used
        state.storage_total = total
        state.updated_at = datetime.utcnow()

    db.session.commit()

    return jsonify({"status": "ok"})

import os

# Define folder structure
structure = {
    "app": {
        "routes": ["auth.py", "admin.py", "doctor.py", "patient.py", "device_api.py"],
        "templates": {
            "shared": ["base.html", "navbar.html"],
            "patient": ["dashboard.html", "medicine.html", "device.html"],
            "doctor": ["dashboard.html", "patient_detail.html"],
            "admin": ["dashboard.html", "approvals.html"],
        },
        "static": {
            "css": [],
            "js": [],
            "images": [],
        },
        "utils": ["mailer.py"],
        "files": ["__init__.py", "config.py", "models.py"]
    },
    "root_files": ["run.py"]
}


def create_structure(base_path="smart_pill_portal"):
    os.makedirs(base_path, exist_ok=True)

    # Root-level files
    for file in structure["root_files"]:
        open(os.path.join(base_path, file), "a").close()

    # app structure
    app_path = os.path.join(base_path, "app")
    os.makedirs(app_path, exist_ok=True)

    # Create base files inside app
    for file in structure["app"]["files"]:
        open(os.path.join(app_path, file), "a").close()

    # Routes
    routes_path = os.path.join(app_path, "routes")
    os.makedirs(routes_path, exist_ok=True)
    for file in structure["app"]["routes"]:
        open(os.path.join(routes_path, file), "a").close()

    # Templates
    templates_path = os.path.join(app_path, "templates")
    os.makedirs(templates_path, exist_ok=True)
    for folder, files in structure["app"]["templates"].items():
        sub_path = os.path.join(templates_path, folder)
        os.makedirs(sub_path, exist_ok=True)
        for file in files:
            open(os.path.join(sub_path, file), "a").close()

    # Static
    static_path = os.path.join(app_path, "static")
    os.makedirs(static_path, exist_ok=True)
    for folder in structure["app"]["static"]:
        os.makedirs(os.path.join(static_path, folder), exist_ok=True)

    # Utils
    utils_path = os.path.join(app_path, "utils")
    os.makedirs(utils_path, exist_ok=True)
    for file in structure["app"]["utils"]:
        open(os.path.join(utils_path, file), "a").close()

    print(f"✅ Project structure created successfully inside '{base_path}'.")


if __name__ == "__main__":
    create_structure()

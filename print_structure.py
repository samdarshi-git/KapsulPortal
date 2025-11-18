import os

def print_structure(base_path=None, indent=0):
    # If no path is passed, use the current directory
    if base_path is None:
        base_path = os.getcwd()

    if not os.path.exists(base_path):
        print(f"Path '{base_path}' not found.")
        return

    items = sorted(os.listdir(base_path))
    for item in items:
        path = os.path.join(base_path, item)
        prefix = "    " * indent
        if os.path.isdir(path):
            print(f"{prefix}📁 {item}/")
            print_structure(path, indent + 1)
        else:
            print(f"{prefix}📄 {item}")

if __name__ == "__main__":
    print_structure()

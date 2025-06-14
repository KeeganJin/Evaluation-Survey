import json
import os

PACKAGE_TASKS_FILE = "./package_tasks_setting.json"
OUTPUT_FILE = "./packages_setting.json"

# Load package_tasks
with open(PACKAGE_TASKS_FILE, "r") as f:
    package_tasks = json.load(f)

# Build new packages.json content
packages = {
    pkg_id: {
        "assigned_to": {},
        "evaluated_by": []
    }
    for pkg_id in package_tasks
}

# Write it out
with open(OUTPUT_FILE, "w") as f:
    json.dump(packages, f, indent=2)

print(f"Generated {OUTPUT_FILE} with {len(packages)} packages.")

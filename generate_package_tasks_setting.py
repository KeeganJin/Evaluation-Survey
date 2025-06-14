import json
from collections import defaultdict
import os

TASK_FOLDER = "tasks"
OUTPUT_FILE = "package_tasks_setting.json"

task_ids = [
    name for name in os.listdir(TASK_FOLDER)
    if os.path.isdir(os.path.join(TASK_FOLDER,name)) and name.startswith(("task_id"))
]

grouped = defaultdict(list)
# task_id_{x}_{y}
for task_id in task_ids:
    parts = task_id.split("_")
    if len(parts) >= 3:
        group_id = parts[2]
        grouped[group_id].append(task_id)

# Step 3: Create package dictionary
package_tasks = {
    f"package_{group}": sorted(tasks)
    for group, tasks in grouped.items()
}

# Step 4: Save to file
with open(OUTPUT_FILE, "w") as f:
    json.dump(package_tasks, f, indent=2)

print(f"Generated {OUTPUT_FILE} with {len(package_tasks)} packages.")


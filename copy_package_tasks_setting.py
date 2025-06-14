import shutil
import os

source_path = "./package_tasks_setting.json"
target_path = "./database/package_tasks.json"

# Ensure the database folder exists
os.makedirs(os.path.dirname(target_path), exist_ok=True)

# Copy the file
shutil.copyfile(source_path, target_path)
print(f"Copied {source_path} to {target_path}")

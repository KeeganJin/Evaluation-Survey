import shutil
import os

source_path = "./packages_setting.json"
target_path = "./database/packages.json"

# Ensure the database folder exists
os.makedirs(os.path.dirname(target_path), exist_ok=True)

# Copy the file
shutil.copyfile(source_path, target_path)
print(f"Copied {source_path} to {target_path}")

import os
import shutil
import re

def main():
    # Define paths
    source_dir = './uncatagorized_files/'
    output_dir = './tasks/'

    # Make sure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Get all filenames
    all_files = os.listdir(source_dir)

    # Process each translation PDF file
    for filename in all_files:
        if filename.startswith("translation_id_") and filename.endswith(".pdf"):
            # Extract the task number from the filename
            match = re.match(r'translation_id_(\d+)_(\d+)\.pdf', filename)
            if match:
                task_num = match.group(1)
                subtask_num = match.group(2)
                task_id = f"{task_num}_{subtask_num}"
                folder_name = f"task_id_{task_id}"
                folder_path = os.path.join(output_dir, folder_name)
                os.makedirs(folder_path, exist_ok=True)

                # Files to copy
                files_to_copy = [
                    f"translation_id_{task_id}.pdf",
                    f"ID_{task_num}.png",
                ]

                for file in files_to_copy:
                    source_file = os.path.join(source_dir, file)
                    dest_file = os.path.join(folder_path, file)
                    if os.path.exists(source_file):
                        shutil.copy2(source_file, dest_file)
                        print(f"Copied {file} to {folder_path}")
                    else:
                        print(f"Warning: {file} not found in {source_dir}")

if __name__ == "__main__":
    main()

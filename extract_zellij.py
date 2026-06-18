import zipfile
import os

zip_path = "/home/scott/shared/projects/amux/zellij-tile-0.44.3.zip"
extract_dir = "/home/scott/projects/amux-hermes/amux/zellij"

try:
    os.makedirs(extract_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)
    print("Successfully extracted zellij-tile-0.44.3.zip to zellij/")
except Exception as e:
    print(f"Error during extraction: {e}")

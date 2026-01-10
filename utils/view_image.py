import os
import platform
import subprocess

# Path to your image
image_path = "project_loc_summary.png"

# Check if file exists
if not os.path.exists(image_path):
    raise FileNotFoundError(f"{image_path} not found")

# Open image depending on OS
current_os = platform.system()

if current_os == "Darwin":  # macOS
    subprocess.run(["open", image_path])
elif current_os == "Windows":  # Windows
    os.startfile(image_path)
else:  # Linux / other Unix
    subprocess.run(["xdg-open", image_path])


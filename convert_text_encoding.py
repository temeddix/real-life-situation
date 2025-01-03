import glob
import os

# Get the folder path from the user
folder_path = input("Enter the folder path: ")

# Find all shp files in the folder
shp_files = glob.glob(os.path.join(folder_path, "*"))

# Loop through the shp files and convert the encoding
for file_path in shp_files:
    file_name = os.path.basename(file_path)
    try:
        with open(file_path, "r", encoding="cp949") as f:
            content = f.read()
        with open(file_path, "w", encoding="utf8") as f:
            f.write(content)
        print(f"Converted {file_name} from cp949 to utf8")
    except UnicodeDecodeError:
        print(f"Skipped conversion of {file_name}")

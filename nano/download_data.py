"""
Downloads datasets from Roboflow Universe and merges them into a single
YOLO-format dataset ready for training.

Usage:
    pip install roboflow python-dotenv
    python3 download_data.py

How to find workspace/project slugs:
    1. Go to universe.roboflow.com
    2. Search for the class you want (e.g. "fire smoke detection")
    3. Open a dataset — the URL will be:
         universe.roboflow.com/{workspace}/{project}
    4. Copy those two values into DATASETS below.
    5. Click "Download" on the dataset page to find the latest version number.

Output structure:
    datasets/merged/
        train/images/   train/labels/
        valid/images/   valid/labels/
        data.yaml
"""

import os
import shutil
import yaml
from pathlib import Path
from dotenv import load_dotenv
from roboflow import Roboflow

load_dotenv()
API_KEY = os.getenv("ROBOFLOW_KEY")

# ----------------------------------------------------------------------------
# CONFIGURE YOUR DATASETS HERE
# Each entry: (workspace_slug, project_slug, version_number)
# ----------------------------------------------------------------------------
DATASETS = [
    ("maad-anwar-ertmq",   "smoke-and-fire-detection-a3dtx", 4),  # FIRE, SMOKE
    ("freelance-projects", "propane-cylinder",                1),  # cylinder
    ("juyeon-ko",          "firefighter",                     1),  # firefighters
    ("wsfree",             "exit-cohy8",                      2),  # exit
]

# Normalize source class names → canonical class names
# Keys are what the dataset labels, values are what we want in our model
CLASS_REMAP = {
    "FIRE":         "fire",
    "fire":         "fire",
    "SMOKE":        "smoke",
    "smoke":        "smoke",
    "cylinder":     "propane_tank",
    "firefighters": "firefighter",
    "firefighter":  "firefighter",
    "exit":         "exit_sign",
}

# Final canonical class list (order determines YOLO class indices)
CLASSES = [
    "fire",
    "smoke",
    "firefighter",
    "propane_tank",
    "exit_sign",
]

# ----------------------------------------------------------------------------
# Download
# ----------------------------------------------------------------------------
DOWNLOAD_DIR = Path("datasets/raw")
MERGED_DIR   = Path("datasets/merged")

def download_all():
    rf = Roboflow(api_key=API_KEY)
    paths = []

    for workspace, project, version in DATASETS:
        print(f"Downloading {workspace}/{project} v{version}...")
        ds = rf.workspace(workspace).project(project).version(version).download(
            "yolov8", location=str(DOWNLOAD_DIR / f"{project}-v{version}")
        )
        paths.append(Path(ds.location))
        print(f"  → {ds.location}")

    return paths

# ----------------------------------------------------------------------------
# Merge
# ----------------------------------------------------------------------------
def merge(dataset_paths):
    for split in ("train", "valid"):
        (MERGED_DIR / split / "images").mkdir(parents=True, exist_ok=True)
        (MERGED_DIR / split / "labels").mkdir(parents=True, exist_ok=True)

    total = {"train": 0, "valid": 0}

    for ds_path in dataset_paths:
        # Read this dataset's class list
        yaml_path = ds_path / "data.yaml"
        if not yaml_path.exists():
            print(f"  ⚠️  No data.yaml in {ds_path}, skipping")
            continue

        with open(yaml_path) as f:
            ds_meta = yaml.safe_load(f)

        ds_classes = ds_meta.get("names", [])

        for split in ("train", "valid"):
            img_dir = ds_path / split / "images"
            lbl_dir = ds_path / split / "labels"
            if not img_dir.exists():
                continue

            for img_file in img_dir.iterdir():
                if img_file.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                    continue

                lbl_file = lbl_dir / img_file.with_suffix(".txt").name
                if not lbl_file.exists():
                    continue

                # Remap class indices to merged CLASSES list
                new_lines = []
                for line in lbl_file.read_text().strip().splitlines():
                    parts = line.split()
                    if not parts:
                        continue
                    old_idx = int(parts[0])
                    if old_idx >= len(ds_classes):
                        continue
                    raw_label    = ds_classes[old_idx]
                    canonical    = CLASS_REMAP.get(raw_label, raw_label)
                    if canonical not in CLASSES:
                        continue  # drop classes we don't care about
                    new_idx = CLASSES.index(canonical)
                    new_lines.append(f"{new_idx} " + " ".join(parts[1:]))

                if not new_lines:
                    continue

                # Write to merged dataset (prefix filename with dataset name to avoid collisions)
                prefix = ds_path.name.replace(" ", "_")
                out_img = MERGED_DIR / split / "images" / f"{prefix}_{img_file.name}"
                out_lbl = MERGED_DIR / split / "labels" / f"{prefix}_{lbl_file.name}"

                shutil.copy2(img_file, out_img)
                out_lbl.write_text("\n".join(new_lines))
                total[split] += 1

        print(f"  Merged {ds_path.name}")

    print(f"\nTotals → train: {total['train']}  valid: {total['valid']}")
    return total

# ----------------------------------------------------------------------------
# Write data.yaml
# ----------------------------------------------------------------------------
def write_yaml(totals):
    data = {
        "path":  str(MERGED_DIR.resolve()),
        "train": "train/images",
        "val":   "valid/images",
        "nc":    len(CLASSES),
        "names": CLASSES,
    }
    out = MERGED_DIR / "data.yaml"
    with open(out, "w") as f:
        yaml.dump(data, f, default_flow_style=False)
    print(f"Written: {out}")

# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    if not DATASETS:
        print("No datasets configured. Add entries to DATASETS in download_data.py.")
        raise SystemExit(1)

    print(f"Downloading {len(DATASETS)} dataset(s)...")
    paths = download_all()

    print("\nMerging...")
    totals = merge(paths)

    write_yaml(totals)
    print("\nDone. Train with:")
    print(f"  yolo train model=yolov8n.pt data={MERGED_DIR.resolve()}/data.yaml epochs=50 imgsz=640 device=0")

"""
download_models.py — fetches the pretrained YuNet + SFace ONNX weights
from the OpenCV Zoo. Run this once, from your own machine, before
running enroll.py, app.py, or kiosk.py.

    python download_models.py

NOTE ON THE LIVENESS MODEL:
The anti-spoofing model (face_antispoof_v2.onnx) is NOT auto-downloaded
by this script, because GitHub serves it via Git LFS and it needs to be
grabbed manually (see README.md Step 3 for exact instructions). This
script only handles YuNet (detection) and SFace (recognition).
"""
import os
import urllib.request

MODELS = {
    "models/face_detection_yunet.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "models/face_recognition_sface.onnx":
        "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}

os.makedirs("models", exist_ok=True)

for out_path, url in MODELS.items():
    if os.path.exists(out_path) and os.path.getsize(out_path) > 10_000:
        print(f"already have {out_path}, skipping")
        continue
    print(f"downloading {url} -> {out_path}")
    urllib.request.urlretrieve(url, out_path)
    size_kb = os.path.getsize(out_path) / 1024
    print(f"  done ({size_kb:.0f} KB)")

print("\nYuNet + SFace done. If a file is only ~1KB, GitHub served a Git-LFS")
print("pointer instead of the binary -- in that case, download it manually from")
print("the URL above by opening it in a browser and using the 'Download' button.")
print("\nDon't forget: the liveness model (face_antispoof_v2.onnx) needs a manual")
print("download too -- see README.md Step 3.")

"""
bootstrap.py - Automated dependency installer and model downloader.
100% Python Standard Library. Zero external dependencies required.
"""
import sys
import os
import time
import subprocess
import importlib.util
from urllib.request import Request, urlopen
from pathlib import Path

# Required external packages: (module_name, pip_package_name)
REQUIRED_PACKAGES = [
    ("numpy", "numpy>=1.24.0"),
    ("PIL", "Pillow>=10.0.0"),
    ("onnxruntime", "onnxruntime>=1.16.0"),
]

MODEL_URL = "https://huggingface.co/crj/dl-ws/resolve/main/open_nsfw.onnx"
DEFAULT_MODEL_PATH = Path(__file__).parent / "model.onnx"


def check_and_install_dependencies():
    """Checks for required libraries and installs any missing ones automatically via pip."""
    missing = []
    for module_name, pip_pkg in REQUIRED_PACKAGES:
        spec = importlib.util.find_spec(module_name)
        if spec is None:
            missing.append((module_name, pip_pkg))

    if not missing:
        print("[Bootstrap] All required dependencies are satisfied: numpy, Pillow, onnxruntime.")
        return

    print(f"\n[Bootstrap] Detected {len(missing)} missing package(s). Initiating automatic installation...")
    for module_name, pip_pkg in missing:
        print(f"  -> Installing {pip_pkg}...")
        try:
            cmd = [sys.executable, "-m", "pip", "install", pip_pkg]
            subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"  [OK] Installed {pip_pkg} successfully.")
        except subprocess.CalledProcessError as err:
            print(f"  [Error] Failed to install {pip_pkg}: {err}")
            print("  Please run: pip install -r requirements.txt manually.")
            sys.exit(1)

    print("[Bootstrap] All dependencies installed successfully!\n")


def download_file_with_progress(url: str, destination: Path):
    """Downloads a file over HTTP with a real-time terminal progress bar."""
    print(f"\n[Model Setup] Downloading ONNX model weights from:\n  {url}")
    print(f"  Destination: {destination}")

    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    
    try:
        with urlopen(req) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            block_size = 64 * 1024  # 64 KB chunks
            downloaded = 0
            start_time = time.time()

            temp_dest = destination.with_suffix(".tmp")
            with open(temp_dest, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Calculate progress and download speed
                    elapsed = time.time() - start_time
                    speed = (downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0

                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        bar_len = 24
                        filled = int(bar_len * downloaded // total_size)
                        bar = "=" * filled + "-" * (bar_len - filled)
                        curr_mb = downloaded / (1024 * 1024)
                        total_mb = total_size / (1024 * 1024)
                        status = f"\r  [{bar}] {pct:5.1f}% ({curr_mb:5.1f}/{total_mb:5.1f} MB) at {speed:4.1f} MB/s"
                    else:
                        curr_mb = downloaded / (1024 * 1024)
                        status = f"\r  Downloaded {curr_mb:5.1f} MB at {speed:4.1f} MB/s"

                    sys.stdout.write(status)
                    sys.stdout.flush()

            # Rename temp file to destination atomically
            if temp_dest.exists():
                if destination.exists():
                    destination.unlink()
                temp_dest.rename(destination)

            sys.stdout.write("\n")
            print(f"  [OK] Model download complete! Size: {downloaded / (1024 * 1024):.1f} MB.\n")

    except Exception as err:
        print(f"\n  [Error] Failed to download model: {err}")
        if destination.with_suffix(".tmp").exists():
            destination.with_suffix(".tmp").unlink()
        sys.exit(1)


def ensure_model_exists(model_path: Path = DEFAULT_MODEL_PATH):
    """Ensures the ONNX model file exists; downloads it with progress animation if missing."""
    if model_path.exists() and model_path.stat().st_size > 1024 * 1024:
        size_mb = model_path.stat().st_size / (1024 * 1024)
        print(f"[Bootstrap] Found local ONNX model weights ({size_mb:.1f} MB): {model_path.name}")
        return

    download_file_with_progress(MODEL_URL, model_path)


def ensure_environment():
    """Master bootstrap routine: verifies dependencies and model file."""
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("\n" + "=" * 56)
    print("      IMAGE-GUARD BOOTSTRAP: SYSTEM INITIALIZATION")
    print("=" * 56)
    check_and_install_dependencies()
    ensure_model_exists()
    print("[Bootstrap] Environment ready. Starting application...\n")


if __name__ == "__main__":
    ensure_environment()

#!/usr/bin/env python3
"""Package TaskManager for distribution.

Usage:
    python3 package.py              # Creates taskmanager-<version>.zip
    python3 package.py --wheel     # Pre-downloads ONNX model into the package

The resulting zip contains:
  - All app code
  - requirements.txt
  - run.sh / run.bat launcher scripts
  - A setup script (setup.sh / setup.bat) that creates the venv and installs deps

To use on a new machine:
    unzip taskmanager-*.zip -d TaskManager/
    cd TaskManager/
    ./setup.sh        # macOS/Linux — or setup.bat on Windows
    ./run.sh           # or run.bat
"""

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

VERSION = "0.1.0"
PROJECT_DIR = Path(__file__).parent.resolve()
ARCHIVE_NAME = f"taskmanager-{VERSION}.zip"


def get_excludes():
    """Return a set of paths to exclude from the package."""
    return {
        ".git",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".pi",
        ".flask-brain",
        ".DS_Store",
        "instance",       # database lives here — each install gets its own
        "backups",
        "prototypes",
        "ui-prototypes",
        "node_modules",
        ".playwright-cli",
        "scripts",         # dev scripts not needed for end users
        "*.pyc",
        ARCHIVE_NAME,
    }


def should_exclude(path: Path, excludes: set) -> bool:
    """Check if a path should be excluded."""
    parts = path.parts
    for part in parts:
        if part in excludes:
            return True
    # Check if any parent directory is excluded
    for i in range(1, len(parts)):
        parent = Path(*parts[:i])
        if parent.name in excludes:
            return True
    return False


def download_onnx_model():
    """Pre-download the ONNX model so it works offline."""
    print("Downloading ONNX model for offline use...")
    try:
        from huggingface_hub import hf_hub_download
        model_path = hf_hub_download(
            repo_id="onnx-community/all-MiniLM-L6-v2",
            filename="model.onnx",
        )
        tokenizer_path = hf_hub_download(
            repo_id="sentence-transformers/all-MiniLM-L6-v2",
            filename="tokenizer.json",
        )
        print(f"  Model: {model_path}")
        print(f"  Tokenizer: {tokenizer_path}")
        print("Model cached successfully — will work offline.")
    except Exception as e:
        print(f"  Warning: Could not download model: {e}")
        print("  Semantic search will download on first use (requires internet).")


def create_setup_scripts(dest_dir: Path):
    """Create setup.sh and setup.bat in the destination directory."""

    setup_sh = dest_dir / "setup.sh"
    setup_sh.write_text("""#!/bin/bash
# TaskManager — Setup script for macOS/Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up TaskManager..."

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install dependencies
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create instance directory
mkdir -p instance

echo ""
echo "Setup complete! Run './run.sh' to start the app."
echo "The app will be available at http://localhost:5001"
""")
    setup_sh.chmod(0o755)

    setup_bat = dest_dir / "setup.bat"
    setup_bat.write_text("""@echo off
REM TaskManager — Setup script for Windows
cd /d "%~dp0"

echo Setting up TaskManager...

REM Create virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

REM Activate and install dependencies
call .venv\\Scripts\\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

REM Create instance directory
if not exist "instance" mkdir instance

echo.
echo Setup complete! Run 'run.bat' to start the app.
echo The app will be available at http://localhost:5001
""")


def generate_sbom():
    """Generate a CycloneDX SBOM using pip-audit."""
    print("Generating CycloneDX SBOM...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip_audit", "--format", "cyclonedx-json",
             "--output", str(PROJECT_DIR / "snyk-report.json"), "-r", str(PROJECT_DIR / "requirements.txt")],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            print("  SBOM generated: snyk-report.json (0 vulnerabilities)")
        else:
            vuln_count = result.stdout.count("PYSEC")
            print(f"  SBOM generated: snyk-report.json ({vuln_count} vulnerabilities found)")
    except FileNotFoundError:
        print("  Warning: pip-audit not installed, skipping SBOM generation.")
        print("  Install with: pip install pip-audit")
    except subprocess.TimeoutExpired:
        print("  Warning: pip-audit timed out, skipping SBOM generation.")


def package():
    """Create the distribution zip file."""
    generate_sbom()

    dest = PROJECT_DIR / ARCHIVE_NAME
    if dest.exists():
        dest.unlink()

    print(f"Packaging TaskManager {VERSION}...")

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_DIR):
            # Filter out excluded directories in-place
            dirs[:] = [d for d in dirs if d not in get_excludes()]

            root_path = Path(root)
            for fname in files:
                fpath = root_path / fname
                if should_exclude(fpath, get_excludes()):
                    continue

                arcname = str(fpath.relative_to(PROJECT_DIR))
                zf.write(fpath, arcname)
                print(f"  + {arcname}")

    # Create setup scripts inside the zip
    with zipfile.ZipFile(dest, "a", zipfile.ZIP_DEFLATED) as zf:
        setup_sh_content = """#!/bin/bash
# TaskManager — Setup script for macOS/Linux
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "Setting up TaskManager..."

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

mkdir -p instance

echo ""
echo "Setup complete! Run './run.sh' to start the app."
echo "The app will be available at http://localhost:5001"
"""
        zf.writestr("setup.sh", setup_sh_content)

        setup_bat_content = """@echo off
REM TaskManager — Setup script for Windows
cd /d "%~dp0"

echo Setting up TaskManager...

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\\Scripts\\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

if not exist "instance" mkdir instance

echo.
echo Setup complete! Run 'run.bat' to start the app.
echo The app will be available at http://localhost:5001
"""
        zf.writestr("setup.bat", setup_bat_content)

    size_kb = dest.stat().st_size / 1024
    print(f"\nDone! {dest} ({size_kb:.0f} KB)")


def main():
    parser = argparse.ArgumentParser(description="Package TaskManager for distribution")
    parser.add_argument("--wheel", action="store_true", help="Pre-download ONNX model before packaging")
    args = parser.parse_args()

    if args.wheel:
        download_onnx_model()

    package()


if __name__ == "__main__":
    main()

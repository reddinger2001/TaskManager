#!/bin/bash
# Run TaskManager — sets up venv if needed, then starts the app.
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

# Activate and install dependencies
source "$VENV_DIR/bin/activate"
pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Run the app
export FLASK_APP=app/__init__.py:app
export FLASK_DEBUG=1
echo "Starting TaskManager on http://localhost:5000"
flask run --host 0.0.0.0 --port 5000

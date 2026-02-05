#!/usr/bin/env bash

set -e  # stop on error

VENV_NAME=".venv"
PYTHON_BIN="python3"

echo "🔹 Creating virtual environment..."
$PYTHON_BIN -m venv $VENV_NAME

echo "🔹 Activating virtual environment..."
source $VENV_NAME/bin/activate

echo "🔹 Upgrading pip..."
pip install --upgrade pip

if [ -f requirements.txt ]; then
    echo "🔹 Installing requirements..."
    pip install -r requirements.txt
else
    echo "⚠️  requirements.txt not found"
fi

echo "✅ Environment ready!"
echo "👉 Activate later with: source $VENV_NAME/bin/activate"

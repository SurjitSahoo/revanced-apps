#!/bin/zsh
# Script to check for Python virtual environment, create if missing, activate, and install dependencies


# Check if the script is being sourced in zsh
if [ -z "$ZSH_EVAL_CONTEXT" ] || [[ "$ZSH_EVAL_CONTEXT" != *:file* ]]; then
    echo "Please source this script: source ./setup_env.sh"
    return 1 2>/dev/null || exit 1
fi


VENV_DIR=".venv"
REQ_FILE="requirements.txt"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found. Creating..."
    python3 -m venv "$VENV_DIR"
fi

# Activate the virtual environment
source "$VENV_DIR/bin/activate"

# Install dependencies
if [ -f "$REQ_FILE" ]; then
    echo "Installing dependencies from $REQ_FILE..."
    pip install --upgrade pip
    pip install -r "$REQ_FILE"
else
    echo "Requirements file $REQ_FILE not found. Skipping dependency installation."
fi

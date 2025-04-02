#!/bin/bash
# SafeSpace - Shell script wrapper for the SafeSpace Python package

# Find the Python interpreter
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "Error: Python interpreter not found."
    echo "Please install Python 3.8 or higher."
    exit 1
fi

# Check if the SafeSpace package is installed
if ! $PYTHON -c "import safespace" 2>/dev/null; then
    echo "Error: SafeSpace package not found."
    echo "Please install it with: pip install safespace"
    exit 1
fi

# Run the SafeSpace package with all arguments
exec $PYTHON -m safespace "$@" 
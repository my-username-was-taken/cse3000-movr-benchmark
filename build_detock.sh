#!/bin/bash

IMAGE_NAME=${1:-detock}

# Create a Python 3.8 virtual environment if it doesn't already exist
if [ ! -d "build_detock" ]; then
    python3.8 -m venv build_detock
fi
source build_detock/bin/activate

# Upgrade pip
pip install --upgrade pip

# Set 'python' to use Python 3.8 in this shell
alias python="python3.8"

pip install -r tools/requirements.txt

docker build . -t "$IMAGE_NAME"
docker push "$IMAGE_NAME"

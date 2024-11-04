#!/bin/bash

IMAGE_NAME=${1:-detock}

base_repo_address=omraz
repo_name=seq_eval
tag=latest

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

push_address=${base_repo_address}/${IMAGE_NAME}:${tag}
docker build . -t "$IMAGE_NAME" -t ${push_address}
docker push ${push_address}

# Tag and push the Detock img
docker tag $IMAGE_NAME ${base_repo_address}/${repo_name}:${tag}
docker push ${base_repo_address}/${repo_name}:${tag}
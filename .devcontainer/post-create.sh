#!/usr/bin/env bash

echo "Python version set to: $PYTHON_VERSION"

# Make sure Docker socket is available inside the container
# sudo chmod 666 /var/run/docker.sock

# Make sure Docker can be found by the Docker extension
# sudo ln -s /usr/bin/docker /usr/local/bin/docker

# Configure git to avoid permission issues
git config --global --add safe.directory /workspace

echo "Initializing uv environment for workspace..."

cd /workspace

# uv init --verbose
uv venv --python ${PYTHON_VERSION}
uv sync --all-packages --verbose

# uv pip install debugpy
# uv pip install pytest
# uv pip install pytest-timeout
# uv pip install pytest-cov
# uv pip install -r /workspace/.devcontainer/requirements-dev.txt

cd /workspace

chmod +x load_env.sh

echo "Post-create script completed!"

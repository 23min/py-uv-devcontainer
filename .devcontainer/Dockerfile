# Base Image: Using a slim version of Python 3.13
FROM python:3.13-slim-bookworm

# Arguments for user and environment customization
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
ARG PYTHON_VERSION=3.13
ARG VENV_IN_PROJECT=true
ARG TIMEZONE=Europe/Amsterdam

# Set environment variables for Python, pipx, timezone, and caching
ENV GIT_PYTHON_REFRESH=quiet \
    TZ=$TIMEZONE \
    HOME="/home/$USERNAME" \
    PIPX_HOME="$HOME/.pipx" \
    PIPX_BIN_DIR="$HOME/.local/bin" \
    PYTHON_VERSION=${PYTHON_VERSION} \
    UV_CACHE_DIR="$HOME/.cache/uv" \
    UV_LINK_MODE="copy" \
    UV_PYTHON_PREFERENCE="only-managed" \
    USERNAME=${USERNAME} \
    USER_UID=${USER_UID} \
    USER_GID=${USER_GID}

# Create necessary directories and ensure they have the correct permissions
RUN mkdir -p $UV_CACHE_DIR $PIPX_HOME $PIPX_BIN_DIR && \
    chown -R ${USER_UID}:${USER_GID} $UV_CACHE_DIR $PIPX_HOME $PIPX_BIN_DIR

# Install system dependencies, Oh My Zsh, Just command runner, Docker Compose, and additional tools
RUN apt-get update && \
    apt-get install -y \
    git iputils-ping curl zsh bash sudo pipx docker.io openssh-client \
    --no-install-recommends curl ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/* && \
    # Install Oh My Zsh
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" || true && \
    # Install Just command runner
    curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh | bash -s -- --to $PIPX_BIN_DIR && \
    # Install Docker Compose v2
    curl -SL https://github.com/docker/compose/releases/download/v2.29.0/docker-compose-linux-x86_64 -o /usr/local/bin/docker-compose && \
    chmod +x /usr/local/bin/docker-compose && \
    ln -s /usr/local/bin/docker-compose /usr/bin/docker-compose && \
    # Install Ruff
    curl -LsSf https://astral.sh/ruff/install.sh | sh  && \
    # Install pipreqs for generating requirements files based on imports
    # Redirect pipx install logs and install uv through pipx
    pipx install uv >> /var/log/build.log 2>&1 && \
    pipx ensurepath >> /var/log/build.log 2>&1 && \
    uv --version >> /var/log/build.log 2>&1 || echo "UV installation failed" >> /var/log/build.log

# Configure direnv for zsh environment
# RUN echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc

# Create sudoers file for passwordless sudo access, create the user, and set permissions
RUN mkdir -p /etc/sudoers.d && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/nopasswd && \
    chmod 440 /etc/sudoers.d/nopasswd && \
    # Create the user if it does not exist
    if ! id -u $USERNAME > /dev/null 2>&1; then \
    groupadd --gid $USER_GID $USERNAME; \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME; \
    fi && \
    # Ensure Docker group exists and add the user to it for Docker access
    if ! getent group docker > /dev/null; then \
    groupadd docker; \
    fi && usermod -aG docker $USERNAME && \
    # Set permissions for the workspace folder
    mkdir -p /workspace && chown -R ${USERNAME}:${USERNAME} /workspace && \
    chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

# Set working directory
WORKDIR /workspace

# Copy application code into the container
COPY . .

# Set Git safe directory for the workspace
RUN git config --global --add safe.directory /workspace

# Set the default user to avoid running as root
USER ${USERNAME}

# Default command to keep the container running for development
CMD ["sleep", "infinity"]
# Alternative command
# CMD ["tail", "-f", "/dev/null"]

# Slim base: uv will install Python, so we don't need a Python image
FROM debian:bookworm-slim

ARG HOST_USER
ARG HOST_UID=1000
ARG HOST_GID=1000

ENV HOST_USER=${HOST_USER}
ENV ENV=local

# Install system dependencies (no Python here; uv provides it)
RUN apt-get update && apt-get install -y \
    build-essential \
    ca-certificates \
    curl \
    git \
    jq \
    locales \
    nano \
    openssh-server \
    sudo \
    unzip \
    vim \
    wget \
    dos2unix \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Configure locale (slim image: enable in locale.gen, generate; ENV is enough in container)
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8

# Install AWS CLI
RUN cd /tmp && \
    curl "https://awscli.amazonaws.com/awscli-exe-linux-$(uname -m).zip" -o "/tmp/awscliv2.zip" && \
    unzip /tmp/awscliv2.zip && \
    /tmp/aws/install && \
    rm -rf /tmp/aws /tmp/awscliv2.zip

# Install Node.js and make accessible to all users
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    ln -sf /usr/bin/node /usr/local/bin/node && \
    ln -sf /usr/bin/npm /usr/local/bin/npm

ENV AWS_DEFAULT_REGION=us-east-2
ENV AWS_SHARED_CREDENTIALS_FILE=/home/dev/.aws/credentials
ENV EDITOR=vim

# Create dev user and group
RUN groupadd -g ${HOST_GID} dev && \
    useradd -m -s /bin/bash -u ${HOST_UID} -g ${HOST_GID} -G sudo dev && \
    echo 'dev ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/dev && \
    chmod 0440 /etc/sudoers.d/dev

# Set up workspace
WORKDIR /home/dev/dashboards
COPY . .
RUN chown -R dev:dev /home/dev/dashboards && \
    chmod +x /home/dev/dashboards/docker/entrypoint.sh

# Switch to dev user for Python setup
USER dev
ENV PATH="/home/dev/.local/bin:/usr/local/bin:/usr/bin:$PATH"

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Python 3.12
RUN /home/dev/.local/bin/uv python install 3.13

# Create and sync venv (include dev deps so pre-commit is available in container)
RUN /home/dev/.local/bin/uv venv
RUN /home/dev/.local/bin/uv sync --group dev

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/home/dev/dashboards
ENV VIRTUAL_ENV=/home/dev/dashboards/.venv

# Switch back to root for entrypoint
USER root
ENTRYPOINT ["/home/dev/dashboards/docker/entrypoint.sh"]

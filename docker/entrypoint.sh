#!/usr/bin/env bash
set -e

# Normalize HOST_USER to avoid dots (.) in usernames/paths
if [[ -n "${HOST_USER:-}" ]]; then
  export HOST_USER="${HOST_USER//./_}"
fi

# Set up environment configuration directory
echo "Setting up environment configuration..."
mkdir -p /home/dev/.config/dashboard

# Set permissions
chown -R dev:dev /home/dev/.config
chmod 755 /home/dev/.config
chmod 755 /home/dev/.config/dashboard

# Ensure AWS region is set
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-2}

# Set up bash/zsh configuration
cp /etc/skel/.bashrc /etc/skel/.profile /etc/skel/.bash_logout /home/dev/ 2>/dev/null || true
chown dev:dev /home/dev/.bashrc /home/dev/.profile /home/dev/.bash_logout 2>/dev/null || true

BASHRC=/home/dev/.bashrc

# Add AWS region to environment
echo "
# AWS Configuration
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
" >> "$BASHRC"

# Add venv activation and cd to .bashrc if not already added
if ! grep -Fxq "source /home/dev/dashboards/.venv/bin/activate" "$BASHRC"; then
    echo "source /home/dev/dashboards/.venv/bin/activate" >> "$BASHRC"
    echo "cd /home/dev/dashboards" >> "$BASHRC"
fi

# Set up SSH directory structure
mkdir -p /home/dev/.ssh && \
  chmod 700 /home/dev/.ssh && \
  chown -R dev:dev /home/dev/.ssh && \
  echo 'dev:dev' | chpasswd

# Create SSH key for dev user if one doesn't exist
if [[ ! -f /home/dev/.ssh/dashboard_dev_env.pub ]]; then
  echo "Creating new SSH key..."
  su -l dev -c 'ssh-keygen -b 4096 -t rsa -f /home/dev/.ssh/dashboard_dev_env -q -N ""'
  chown -R dev:dev /home/dev/.ssh
else
  echo "Using existing SSH key."
fi

# Install pre-commit hooks
echo "Installing pre-commit hooks..."
su -l dev -c "cd /home/dev/dashboards && source /home/dev/dashboards/.venv/bin/activate && pre-commit install"

echo "Container setup complete!"
echo "Current working directory: $(pwd)"

# Keep container running
tail -f /dev/null

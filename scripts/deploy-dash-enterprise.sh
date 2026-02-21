#!/bin/bash
# Deploys a Dash app to Dash Enterprise: updating requirements.txt, building
# workspace packages into wheels, and deploying to Dash Enterprise.
#
# Example: scripts/deploy-dash-enterprise.sh dash/apps/cornsacks cornsacks-dev

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <app_path> <de_app_name>"
    echo "Example: $0 dash/apps/cornsacks my-cornsacks-app"
    exit 1
fi

APP_PATH="$1"
DE_APP_NAME="$2"
PROJECT_ROOT="/home/dev/dashboards"
APP_DIR="$PROJECT_ROOT/$APP_PATH"

echo "🚀 Deploying $APP_PATH to Dash Enterprise as '$DE_APP_NAME'"

# 1: Build the shared library into a wheel into the app directory
echo "🔨 Building neris-dash-common..."
cd "$PROJECT_ROOT"
uv build --package neris-dash-common --wheel --out-dir "$APP_DIR"

# 2: Sync Dash Enterprise dependencies
echo "🔄 Ensuring Dash Enterprise dependency is synced when this script is run..."
cd "$PROJECT_ROOT"
uv sync

# 3: Generate requirements.txt with local wheels
echo "📝 Generating requirements.txt..."
cd "$APP_DIR"

uv export --format requirements-txt --no-hashes --no-emit-local --no-emit-workspace --no-emit-project -o requirements.txt
# I feel like it should be possible to have uv recognize the workspace dependency and add it to the requirements.txt
# automatically, but I can't get it to work so we'll just add it manually for now.

# Add wheel files to requirements.txt
echo "📦 Adding wheel files..."
cd "$APP_DIR"
for wheel_file in *.whl; do
    if [ -f "$wheel_file" ]; then
        echo "./$wheel_file" >> requirements.txt
        echo "  Added: $wheel_file"
    fi
done

# 4: Deploy
de deploy . --name "$DE_APP_NAME"

# 5: Cleanup shared package build artifacts and generated requirements.txt
echo "🧹 Cleaning up..."
rm -f "$APP_DIR"/*.whl
rm -rf "$APP_DIR"/*.egg-info
rm -rf "$APP_DIR"/build
rm -f "$APP_DIR/requirements.txt"
find "$PROJECT_ROOT/dash/libs" -name "dist" -type d -exec rm -rf {} + 2>/dev/null || true
find "$PROJECT_ROOT/dash/libs" -name "*.egg-info" -type d -exec rm -rf {} + 2>/dev/null || true

echo "✅ Deployment completed!"

#!/usr/bin/env bash
# Frontend quality check script
# Runs Prettier format check on all frontend files

set -e

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "Running frontend quality checks..."
echo "Frontend dir: $FRONTEND_DIR"
echo ""

# Check if npm is available
if ! command -v npm &> /dev/null; then
  echo "ERROR: npm is not installed. Please install Node.js first."
  exit 1
fi

# Install dependencies if node_modules is missing
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "Installing frontend dependencies..."
  npm install --prefix "$FRONTEND_DIR"
  echo ""
fi

# Run Prettier check
echo "Checking formatting with Prettier..."
npm run format:check --prefix "$FRONTEND_DIR"

echo ""
echo "All frontend quality checks passed."

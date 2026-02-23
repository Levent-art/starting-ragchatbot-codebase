#!/usr/bin/env bash
# Frontend auto-format script
# Applies Prettier formatting to all frontend files

set -e

FRONTEND_DIR="$(cd "$(dirname "$0")/../frontend" && pwd)"

echo "Formatting frontend files with Prettier..."
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

# Run Prettier format
npm run format --prefix "$FRONTEND_DIR"

echo ""
echo "Frontend formatting complete."

#!/bin/bash

set -Eeuo pipefail

SCRIPT_DIR="$(command cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Removing existing millhouse marketplace (if present)..."
claude plugin marketplace remove millhouse || true

echo "Adding millhouse from local directory..."
claude plugin marketplace add "$SCRIPT_DIR"

echo "Installing plugins..."
claude plugin install taskmill@millhouse
claude plugin install codeguide@millhouse

echo "Installing Python dependencies..."
pip install -r "$SCRIPT_DIR/plugins/taskmill/requirements.txt"

echo "Installation complete!"

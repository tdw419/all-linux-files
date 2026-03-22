#!/bin/bash
set -e

echo "📦 Starting Linux Everything Release Build..."

# Check if cargo-deb is installed
if ! command -v cargo-deb &> /dev/null; then
    echo "⬇️  Installing cargo-deb..."
    cargo install cargo-deb
fi

# Build and package
echo "🔨 Building .deb package..."
cargo deb

# Output location
DEB_FILE=$(ls target/debian/*.deb | head -n 1)
echo "✅ Build complete!"
echo "📄 Package available at: $DEB_FILE"
echo ""
echo "To install, run:"
echo "sudo dpkg -i $DEB_FILE"

#!/usr/bin/env bash
set -euo pipefail

REPO="ken11/tokuye"
BINARY_NAME="tokuye"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

# ---- detect OS and arch ----
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Linux)
    OS_NAME="linux"
    ;;
  Darwin)
    OS_NAME="darwin"
    ;;
  *)
    echo "Error: Unsupported OS: $OS" >&2
    echo "Only Linux and macOS are supported." >&2
    exit 1
    ;;
esac

case "$ARCH" in
  x86_64 | amd64)
    ARCH_NAME="x86_64"
    ;;
  arm64 | aarch64)
    ARCH_NAME="arm64"
    ;;
  *)
    echo "Error: Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac

ASSET_NAME="${BINARY_NAME}-${OS_NAME}-${ARCH_NAME}"

# ---- resolve version ----
if [ -n "${VERSION:-}" ]; then
  TAG="$VERSION"
else
  echo "Fetching latest release..."
  TAG="$(curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | grep '"tag_name"' \
    | sed -E 's/.*"tag_name": *"([^"]+)".*/\1/')"
fi

if [ -z "$TAG" ]; then
  echo "Error: Could not determine release version." >&2
  exit 1
fi

DOWNLOAD_URL="https://github.com/${REPO}/releases/download/${TAG}/${ASSET_NAME}"

echo "Installing tokuye ${TAG} (${OS_NAME}/${ARCH_NAME})..."

# ---- download ----
TMP_FILE="$(mktemp)"
trap 'rm -f "$TMP_FILE"' EXIT

if command -v curl &>/dev/null; then
  curl -fsSL -o "$TMP_FILE" "$DOWNLOAD_URL"
elif command -v wget &>/dev/null; then
  wget -qO "$TMP_FILE" "$DOWNLOAD_URL"
else
  echo "Error: curl or wget is required." >&2
  exit 1
fi

# ---- install ----
mkdir -p "$INSTALL_DIR"
mv "$TMP_FILE" "${INSTALL_DIR}/${BINARY_NAME}"
chmod +x "${INSTALL_DIR}/${BINARY_NAME}"

echo ""
echo "tokuye has been installed to: ${INSTALL_DIR}/${BINARY_NAME}"

# ---- PATH hint ----
case ":${PATH}:" in
  *":${INSTALL_DIR}:"*)
    ;;
  *)
    echo ""
    echo "NOTE: ${INSTALL_DIR} is not in your PATH."
    echo "Add the following line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    ;;
esac

echo ""
echo "Run 'tokuye --help' to get started."

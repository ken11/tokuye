#!/usr/bin/env bash
set -euo pipefail

REPO="ken11/tokuye"
BINARY_NAME="tokuye"

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

# ---- resolve install dir ----
if [ -n "${INSTALL_DIR:-}" ]; then
  # User-specified: use as-is
  :
elif [ "$OS_NAME" = "darwin" ] && [ -d "/usr/local/bin" ] && [ -w "/usr/local/bin" ]; then
  INSTALL_DIR="/usr/local/bin"
else
  INSTALL_DIR="$HOME/.local/bin"
fi

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

echo "Installing tokuye ${TAG} (${OS_NAME}/${ARCH_NAME}) to ${INSTALL_DIR}..."

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
echo "✓ tokuye has been installed to: ${INSTALL_DIR}/${BINARY_NAME}"

# ---- PATH hint ----
case ":${PATH}:" in
  *":${INSTALL_DIR}:"*)
    ;;
  *)
    echo ""
    echo "NOTE: ${INSTALL_DIR} is not in your PATH."
    echo "Add the following line to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo "  export PATH=\"${INSTALL_DIR}:\$PATH\""
    ;;
esac

# ---- global config hint ----
GLOBAL_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/tokuye"
GLOBAL_CONFIG_FILE="${GLOBAL_CONFIG_DIR}/config.yaml"

echo ""
echo "─────────────────────────────────────────────"
echo " Next step: create your global config"
echo "─────────────────────────────────────────────"

if [ -f "$GLOBAL_CONFIG_FILE" ]; then
  echo ""
  echo "Global config already exists at: ${GLOBAL_CONFIG_FILE}"
  echo "Skip creation, or edit it manually."
else
  echo ""
  echo "Run the following to create a global config:"
  echo ""
  echo "  mkdir -p \"${GLOBAL_CONFIG_DIR}\""
  echo "  cat > \"${GLOBAL_CONFIG_FILE}\" << 'EOF'"
  echo "bedrock_model_id: global.anthropic.claude-sonnet-4-6"
  echo "bedrock_embedding_model_id: amazon.titan-embed-text-v2:0"
  echo "model_temperature: 0.2"
  echo "pr_branch_prefix: tokuye/"
  echo "name: Alice"
  echo "EOF"
fi

echo ""
echo "Once configured, run tokuye in any project:"
echo ""
echo "  cd /path/to/your/project"
echo "  tokuye --project-root /path/to/your/project"
echo ""

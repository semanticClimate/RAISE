#!/usr/bin/env bash
# ==============================================================================
#  RAISE — Universal POSIX / Linux / macOS Startup for Frontend
# ==============================================================================

cd "$(dirname "$0")" || exit 1

echo "============================================================================"
echo "                              RAISE FRONTEND"
echo "============================================================================"
echo ""

echo "[1/3] Checking environment & Node.js installation..."

OS_TYPE=$(uname -s)
RAW_ARCH=$(uname -m)

if [ "$OS_TYPE" = "Darwin" ]; then
    PLATFORM="darwin"
    [ "$RAW_ARCH" = "arm64" ] && NODE_ARCH="arm64" || NODE_ARCH="x64"
else
    PLATFORM="linux"
    [ "$RAW_ARCH" = "aarch64" ] && NODE_ARCH="arm64" || NODE_ARCH="x64"
fi

NODE_VER="v26.10.0"
NODE_FOLDER="node-${NODE_VER}-${PLATFORM}-${NODE_ARCH}"
PORTABLE_BIN="$(pwd)/.node/${NODE_FOLDER}/bin"

if [ -x "${PORTABLE_BIN}/node" ]; then
    export PATH="${PORTABLE_BIN}:$PATH"
    NODE_CMD="${PORTABLE_BIN}/node"
    NPM_CMD="${PORTABLE_BIN}/npm"
    echo "      [SUCCESS] Local portable Node.js Available in .node folder."
elif command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    NODE_CMD="node"
    NPM_CMD="npm"
    echo "      [SUCCESS] System Node.js Available in PATH: $(node -v)."
else
    echo ""
    echo "============================================================================"
    echo " [NOTICE] Node.js is NOT installed on this machine."
    echo " Automatically downloading portable Node.js LTS (${NODE_VER} for ${PLATFORM}-${NODE_ARCH})..."
    echo "============================================================================"
    echo ""

    mkdir -p .node
    if [ "$PLATFORM" = "darwin" ]; then
        TAR_FILE="/tmp/${NODE_FOLDER}.tar.gz"
        DOWNLOAD_URL="https://nodejs.org/dist/${NODE_VER}/${NODE_FOLDER}.tar.gz"
        curl -# -fLo "$TAR_FILE" "$DOWNLOAD_URL"
        tar -xzf "$TAR_FILE" -C .node
        rm -f "$TAR_FILE"
    else
        TAR_FILE="/tmp/${NODE_FOLDER}.tar.xz"
        DOWNLOAD_URL="https://nodejs.org/dist/${NODE_VER}/${NODE_FOLDER}.tar.xz"
        curl -# -fLo "$TAR_FILE" "$DOWNLOAD_URL"
        tar -xf "$TAR_FILE" -C .node
        rm -f "$TAR_FILE"
    fi

    export PATH="${PORTABLE_BIN}:$PATH"
    NODE_CMD="${PORTABLE_BIN}/node"
    NPM_CMD="${PORTABLE_BIN}/npm"
    echo "      [SUCCESS] Portable Node.js runtime is extracted and ready!"
fi



echo ""
echo "      - Node.js version: $("$NODE_CMD" -v 2>/dev/null)"
echo "      - npm version:     $("$NPM_CMD" -v 2>/dev/null)"
echo "      - Platform:        ${PLATFORM} (${NODE_ARCH})"
echo "      - Engine status:   READY"
echo ""

# Safely approve ONLY esbuild for install-scripts if supported
"$NPM_CMD" install-scripts approve esbuild --no-allow-scripts-pin >/dev/null 2>&1 || true

echo "[2/3] Checking project dependencies (node_modules)..."
if [ -d "node_modules" ]; then
    echo "      [SUCCESS] Dependencies (node_modules) Available."
else
    echo "      [DOWNLOADING] Installing all required npm packages..."
    "$NPM_CMD" install --no-fund --no-audit
    INSTALL_CODE=$?
    if [ $INSTALL_CODE -ne 0 ]; then
        echo "[ERROR] npm install failed with exit code $INSTALL_CODE."
        exit 1
    fi
    echo "      [SUCCESS] Dependencies installed successfully!"
fi

echo ""
echo "[3/3] Starting RAISE Frontend Development Server (Vite)..."
echo "============================================================================"
echo "  Local Address: http://localhost:5173/"
echo "  Press Ctrl+C to stop the server."
echo "============================================================================"
echo ""

"$NPM_CMD" run dev

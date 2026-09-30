#!/usr/bin/env bash
# ==============================================================================
#  RAISE — Universal POSIX / Linux / macOS Startup for Frontend
# ==============================================================================

cd "$(dirname "$0")" || exit 1

echo "============================================================================"
echo "                              RAISE FRONTEND"
echo "============================================================================"
# ------------------------------------------------------------------------------
# [0/3] Check if Frontend Source Code is Present; Auto-fetch if missing
# ------------------------------------------------------------------------------
if [ -f "package.json" ]; then
    echo "[0/3] Workspace verification: ready."
    echo ""
else
    echo "[0/3] Initializing workspace: fetching frontend assets from repository..."
    echo ""
    FETCH_SUCCESS=0
    if command -v git >/dev/null 2>&1; then
        echo "      [GIT] Cloning frontend branch from semanticClimate/RAISE..."
        git clone --depth 1 -b frontend https://github.com/semanticClimate/RAISE.git .temp_raise_frontend
        if [ $? -eq 0 ] && [ -f ".temp_raise_frontend/package.json" ]; then
            cp -R .temp_raise_frontend/* .
            cp -R .temp_raise_frontend/.* . 2>/dev/null || true
            rm -rf .temp_raise_frontend
            FETCH_SUCCESS=1
        fi
    fi
    if [ $FETCH_SUCCESS -eq 0 ] && command -v curl >/dev/null 2>&1; then
        echo "      [CURL] Downloading frontend branch archive..."
        curl -# -fLo /tmp/RAISE-frontend.zip "https://github.com/semanticClimate/RAISE/archive/refs/heads/frontend.zip"
        if [ $? -eq 0 ]; then
            unzip -q -o /tmp/RAISE-frontend.zip -d /tmp/RAISE-fe-extracted
            EXTRACTED_SUBDIR=$(find /tmp/RAISE-fe-extracted -mindepth 1 -maxdepth 1 -type d | head -n 1)
            if [ -n "$EXTRACTED_SUBDIR" ] && [ -d "$EXTRACTED_SUBDIR" ]; then
                cp -R "$EXTRACTED_SUBDIR"/* .
                cp -R "$EXTRACTED_SUBDIR"/.* . 2>/dev/null || true
                FETCH_SUCCESS=1
            fi
            rm -rf /tmp/RAISE-frontend.zip /tmp/RAISE-fe-extracted
        fi
    fi
    if [ ! -f "package.json" ]; then
        echo ""
        echo "============================================================================"
        echo " [ERROR] Could not fetch frontend code automatically."
        echo " Please clone the frontend branch manually:"
        echo "   git clone -b frontend https://github.com/semanticClimate/RAISE.git"
        echo "============================================================================"
        exit 1
    fi
    echo "      [SUCCESS] Frontend source code downloaded and prepared!"
    echo ""
fi

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

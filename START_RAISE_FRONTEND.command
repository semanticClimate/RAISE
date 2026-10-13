#!/usr/bin/env bash
# ==============================================================================
#  RAISE — Single-Click macOS Startup for Frontend
#  Double-clickable directly in Finder on macOS (Apple Silicon & Intel)
# ==============================================================================

# Ensure terminal directory is anchored to the script location
cd "$(dirname "$0")" || exit 1

clear
echo "============================================================================"
echo "                              RAISE FRONTEND"
echo "============================================================================"
echo ""

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
        read -p "Press Enter to exit..."
        exit 1
    fi
    echo "      [SUCCESS] Frontend source code downloaded and prepared!"
    echo ""
fi

# ------------------------------------------------------------------------------
# [1/3] Detect or Automatically Download Node.js & npm for macOS
# ------------------------------------------------------------------------------
echo "[1/3] Checking environment & Node.js installation..."

# Detect Mac hardware architecture (Apple Silicon M1/M2/M3/M4 = arm64; Intel = x64)
RAW_ARCH=$(uname -m)
if [ "$RAW_ARCH" = "arm64" ]; then
    MAC_ARCH="arm64"
else
    MAC_ARCH="x64"
fi

NODE_VER="v22.14.0"
NODE_FOLDER="node-${NODE_VER}-darwin-${MAC_ARCH}"
PORTABLE_BIN="$(pwd)/.node/${NODE_FOLDER}/bin"

# 1. Check if portable Node.js is Available in .node/
if [ -x "${PORTABLE_BIN}/node" ]; then
    export PATH="${PORTABLE_BIN}:$PATH"
    NODE_CMD="${PORTABLE_BIN}/node"
    NPM_CMD="${PORTABLE_BIN}/npm"
    echo "      [SUCCESS] Local portable Node.js Available in .node folder."
# 2. Check if system Node.js is Available and meets minimum requirements (Node 22 LTS)
elif command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    SYS_NODE_VER=$(node -v 2>/dev/null | tr -d 'v')
    SYS_MAJOR=$(echo "$SYS_NODE_VER" | cut -d'.' -f1)
    if [ "$SYS_MAJOR" -ge 22 ]; then
        NODE_CMD="node"
        NPM_CMD="npm"
        echo "      [SUCCESS] Modern system Node.js Available in PATH: $(node -v)."
    else
        echo "      [WARNING] Detected outdated Node.js ($(node -v)). Node 22.14+ LTS is required."
        echo "      Proceeding to download portable Node.js LTS (${NODE_VER})..."
    fi
fi

# 3. Neither found or outdated: Auto-download portable Node.js LTS for macOS
if [ -z "$NODE_CMD" ]; then
    echo ""
    echo "============================================================================"
    echo " [NOTICE] Node.js 22.14+ LTS is required."
    echo " Automatically downloading portable Node.js LTS (${NODE_VER} for ${MAC_ARCH})..."
    echo " (One-time download so you DO NOT have to install Homebrew, sudo, or anything!)"
    echo "============================================================================"
    echo ""

    mkdir -p .node
    TAR_FILE="/tmp/${NODE_FOLDER}.tar.gz"
    DOWNLOAD_URL="https://nodejs.org/dist/${NODE_VER}/${NODE_FOLDER}.tar.gz"

    echo "[DOWNLOADING] Fetching Node.js LTS from nodejs.org..."
    if command -v curl >/dev/null 2>&1; then
        curl -# -fLo "$TAR_FILE" "$DOWNLOAD_URL"
    else
        echo "[ERROR] curl is not installed. Please install Node.js manually: https://nodejs.org/"
        read -p "Press Enter to exit..."
        exit 1
    fi

    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to download Node.js archive. Check your internet connection."
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo ""
    echo "[EXTRACTING] Unpacking portable Node.js into .node folder..."
    tar -xzf "$TAR_FILE" -C .node
    rm -f "$TAR_FILE"

    if [ ! -x "${PORTABLE_BIN}/node" ]; then
        echo "[ERROR] Extraction failed. Node binary not found at ${PORTABLE_BIN}/node."
        read -p "Press Enter to exit..."
        exit 1
    fi

    export PATH="${PORTABLE_BIN}:$PATH"
    NODE_CMD="${PORTABLE_BIN}/node"
    NPM_CMD="${PORTABLE_BIN}/npm"
    echo "      [SUCCESS] Portable Node.js runtime is extracted and ready!"
fi



echo ""
echo "      - Node.js version: $("$NODE_CMD" -v 2>/dev/null)"
echo "      - npm version:     $("$NPM_CMD" -v 2>/dev/null)"
echo "      - Architecture:    ${MAC_ARCH} (macOS)"
echo "      - Engine status:   READY"
echo ""

# Safely approve ONLY esbuild for install-scripts if supported
"$NPM_CMD" install-scripts approve esbuild --no-allow-scripts-pin >/dev/null 2>&1 || true

# ------------------------------------------------------------------------------
# [2/3] Check & Install Project Dependencies (node_modules)
# ------------------------------------------------------------------------------
echo "[2/3] Checking project dependencies (node_modules)..."

if [ -d "node_modules" ]; then
    echo "      [SUCCESS] Dependencies (node_modules) Available."
else
    echo "      [DOWNLOADING] node_modules directory NOT found."
    echo "                    Installing all required npm packages..."
    echo "                    (Downloading React 19, Vite, Tailwind, and UI components)"
    echo ""
    "$NPM_CMD" install --no-fund --no-audit
    INSTALL_CODE=$?
    if [ $INSTALL_CODE -ne 0 ]; then
        echo ""
        echo "============================================================================"
        echo " [ERROR] npm install failed with exit code $INSTALL_CODE."
        echo " Please verify your internet connection and retry."
        echo "============================================================================"
        echo ""
        read -p "Press Enter to exit..."
        exit 1
    fi
    echo ""
    echo "      [SUCCESS] Dependencies installed successfully!"
fi

echo ""

# ------------------------------------------------------------------------------
# [3/3] Launch Vite Development Server
# ------------------------------------------------------------------------------
echo "[3/3] Starting RAISE Frontend Development Server (Vite)..."
echo ""
echo "============================================================================"
echo "  Vite server is launching..."
echo "  Local Address: http://localhost:5173/"
echo ""
echo "  [!] KEEP THIS TERMINAL WINDOW OPEN while using the application."
echo "  Press Ctrl+C to stop the server when finished."
echo "============================================================================"
echo ""

"$NPM_CMD" run dev

echo ""
echo "============================================================================"
echo "  Vite development server has stopped."
echo "============================================================================"
echo ""
read -p "Press Enter to close this window..."

#!/bin/bash

# A2S.Liquid - Unified macOS Dashboard Launcher (SPEC_v1.0)
# Launches both the Bun-based Next.js frontend and confirms Python environment.

# 1. Colors for Console
BLUE='\033[0;34m'
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${PURPLE}=============================================${NC}"
echo -e "${PURPLE}   🚀 A2S.Liquid Dashboard - macOS Core v1.0  ${NC}"
echo -e "${PURPLE}=============================================${NC}"

# 2. Check for Bun
if ! command -v bun &> /dev/null
then
    echo -e "${BLUE}[INF]${NC} Bun not found. Attempting to install..."
    curl -fsSL https://bun.sh/install | bash
    source ~/.bashrc
fi

# 3. Check for Python Environment
echo -e "${BLUE}[INF]${NC} Checking Python core..."
if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}[INF]${NC} Found requirements.txt. Ensure 'pip install -r requirements.txt' is run."
fi

# 4. Launch Next.js Dashboard
echo -e "${GREEN}[SUCCESS]${NC} Launching A2S.Liquid Topology Engine..."
cd frontend_next && bun dev &

# 5. Provide Access Info
echo -e ""
echo -e "${GREEN}[READY]${NC} Dashboard active at: ${BLUE}http://localhost:3000${NC}"
echo -e "${BLUE}[INF]${NC} Use Terminal Console in the UI to monitor agents."
echo -e "${PURPLE}=============================================${NC}"

# Wait for background processes
wait

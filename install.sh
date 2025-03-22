#!/bin/bash

# Installation script for Terminal AI Assistant Lite

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Terminal AI Assistant Lite Installer ===${NC}"
echo ""

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    echo -e "${RED}Error: curl is required but not installed.${NC}"
    echo "Please install curl to continue."
    exit 1
fi

# Check if bash is installed
if ! command -v bash &> /dev/null; then
    echo -e "${RED}Error: bash is required but not installed.${NC}"
    echo "Please install bash to continue."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}Warning: jq is not installed. Some features may be limited.${NC}"
    echo "Consider installing jq for better JSON handling."
    
    # Suggest installation command based on package manager
    if command -v apt-get &> /dev/null; then
        echo -e "  ${GREEN}sudo apt-get install jq${NC}"
    elif command -v dnf &> /dev/null; then
        echo -e "  ${GREEN}sudo dnf install jq${NC}"
    elif command -v yum &> /dev/null; then
        echo -e "  ${GREEN}sudo yum install jq${NC}"
    elif command -v pacman &> /dev/null; then
        echo -e "  ${GREEN}sudo pacman -S jq${NC}"
    elif command -v brew &> /dev/null; then
        echo -e "  ${GREEN}brew install jq${NC}"
    fi
    echo ""
fi

# Destination directory
INSTALL_DIR="$HOME/bin"
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Creating directory $INSTALL_DIR${NC}"
    mkdir -p "$INSTALL_DIR"
fi

# Copy script to destination
echo -e "${GREEN}Installing Terminal AI Assistant Lite...${NC}"
cp terminal_ai_lite.sh "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/terminal_ai_lite.sh"

# Copy config example
echo -e "${GREEN}Installing configuration example...${NC}"
mkdir -p "$HOME/.config/terminal_ai_lite"
cp terminal_ai_lite.config "$HOME/.config/terminal_ai_lite/config.example"

# Check if PATH includes the bin directory
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo -e "${YELLOW}Adding $INSTALL_DIR to your PATH...${NC}"
    echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
    echo "Please restart your shell or run 'source ~/.bashrc' to update your PATH."
fi

echo ""
echo -e "${GREEN}Installation complete!${NC}"
echo -e "Run the assistant with: ${BLUE}terminal_ai_lite.sh${NC}"
echo -e "On first run, you'll be prompted to enter your Google Gemini API key."
echo ""
echo -e "${YELLOW}Note:${NC} If you'd like to customize the configuration, copy and edit the example:"
echo -e "  ${GREEN}cp $HOME/.config/terminal_ai_lite/config.example ~/.terminal_ai_lite_config${NC}"
echo "" 
#!/bin/bash

# Installation script for Terminal AI Assistant Lite

# Colors - Update for Windows compatibility
RED='\e[0;31m'
GREEN='\e[0;32m'
YELLOW='\e[0;33m'
BLUE='\e[0;34m'
NC='\e[0m' # No Color

printf "${BLUE}=== Terminal AI Assistant Lite Installer ===${NC}\n"
echo ""

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    printf "${RED}Error: curl is required but not installed.${NC}\n"
    echo "Please install curl to continue."
    exit 1
fi

# Check if bash is installed
if ! command -v bash &> /dev/null; then
    printf "${RED}Error: bash is required but not installed.${NC}\n"
    echo "Please install bash to continue."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    printf "${YELLOW}Warning: jq is not installed. Some features may be limited.${NC}\n"
    echo "Consider installing jq for better JSON handling."
    
    # Suggest installation command based on package manager
    if command -v apt-get &> /dev/null; then
        printf "  ${GREEN}sudo apt-get install jq${NC}\n"
    elif command -v dnf &> /dev/null; then
        printf "  ${GREEN}sudo dnf install jq${NC}\n"
    elif command -v yum &> /dev/null; then
        printf "  ${GREEN}sudo yum install jq${NC}\n"
    elif command -v pacman &> /dev/null; then
        printf "  ${GREEN}sudo pacman -S jq${NC}\n"
    elif command -v brew &> /dev/null; then
        printf "  ${GREEN}brew install jq${NC}\n"
    fi
    echo ""
fi

# Destination directory
INSTALL_DIR="$HOME/bin"
if [ ! -d "$INSTALL_DIR" ]; then
    printf "${YELLOW}Creating directory $INSTALL_DIR${NC}\n"
    mkdir -p "$INSTALL_DIR"
fi

# Copy script to destination
printf "${GREEN}Installing Terminal AI Assistant Lite...${NC}\n"
cp terminal_ai_lite.sh "$INSTALL_DIR/"

# Set execute permissions based on OS
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    # Windows environment
    printf "${YELLOW}Setting executable permissions for Windows...${NC}\n"
    if command -v powershell.exe &> /dev/null; then
        powershell.exe -Command "Set-ItemProperty -Path \"$INSTALL_DIR/terminal_ai_lite.sh\" -Name IsReadOnly -Value \$false"
    else
        # Fallback to chmod if PowerShell is not available
        chmod +x "$INSTALL_DIR/terminal_ai_lite.sh" 2>/dev/null || true
    fi
else
    # Unix/Linux environment
    chmod +x "$INSTALL_DIR/terminal_ai_lite.sh"
fi

# Copy config example
printf "${GREEN}Installing configuration example...${NC}\n"
mkdir -p "$HOME/.config/terminal_ai_lite"
cp terminal_ai_lite.config "$HOME/.config/terminal_ai_lite/config.example"

# Check if PATH includes the bin directory
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    printf "${YELLOW}Adding $INSTALL_DIR to your PATH...${NC}\n"
    
    # Add to appropriate shell config based on OS
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
        # Windows - check if PowerShell profile exists
        if command -v powershell.exe &> /dev/null; then
            POWERSHELL_PROFILE=$(powershell.exe -Command "if (!(Test-Path -Path \$PROFILE)) { New-Item -Path \$PROFILE -Type File -Force }; \$PROFILE")
            printf "${YELLOW}Adding path to PowerShell profile: $POWERSHELL_PROFILE${NC}\n"
            powershell.exe -Command "Add-Content -Path \$PROFILE -Value \"\`$env:PATH += \";$INSTALL_DIR\"\""
            echo "Please restart your PowerShell to update your PATH."
        else
            echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
            echo "Please restart your shell or run 'source ~/.bashrc' to update your PATH."
        fi
    else
        # Unix/Linux
        echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
        echo "Please restart your shell or run 'source ~/.bashrc' to update your PATH."
    fi
fi

echo ""
printf "${GREEN}Installation complete!${NC}\n"
printf "Run the assistant with: ${BLUE}terminal_ai_lite.sh${NC}\n"
printf "On first run, you'll be prompted to enter your Google Gemini API key.\n"
echo ""
printf "${YELLOW}Note:${NC} If you'd like to customize the configuration, copy and edit the example:\n"
printf "  ${GREEN}cp $HOME/.config/terminal_ai_lite/config.example ~/.terminal_ai_lite_config${NC}\n"
echo "" 
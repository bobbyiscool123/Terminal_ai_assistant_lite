#!/bin/bash

# Terminal AI Assistant Lite
# A lightweight version for Linux terminals with minimal dependencies

# Detect if running in Windows environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" || "$OSTYPE" == "cygwin" ]]; then
    # In Windows, disable colors
    IS_WINDOWS=true
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    MAGENTA=''
    CYAN=''
    NC=''
else
    # Colors for Unix/Linux
    IS_WINDOWS=false
    RED='\e[0;31m'
    GREEN='\e[0;32m'
    YELLOW='\e[0;33m'
    BLUE='\e[0;34m'
    MAGENTA='\e[0;35m'
    CYAN='\e[0;36m'
    NC='\e[0m' # No Color
fi

# Configuration
HISTORY_FILE="$HOME/.terminal_ai_lite_history"
CONFIG_FILE="$HOME/.terminal_ai_lite_config"
API_KEY_FILE="$HOME/.terminal_ai_lite_api_key"
MAX_HISTORY=100
CONFIRM_DANGEROUS=true
STREAM_OUTPUT=true
MODEL="gemini-2.0-flash"

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    printf "${RED}Error: curl is required but not installed.${NC}\n"
    echo "Please install curl to use this application."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    printf "${YELLOW}Warning: jq is not installed. Some features may be limited.${NC}\n"
    echo "Consider installing jq for better JSON handling."
fi

# Load API key
if [ -f "$API_KEY_FILE" ]; then
    API_KEY=$(cat "$API_KEY_FILE")
else
    printf "${YELLOW}No API key found.${NC}\n"
    echo -n "Please enter your Google Gemini API key: "
    read -r API_KEY
    echo "$API_KEY" > "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE" # Set permissions to protect the API key
fi

# Load configuration if exists
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi

# Create history file if it doesn't exist
if [ ! -f "$HISTORY_FILE" ]; then
    touch "$HISTORY_FILE"
fi

# Function to display banner
show_banner() {
    if [ "$IS_WINDOWS" = true ]; then
        echo "╔══════════════════════════════════════════╗"
        echo "║ Terminal AI Assistant Lite                ║"
        echo "║ Type 'exit' to quit, 'help' for commands ║"
        echo "╚══════════════════════════════════════════╝"
    else
        printf "${BLUE}╔══════════════════════════════════════════╗${NC}\n"
        printf "${BLUE}║${GREEN} Terminal AI Assistant Lite                ${BLUE}║${NC}\n"
        printf "${BLUE}║${YELLOW} Type 'exit' to quit, 'help' for commands ${BLUE}║${NC}\n"
        printf "${BLUE}╚══════════════════════════════════════════╝${NC}\n"
    fi
}

# Function to show help
show_help() {
    if [ "$IS_WINDOWS" = true ]; then
        echo "Available Commands:"
        echo "  help     - Show this help message"
        echo "  exit     - Exit the program"
        echo "  clear    - Clear the screen"
        echo "  history  - Show command history"
        echo "  config   - Show current configuration"
        echo "  cd DIR   - Change directory"
        echo "  pwd      - Show current directory"
    else
        printf "${CYAN}Available Commands:${NC}\n"
        printf "  ${GREEN}help${NC}     - Show this help message\n"
        printf "  ${GREEN}exit${NC}     - Exit the program\n"
        printf "  ${GREEN}clear${NC}    - Clear the screen\n"
        printf "  ${GREEN}history${NC}  - Show command history\n"
        printf "  ${GREEN}config${NC}   - Show current configuration\n"
        printf "  ${GREEN}cd DIR${NC}   - Change directory\n"
        printf "  ${GREEN}pwd${NC}      - Show current directory\n"
    fi
}

# Function to check if a command is dangerous
is_dangerous_command() {
    local command="$1"
    local dangerous_patterns=("rm -rf" "mkfs" "dd" "chmod" "chown" "sudo" "> /dev/sda" "mkfs.ext4" "dd if=" "rm -rf /")
    
    for pattern in "${dangerous_patterns[@]}"; do
        if [[ "$command" == *"$pattern"* ]]; then
            return 0 # true in bash
        fi
    done
    
    return 1 # false in bash
}

# Function to call Gemini API
get_ai_response() {
    local task="$1"
    local current_dir=$(pwd)
    
    # Prepare the prompt
    local prompt="You are a terminal command expert for Linux. Given the following task, provide a list of commands to execute in sequence.
    Each command should be a single line and should be executable in a Linux terminal.
    Task: $task
    Current directory: $current_dir
    Return only the commands, one per line, without any explanations or markdown formatting."
    
    # Call Gemini API - Fix color escape sequence
    if [ "$IS_WINDOWS" = true ]; then
        echo "Thinking..."
    else
        printf "${YELLOW}Thinking...${NC}\n"
    fi
    
    local response
    response=$(curl -s -X POST "https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent?key=$API_KEY" \
        -H "Content-Type: application/json" \
        -d "{
            \"contents\": [{
                \"parts\": [{
                    \"text\": \"$prompt\"
                }]
            }]
        }")
    
    # Extract commands from response
    if command -v jq &> /dev/null; then
        echo "$response" | jq -r '.candidates[0].content.parts[0].text' | grep -v '^\s*$'
    else
        # Fallback if jq is not available
        echo "$response" | grep -o '"text": "[^"]*"' | sed 's/"text": "\(.*\)"/\1/' | grep -v '^\s*$'
    fi
}

# Function to execute a command
execute_command() {
    local command="$1"
    
    # Check if command is dangerous
    if $CONFIRM_DANGEROUS && is_dangerous_command "$command"; then
        if [ "$IS_WINDOWS" = true ]; then
            echo "Warning: This command might be dangerous."
        else
            printf "${RED}Warning: This command might be dangerous.${NC}\n"
        fi
        echo -n "Continue? (y/n): "
        read -r confirm
        if [[ "$confirm" != "y" ]]; then
            return
        fi
    fi
    
    # Add to history
    echo "$(date '+%Y-%m-%d %H:%M:%S') $command" >> "$HISTORY_FILE"
    
    # Execute command
    if [ "$IS_WINDOWS" = true ]; then
        echo "Executing: $command"
    else
        printf "${GREEN}Executing:${NC} $command\n"
    fi
    
    if $STREAM_OUTPUT; then
        eval "$command"
    else
        output=$(eval "$command" 2>&1)
        echo "$output"
    fi
}

# Function to process built-in commands
process_builtin_command() {
    local input="$1"
    
    case "$input" in
        "help")
            show_help
            return 0
            ;;
        "exit" | "quit")
            if [ "$IS_WINDOWS" = true ]; then
                echo "Goodbye!"
            else
                printf "${GREEN}Goodbye!${NC}\n"
            fi
            exit 0
            ;;
        "clear")
            clear
            show_banner
            return 0
            ;;
        "history")
            if [ -f "$HISTORY_FILE" ]; then
                tail -n $MAX_HISTORY "$HISTORY_FILE"
            else
                echo "No history available."
            fi
            return 0
            ;;
        "config")
            if [ "$IS_WINDOWS" = true ]; then
                echo "Current Configuration:"
            else
                printf "${CYAN}Current Configuration:${NC}\n"
            fi
            echo "MAX_HISTORY=$MAX_HISTORY"
            echo "CONFIRM_DANGEROUS=$CONFIRM_DANGEROUS"
            echo "STREAM_OUTPUT=$STREAM_OUTPUT"
            echo "MODEL=$MODEL"
            return 0
            ;;
        "pwd")
            pwd
            return 0
            ;;
        cd*)
            # Handle cd command
            eval "$input"
            echo "Changed directory to: $(pwd)"
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Main function
main() {
    clear
    show_banner
    
    while true; do
        echo ""
        if [ "$IS_WINDOWS" = true ]; then
            echo -n "What would you like me to do? "
        else
            printf "${GREEN}What would you like me to do?${NC} "
        fi
        read -r user_input
        
        # Check if it's a built-in command
        if process_builtin_command "$user_input"; then
            continue
        fi
        
        # Get AI response
        commands=$(get_ai_response "$user_input")
        
        # Execute each command
        if [ -n "$commands" ]; then
            if [ "$IS_WINDOWS" = true ]; then
                echo "I'll run these commands for you:"
            else
                printf "${CYAN}I'll run these commands for you:${NC}\n"
            fi
            echo "$commands" | while read -r command; do
                if [ -n "$command" ]; then
                    execute_command "$command"
                fi
            done
        else
            if [ "$IS_WINDOWS" = true ]; then
                echo "Sorry, I couldn't generate any commands for that request."
            else
                printf "${RED}Sorry, I couldn't generate any commands for that request.${NC}\n"
            fi
        fi
    done
}

# Start the application
main 
#!/bin/bash

# Terminal AI Assistant Lite
# A lightweight version for Termux and other terminals with minimal dependencies

# Disable colors completely to avoid any escape sequence errors
RED=''
GREEN=''
YELLOW=''
BLUE=''
MAGENTA=''
CYAN=''
NC=''

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
    echo "Error: curl is required but not installed."
    echo "Please install curl to use this application."
    exit 1
fi

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Warning: jq is not installed. Some features may be limited."
    echo "Consider installing jq for better JSON handling."
    echo "In Termux, run: pkg install jq"
fi

# Load API key
if [ -f "$API_KEY_FILE" ]; then
    API_KEY=$(cat "$API_KEY_FILE")
else
    echo "No API key found."
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
    echo "╔══════════════════════════════════════════╗"
    echo "║ Terminal AI Assistant Lite                ║"
    echo "║ Type 'exit' to quit, 'help' for commands ║"
    echo "╚══════════════════════════════════════════╝"
}

# Function to show help
show_help() {
    echo "Available Commands:"
    echo "  help     - Show this help message"
    echo "  exit     - Exit the program"
    echo "  clear    - Clear the screen"
    echo "  history  - Show command history"
    echo "  config   - Show current configuration"
    echo "  cd DIR   - Change directory"
    echo "  pwd      - Show current directory"
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
    
    # Prepare the prompt with Termux-specific context
    local prompt="You are a terminal command expert for Termux on Android. Given the following task, provide a list of commands to execute in sequence.
    Each command should be a single line and should be executable in Termux.
    Task: $task
    Current directory: $current_dir
    Return only the commands, one per line, without any explanations or markdown formatting.
    Use Termux-specific commands where appropriate (e.g., pkg instead of apt)."
    
    # Call Gemini API without color escape sequences - to stderr to avoid being captured as command
    echo "Thinking..." >&2
    
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
        echo "Warning: This command might be dangerous."
        echo -n "Continue? (y/n): "
        read -r confirm
        if [[ "$confirm" != "y" ]]; then
            return
        fi
    fi
    
    # Add to history
    echo "$(date '+%Y-%m-%d %H:%M:%S') $command" >> "$HISTORY_FILE"
    
    # Execute command
    echo "Executing: $command"
    
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
            echo "Goodbye!"
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
            echo "Current Configuration:"
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
        echo -n "What would you like me to do? "
        read -r user_input
        
        # Check if it's a built-in command
        if process_builtin_command "$user_input"; then
            continue
        fi
        
        # Get AI response
        echo "I'll run these commands for you:" >&2
        commands=$(get_ai_response "$user_input")
        
        # Execute each command
        if [ -n "$commands" ]; then
            echo "$commands" | while read -r command; do
                if [ -n "$command" ]; then
                    execute_command "$command"
                fi
            done
        else
            echo "Sorry, I couldn't generate any commands for that request."
        fi
    done
}

# Start the application
main 
#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import datetime
import re
from pathlib import Path
from dotenv import load_dotenv
from colorama import init, Fore, Back, Style

# Initialize colorama for cross-platform color support
init()

# Microsoft theme colors
MS_BLUE = Fore.BLUE
MS_CYAN = Fore.CYAN
MS_GREEN = Fore.GREEN
MS_YELLOW = Fore.YELLOW
MS_RED = Fore.RED
MS_MAGENTA = Fore.MAGENTA
MS_WHITE = Fore.WHITE
MS_RESET = Style.RESET_ALL
MS_BRIGHT = Style.BRIGHT
MS_DIM = Style.DIM

# Load environment variables from .env file
load_dotenv()

# Configuration
HISTORY_FILE = os.path.expanduser("~/.terminal_ai_lite_history")
CONFIG_FILE = os.path.expanduser("~/.terminal_ai_lite_config")
MAX_HISTORY = 100
CONFIRM_DANGEROUS = True
STREAM_OUTPUT = True
MODEL = "gemini-2.0-flash"

# Get API key from .env file
API_KEY = os.getenv("GEMINI_API_KEY")

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        subprocess.run(["curl", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        print(f"{MS_RED}Error: curl is required but not installed.{MS_RESET}")
        print("Please install curl to use this application.")
        sys.exit(1)
    
    try:
        import json
    except ImportError:
        print(f"{MS_YELLOW}Warning: json module not available. Some features may be limited.{MS_RESET}")

def load_config():
    """Load configuration from file if it exists"""
    global MAX_HISTORY, CONFIRM_DANGEROUS, STREAM_OUTPUT, MODEL
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        key, value = line.strip().split('=', 1)
                        if key == "MAX_HISTORY":
                            MAX_HISTORY = int(value)
                        elif key == "CONFIRM_DANGEROUS":
                            CONFIRM_DANGEROUS = (value.lower() == "true")
                        elif key == "STREAM_OUTPUT":
                            STREAM_OUTPUT = (value.lower() == "true")
                        elif key == "MODEL":
                            MODEL = value.strip('"\'')
        except Exception as e:
            print(f"{MS_RED}Error loading config: {e}{MS_RESET}")

def ensure_history_file():
    """Create history file if it doesn't exist"""
    if not os.path.exists(HISTORY_FILE):
        Path(HISTORY_FILE).touch()

def show_banner():
    """Display the terminal assistant banner"""
    print(f"{MS_BLUE}╔══════════════════════════════════════════╗{MS_RESET}")
    print(f"{MS_BLUE}║{MS_CYAN} Terminal AI Assistant Lite                {MS_BLUE}║{MS_RESET}")
    print(f"{MS_BLUE}║{MS_YELLOW} Type 'exit' to quit, 'help' for commands {MS_BLUE}║{MS_RESET}")
    print(f"{MS_BLUE}╚══════════════════════════════════════════╝{MS_RESET}")

def show_help():
    """Display help information"""
    print(f"{MS_CYAN}Available Commands:{MS_RESET}")
    print(f"  {MS_GREEN}help{MS_RESET}     - Show this help message")
    print(f"  {MS_GREEN}exit{MS_RESET}     - Exit the program")
    print(f"  {MS_GREEN}clear{MS_RESET}    - Clear the screen")
    print(f"  {MS_GREEN}history{MS_RESET}  - Show command history")
    print(f"  {MS_GREEN}config{MS_RESET}   - Show current configuration")
    print(f"  {MS_GREEN}cd DIR{MS_RESET}   - Change directory")
    print(f"  {MS_GREEN}pwd{MS_RESET}      - Show current directory")
    print(f"  {MS_GREEN}api-key{MS_RESET}  - Update your API key")

def is_dangerous_command(command):
    """Check if a command is potentially dangerous"""
    dangerous_patterns = ["rm -rf", "mkfs", "dd", "chmod", "chown", "sudo", 
                         "> /dev/sda", "mkfs.ext4", "dd if=", "rm -rf /"]
    
    for pattern in dangerous_patterns:
        if pattern in command:
            return True
    return False

def get_ai_response(task):
    """Call Gemini API to get command suggestions"""
    global API_KEY
    
    if not API_KEY:
        print(f"{MS_RED}API key not found in .env file. Please set GEMINI_API_KEY in your .env file.{MS_RESET}")
        return ""
    
    current_dir = os.getcwd()
    
    # Prepare the prompt
    prompt = f"""You are a terminal command expert for Termux on Android. Given the following task, provide a list of commands to execute in sequence.
    Each command should be a single line and should be executable in Termux.
    Task: {task}
    Current directory: {current_dir}
    Return only the commands, one per line, without any explanations or markdown formatting.
    Use Termux-specific commands where appropriate (e.g., pkg instead of apt)."""
    
    print(f"{MS_YELLOW}Thinking...{MS_RESET}", file=sys.stderr)
    
    # Simple responses for basic commands
    if task.lower() in ["hi", "hello", "test"]:
        return 'echo "Hello from Terminal AI Assistant! I\'m working correctly."'
    
    # Package update commands
    if "pkg update" in task.lower() or "upgrade" in task.lower():
        return "pkg update\npkg upgrade -y"
    
    try:
        # Construct API request
        curl_command = [
            "curl", "-s", "-X", "POST",
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }]
            })
        ]
        
        # Call API
        result = subprocess.run(curl_command, capture_output=True, text=True)
        response = result.stdout
        
        # Check for errors
        if "error" in response:
            try:
                error_data = json.loads(response)
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                print(f"{MS_RED}API Error: {error_message}{MS_RESET}", file=sys.stderr)
            except:
                print(f"{MS_RED}API Error. Check your API key and internet connection.{MS_RESET}", file=sys.stderr)
            return ""
        
        if not response:
            print(f"{MS_RED}Empty response from API. Check your internet connection.{MS_RESET}", file=sys.stderr)
            return ""
        
        # Parse response
        try:
            response_data = json.loads(response)
            commands = response_data["candidates"][0]["content"]["parts"][0]["text"]
            return commands.strip()
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            print(f"{MS_RED}Failed to extract commands from API response: {e}{MS_RESET}", file=sys.stderr)
            return ""
            
    except Exception as e:
        print(f"{MS_RED}Error calling API: {e}{MS_RESET}", file=sys.stderr)
        return ""

def execute_command(command):
    """Execute a shell command with appropriate safeguards"""
    global CONFIRM_DANGEROUS, STREAM_OUTPUT
    
    # Check if command is dangerous
    if CONFIRM_DANGEROUS and is_dangerous_command(command):
        print(f"{MS_RED}Warning: This command might be dangerous.{MS_RESET}")
        confirm = input("Continue? (y/n): ")
        if confirm.lower() != "y":
            return
    
    # Add to history
    with open(HISTORY_FILE, "a") as f:
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"{timestamp} {command}\n")
    
    # Execute command
    print(f"{MS_GREEN}Executing:{MS_RESET} {command}")
    
    try:
        if STREAM_OUTPUT:
            # Stream output in real-time
            process = subprocess.Popen(command, shell=True, executable="/bin/bash" if os.name != "nt" else None)
            process.communicate()
        else:
            # Capture and display output
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr)
    except Exception as e:
        print(f"{MS_RED}Error executing command: {e}{MS_RESET}")

def process_builtin_command(input_cmd):
    """Process built-in commands"""
    if input_cmd == "help":
        show_help()
        return True
    elif input_cmd in ["exit", "quit"]:
        print(f"{MS_GREEN}Goodbye!{MS_RESET}")
        sys.exit(0)
    elif input_cmd == "clear":
        os.system("cls" if os.name == "nt" else "clear")
        show_banner()
        return True
    elif input_cmd == "history":
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                lines = f.readlines()
                for line in lines[-MAX_HISTORY:]:
                    print(line.strip())
        else:
            print("No history available.")
        return True
    elif input_cmd == "config":
        print(f"{MS_CYAN}Current Configuration:{MS_RESET}")
        print(f"MAX_HISTORY={MAX_HISTORY}")
        print(f"CONFIRM_DANGEROUS={CONFIRM_DANGEROUS}")
        print(f"STREAM_OUTPUT={STREAM_OUTPUT}")
        print(f"MODEL={MODEL}")
        return True
    elif input_cmd == "pwd":
        print(os.getcwd())
        return True
    elif input_cmd == "api-key":
        new_key = input(f"Enter your new Gemini API key: ")
        if new_key.strip():
            # Update key in memory
            global API_KEY
            API_KEY = new_key
            
            # Update .env file
            env_path = os.path.join(os.getcwd(), '.env')
            
            # Read existing content to preserve other variables
            env_content = {}
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    for line in f:
                        if '=' in line and not line.strip().startswith('#'):
                            key, value = line.strip().split('=', 1)
                            env_content[key] = value
            
            # Update API key
            env_content["GEMINI_API_KEY"] = new_key
            
            # Write back to file
            with open(env_path, 'w') as f:
                for key, value in env_content.items():
                    f.write(f"{key}={value}\n")
            
            print(f"{MS_GREEN}API key updated successfully in .env file{MS_RESET}")
        return True
    elif input_cmd.startswith("cd "):
        directory = input_cmd[3:]
        try:
            os.chdir(os.path.expanduser(directory))
            print(f"Changed directory to: {os.getcwd()}")
        except Exception as e:
            print(f"{MS_RED}Error changing directory: {e}{MS_RESET}")
        return True
    
    return False

def main():
    """Main function"""
    # Initialization
    check_dependencies()
    load_config()
    ensure_history_file()
    
    # Check for API key
    global API_KEY
    if not API_KEY:
        print(f"{MS_YELLOW}API key not found in .env file. Please set GEMINI_API_KEY in your .env file.{MS_RESET}")
        new_key = input("Enter your Gemini API key now (or press Enter to quit): ")
        if not new_key.strip():
            print(f"{MS_RED}No API key provided. Exiting.{MS_RESET}")
            sys.exit(1)
        
        # Save API key to .env file
        API_KEY = new_key
        with open('.env', 'w') as f:
            f.write(f"GEMINI_API_KEY={new_key}\n")
        print(f"{MS_GREEN}API key saved to .env file{MS_RESET}")
    
    # Main loop
    os.system("cls" if os.name == "nt" else "clear")
    show_banner()
    
    while True:
        print("")
        user_input = input(f"{MS_GREEN}What would you like me to do?{MS_RESET} ")
        
        # Check if it's a built-in command
        if process_builtin_command(user_input):
            continue
        
        # Get AI response
        print(f"{MS_CYAN}I'll run these commands for you:{MS_RESET}", file=sys.stderr)
        commands = get_ai_response(user_input)
        
        # Execute each command
        if commands:
            for command in commands.splitlines():
                if command.strip():
                    execute_command(command.strip())
        else:
            print(f"{MS_RED}Sorry, I couldn't generate any commands for that request.{MS_RESET}")
            print("You can try rephrasing your request or check your API key if this continues.")

if __name__ == "__main__":
    main() 
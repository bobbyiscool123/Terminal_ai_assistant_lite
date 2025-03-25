#!/usr/bin/env python3

import os
import sys
import json
import subprocess
import datetime
import re
import time
import pickle
import shlex
import asyncio
import threading
import select
from pathlib import Path
from dotenv import load_dotenv
from colorama import init, Fore, Back, Style, AnsiToWin32
try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

try:
    import pyperclip
    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Initialize colorama with Windows specific settings
if os.name == "nt":
    init(wrap=True, convert=True, strip=False, autoreset=True)
    # Force colorama to wrap stdout/stderr
    sys.stdout = AnsiToWin32(sys.stdout).stream
    sys.stderr = AnsiToWin32(sys.stderr).stream
else:
    init(autoreset=True)

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
TOKEN_CACHE_FILE = os.path.expanduser("~/.terminal_ai_lite_token_cache")
TEMPLATE_FILE = os.path.expanduser("~/.terminal_ai_lite_templates")
COMMAND_GROUPS_FILE = os.path.expanduser("~/.terminal_ai_lite_command_groups")
MAX_HISTORY = 100
CONFIRM_DANGEROUS = True
STREAM_OUTPUT = True
MODEL = "gemini-1.5-flash"
API_ENDPOINT = "https://generativelanguage.googleapis.com"
API_VERSION = "v1"
EXPLAIN_COMMANDS = False
USE_STREAMING_API = True
USE_TOKEN_CACHE = True
TOKEN_CACHE_EXPIRY = 7 # days
FORMAT_OUTPUT = False
VERIFY_COMMANDS = True
USE_CLIPBOARD = True
ALLOW_COMMAND_CHAINING = True
USE_ASYNC_EXECUTION = True

# Get API key from .env file
API_KEY = os.getenv("GEMINI_API_KEY")

# Store active background processes
background_processes = {}

# Token cache dictionary
token_cache = {}

# Command templates
templates = {
    "update": "Update all packages",
    "network": "Show network information",
    "disk": "Show disk usage",
    "process": "Show running processes",
    "memory": "Show memory usage",
    "backup": "Backup important files"
}

# Command groups with categories
command_groups = {
    "file": ["ls", "cd", "cp", "mv", "rm", "mkdir", "touch", "cat", "nano", "find"],
    "network": ["ifconfig", "ping", "traceroute", "netstat", "ssh", "curl", "wget"],
    "system": ["top", "ps", "kill", "termux-info", "df", "du", "free"],
    "package": ["pkg", "apt", "dpkg", "pip"],
    "archive": ["tar", "zip", "unzip", "gzip", "gunzip"],
    "git": ["git clone", "git pull", "git push", "git commit", "git status"],
    "termux": ["termux-open", "termux-open-url", "termux-share", "termux-notification"]
}

# Output formatters
output_formatters = {
    "json": lambda text: json.dumps(json.loads(text), indent=2) if is_json(text) else text,
    "lines": lambda text: "\n".join([line for line in text.split("\n") if line.strip()]),
    "truncate": lambda text: text[:500] + "..." if len(text) > 500 else text,
    "upper": lambda text: text.upper(),
    "lower": lambda text: text.lower(),
    "grep": lambda text, pattern: "\n".join([line for line in text.split("\n") if pattern in line])
}

def is_json(text):
    """Check if text is valid JSON"""
    try:
        json.loads(text)
        return True
    except:
        return False

def format_output(text, formatter, pattern=None):
    """Format output using specified formatter"""
    if formatter not in output_formatters:
        return text
    
    try:
        if formatter == "grep" and pattern:
            return output_formatters[formatter](text, pattern)
        else:
            return output_formatters[formatter](text)
    except Exception as e:
        print(f"{MS_RED}Error formatting output: {e}{MS_RESET}")
        return text

def copy_to_clipboard(text):
    """Copy text to clipboard if clipboard module is available"""
    if not CLIPBOARD_AVAILABLE:
        print(f"{MS_YELLOW}Clipboard functionality not available. Install pyperclip.{MS_RESET}")
        return False
    
    try:
        pyperclip.copy(text)
        print(f"{MS_GREEN}Copied to clipboard.{MS_RESET}")
        return True
    except Exception as e:
        print(f"{MS_RED}Error copying to clipboard: {e}{MS_RESET}")
        return False

def load_templates():
    """Load command templates from file if it exists"""
    global templates
    
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, 'rb') as f:
                templates = pickle.load(f)
        except Exception as e:
            print(f"{MS_YELLOW}Error loading templates: {e}. Using defaults.{MS_RESET}")

def save_templates():
    """Save command templates to file"""
    try:
        with open(TEMPLATE_FILE, 'wb') as f:
            pickle.dump(templates, f)
        print(f"{MS_GREEN}Templates saved.{MS_RESET}")
    except Exception as e:
        print(f"{MS_RED}Error saving templates: {e}{MS_RESET}")

def load_command_groups():
    """Load command groups from file if it exists"""
    global command_groups
    
    if os.path.exists(COMMAND_GROUPS_FILE):
        try:
            with open(COMMAND_GROUPS_FILE, 'rb') as f:
                command_groups = pickle.load(f)
        except Exception as e:
            print(f"{MS_YELLOW}Error loading command groups: {e}. Using defaults.{MS_RESET}")

def save_command_groups():
    """Save command groups to file"""
    try:
        with open(COMMAND_GROUPS_FILE, 'wb') as f:
            pickle.dump(command_groups, f)
        print(f"{MS_GREEN}Command groups saved.{MS_RESET}")
    except Exception as e:
        print(f"{MS_RED}Error saving command groups: {e}{MS_RESET}")

def load_token_cache():
    """Load token cache from file if it exists"""
    global token_cache
    
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, 'rb') as f:
                token_cache = pickle.load(f)
                
            # Clean expired tokens
            current_time = time.time()
            expired_keys = []
            for key, (value, timestamp) in token_cache.items():
                if current_time - timestamp > TOKEN_CACHE_EXPIRY * 86400:  # seconds in a day
                    expired_keys.append(key)
            
            for key in expired_keys:
                del token_cache[key]
                
        except Exception as e:
            print(f"{MS_YELLOW}Error loading token cache: {e}. Creating new cache.{MS_RESET}")
            token_cache = {}

def save_token_cache():
    """Save token cache to file"""
    try:
        with open(TOKEN_CACHE_FILE, 'wb') as f:
            pickle.dump(token_cache, f)
    except Exception as e:
        print(f"{MS_YELLOW}Error saving token cache: {e}{MS_RESET}")

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
    
    if not PROMPT_TOOLKIT_AVAILABLE:
        print(f"{MS_YELLOW}Warning: prompt_toolkit not available. Command history navigation will be disabled.{MS_RESET}")
        print("Install prompt_toolkit for enhanced command history features.")
    
    if not CLIPBOARD_AVAILABLE:
        print(f"{MS_YELLOW}Warning: pyperclip not available. Clipboard integration will be disabled.{MS_RESET}")
        print("Install pyperclip for clipboard integration features.")

def load_config():
    """Load configuration from file if it exists"""
    global MAX_HISTORY, CONFIRM_DANGEROUS, STREAM_OUTPUT, MODEL
    global EXPLAIN_COMMANDS, USE_STREAMING_API, USE_TOKEN_CACHE, TOKEN_CACHE_EXPIRY
    global FORMAT_OUTPUT, VERIFY_COMMANDS, USE_CLIPBOARD
    global ALLOW_COMMAND_CHAINING, USE_ASYNC_EXECUTION
    
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
                        elif key == "EXPLAIN_COMMANDS":
                            EXPLAIN_COMMANDS = (value.lower() == "true")
                        elif key == "USE_STREAMING_API":
                            USE_STREAMING_API = (value.lower() == "true")
                        elif key == "USE_TOKEN_CACHE":
                            USE_TOKEN_CACHE = (value.lower() == "true")
                        elif key == "TOKEN_CACHE_EXPIRY":
                            TOKEN_CACHE_EXPIRY = int(value)
                        elif key == "FORMAT_OUTPUT":
                            FORMAT_OUTPUT = (value.lower() == "true")
                        elif key == "VERIFY_COMMANDS":
                            VERIFY_COMMANDS = (value.lower() == "true")
                        elif key == "USE_CLIPBOARD":
                            USE_CLIPBOARD = (value.lower() == "true")
                        elif key == "ALLOW_COMMAND_CHAINING":
                            ALLOW_COMMAND_CHAINING = (value.lower() == "true")
                        elif key == "USE_ASYNC_EXECUTION":
                            USE_ASYNC_EXECUTION = (value.lower() == "true")
        except Exception as e:
            print(f"{MS_RED}Error loading config: {e}{MS_RESET}")
            print(f"{MS_YELLOW}Using default configuration.{MS_RESET}")

def save_config():
    """Save current configuration to file"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            f.write(f"MAX_HISTORY={MAX_HISTORY}\n")
            f.write(f"CONFIRM_DANGEROUS={CONFIRM_DANGEROUS}\n")
            f.write(f"STREAM_OUTPUT={STREAM_OUTPUT}\n")
            f.write(f"MODEL={MODEL}\n")
            f.write(f"EXPLAIN_COMMANDS={EXPLAIN_COMMANDS}\n")
            f.write(f"USE_STREAMING_API={USE_STREAMING_API}\n")
            f.write(f"USE_TOKEN_CACHE={USE_TOKEN_CACHE}\n")
            f.write(f"TOKEN_CACHE_EXPIRY={TOKEN_CACHE_EXPIRY}\n")
            f.write(f"FORMAT_OUTPUT={FORMAT_OUTPUT}\n")
            f.write(f"VERIFY_COMMANDS={VERIFY_COMMANDS}\n")
            f.write(f"USE_CLIPBOARD={USE_CLIPBOARD}\n")
            f.write(f"ALLOW_COMMAND_CHAINING={ALLOW_COMMAND_CHAINING}\n")
            f.write(f"USE_ASYNC_EXECUTION={USE_ASYNC_EXECUTION}\n")
        print(f"{MS_GREEN}Configuration saved.{MS_RESET}")
    except Exception as e:
        print(f"{MS_RED}Error saving configuration: {e}{MS_RESET}")

def ensure_history_file():
    """Create history file if it doesn't exist"""
    if not os.path.exists(HISTORY_FILE):
        Path(HISTORY_FILE).touch()

def show_banner():
    """Display the terminal assistant banner"""
    # Reset colors first
    print(Style.RESET_ALL, end="")
    
    # Print banner with explicit color resets
    print(f"{MS_BLUE}+==========================================+{MS_RESET}")
    print(f"{MS_BLUE}|{MS_CYAN} Terminal AI Assistant Lite                {MS_BLUE}|{MS_RESET}")
    print(f"{MS_BLUE}|{MS_YELLOW} Type 'exit' to quit, 'help' for commands {MS_BLUE}|{MS_RESET}")
    print(f"{MS_BLUE}+==========================================+{MS_RESET}")
    
    # Ensure colors are reset
    print(Style.RESET_ALL, end="")

def show_help():
    """Display help information"""
    print(f"{MS_CYAN}Available Commands:{MS_RESET}")
    print(f"  {MS_GREEN}help{MS_RESET}     - Show this help message")
    print(f"  {MS_GREEN}exit{MS_RESET}     - Exit the program")
    print(f"  {MS_GREEN}clear{MS_RESET}    - Clear the screen")
    print(f"  {MS_GREEN}history{MS_RESET}  - Show command history")
    print(f"  {MS_GREEN}config{MS_RESET}   - Show current configuration")
    print(f"  {MS_GREEN}set{MS_RESET}      - Change configuration settings")
    print(f"  {MS_GREEN}cd DIR{MS_RESET}   - Change directory")
    print(f"  {MS_GREEN}pwd{MS_RESET}      - Show current directory")
    print(f"  {MS_GREEN}api-key{MS_RESET}  - Update your API key")
    print(f"  {MS_GREEN}setup{MS_RESET}    - Run setup wizard")
    print(f"  {MS_GREEN}templates{MS_RESET} - Manage command templates")
    print(f"  {MS_GREEN}groups{MS_RESET}   - Manage command groups")
    print(f"  {MS_GREEN}format{MS_RESET}   - Format last command output")
    print(f"  {MS_GREEN}copy{MS_RESET}     - Copy last command output to clipboard")
    print(f"  {MS_GREEN}async{MS_RESET}    - Run command in background (e.g. async ls)")
    print(f"  {MS_GREEN}jobs{MS_RESET}     - Show running background jobs")
    print(f"  {MS_GREEN}kill{MS_RESET}     - Kill a background job (e.g. kill 1)")
    print(f"  {MS_GREEN}!TEMPLATE{MS_RESET} - Run a template (e.g. !update)")
    print(f"  {MS_GREEN}verify{MS_RESET}   - Toggle command verification")
    print(f"  {MS_GREEN}chain{MS_RESET}    - Toggle command chaining")

def explain_command(command):
    """Get an explanation for a command"""
    global API_KEY, API_ENDPOINT, API_VERSION
    
    if not API_KEY:
        print(f"{MS_RED}API key not found. Cannot explain command.{MS_RESET}")
        return
    
    print(f"{MS_YELLOW}Getting explanation...{MS_RESET}")
    
    # Prepare the explanation prompt
    prompt = f"""Explain what this terminal command does in simple terms:
    {command}
    
    Provide a brief explanation that a beginner could understand. Include any potential risks or side effects.
    """
    
    # Call API for explanation
    try:
        curl_command = [
            "curl", "-s", "-X", "POST",
            f"{API_ENDPOINT}/{API_VERSION}/models/gemini-1.5-flash:generateContent?key={API_KEY}",
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
        
        response_data = json.loads(response)
        explanation = response_data["candidates"][0]["content"]["parts"][0]["text"]
        
        print(f"{MS_CYAN}Command Explanation:{MS_RESET}")
        print(f"{explanation.strip()}")
        
    except Exception as e:
        print(f"{MS_RED}Could not get explanation: {e}{MS_RESET}")

def verify_command(command):
    """Verify if a command is safe to execute"""
    global API_KEY, MODEL, VERIFY_COMMANDS, API_ENDPOINT, API_VERSION
    
    # Skip verification if disabled
    if not VERIFY_COMMANDS:
        return True, ""
    
    # Quick pass for simple commands
    simple_commands = ["ls", "pwd", "echo", "cat", "cd", "clear", "whoami", "date", "time", "help"]
    command_base = command.split()[0] if command.split() else ""
    if command_base in simple_commands:
        return True, ""
    
    # Check for dangerous patterns
    if is_dangerous_command(command):
        prompt = f"The command '{command}' appears potentially dangerous. "
        prompt += f"Would you like to run it anyway? (y/n): "
        choice = input(prompt)
        if choice.lower() != 'y':
            return False, "Command cancelled by user"
    
    # For other commands, call AI to verify
    if API_KEY:
        print(f"{MS_YELLOW}Verifying command safety...{MS_RESET}")
        
        os_type = "Windows" if os.name == "nt" else "Unix/Linux"
        
        # Prepare prompt for verification
        prompt = f"""Analyze this shell command and assess its safety:
        
        COMMAND: {command}
        OPERATING SYSTEM: {os_type}
        
        Respond with a JSON object that includes:
        1. "safe": boolean indicating if the command is safe to run
        2. "reason": brief explanation of your assessment
        3. "risk_level": a number from 0-10 where 0 is completely safe and 10 is extremely dangerous
        
        Example response:
        {{
          "safe": true,
          "reason": "This command only lists files and does not modify anything",
          "risk_level": 0
        }}"""
        
        # Call API for verification
        try:
            curl_command = [
                "curl", "-s", "-X", "POST",
                f"{API_ENDPOINT}/{API_VERSION}/models/{MODEL}:generateContent?key={API_KEY}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.1,
                        "topP": 0.8,
                        "topK": 40,
                        "maxOutputTokens": 1024
                    }
                })
            ]
            
            # Call API
            result = subprocess.run(curl_command, capture_output=True, text=True)
            response = result.stdout
            
            response_data = json.loads(response)
            verification = response_data["candidates"][0]["content"]["parts"][0]["text"]
            
            print(f"{MS_CYAN}Command Verification:{MS_RESET}")
            print(f"{verification.strip()}")
            
            # Extract the safety assessment
            safety_line = ""
            for line in verification.splitlines():
                if line.strip().startswith("SAFETY:"):
                    safety_line = line.strip().lower()
                    break
            
            # Highlight safety concerns with color
            if "unsafe" in safety_line or "dangerous" in safety_line:
                print(f"{MS_RED}This command may be unsafe. Please review carefully.{MS_RESET}")
            elif "safe" in safety_line:
                print(f"{MS_GREEN}Command appears to be safe.{MS_RESET}")
            else:
                print(f"{MS_YELLOW}Safety assessment unclear. Please review manually.{MS_RESET}")
            
            confirm = input(f"{MS_YELLOW}Execute this command? (y/n):{MS_RESET} ")
            return confirm.lower() == 'y', verification
        except Exception as e:
            print(f"{MS_RED}Error parsing verification: {e}{MS_RESET}")
            confirm = input(f"{MS_YELLOW}Execute anyway? (y/n):{MS_RESET} ")
            return confirm.lower() == 'y', "Verification error"
    else:
        return False, "API key not found"

def is_dangerous_command(command):
    """Check if a command is potentially dangerous using regex patterns"""
    import re
    
    # Normalized command (lowercase, extra spaces removed)
    normalized_cmd = re.sub(r'\s+', ' ', command.lower().strip())
    
    # Regex patterns for dangerous commands
    dangerous_patterns = [
        # System modification commands
        r'rm\s+(-[a-z]*[rf][a-z]*\s+|-[a-z]*\s+)?(/|\.|~)',  # rm with r or f flags targeting root/home
        r'mv\s+(/|\.|~).*\s+/dev',  # Moving critical files to /dev
        r'mkfs',  # Filesystem formatting
        r'dd(\s+|=)',  # Low-level disk operations
        r'chmod\s+([0-7])?[0-7][0-7][0-7]\s+(/|\.|~|/etc|/var|/usr)',  # chmod on system directories
        r'chown\s+.*\s+(/|\.|~|/etc|/var|/usr)',  # chown on system directories
        
        # Privilege escalation
        r'sudo',  # Sudo command
        r'su\s',  # Switch user
        
        # Dangerous redirections
        r'>\s*/dev/sd[a-z]',  # Writing to disk devices
        r'>\s*/dev/null.*<',  # Null redirection with input
        
        # Fork bombs and dangerous bash constructs
        r':\(\)\s*{.*}.*:',  # Fork bomb pattern
        r'\(\s*[a-zA-Z]+.*\)\s*{\s*.*\s*}\s*;',  # Suspicious bash function declarations
        
        # Command execution in subshells
        r'\$\(.*\)',  # Command substitution
        r'`.*`',      # Backtick command substitution
        
        # Network and remote access
        r'nc\s+-[el]',  # Netcat in listening mode
        r'curl\s+.*\|\s*sh',  # Piping curl to shell
        r'wget\s+.*\|\s*sh',  # Piping wget to shell
        
        # Sensitive paths
        r'(rm|mv|cp)\s+-[a-z]*\s+.*(/etc/passwd|/etc/shadow|/etc/sudoers)',  # Modifying critical system files
        r'(rm|mv|cp)\s+-[a-z]*\s+.*/boot',  # Modifying boot files
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, normalized_cmd):
            return True
    
    # Check for sensitive directories that should not be removed or modified
    sensitive_dirs = ["/", "/etc", "/var", "/usr", "/bin", "/sbin", "/lib", "/boot", "/dev", "/proc", "/sys"]
    for directory in sensitive_dirs:
        if f"rm -rf {directory}" in normalized_cmd or f"rm -fr {directory}" in normalized_cmd:
            return True
            
    return False

# Store last command output for formatting/copying
last_command_output = ""

def execute_command(command, is_async=False):
    """Execute a shell command with appropriate safeguards"""
    global CONFIRM_DANGEROUS, STREAM_OUTPUT, EXPLAIN_COMMANDS, VERIFY_COMMANDS, FORMAT_OUTPUT, last_command_output
    
    # Skip empty commands
    if not command or command.isspace():
        print(f"{MS_YELLOW}Empty command. Nothing to execute.{MS_RESET}")
        return
    
    # Handle async execution
    if is_async or command.startswith("&"):
        if command.startswith("&"):
            command = command[1:].strip()
        
        # Apply security checks before running in background
        if CONFIRM_DANGEROUS and is_dangerous_command(command):
            print(f"{MS_RED}Warning: This command might be dangerous.{MS_RESET}")
            confirm = input("Continue in background? (y/n): ")
            if confirm.lower() != "y":
                return
        
        job_id = start_async_command(command)
        print(f"{MS_GREEN}Started background job #{job_id}{MS_RESET}")
        return
    
    # Check if command is dangerous
    if CONFIRM_DANGEROUS and is_dangerous_command(command):
        print(f"{MS_RED}Warning: This command might be dangerous.{MS_RESET}")
        print(f"{MS_RED}Command: {command}{MS_RESET}")
        confirm = input("Continue? (y/n): ")
        if confirm.lower() != "y":
            return
    
    # Verify command if enabled
    if VERIFY_COMMANDS and not verify_command(command):
        return
    
    # Explain command if enabled
    if EXPLAIN_COMMANDS:
        explain_command(command)
        proceed = input(f"\n{MS_CYAN}Execute this command? (y/n):{MS_RESET} ")
        if proceed.lower() != "y":
            return
    
    # Parse command for potential pipes to formatters
    formatted_output = False
    base_command = command
    
    if " | format:" in command:
        parts = command.split(" | format:", 1)
        base_command = parts[0]
        formatter = parts[1].strip()
        formatted_output = True
    
    # Add to history
    try:
        with open(HISTORY_FILE, "a") as f:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{timestamp} {command}\n")
    except Exception as e:
        print(f"{MS_YELLOW}Could not write to history file: {e}{MS_RESET}")
    
    # Execute command with timeout handling
    print(f"{MS_GREEN}Executing:{MS_RESET} {base_command}")
    
    try:
        if STREAM_OUTPUT and not formatted_output:
            # Stream output in real-time with timeout
            try:
                # Create process
                process = subprocess.Popen(
                    base_command, 
                    shell=True, 
                    executable="/bin/bash" if os.name != "nt" else None,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1
                )
                
                # Set timeout
                start_time = time.time()
                max_execution_time = 300  # 5 minutes
                
                # Stream output with timeout check
                while process.poll() is None:
                    # Check for timeout
                    if time.time() - start_time > max_execution_time:
                        process.terminate()
                        print(f"\n{MS_RED}Command execution timed out after {max_execution_time} seconds{MS_RESET}")
                        return
                    
                    # Read stdout with timeout
                    ready_to_read, _, _ = select.select([process.stdout, process.stderr], [], [], 0.1)
                    for stream in ready_to_read:
                        line = stream.readline()
                        if line:
                            if stream == process.stdout:
                                print(line, end="")
                            else:
                                print(f"{MS_RED}{line}{MS_RESET}", end="")
                
                # Read any remaining output
                stdout, stderr = process.communicate()
                if stdout:
                    print(stdout, end="")
                if stderr:
                    print(f"{MS_RED}{stderr}{MS_RESET}", end="")
                
                last_command_output = "Output was streamed and not captured"
                
                # Check return code
                if process.returncode != 0:
                    print(f"\n{MS_YELLOW}Command completed with return code: {process.returncode}{MS_RESET}")
                
            except Exception as e:
                print(f"{MS_RED}Error streaming command output: {e}{MS_RESET}")
                
        else:
            # Capture and display output with timeout
            try:
                result = subprocess.run(
                    base_command, 
                    shell=True, 
                    capture_output=True, 
                    text=True, 
                    timeout=300  # 5 minute timeout
                )
                
                output = result.stdout
                error = result.stderr
                
                # Store output for later formatting or copying
                last_command_output = output
                
                # Format output if requested
                if formatted_output:
                    output = format_output(output, formatter)
                
                if output:
                    print(output)
                if error:
                    print(f"{MS_RED}{error}{MS_RESET}")
                    
                # Display return code if non-zero
                if result.returncode != 0:
                    print(f"{MS_YELLOW}Command completed with return code: {result.returncode}{MS_RESET}")
                
                # Automatically copy to clipboard if enabled and a copy formatter was used
                if " | copy" in command and USE_CLIPBOARD:
                    copy_to_clipboard(output)
                    
            except subprocess.TimeoutExpired:
                print(f"{MS_RED}Command execution timed out after 5 minutes{MS_RESET}")
    except Exception as e:
        print(f"{MS_RED}Error executing command: {e}{MS_RESET}")

def format_last_output():
    """Format the last command output"""
    global last_command_output
    
    if not last_command_output:
        print(f"{MS_YELLOW}No output to format.{MS_RESET}")
        return
    
    print(f"{MS_CYAN}Available formatters:{MS_RESET}")
    print("1. json - Format JSON with indentation")
    print("2. lines - Remove empty lines")
    print("3. truncate - Truncate long output")
    print("4. upper - Convert to uppercase")
    print("5. lower - Convert to lowercase")
    print("6. grep - Filter lines containing pattern")
    
    choice = input(f"{MS_GREEN}Select formatter (1-6):{MS_RESET} ")
    
    try:
        choice = int(choice)
        formatter = list(output_formatters.keys())[choice-1]
        
        if formatter == "grep":
            pattern = input("Enter pattern to grep for: ")
            formatted = format_output(last_command_output, formatter, pattern)
        else:
            formatted = format_output(last_command_output, formatter)
        
        print(f"{MS_CYAN}Formatted output:{MS_RESET}")
        print(formatted)
        
        if USE_CLIPBOARD:
            if input(f"{MS_GREEN}Copy to clipboard? (y/n):{MS_RESET} ").lower() == 'y':
                copy_to_clipboard(formatted)
    except (ValueError, IndexError):
        print(f"{MS_RED}Invalid choice.{MS_RESET}")

def set_config():
    """Change configuration settings"""
    global MAX_HISTORY, CONFIRM_DANGEROUS, STREAM_OUTPUT, MODEL
    global EXPLAIN_COMMANDS, USE_STREAMING_API, USE_TOKEN_CACHE, TOKEN_CACHE_EXPIRY
    global FORMAT_OUTPUT, VERIFY_COMMANDS, USE_CLIPBOARD
    global ALLOW_COMMAND_CHAINING, USE_ASYNC_EXECUTION
    
    print(f"{MS_CYAN}Configuration Settings:{MS_RESET}")
    print(f"1. MAX_HISTORY = {MAX_HISTORY}")
    print(f"2. CONFIRM_DANGEROUS = {CONFIRM_DANGEROUS}")
    print(f"3. STREAM_OUTPUT = {STREAM_OUTPUT}")
    print(f"4. MODEL = {MODEL}")
    print(f"5. EXPLAIN_COMMANDS = {EXPLAIN_COMMANDS}")
    print(f"6. USE_STREAMING_API = {USE_STREAMING_API}")
    print(f"7. USE_TOKEN_CACHE = {USE_TOKEN_CACHE}")
    print(f"8. TOKEN_CACHE_EXPIRY = {TOKEN_CACHE_EXPIRY} days")
    print(f"9. FORMAT_OUTPUT = {FORMAT_OUTPUT}")
    print(f"10. VERIFY_COMMANDS = {VERIFY_COMMANDS}")
    print(f"11. USE_CLIPBOARD = {USE_CLIPBOARD}")
    print(f"12. ALLOW_COMMAND_CHAINING = {ALLOW_COMMAND_CHAINING}")
    print(f"13. USE_ASYNC_EXECUTION = {USE_ASYNC_EXECUTION}")
    print(f"0. Save and exit")
    
    choice = input(f"\n{MS_GREEN}Enter number to change (0-13):{MS_RESET} ")
    
    try:
        choice = int(choice)
        if choice == 1:
            new_val = input(f"Enter new MAX_HISTORY value: ")
            MAX_HISTORY = int(new_val)
        elif choice == 2:
            new_val = input(f"Enable CONFIRM_DANGEROUS? (true/false): ")
            CONFIRM_DANGEROUS = (new_val.lower() == "true")
        elif choice == 3:
            new_val = input(f"Enable STREAM_OUTPUT? (true/false): ")
            STREAM_OUTPUT = (new_val.lower() == "true")
        elif choice == 4:
            new_val = input(f"Enter MODEL (e.g. gemini-2.0-flash): ")
            MODEL = new_val
        elif choice == 5:
            new_val = input(f"Enable EXPLAIN_COMMANDS? (true/false): ")
            EXPLAIN_COMMANDS = (new_val.lower() == "true")
        elif choice == 6:
            new_val = input(f"Enable USE_STREAMING_API? (true/false): ")
            USE_STREAMING_API = (new_val.lower() == "true")
        elif choice == 7:
            new_val = input(f"Enable USE_TOKEN_CACHE? (true/false): ")
            USE_TOKEN_CACHE = (new_val.lower() == "true")
        elif choice == 8:
            new_val = input(f"Enter TOKEN_CACHE_EXPIRY in days: ")
            TOKEN_CACHE_EXPIRY = int(new_val)
        elif choice == 9:
            new_val = input(f"Enable FORMAT_OUTPUT? (true/false): ")
            FORMAT_OUTPUT = (new_val.lower() == "true")
        elif choice == 10:
            new_val = input(f"Enable VERIFY_COMMANDS? (true/false): ")
            VERIFY_COMMANDS = (new_val.lower() == "true")
        elif choice == 11:
            new_val = input(f"Enable USE_CLIPBOARD? (true/false): ")
            USE_CLIPBOARD = (new_val.lower() == "true")
        elif choice == 12:
            new_val = input(f"Enable ALLOW_COMMAND_CHAINING? (true/false): ")
            ALLOW_COMMAND_CHAINING = (new_val.lower() == "true")
        elif choice == 13:
            new_val = input(f"Enable USE_ASYNC_EXECUTION? (true/false): ")
            USE_ASYNC_EXECUTION = (new_val.lower() == "true")
        elif choice == 0:
            save_config()
        else:
            print(f"{MS_RED}Invalid choice.{MS_RESET}")
    except ValueError:
        print(f"{MS_RED}Invalid input. Please enter a number.{MS_RESET}")

def manage_templates():
    """Manage command templates"""
    global templates
    
    while True:
        print(f"\n{MS_CYAN}Command Templates:{MS_RESET}")
        if not templates:
            print("No templates defined.")
        else:
            for name, description in templates.items():
                print(f"  {MS_GREEN}!{name}{MS_RESET} - {description}")
        
        print(f"\n{MS_CYAN}Options:{MS_RESET}")
        print(f"1. Add template")
        print(f"2. Remove template")
        print(f"3. Run template")
        print(f"0. Back to main menu")
        
        choice = input(f"\n{MS_GREEN}Enter choice (0-3):{MS_RESET} ")
        
        try:
            choice = int(choice)
            if choice == 1:
                name = input("Enter template name (without !): ")
                if not name or name.isspace():
                    print(f"{MS_RED}Invalid name.{MS_RESET}")
                    continue
                    
                description = input("Enter template description: ")
                templates[name] = description
                save_templates()
                print(f"{MS_GREEN}Template added.{MS_RESET}")
                
            elif choice == 2:
                name = input("Enter template name to remove: ")
                if name in templates:
                    del templates[name]
                    save_templates()
                    print(f"{MS_GREEN}Template removed.{MS_RESET}")
                else:
                    print(f"{MS_RED}Template not found.{MS_RESET}")
                    
            elif choice == 3:
                name = input("Enter template name to run: ")
                if name in templates:
                    return run_template(name)
                else:
                    print(f"{MS_RED}Template not found.{MS_RESET}")
                    
            elif choice == 0:
                return
                
        except ValueError:
            print(f"{MS_RED}Invalid choice.{MS_RESET}")

def run_template(name):
    """Run a predefined template"""
    global templates
    
    if name not in templates:
        print(f"{MS_RED}Template '{name}' not found.{MS_RESET}")
        return
    
    description = templates[name]
    print(f"{MS_CYAN}Running template: {name} - {description}{MS_RESET}")
    
    # Get AI response for the template description
    commands = get_ai_response(description)
    
    # Execute each command
    if commands:
        for command in commands.splitlines():
            if command.strip():
                execute_command(command.strip())
    else:
        print(f"{MS_RED}Couldn't generate commands for template.{MS_RESET}")

def manage_command_groups():
    """Manage command groups"""
    global command_groups
    
    while True:
        print(f"\n{MS_CYAN}Command Groups:{MS_RESET}")
        if not command_groups:
            print("No command groups defined.")
        else:
            for category, commands in command_groups.items():
                print(f"  {MS_GREEN}{category}{MS_RESET} - {', '.join(commands[:3])}...")
        
        print(f"\n{MS_CYAN}Options:{MS_RESET}")
        print(f"1. View group details")
        print(f"2. Add group")
        print(f"3. Remove group")
        print(f"4. Add command to group")
        print(f"5. Remove command from group")
        print(f"0. Back to main menu")
        
        choice = input(f"\n{MS_GREEN}Enter choice (0-5):{MS_RESET} ")
        
        try:
            choice = int(choice)
            if choice == 1:
                group = input("Enter group name to view: ")
                if group in command_groups:
                    print(f"\n{MS_CYAN}Commands in '{group}' group:{MS_RESET}")
                    for cmd in command_groups[group]:
                        print(f"  {cmd}")
                else:
                    print(f"{MS_RED}Group not found.{MS_RESET}")
                    
            elif choice == 2:
                group = input("Enter new group name: ")
                if group in command_groups:
                    print(f"{MS_RED}Group already exists.{MS_RESET}")
                else:
                    command_groups[group] = []
                    save_command_groups()
                    print(f"{MS_GREEN}Group added.{MS_RESET}")
                    
            elif choice == 3:
                group = input("Enter group name to remove: ")
                if group in command_groups:
                    del command_groups[group]
                    save_command_groups()
                    print(f"{MS_GREEN}Group removed.{MS_RESET}")
                else:
                    print(f"{MS_RED}Group not found.{MS_RESET}")
                    
            elif choice == 4:
                group = input("Enter group name: ")
                if group in command_groups:
                    cmd = input("Enter command to add: ")
                    if cmd not in command_groups[group]:
                        command_groups[group].append(cmd)
                        save_command_groups()
                        print(f"{MS_GREEN}Command added to group.{MS_RESET}")
                    else:
                        print(f"{MS_RED}Command already in group.{MS_RESET}")
                else:
                    print(f"{MS_RED}Group not found.{MS_RESET}")
                    
            elif choice == 5:
                group = input("Enter group name: ")
                if group in command_groups:
                    cmd = input("Enter command to remove: ")
                    if cmd in command_groups[group]:
                        command_groups[group].remove(cmd)
                        save_command_groups()
                        print(f"{MS_GREEN}Command removed from group.{MS_RESET}")
                    else:
                        print(f"{MS_RED}Command not in group.{MS_RESET}")
                else:
                    print(f"{MS_RED}Group not found.{MS_RESET}")
                    
            elif choice == 0:
                return
                
        except ValueError:
            print(f"{MS_RED}Invalid choice.{MS_RESET}")

def process_builtin_command(input_cmd):
    """Process built-in commands"""
    global templates, VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, USE_ASYNC_EXECUTION
    
    # Check for async execution
    if input_cmd.startswith("async "):
        if USE_ASYNC_EXECUTION:
            async_cmd = input_cmd[5:].strip()
            execute_command(async_cmd, is_async=True)
        else:
            print(f"{MS_RED}Async execution is disabled.{MS_RESET}")
        return True
    
    # Process job management commands
    if input_cmd == "jobs":
        show_jobs()
        return True
    elif input_cmd.startswith("kill "):
        job_id = input_cmd[5:].strip()
        kill_job(job_id)
        return True
    
    # Check if it's a template command (starts with !)
    if input_cmd.startswith("!"):
        template_name = input_cmd[1:]
        if template_name in templates:
            run_template(template_name)
            return True
        else:
            print(f"{MS_RED}Template '{template_name}' not found.{MS_RESET}")
            return True
    
    if input_cmd == "help":
        show_help()
        return True
    elif input_cmd == "chain":
        ALLOW_COMMAND_CHAINING = not ALLOW_COMMAND_CHAINING
        print(f"{MS_GREEN}Command chaining {'enabled' if ALLOW_COMMAND_CHAINING else 'disabled'}.{MS_RESET}")
        return True
    elif input_cmd == "setup":
        run_setup_wizard()
        return True
    elif input_cmd == "templates":
        manage_templates()
        return True
    elif input_cmd == "groups":
        manage_command_groups()
        return True
    elif input_cmd == "format":
        format_last_output()
        return True
    elif input_cmd == "copy":
        if last_command_output:
            copy_to_clipboard(last_command_output)
        else:
            print(f"{MS_YELLOW}No output to copy.{MS_RESET}")
        return True
    elif input_cmd == "verify":
        VERIFY_COMMANDS = not VERIFY_COMMANDS
        print(f"{MS_GREEN}Command verification {'enabled' if VERIFY_COMMANDS else 'disabled'}.{MS_RESET}")
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
        print(f"EXPLAIN_COMMANDS={EXPLAIN_COMMANDS}")
        print(f"USE_STREAMING_API={USE_STREAMING_API}")
        print(f"USE_TOKEN_CACHE={USE_TOKEN_CACHE}")
        print(f"TOKEN_CACHE_EXPIRY={TOKEN_CACHE_EXPIRY}")
        print(f"FORMAT_OUTPUT={FORMAT_OUTPUT}")
        print(f"VERIFY_COMMANDS={VERIFY_COMMANDS}")
        print(f"USE_CLIPBOARD={USE_CLIPBOARD}")
        print(f"ALLOW_COMMAND_CHAINING={ALLOW_COMMAND_CHAINING}")
        print(f"USE_ASYNC_EXECUTION={USE_ASYNC_EXECUTION}")
        return True
    elif input_cmd == "set":
        set_config()
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

def run_setup_wizard():
    """Run the setup wizard for first-time configuration"""
    global API_KEY, MODEL, EXPLAIN_COMMANDS, USE_STREAMING_API, USE_TOKEN_CACHE
    global FORMAT_OUTPUT, VERIFY_COMMANDS, USE_CLIPBOARD, ALLOW_COMMAND_CHAINING, USE_ASYNC_EXECUTION
    global API_ENDPOINT, API_VERSION
    
    print(f"{MS_CYAN}Welcome to Terminal AI Assistant Lite Setup Wizard!{MS_RESET}")
    print(f"This will help you configure the assistant for first use.\n")
    
    # API Key
    if not API_KEY:
        print(f"{MS_YELLOW}No API key found.{MS_RESET}")
        new_key = input("Enter your Gemini API key: ")
        if new_key.strip():
            API_KEY = new_key
            
            # Save to .env file
            with open('.env', 'w') as f:
                f.write(f"GEMINI_API_KEY={new_key}\n")
            print(f"{MS_GREEN}API key saved.{MS_RESET}")
    
    # API Endpoint Configuration
    print(f"\n{MS_CYAN}API Configuration:{MS_RESET}")
    new_endpoint = input(f"Enter Gemini API endpoint [{API_ENDPOINT}]: ")
    if new_endpoint.strip():
        API_ENDPOINT = new_endpoint
    
    new_version = input(f"Enter API version [{API_VERSION}]: ")
    if new_version.strip():
        API_VERSION = new_version
        
    # Model selection
    print(f"\n{MS_CYAN}Select AI model:{MS_RESET}")
    print(f"1. gemini-1.5-flash (faster)")
    print(f"2. gemini-1.5-pro (more capable)")
    print(f"3. gemini-1.0-pro (older version)")
    print(f"4. gemini-pro (older version)")
    print(f"5. Keep current: {MODEL}")
    
    choice = input(f"Enter choice (1-5): ")
    try:
        choice = int(choice)
        if choice == 1:
            MODEL = "gemini-1.5-flash"
        elif choice == 2:
            MODEL = "gemini-1.5-pro"
        elif choice == 3:
            MODEL = "gemini-1.0-pro"
        elif choice == 4:
            MODEL = "gemini-pro"
        # Choice 5 keeps current model
    except ValueError:
        print(f"{MS_YELLOW}Invalid choice. Keeping current model.{MS_RESET}")
    
    # Features
    print(f"\n{MS_CYAN}Enable/Disable Features:{MS_RESET}")
    
    choice = input(f"Explain commands before execution? (y/n): ")
    EXPLAIN_COMMANDS = choice.lower() == 'y'
    
    choice = input(f"Use streaming API for faster responses? (y/n): ")
    USE_STREAMING_API = choice.lower() == 'y'
    
    choice = input(f"Cache responses to save API quota? (y/n): ")
    USE_TOKEN_CACHE = choice.lower() == 'y'
    
    choice = input(f"Format command output when possible? (y/n): ")
    FORMAT_OUTPUT = choice.lower() == 'y'
    
    choice = input(f"Verify commands before execution? (y/n): ")
    VERIFY_COMMANDS = choice.lower() == 'y'
    
    choice = input(f"Enable clipboard integration? (y/n): ")
    USE_CLIPBOARD = choice.lower() == 'y'
    
    choice = input(f"Allow command chaining (&&, ||)? (y/n): ")
    ALLOW_COMMAND_CHAINING = choice.lower() == 'y'
    
    choice = input(f"Enable async command execution? (y/n): ")
    USE_ASYNC_EXECUTION = choice.lower() == 'y'
    
    # Save configuration
    save_config()
    print(f"\n{MS_GREEN}Setup complete! Configuration saved.{MS_RESET}")

def get_ai_response(task):
    """Call Gemini API to get command suggestions"""
    global API_KEY, USE_STREAMING_API
    
    if not GENAI_AVAILABLE:
        print(f"{MS_YELLOW}Google Generative AI library not available. Install with: pip install google-generativeai{MS_RESET}")
        print(f"{MS_YELLOW}Falling back to curl-based API calls.{MS_RESET}")
        # Fall back to curl-based methods
        if USE_STREAMING_API:
            commands = stream_ai_response_curl(task)
        else:
            commands = call_ai_api_curl(task)
    else:
        # Use the Python library
        if USE_STREAMING_API:
            commands = stream_ai_response(task)
        else:
            commands = call_ai_api(task)
    
    return commands

def call_ai_api(task):
    """Non-streaming API call to Gemini using Python library"""
    global API_KEY, MODEL
    
    if not API_KEY:
        print(f"{MS_RED}API key not found in .env file. Please set GEMINI_API_KEY in your .env file.{MS_RESET}")
        return ""
    
    current_dir = os.getcwd()
    os_type = "Windows" if os.name == "nt" else "Unix/Linux"
    
    # Configure the genai library
    genai.configure(api_key=API_KEY)
    
    # Prepare the prompt with OS-specific context
    prompt = f"""You are a terminal command expert. Generate executable commands for the following task.
    
    TASK: {task}
    CURRENT DIRECTORY: {current_dir}
    OPERATING SYSTEM: {os_type}
    
    Respond ONLY with the exact commands to execute, one per line.
    Do not include explanations, markdown formatting, or any text that is not meant to be executed.
    Ensure each command is complete and executable as-is.
    If the request cannot be satisfied with a command, respond with a single line explaining why."""
    
    print(f"{MS_YELLOW}Thinking...{MS_RESET}", file=sys.stderr)
    
    try:
        # Create a generative model instance
        model = genai.GenerativeModel(MODEL)
        
        # Configure generation parameters
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        
        # Generate content
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        if not response or not hasattr(response, 'text'):
            print(f"{MS_RED}Empty response from API.{MS_RESET}", file=sys.stderr)
            return ""
        
        # Get the commands from the response
        commands = response.text
        
        # Clean up the response
        commands = "\n".join(line.strip() for line in commands.splitlines() if line.strip())
        
        if not commands:
            print(f"{MS_YELLOW}API returned empty command set.{MS_RESET}", file=sys.stderr)
            
        return commands
            
    except Exception as e:
        print(f"{MS_RED}Error calling API: {e}{MS_RESET}", file=sys.stderr)
        return ""

def stream_ai_response(task):
    """Streaming API call to Gemini using Python library"""
    global API_KEY, MODEL
    
    if not API_KEY:
        print(f"{MS_RED}API key not found in .env file. Please set GEMINI_API_KEY in your .env file.{MS_RESET}")
        return ""
    
    current_dir = os.getcwd()
    os_type = "Windows" if os.name == "nt" else "Unix/Linux"
    
    # Configure the genai library
    genai.configure(api_key=API_KEY)
    
    # Prepare the prompt with OS-specific context
    prompt = f"""You are a terminal command expert. Generate executable commands for the following task.
    
    TASK: {task}
    CURRENT DIRECTORY: {current_dir}
    OPERATING SYSTEM: {os_type}
    
    Respond ONLY with the exact commands to execute, one per line.
    Do not include explanations, markdown formatting, or any text that is not meant to be executed.
    Ensure each command is complete and executable as-is.
    If the request cannot be satisfied with a command, respond with a single line explaining why."""
    
    print(f"{MS_YELLOW}Thinking...{MS_RESET}", file=sys.stderr)
    
    try:
        # Create a generative model instance
        model = genai.GenerativeModel(MODEL)
        
        # Configure generation parameters
        generation_config = {
            "temperature": 0.2,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        
        # Create a variable to collect all text
        all_text = ""
        print(f"{MS_CYAN}Commands (streaming):{MS_RESET}", file=sys.stderr)
        
        # Start time for timeout tracking
        start_time = time.time()
        timeout = 60  # 60 seconds timeout
        
        # Generate content with streaming
        for chunk in model.generate_content(
            prompt,
            generation_config=generation_config,
            stream=True
        ):
            # Check if we've exceeded timeout
            if time.time() - start_time > timeout:
                print(f"\n{MS_RED}Streaming API request timed out after {timeout} seconds{MS_RESET}", file=sys.stderr)
                break
                
            if not hasattr(chunk, 'text') or not chunk.text:
                continue
                
            # Get the text from the chunk
            text = chunk.text
            all_text += text
            print(text, end="", flush=True, file=sys.stderr)
            
        print("", file=sys.stderr)  # New line
        
        # Process complete text to extract commands
        commands = []
        for line in all_text.splitlines():
            line = line.strip()
            if line:  # Only add non-empty lines
                commands.append(line)
                
        return "\n".join(commands)
        
    except Exception as e:
        print(f"{MS_RED}Error in streaming API call: {e}{MS_RESET}", file=sys.stderr)
        return ""

# Rename original functions to use as fallbacks
def call_ai_api_curl(task):
    """Non-streaming API call to Gemini using curl"""
    global API_KEY, MODEL, API_ENDPOINT, API_VERSION
    
    if not API_KEY:
        print(f"{MS_RED}API key not found in .env file. Please set GEMINI_API_KEY in your .env file.{MS_RESET}")
        return ""
    
    current_dir = os.getcwd()
    os_type = "Windows" if os.name == "nt" else "Unix/Linux"
    
    # Prepare the prompt with OS-specific context
    prompt = f"""You are a terminal command expert. Generate executable commands for the following task.
    
    TASK: {task}
    CURRENT DIRECTORY: {current_dir}
    OPERATING SYSTEM: {os_type}
    
    Respond ONLY with the exact commands to execute, one per line.
    Do not include explanations, markdown formatting, or any text that is not meant to be executed.
    Ensure each command is complete and executable as-is.
    If the request cannot be satisfied with a command, respond with a single line explaining why."""
    
    print(f"{MS_YELLOW}Thinking...{MS_RESET}", file=sys.stderr)
    
    try:
        # Construct API request
        curl_command = [
            "curl", "-s", "-X", "POST",
            f"{API_ENDPOINT}/{API_VERSION}/models/{MODEL}:generateContent?key={API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 1024
                }
            })
        ]
        
        # Call API with timeout
        result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
        response = result.stdout
        
        # Check for errors
        if not response or response.isspace():
            print(f"{MS_RED}Empty response from API. Check your internet connection.{MS_RESET}", file=sys.stderr)
            return ""
            
        if "error" in response:
            try:
                error_data = json.loads(response)
                error_message = error_data.get("error", {}).get("message", "Unknown error")
                print(f"{MS_RED}API Error: {error_message}{MS_RESET}", file=sys.stderr)
            except json.JSONDecodeError:
                print(f"{MS_RED}API Error. Unable to parse error response.{MS_RESET}", file=sys.stderr)
            except Exception as e:
                print(f"{MS_RED}API Error: {str(e)}{MS_RESET}", file=sys.stderr)
            return ""
        
        # Parse response
        try:
            response_data = json.loads(response)
            
            # Check if we have candidates
            if not response_data.get("candidates", []):
                print(f"{MS_RED}No candidates in API response.{MS_RESET}", file=sys.stderr)
                return ""
                
            # Check for content
            candidate = response_data["candidates"][0]
            if not candidate.get("content", {}).get("parts", []):
                print(f"{MS_RED}No content parts in API response.{MS_RESET}", file=sys.stderr)
                return ""
                
            # Extract text
            commands = candidate["content"]["parts"][0].get("text", "")
            
            # Clean up the response
            commands = "\n".join(line.strip() for line in commands.splitlines() if line.strip())
            
            if not commands:
                print(f"{MS_YELLOW}API returned empty command set.{MS_RESET}", file=sys.stderr)
                
            return commands
            
        except json.JSONDecodeError:
            print(f"{MS_RED}Failed to parse API response as JSON.{MS_RESET}", file=sys.stderr)
            return ""
        except KeyError as e:
            print(f"{MS_RED}Missing expected field in API response: {e}{MS_RESET}", file=sys.stderr)
            return ""
        except Exception as e:
            print(f"{MS_RED}Failed to extract commands from API response: {e}{MS_RESET}", file=sys.stderr)
            return ""
            
    except subprocess.TimeoutExpired:
        print(f"{MS_RED}API request timed out. Please try again.{MS_RESET}", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"{MS_RED}Error calling API: {e}{MS_RESET}", file=sys.stderr)
        return ""

def stream_ai_response_curl(task):
    """Streaming API call to Gemini using curl"""
    global API_KEY, MODEL, API_ENDPOINT, API_VERSION
    
    if not API_KEY:
        print(f"{MS_RED}API key not found in .env file. Please set GEMINI_API_KEY in your .env file.{MS_RESET}")
        return ""
    
    current_dir = os.getcwd()
    os_type = "Windows" if os.name == "nt" else "Unix/Linux"
    
    # Prepare the prompt with OS-specific context
    prompt = f"""You are a terminal command expert. Generate executable commands for the following task.
    
    TASK: {task}
    CURRENT DIRECTORY: {current_dir}
    OPERATING SYSTEM: {os_type}
    
    Respond ONLY with the exact commands to execute, one per line.
    Do not include explanations, markdown formatting, or any text that is not meant to be executed.
    Ensure each command is complete and executable as-is.
    If the request cannot be satisfied with a command, respond with a single line explaining why."""
    
    print(f"{MS_YELLOW}Thinking...{MS_RESET}", file=sys.stderr)
    
    try:
        # Construct API request for streaming
        curl_command = [
            "curl", "-s", "--no-buffer", "-X", "POST",
            f"{API_ENDPOINT}/{API_VERSION}/models/{MODEL}:streamGenerateContent?key={API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "contents": [{
                    "parts": [{
                        "text": prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 1024
                }
            })
        ]
        
        # Start process with timeout management
        process = subprocess.Popen(curl_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Collect all response text
        all_text = ""
        print(f"{MS_CYAN}Commands (streaming):{MS_RESET}", file=sys.stderr)
        
        # Set a timeout for the entire streaming process
        start_time = time.time()
        timeout = 60  # 60 seconds timeout
        
        while True:
            # Check if we've exceeded timeout
            if time.time() - start_time > timeout:
                process.terminate()
                print(f"\n{MS_RED}Streaming API request timed out after {timeout} seconds{MS_RESET}", file=sys.stderr)
                break
                
            # Read a line with timeout
            line_read = False
            for _ in range(10):  # Try reading for 1 second (10 x 0.1s)
                if process.stdout.readable():
                    chunk = process.stdout.readline()
                    line_read = bool(chunk)
                    break
                time.sleep(0.1)
            
            # If no line could be read and process finished
            if not line_read and process.poll() is not None:
                break
                
            # Skip empty lines
            if not chunk or not chunk.strip() or chunk.strip() == "data: [DONE]":
                continue
                
            # Process the chunk
            try:
                if chunk.startswith("data: "):
                    chunk = chunk[6:]  # Remove "data: " prefix
                    
                chunk_data = json.loads(chunk)
                if "candidates" in chunk_data and chunk_data["candidates"] and "content" in chunk_data["candidates"][0]:
                    text_parts = chunk_data["candidates"][0]["content"].get("parts", [])
                    for part in text_parts:
                        if "text" in part:
                            command_part = part["text"]
                            all_text += command_part
                            print(command_part, end="", flush=True, file=sys.stderr)
            except json.JSONDecodeError:
                continue
            except Exception as e:
                print(f"\n{MS_RED}Error processing streaming chunk: {e}{MS_RESET}", file=sys.stderr)
                
        # Check for errors on stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            print(f"{MS_RED}API Error: {stderr_output}{MS_RESET}", file=sys.stderr)
        
        # Make sure process is terminated
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=1)
            
        print("", file=sys.stderr)  # New line
        
        # Process complete text to extract commands
        commands = []
        for line in all_text.splitlines():
            line = line.strip()
            if line:  # Only add non-empty lines
                commands.append(line)
                
        return "\n".join(commands)
        
    except Exception as e:
        print(f"{MS_RED}Error in streaming API call: {e}{MS_RESET}", file=sys.stderr)
        return ""

async def run_command_async(command_id, command):
    """Run a command asynchronously"""
    print(f"{MS_GREEN}Starting async job #{command_id}: {command}{MS_RESET}")
    
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            executable="/bin/bash" if os.name != "nt" else None
        )
        
        # Store process for later reference
        background_processes[command_id] = {
            "process": process,
            "command": command,
            "start_time": datetime.datetime.now()
        }
        
        stdout, stderr = await process.communicate()
        
        # Once completed, update the process info
        if command_id in background_processes:
            background_processes[command_id]["completed"] = True
            background_processes[command_id]["return_code"] = process.returncode
            background_processes[command_id]["stdout"] = stdout.decode('utf-8', errors='replace')
            background_processes[command_id]["stderr"] = stderr.decode('utf-8', errors='replace')
            background_processes[command_id]["end_time"] = datetime.datetime.now()
            
            print(f"{MS_GREEN}Async job #{command_id} completed with return code {process.returncode}{MS_RESET}")
    except Exception as e:
        print(f"{MS_RED}Error in async job #{command_id}: {e}{MS_RESET}")
        if command_id in background_processes:
            background_processes[command_id]["completed"] = True
            background_processes[command_id]["error"] = str(e)
            background_processes[command_id]["end_time"] = datetime.datetime.now()

def start_async_command(command):
    """Start a command asynchronously using asyncio"""
    command_id = 1
    # Find next available ID
    while command_id in background_processes:
        command_id += 1
    
    # Create and start a task for the command
    loop = asyncio.new_event_loop()
    
    def run_in_thread(loop, command_id, command):
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_command_async(command_id, command))
        loop.close()
    
    thread = threading.Thread(target=run_in_thread, args=(loop, command_id, command))
    thread.daemon = True
    thread.start()
    
    return command_id

def show_jobs():
    """Show status of background jobs"""
    if not background_processes:
        print(f"{MS_YELLOW}No background jobs.{MS_RESET}")
        return
    
    print(f"{MS_CYAN}Background Jobs:{MS_RESET}")
    for job_id, job_info in background_processes.items():
        status = "Completed" if job_info.get("completed", False) else "Running"
        runtime = ""
        
        if job_info.get("completed", False):
            duration = job_info.get("end_time") - job_info.get("start_time")
            runtime = f"({duration.total_seconds():.2f}s)"
        else:
            duration = datetime.datetime.now() - job_info.get("start_time")
            runtime = f"({duration.total_seconds():.2f}s and counting)"
        
        print(f"Job #{job_id}: {status} {runtime}")
        print(f"  Command: {job_info.get('command')}")
        
        if job_info.get("completed", False):
            if "return_code" in job_info:
                print(f"  Return code: {job_info.get('return_code')}")
            if "error" in job_info:
                print(f"  Error: {job_info.get('error')}")
            
            # Show truncated output if available
            if "stdout" in job_info and job_info["stdout"].strip():
                stdout = job_info["stdout"].strip()
                if len(stdout) > 100:
                    stdout = stdout[:100] + "..."
                print(f"  Output: {stdout}")
        print("")

def kill_job(job_id):
    """Kill a background job"""
    try:
        job_id = int(job_id)
        if job_id not in background_processes:
            print(f"{MS_RED}Job #{job_id} not found.{MS_RESET}")
            return
        
        job_info = background_processes[job_id]
        if job_info.get("completed", False):
            print(f"{MS_YELLOW}Job #{job_id} already completed.{MS_RESET}")
            return
        
        process = job_info.get("process")
        if process:
            try:
                process.kill()
                print(f"{MS_GREEN}Job #{job_id} terminated.{MS_RESET}")
                job_info["completed"] = True
                job_info["return_code"] = -1
                job_info["end_time"] = datetime.datetime.now()
            except Exception as e:
                print(f"{MS_RED}Error terminating job #{job_id}: {e}{MS_RESET}")
    except ValueError:
        print(f"{MS_RED}Invalid job ID.{MS_RESET}")

def get_user_input_with_history():
    """Get user input with history navigation support"""
    global HISTORY_FILE
    
    # For Windows PowerShell, use a simpler prompt
    if os.name == "nt":
        return input("> ")
    
    # If prompt_toolkit is available, use it for enhanced history
    if PROMPT_TOOLKIT_AVAILABLE:
        try:
            # Create a session with history from file
            session = PromptSession(history=FileHistory(HISTORY_FILE))
            # Use a simple prompt for better compatibility
            return session.prompt("> ")
        except Exception as e:
            # Fallback on error
            print(f"{MS_YELLOW}Error using prompt_toolkit: {e}. Falling back to basic input.{MS_RESET}")
    
    # For other systems, use basic input
    return input("> ")

def execute_command_chain(command_chain):
    """Execute a chain of commands connected by && or ||"""
    global ALLOW_COMMAND_CHAINING
    
    if not ALLOW_COMMAND_CHAINING:
        print(f"{MS_RED}Command chaining is disabled. Use 'chain' to enable it.{MS_RESET}")
        return execute_command(command_chain)
    
    # Tokenize the command chain respecting quotes
    commands = []
    current_command = ""
    in_quotes = False
    quote_char = None
    
    i = 0
    while i < len(command_chain):
        char = command_chain[i]
        
        # Handle quotes
        if char in ["'", "\""]:
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
            current_command += char
        
        # Handle && and || operators, but only when not in quotes
        elif not in_quotes and i < len(command_chain) - 1:
            if char == "&" and command_chain[i+1] == "&":
                if current_command.strip():
                    commands.append((current_command.strip(), "AND"))
                current_command = ""
                i += 1  # Skip the next &
            elif char == "|" and command_chain[i+1] == "|":
                if current_command.strip():
                    commands.append((current_command.strip(), "OR"))
                current_command = ""
                i += 1  # Skip the next |
            else:
                current_command += char
        else:
            current_command += char
        
        i += 1
    
    # Add the last command if any
    if current_command.strip():
        commands.append((current_command.strip(), None))
    
    # Limit chain length
    if len(commands) > 10:
        print(f"{MS_RED}Warning: Command chain too long (max 10 commands). Truncating.{MS_RESET}")
        commands = commands[:10]
    
    # Execute commands in chain
    last_success = True
    for cmd, operator in commands:
        if (operator == "AND" and not last_success) or (operator == "OR" and last_success):
            # Skip this command based on chain logic
            if operator == "AND":
                print(f"{MS_YELLOW}Skipping command due to previous failure in &&-chain: {cmd}{MS_RESET}")
            else:
                print(f"{MS_YELLOW}Skipping command due to previous success in ||-chain: {cmd}{MS_RESET}")
            continue
        
        # Execute the command with timeout
        try:
            # Use subprocess.run with timeout
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)  # 5 minute timeout
            success = result.returncode == 0
            
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(f"{MS_RED}{result.stderr}{MS_RESET}")
            
            last_success = success
        except subprocess.TimeoutExpired:
            print(f"{MS_RED}Command timed out after 5 minutes: {cmd}{MS_RESET}")
            last_success = False
        except Exception as e:
            print(f"{MS_RED}Error executing command: {e}{MS_RESET}")
            last_success = False

def main():
    """Main function"""
    # Initialization
    check_dependencies()
    load_config()
    ensure_history_file()
    load_templates()
    load_command_groups()
    
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
        try:
            print("")
            user_input = get_user_input_with_history()
            
            # Check if it's a built-in command
            if process_builtin_command(user_input):
                continue
            
            # Check if it's a command chain
            if ALLOW_COMMAND_CHAINING and ("&&" in user_input or "||" in user_input):
                execute_command_chain(user_input)
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
        except KeyboardInterrupt:
            print(f"\n{MS_YELLOW}Operation interrupted. Press Ctrl+C again to exit or Enter to continue.{MS_RESET}")
            try:
                if input() == "":
                    continue
            except KeyboardInterrupt:
                print(f"\n{MS_GREEN}Goodbye!{MS_RESET}")
                sys.exit(0)
        except Exception as e:
            print(f"{MS_RED}An error occurred: {e}{MS_RESET}")
            print("Please try again.")

if __name__ == "__main__":
    main() 
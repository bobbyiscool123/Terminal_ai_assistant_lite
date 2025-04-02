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
from collections import OrderedDict
try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    from colorama import init, Fore, Style
    # Initialize colorama with compatibility settings
    init(autoreset=False)

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
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

# Set up rich console if available
if RICH_AVAILABLE:
    custom_theme = Theme({
        "info": "cyan",
        "warning": "yellow",
        "error": "red",
        "success": "green",
        "prompt": "yellow bold"
    })
    console = Console(theme=custom_theme)

# Microsoft theme colors for compatibility with existing code
if RICH_AVAILABLE:
    # Define functions to emulate colorama with rich
    def ms_print(text, style=None):
        console.print(text, style=style)
        
    MS_BLUE = "blue"
    MS_CYAN = "cyan"
    MS_GREEN = "green"
    MS_YELLOW = "yellow"
    MS_RED = "red"
    MS_MAGENTA = "magenta"
    MS_WHITE = "white"
    MS_RESET = ""
    MS_BRIGHT = "bold "
    MS_DIM = "dim "
else:
    # Try to detect if terminal supports colors
    import os
    COLORS_SUPPORTED = os.environ.get('TERM') is not None
    
    # Use colorama directly if colors are supported
    if COLORS_SUPPORTED:
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
    else:
        # Define empty color codes if colors are not supported
        MS_BLUE = ""
        MS_CYAN = ""
        MS_GREEN = ""
        MS_YELLOW = ""
        MS_RED = ""
        MS_MAGENTA = ""
        MS_WHITE = ""
        MS_RESET = ""
        MS_BRIGHT = ""
        MS_DIM = ""

# Register color names to make them easier to match in safe_print
COLOR_NAMES = {
    "MS_BLUE": MS_BLUE,
    "MS_CYAN": MS_CYAN,
    "MS_GREEN": MS_GREEN, 
    "MS_YELLOW": MS_YELLOW,
    "MS_RED": MS_RED,
    "MS_MAGENTA": MS_MAGENTA,
    "MS_WHITE": MS_WHITE,
    "MS_RESET": MS_RESET,
    "MS_BRIGHT": MS_BRIGHT,
    "MS_DIM": MS_DIM
}

# Helper function to safely print colored text
def print_colored(text, color_code=None, end="\n", flush=False):
    """Safely print colored text, falling back to plain text if colors aren't supported
    
    Args:
        text: Text to print
        color_code: Color code to use (MS_CYAN, MS_GREEN, etc.) or None for plain text
        end: String appended after the last value, default a newline
        flush: Whether to forcibly flush the stream
    """
    if RICH_AVAILABLE:
        # Convert MS_* color codes to rich style names
        style = None
        if color_code == MS_CYAN:
            style = "cyan"
        elif color_code == MS_GREEN:
            style = "green"
        elif color_code == MS_YELLOW:
            style = "yellow"
        elif color_code == MS_RED:
            style = "red"
        elif color_code == MS_BLUE:
            style = "blue"
        elif color_code == MS_MAGENTA:
            style = "magenta"
        elif color_code == MS_WHITE:
            style = "white"
            
        console.print(text, style=style, end=end)
    elif not RICH_AVAILABLE and COLORS_SUPPORTED:
        # Use colorama
        if color_code:
            print(f"{color_code}{text}{MS_RESET}", end=end, flush=flush)
        else:
            print(text, end=end, flush=flush)
    else:
        # No color support, just print plain text
        # Clean up any potential color name prefixes from the text
        color_names = ["cyan", "green", "yellow", "red", "blue", "magenta", "white"]
        for color_name in color_names:
            if text.lower().startswith(color_name):
                text = text[len(color_name):]
                break
        print(text, end=end, flush=flush)

# Override the print function to handle color codes
import builtins
original_print = builtins.print

def safe_print(*args, **kwargs):
    """Drop-in replacement for print that handles color-formatted strings"""
    # Check if we have a single string argument that might contain color codes
    if len(args) == 1 and isinstance(args[0], str):
        text = args[0]
        
        # Common pattern: "{MS_COLOR}Text{MS_RESET}"
        if text.startswith("{MS_"):
            # Find color code
            color_end = text.find("}")
            if color_end > 0:
                color_var = text[1:color_end]  # Extract "MS_COLOR"
                
                # Extract the content between the color and reset
                content_start = color_end + 1
                reset_start = text.find("{MS_RESET}")
                
                if reset_start > content_start:
                    # We have a proper "{MS_COLOR}Text{MS_RESET}" pattern
                    content = text[content_start:reset_start]
                else:
                    # Just content with color: "{MS_COLOR}Text"
                    content = text[content_start:]
                
                # Get the actual color code value
                if color_var in COLOR_NAMES:
                    color_code = COLOR_NAMES[color_var]
                    print_colored(content, color_code, **kwargs)
                    return
    
    # Handle cases with literal color label prefixes (e.g. "cyanExecuting:")
    if len(args) == 1 and isinstance(args[0], str):
        text = args[0]
        for color_name in ["cyan", "green", "yellow", "red", "blue", "magenta", "white"]:
            if text.lower().startswith(color_name):
                clean_text = text[len(color_name):]
                color_code = COLOR_NAMES.get(f"MS_{color_name.upper()}", "")
                print_colored(clean_text, color_code, **kwargs)
                return
    
    # Fall back to original print for all other cases
    original_print(*args, **kwargs)

# Replace the built-in print with our version
builtins.print = safe_print

# Helper function for styled printing
def print_styled(text, style=None):
    """Print text with styling using rich if available, otherwise use colorama"""
    if RICH_AVAILABLE:
        console.print(text, style=style)
    else:
        # Map rich style names to colorama constants
        style_map = {
            "cyan": MS_CYAN,
            "green": MS_GREEN,
            "yellow": MS_YELLOW,
            "red": MS_RED,
            "blue": MS_BLUE,
            "magenta": MS_MAGENTA,
            "white": MS_WHITE,
            "bold": MS_BRIGHT,
            "dim": MS_DIM
        }
        
        # Apply styling based on rich style name
        if style in style_map and COLORS_SUPPORTED:
            print(f"{style_map[style]}{text}{MS_RESET}")
        else:
            print(text)

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
AUTO_CLEAR = False  # Auto-clear terminal after command execution

# Get API key from .env file
API_KEY = os.getenv("GEMINI_API_KEY")

# Store active background processes
background_processes = {}

# Token cache dictionary (now using OrderedDict for LRU functionality)
token_cache = OrderedDict()

# Command result cache dictionary (also using OrderedDict)
command_cache = OrderedDict()

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
        print_colored(f"Error formatting output: {e}", MS_RED)
        return text

def copy_to_clipboard(text):
    """Copy text to clipboard if clipboard module is available"""
    if not CLIPBOARD_AVAILABLE:
        print_colored("Clipboard functionality not available. Install pyperclip.", MS_YELLOW)
        return False
    
    try:
        pyperclip.copy(text)
        print_colored("Copied to clipboard.", MS_GREEN)
        return True
    except Exception as e:
        print_colored(f"Error copying to clipboard: {e}", MS_RED)
        return False

def load_templates():
    """Load command templates from file if it exists"""
    global templates
    
    if os.path.exists(TEMPLATE_FILE):
        try:
            with open(TEMPLATE_FILE, 'rb') as f:
                templates = pickle.load(f)
        except Exception as e:
            print_colored(f"Error loading templates: {e}. Using defaults.", MS_YELLOW)

def save_templates():
    """Save command templates to file"""
    try:
        with open(TEMPLATE_FILE, 'wb') as f:
            pickle.dump(templates, f)
        print_colored("Templates saved.", MS_GREEN)
    except Exception as e:
        print_colored(f"Error saving templates: {e}", MS_RED)

def load_command_groups():
    """Load command groups from file if it exists"""
    global command_groups
    
    if os.path.exists(COMMAND_GROUPS_FILE):
        try:
            with open(COMMAND_GROUPS_FILE, 'rb') as f:
                command_groups = pickle.load(f)
        except Exception as e:
            print_colored(f"Error loading command groups: {e}. Using defaults.", MS_YELLOW)

def save_command_groups():
    """Save command groups to file"""
    try:
        with open(COMMAND_GROUPS_FILE, 'wb') as f:
            pickle.dump(command_groups, f)
        print_colored("Command groups saved.", MS_GREEN)
    except Exception as e:
        print_colored(f"Error saving command groups: {e}", MS_RED)

def load_token_cache():
    """Load token cache from file if it exists"""
    global token_cache
    
    if os.path.exists(TOKEN_CACHE_FILE):
        try:
            with open(TOKEN_CACHE_FILE, 'rb') as f:
                # Convert regular dict to OrderedDict
                loaded_cache = pickle.load(f)
                token_cache = OrderedDict()
                
                # Clean expired tokens and add valid ones to OrderedDict
                current_time = time.time()
                for key, (value, timestamp) in loaded_cache.items():
                    if current_time - timestamp <= TOKEN_CACHE_EXPIRY * 86400:  # seconds in a day
                        token_cache[key] = (value, timestamp)
                
        except Exception as e:
            print_colored(f"Error loading token cache: {e}. Creating new cache.", MS_YELLOW)
            token_cache = {}

def save_token_cache():
    """Save token cache to file"""
    try:
        with open(TOKEN_CACHE_FILE, 'wb') as f:
            pickle.dump(dict(token_cache), f)  # Convert to regular dict for backward compatibility
    except Exception as e:
        print_colored(f"Error saving token cache: {e}", MS_RED)

def check_dependencies():
    """Check if required dependencies are installed"""
    try:
        subprocess.run(["curl", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        print_colored("Error: curl is required but not installed.", MS_RED)
        print("Please install curl to use this application.")
        sys.exit(1)
    
    try:
        import json
    except ImportError:
        print_colored("Warning: json module not available. Some features may be limited.", MS_YELLOW)
    
    if not PROMPT_TOOLKIT_AVAILABLE:
        print_colored("Warning: prompt_toolkit not available. Command history navigation will be disabled.", MS_YELLOW)
        print("Install prompt_toolkit for enhanced command history features.")
    
    if not CLIPBOARD_AVAILABLE:
        print_colored("Warning: pyperclip not available. Clipboard integration will be disabled.", MS_YELLOW)
        print("Install pyperclip for clipboard integration features.")

def is_dangerous_command(command):
    """Check if a command is potentially dangerous"""
    # Check for dangerous patterns
    dangerous_patterns = [
        r"\brm\s+-rf\b",           # Recursive force delete
        r"\bdd\b",                  # Disk destroyer
        r"\bmkfs\b",                # Format filesystem
        r"\bformat\b",              # Format disk
        r"\bfdisk\b",               # Partition tool
        r"\bmount\b",               # Mount filesystems
        r"\bchmod\s+777\b",         # Insecure permissions
        r"\bsudo\b",                # Superuser command 
        r"\bsu\b",                  # Switch user
        r"\beval\b",                # Evaluate code
        r":(){.*};:",               # Fork bomb
        r"\bmv\s+\/\s+",            # Move from root
        r"\bwget.*\|\s*sh\b",       # Download and run
        r"\bcurl.*\|\s*sh\b",       # Download and run
        r">(>)?.*\/dev\/(sd|hd|nvme)", # Write to block device
        r"\bwipe\b",                # Wipe device
        r"\bshred\b",               # Shred files
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    
    # Check for dangerous commands that erase data
    dangerous_commands = ["mkfs", "fdisk", "format", "deltree", "rd /s", "rmdir /s"]
    for cmd in dangerous_commands:
        if cmd in command.lower():
            return True
            
    return False

def verify_command(command):
    """Verify if a command is safe to execute"""
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
        print_colored(f"The command '{command}' appears potentially dangerous.", MS_YELLOW)
        print_colored("Suggested alternative: Run a safer version or use with caution.", MS_YELLOW)
        return True, ""  # Still return True to allow execution without prompting
    
    # For other commands, just report they'll be executed without verification
    if API_KEY and False:  # Disable AI verification completely by adding False condition
        print_colored("Verifying command safety...", MS_YELLOW)
        
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
        
        # Call API for verification using curl
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
            
            result = subprocess.run(curl_command, capture_output=True, text=True)
            response = result.stdout
            
            response_data = json.loads(response)
            verification = response_data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Clean up the verification text - remove markdown code blocks
            verification = re.sub(r'```json\s*', '', verification)
            verification = re.sub(r'```\s*', '', verification)
            
            print_colored("Command Verification:", MS_CYAN)
            print_colored(f"{verification.strip()}", MS_WHITE)
            
            # Extract the safety assessment
            safety_line = ""
            for line in verification.splitlines():
                if line.strip().startswith("SAFETY:"):
                    safety_line = line.strip().lower()
                    break
            
            # Try to parse the JSON to determine safety
            try:
                verification_json = json.loads(verification.strip())
                is_safe = verification_json.get("safe", False)
                risk_level = verification_json.get("risk_level", 5)
                reason = verification_json.get("reason", "No reason provided")
                
                # Format the verification output with better styling
                if RICH_AVAILABLE:
                    print()
                    console.print("Command Verification:", style="bold cyan")
                    console.print("{", style="dim")
                    
                    # Safety indicator with color based on safety
                    safety_style = "green bold" if is_safe else "red bold"
                    console.print(f'  "safe": ', style="cyan", end="")
                    console.print(f"{str(is_safe).lower()}", style=safety_style)
                    
                    # Reason with indentation
                    console.print(f'  "reason": ', style="cyan", end="")
                    console.print(f'"{reason}"', style="white")
                    
                    # Risk level with color based on level
                    risk_style = "green" if risk_level <= 3 else "yellow" if risk_level <= 6 else "red bold"
                    console.print(f'  "risk_level": ', style="cyan", end="")
                    console.print(f"{risk_level}", style=risk_style)
                    
                    console.print("}", style="dim")
                    print()
                else:
                    # Fallback formatting for environments without rich
                    print(f"{MS_CYAN}Command Verification:{MS_RESET}")
                    print("{")
                    
                    # Safety indicator
                    safety_color = MS_GREEN if is_safe else MS_RED
                    print(f'  {MS_CYAN}"safe":{MS_RESET} {safety_color}{str(is_safe).lower()}{MS_RESET},')
                    
                    # Reason
                    print(f'  {MS_CYAN}"reason":{MS_RESET} "{reason}",')
                    
                    # Risk level
                    risk_color = MS_GREEN if risk_level <= 3 else MS_YELLOW if risk_level <= 6 else MS_RED
                    print(f'  {MS_CYAN}"risk_level":{MS_RESET} {risk_color}{risk_level}{MS_RESET}')
                    
                    print("}")
                
                if not is_safe or risk_level > 5:
                    print_colored("This command may be unsafe. Please review carefully.", MS_RED)
                else:
                    print_colored("Command appears to be safe.", MS_GREEN)
            except json.JSONDecodeError:
                # If we can't parse JSON, fall back to keyword matching
                if "unsafe" in safety_line or "dangerous" in safety_line:
                    print_colored("This command may be unsafe. Please review carefully.", MS_RED)
                elif "safe" in safety_line:
                    print_colored("Command appears to be safe.", MS_GREEN)
                else:
                    print_colored("Safety assessment unclear. Please review manually.", MS_YELLOW)
            
            # No longer ask for confirmation, always proceed
            return True, verification
            
        except Exception as e:
            print_colored(f"Error during command verification: {e}", MS_RED)
            return True, str(e)  # Still return True to execute
    
    return True, ""  # Always allow command to execute

def get_ai_response(task):
    """Get AI response for a given task"""
    if not API_KEY:
        print_colored("Error: No API key found. Run 'api-key' to set up your API key.", MS_RED)
        return None
    
    try:
        # Show thinking message
        print_colored("Thinking...", MS_YELLOW)
        
        # Prepare the API request
        curl_command = [
            "curl", "-s", "-X", "POST",
            f"{API_ENDPOINT}/{API_VERSION}/models/{MODEL}:generateContent?key={API_KEY}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "contents": [{
                    "parts": [{
                        "text": task
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.7,
                    "topP": 0.8,
                    "topK": 40,
                    "maxOutputTokens": 2048
                }
            })
        ]
        
        # Execute the curl command
        try:
            result = subprocess.run(curl_command, capture_output=True, text=True)
            response = result.stdout
        except subprocess.SubprocessError as e:
            raise NetworkError(
                f"Failed to execute curl command: {e}",
                "Make sure curl is installed and working correctly."
            )
        
        if not response or response.isspace():
            raise APIError(
                "Received empty response from API", 
                "Check your internet connection and API key. The API endpoint might be down."
            )
        
        # Parse the response
        try:
            response_data = json.loads(response)
            
            # Check for API errors in the response
            if "error" in response_data:
                error_info = response_data["error"]
                error_message = error_info.get("message", "Unknown API error")
                error_code = error_info.get("code", "unknown")
                
                raise APIError(
                    f"API Error ({error_code}): {error_message}",
                    "Verify your API key and check if you've exceeded your quota."
                )
                
            result_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            
            # Cache the result if caching is enabled
            if USE_TOKEN_CACHE:
                cache_command_result(task, result_text)
                
            return result_text
            
        except json.JSONDecodeError:
            raise APIError(
                "Failed to parse API response as JSON", 
                "The API response format may have changed or the service may be experiencing issues."
            )
        except KeyError:
            raise APIError(
                "Unexpected API response format", 
                "The response doesn't contain the expected fields. The API structure may have changed."
            )
        
    except Exception as e:
        # Give a helpful suggestion instead of just an error
        print_colored(f"Error getting AI response: {e}", MS_RED)
        print_colored("Try running these commands instead:", MS_YELLOW)
        
        # Analyze the task to suggest a relevant command
        task_lower = task.lower()
        if "list" in task_lower and "file" in task_lower:
            print_colored("ls -la", MS_GREEN)
        elif "disk" in task_lower or "space" in task_lower:
            print_colored("df -h", MS_GREEN)
        elif "memory" in task_lower or "ram" in task_lower:
            print_colored("free -h", MS_GREEN)
        elif "process" in task_lower:
            print_colored("ps aux", MS_GREEN)
        elif "network" in task_lower:
            print_colored("ifconfig || ip addr", MS_GREEN)
        else:
            print_colored("help", MS_GREEN)
            
        return None

async def run_command_async(command_id, command):
    """Run a command asynchronously"""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        background_processes[command_id] = {
            "process": process,
            "command": command,
            "start_time": datetime.datetime.now(),
            "status": "running"
        }
        
        stdout, stderr = await process.communicate()
        
        # Update process status
        if process.returncode == 0:
            background_processes[command_id]["status"] = "completed"
        else:
            background_processes[command_id]["status"] = "failed"
            
        background_processes[command_id]["end_time"] = datetime.datetime.now()
        background_processes[command_id]["return_code"] = process.returncode
        background_processes[command_id]["stdout"] = stdout.decode()
        background_processes[command_id]["stderr"] = stderr.decode()
        
        return process.returncode
        
    except Exception as e:
        print_colored(f"Error running async command: {e}", MS_RED)
        if command_id in background_processes:
            background_processes[command_id]["status"] = "error"
            background_processes[command_id]["error"] = str(e)
        return 1

def start_async_command(command):
    """Start an asynchronous command execution"""
    command_id = str(int(time.time()))
    
    # Create a new event loop
    loop = asyncio.new_event_loop()
    
    # Create a thread to run the event loop
    def run_async_command():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run_command_async(command_id, command))
        loop.close()
    
    # Start the thread
    thread = threading.Thread(target=run_async_command)
    thread.daemon = True
    thread.start()
    
    print_colored(f"Started background command with ID: {command_id}", MS_GREEN)
    return command_id

def execute_command(command, is_async=False):
    """Execute a shell command and return its output"""
    if not command or command.isspace():
        return
    
    # Check if command should be run asynchronously
    if is_async or command.startswith("async "):
        if command.startswith("async "):
            command = command[6:].strip()
        
        if not command:
            print_colored("No command specified for async execution.", MS_YELLOW)
            return
            
        command_id = start_async_command(command)
        print_colored("Command is running in the background. Use 'jobs' to check status.", MS_GREEN)
        return
    
    # Verify command before execution if enabled
    if VERIFY_COMMANDS:
        safe, reason = verify_command(command)
        if not safe:
            print_colored(f"Command execution cancelled: {reason}", MS_RED)
            return

    # Record start time
    start_time = time.time()
    
    print_colored(f"Executing: {command}", MS_CYAN)
    
    # Execute the command
    try:
        # Use subprocess.Popen for streaming output if enabled
        if STREAM_OUTPUT:
            try:
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
            except FileNotFoundError:
                raise CommandError(
                    f"Command not found: {command.split()[0]}",
                    "Check if the command is installed and in your PATH."
                )
            except PermissionError:
                raise CommandError(
                    f"Permission denied when executing: {command}",
                    "Check if you have the necessary permissions to run this command."
                )
            
            # Set up non-blocking reads from stdout and stderr
            process.stdout.fileno()
            process.stderr.fileno()
            
            print_colored("Output:", MS_CYAN)
            
            # Stream output until process completes
            output_lines = []
            error_lines = []
            
            while True:
                # Check if process has finished
                if process.poll() is not None:
                    break
                    
                # Read from stdout and stderr
                reads = [process.stdout, process.stderr]
                ret = select.select(reads, [], [], 0.1)
                
                for fd in ret[0]:
                    if fd is process.stdout:
                        line = fd.readline()
                        if line:
                            output_lines.append(line)
                            print(line, end="", flush=True)
                    elif fd is process.stderr:
                        line = fd.readline()
                        if line:
                            error_lines.append(line)
                            print_colored(line, MS_RED, end="", flush=True)
            
            # Read any remaining output
            remaining_output, remaining_error = process.communicate()
            
            if remaining_output:
                output_lines.append(remaining_output)
                print(remaining_output, end="", flush=True)
                
            if remaining_error:
                error_lines.append(remaining_error)
                print_colored(remaining_error, MS_RED, end="", flush=True)
                
            # Join output lines
            output = "".join(output_lines)
            error = "".join(error_lines)
            
            # Display any errors
            if error and not error.isspace():
                print_colored(error, MS_RED)
                
            # Display return code if non-zero
            if process.returncode != 0:
                print_colored(f"Command completed with return code: {process.returncode}", MS_YELLOW)
                
            # Automatically copy to clipboard if enabled and a copy formatter was used
            if " | copy" in command and USE_CLIPBOARD:
                copy_to_clipboard(output)
                
            # Format output if requested
            if " | format " in command:
                try:
                    format_parts = command.split(" | format ")
                    formatter = format_parts[1].strip()
                    formatted_output = format_output(output, formatter)
                    print_colored(f"Formatted output ({formatter}):", MS_CYAN)
                    print(formatted_output)
                except Exception as e:
                    print_colored(f"Error formatting output: {e}", MS_RED)
            
            # Calculate execution time
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Record in history
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print_colored(f"Command completed in {execution_time:.2f} seconds.", MS_GREEN)
            
            # Auto-clear the terminal after a short delay if enabled
            if AUTO_CLEAR:
                print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
                time.sleep(2)
                os.system("cls" if os.name == "nt" else "clear")
            
            return output
            
        else:
            # Use simpler method if streaming is disabled
            try:
                result = subprocess.run(command, shell=True, capture_output=True, text=True)
            except FileNotFoundError:
                raise CommandError(
                    f"Command not found: {command.split()[0]}",
                    "Check if the command is installed and in your PATH."
                )
            except PermissionError:
                raise CommandError(
                    f"Permission denied when executing: {command}",
                    "Check if you have the necessary permissions to run this command."
                )
            
            # Record execution time
            execution_time = time.time() - start_time
            
            result_dict = {
                "output": result.stdout,
                "error": result.stderr,
                "return_code": result.returncode,
                "execution_time": execution_time
            }
            
            # Check for errors
            if result.stderr:
                print_colored(result.stderr, MS_RED)
                
            # Print output
            if result.stdout:
                print(f"{MS_CYAN}Output:{MS_RESET}")
                print(result.stdout)
                
            # Display return code if non-zero
            if result.returncode != 0:
                print_colored(f"Command completed with return code: {result.returncode}", MS_YELLOW)
                
            # Calculate execution time
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Display execution time
            print_colored(f"Command completed in {execution_time:.2f} seconds.", MS_GREEN)
            
            # Auto-clear the terminal after a short delay if enabled
            if AUTO_CLEAR:
                print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
                time.sleep(2)
                os.system("cls" if os.name == "nt" else "clear")
            
            # Ask if user wants to clear the console
            if result.stdout or result.stderr:
                clear_choice = input(f"{MS_YELLOW}Clear console? (y/n): {MS_RESET}")
                if clear_choice.lower() == 'y':
                    os.system("cls" if os.name == "nt" else "clear")
                
            return result_dict
    
    except KeyboardInterrupt:
        print_colored("Command interrupted by user.", MS_YELLOW)
        return None
    except Exception as e:
        print_colored(f"Error executing command: {e}", MS_RED)
        return None

def toggle_auto_clear():
    """Toggle auto-clear terminal after commands"""
    global AUTO_CLEAR
    # Get the current value and negate it
    current_value = AUTO_CLEAR
    AUTO_CLEAR = not current_value
    print_colored(f"Auto-clear terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_GREEN)
    return AUTO_CLEAR

def process_user_command(command):
    """Process a built-in command or pass to shell"""
    if not command or command.isspace():
        return
    
    # Don't auto-clear for certain commands that are interface-related
    skip_auto_clear = command.lower() in ["help", "exit", "quit", "clear", "history", "config", "api-key", "templates", "groups", "setup", "auto-clear", "verify", "chain"]
    
    # Check for built-in commands
    if command.lower() == "exit" or command.lower() == "quit":
        print_colored("Exiting Terminal AI Assistant.", MS_GREEN)
        sys.exit(0)
        
    elif command.lower() == "help":
        show_help()
        return
        
    elif command.lower() == "clear":
        os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower() == "history":
        show_history()
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower() == "config":
        show_config()
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower().startswith("set "):
        set_config(command[4:])
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower() == "api-key":
        try:
            set_api_key()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "pwd":
        print(os.getcwd())
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower().startswith("cd "):
        try:
            path = command[3:].strip()
            # Expand ~ to user's home directory
            path = os.path.expanduser(path)
            # Handle special case for CD without arguments
            if not path:
                path = os.path.expanduser("~")
            os.chdir(path)
            print_colored(f"Changed directory to: {os.getcwd()}", MS_GREEN)
            # Apply auto-clear if enabled
            if AUTO_CLEAR and not skip_auto_clear:
                print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
                time.sleep(2)
                os.system("cls" if os.name == "nt" else "clear")
        except Exception as e:
            print_colored(f"Error changing directory: {e}", MS_RED)
        return
        
    elif command.lower() == "templates":
        try:
            manage_templates()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "groups":
        try:
            manage_command_groups()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "verify":
        toggle_verification()
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower() == "chain":
        toggle_command_chaining()
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower() == "auto-clear" or command.lower() == "autoclear":
        toggle_auto_clear()
        return
        
    elif command.lower() == "jobs":
        show_background_jobs()
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower().startswith("kill "):
        kill_background_job(command[5:].strip())
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower().startswith("!"):
        try:
            run_template(command[1:])
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "setup":
        try:
            run_setup_wizard()
        except Exception as e:
            print(format_error(e))
        return
        
    # Check for command chaining with && or ||
    if ALLOW_COMMAND_CHAINING and ("&&" in command or "||" in command):
        try:
            process_command_chain(command)
        except Exception as e:
            print(format_error(e))
        return
        
    # Execute as shell command
    try:
        execute_command(command)
    except Exception as e:
        print(format_error(e))

def process_command_chain(command_chain):
    """Process a chain of commands connected with && or ||"""
    # Tokenize the command chain
    tokens = []
    current_token = ""
    in_quotes = False
    quote_char = None
    
    for char in command_chain:
        if char in ['"', "'"]:
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
                
        if char in [' ', '\t'] and not in_quotes:
            if current_token:
                tokens.append(current_token)
                current_token = ""
        else:
            current_token += char
            
    if current_token:
        tokens.append(current_token)
        
    # Parse tokens to identify command boundaries and operators
    commands = []
    operators = []
    current_command = []
    
    for token in tokens:
        if token == "&&" or token == "||":
            if current_command:
                commands.append(" ".join(current_command))
                current_command = []
                operators.append(token)
        else:
            current_command.append(token)
            
    if current_command:
        commands.append(" ".join(current_command))
        
    # Execute commands in sequence
    last_result = 0
    execute_next = True
    
    for i, cmd in enumerate(commands):
        if i == 0 or execute_next:
            # Execute this command
            print(f"{MS_CYAN}Chain command {i+1}/{len(commands)}: {cmd}{MS_RESET}")
            result = execute_command(cmd)
            
            # Determine if we should execute the next command
            if i < len(operators):
                if operators[i] == "&&":
                    # Execute next only if this one succeeded
                    execute_next = result is not None and result != 1
                elif operators[i] == "||":
                    # Execute next only if this one failed
                    execute_next = result is None or result == 1
        else:
            # Skip this command based on logic
            print(f"{MS_YELLOW}Skipping command: {cmd}{MS_RESET}")
            
    print(f"{MS_GREEN}Command chain completed.{MS_RESET}")

def show_background_jobs():
    """Display status of background jobs"""
    if not background_processes:
        print_colored("No background jobs running.", MS_YELLOW)
        return
        
    print(f"{MS_CYAN}Background Jobs:{MS_RESET}")
    print(f"{'ID':<10} {'Status':<15} {'Start Time':<20} {'Command':<40}")
    print("-" * 85)
    
    for job_id, job in background_processes.items():
        print(f"{job_id:<10} {job.get('status', 'unknown'):<15} {job.get('start_time').strftime('%Y-%m-%d %H:%M:%S'):<20} {job.get('command', 'unknown')[:40]}")
        
    print(f"\n{MS_YELLOW}Use 'kill JOB_ID' to terminate a job.{MS_RESET}")

def kill_background_job(job_id):
    """Kill a background job by ID"""
    if not job_id:
        print_colored("No job ID specified.", MS_YELLOW)
        return
        
    if job_id not in background_processes:
        print_colored(f"Job ID '{job_id}' not found.", MS_RED)
        return
        
    job = background_processes[job_id]
    process = job.get("process")
    
    if not process:
        print_colored(f"No process found for job ID '{job_id}'.", MS_RED)
        return
        
    if job.get("status") in ["completed", "failed", "error"]:
        print_colored(f"Job already finished with status: {job.get('status')}", MS_YELLOW)
        return
        
    try:
        process.terminate()
        print_colored(f"Terminated job: {job_id}", MS_GREEN)
        job["status"] = "terminated"
        job["end_time"] = datetime.datetime.now()
    except Exception as e:
        print_colored(f"Error terminating job: {e}", MS_RED)

def show_help():
    """Display help information"""
    print_styled("Terminal AI Assistant Lite - Help", style="cyan")
    print_styled("\nGeneral Commands:", style="yellow")
    print("  help       - Show this help information")
    print("  exit/quit  - Exit the program")
    print("  clear      - Clear the screen")
    print("  history    - Show command history")
    print("  config     - Show current configuration")
    print("  set KEY=VAL- Change configuration settings")
    
    print_styled("\nNavigation:", style="yellow")
    print("  cd DIR     - Change directory")
    print("  pwd        - Show current directory")
    
    print_styled("\nAPI & Configuration:", style="yellow")
    print("  api-key    - Update your Gemini API key")
    print("  templates  - Manage command templates")
    print("  groups     - Manage command groups")
    
    print_styled("\nExecution Control:", style="yellow")
    print("  format     - Format last command output")
    print("  copy       - Copy last command output to clipboard")
    print("  async      - Run command in background")
    print("  jobs       - Show running background jobs")
    print("  kill ID    - Kill a background job")
    print("  !TEMPLATE  - Run a saved template")
    print("  verify     - Toggle command verification")
    print("  chain      - Toggle command chaining")
    print("  auto-clear - Toggle auto-clear terminal after commands")
    print("  setup      - Run setup wizard")
    
    print_styled("\nExamples:", style="yellow")
    print("  Find all text files: find . -name \"*.txt\"")
    print("  Check disk space: df -h")
    print("  Format JSON output: cat data.json | format json")
    print("  Run in background: async long-running-command")
    
    print_styled("\nFor AI assistance, simply type your task in natural language.", style="green")

def show_history():
    """Display command history"""
    try:
        if os.path.exists(HISTORY_FILE) and PROMPT_TOOLKIT_AVAILABLE:
            with open(HISTORY_FILE, 'r') as f:
                lines = f.readlines()
                
            print(f"{MS_CYAN}Command History:{MS_RESET}")
            
            # Display with numbers, most recent at the bottom
            for i, cmd in enumerate(lines[-MAX_HISTORY:]):
                print(f"{i+1:3d}: {cmd.strip()}")
        else:
            print_colored("Command history not available. Enable prompt_toolkit for history support.", MS_YELLOW)
    except Exception as e:
        print_colored(f"Error displaying history: {e}", MS_RED)

def show_config():
    """Display current configuration"""
    print(f"{MS_CYAN}Current Configuration:{MS_RESET}")
    print(f"  API Key: {'Set' if API_KEY else 'Not Set'}")
    print(f"  Model: {MODEL}")
    print(f"  Command Verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}")
    print(f"  Command Chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}")
    print(f"  Output Streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}")
    print(f"  Clipboard Integration: {'Enabled' if USE_CLIPBOARD else 'Disabled'}")
    print(f"  Async Command Execution: {'Enabled' if USE_ASYNC_EXECUTION else 'Disabled'}")
    print(f"  Auto-Clear Terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}")

def set_config(config_str):
    """Set configuration values"""
    global MODEL, VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, STREAM_OUTPUT, USE_CLIPBOARD, USE_ASYNC_EXECUTION, AUTO_CLEAR
    
    if not config_str or "=" not in config_str:
        print_colored("Invalid config format. Use: set KEY=VALUE", MS_YELLOW)
        return
        
    key, value = config_str.split("=", 1)
    key = key.strip().lower()
    value = value.strip()
    
    if key == "model":
        MODEL = value
        print_colored(f"Model set to: {MODEL}", MS_GREEN)
    elif key == "verify":
        VERIFY_COMMANDS = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print_colored(f"Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_GREEN)
    elif key == "chain":
        ALLOW_COMMAND_CHAINING = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print_colored(f"Command chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}", MS_GREEN)
    elif key == "stream":
        STREAM_OUTPUT = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print_colored(f"Output streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}", MS_GREEN)
    elif key == "clipboard":
        USE_CLIPBOARD = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print_colored(f"Clipboard integration: {'Enabled' if USE_CLIPBOARD else 'Disabled'}", MS_GREEN)
    elif key == "async":
        USE_ASYNC_EXECUTION = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print_colored(f"Async execution: {'Enabled' if USE_ASYNC_EXECUTION else 'Disabled'}", MS_GREEN)
    elif key == "auto_clear" or key == "autoclear":
        AUTO_CLEAR = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print_colored(f"Auto-clear terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_GREEN)
    else:
        print_colored(f"Unknown configuration key: {key}", MS_YELLOW)

def toggle_verification():
    """Toggle command verification"""
    global VERIFY_COMMANDS
    VERIFY_COMMANDS = not VERIFY_COMMANDS
    print_colored(f"Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_GREEN)

def toggle_command_chaining():
    """Toggle command chaining"""
    global ALLOW_COMMAND_CHAINING
    ALLOW_COMMAND_CHAINING = not ALLOW_COMMAND_CHAINING
    print_colored(f"Command chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}", MS_GREEN)

def set_api_key():
    """Set or update API key"""
    global API_KEY
    
    print_styled("Enter your Gemini API Key (input will be hidden):", style="cyan")
    
    try:
        # Handle input differently based on platform
        if os.name == "nt":
            import msvcrt
            api_key = ""
            while True:
                char = msvcrt.getch().decode("utf-8", errors="ignore")
                if char == '\r' or char == '\n':
                    break
                elif char == '\b':
                    api_key = api_key[:-1]
                    print("\b \b", end="", flush=True)
                else:
                    api_key += char
                    print("*", end="", flush=True)
            print()
        else:
            import getpass
            api_key = getpass.getpass("")
    except Exception:
        api_key = input("API Key: ")
        
    if not api_key:
        print_styled("API key not provided. Keeping existing key.", style="yellow")
        return
        
    # Save to .env file
    with open(".env", "w") as f:
        f.write(f"GEMINI_API_KEY={api_key}")
        
    # Make sure to use the global variable
    API_KEY = api_key
    print_styled("API key updated successfully.", style="green")

def manage_templates():
    """Manage command templates"""
    print(f"{MS_CYAN}Command Templates:{MS_RESET}")
    print(f"{'Name':<15} {'Description':<50}")
    print("-" * 65)
    
    for name, description in templates.items():
        print(f"{name:<15} {description:<50}")
        
    print("\nOptions:")
    print("  add    - Add a new template")
    print("  delete - Delete a template")
    print("  exit   - Return to main prompt")
    
    choice = input(f"\n{MS_YELLOW}Action:{MS_RESET} ").strip().lower()
    
    if choice == "add":
        name = input(f"{MS_YELLOW}Template name:{MS_RESET} ").strip()
        if not name:
            print_colored("Template name cannot be empty.", MS_RED)
            return
            
        description = input(f"{MS_YELLOW}Description:{MS_RESET} ").strip()
        if not description:
            print_colored("Description cannot be empty.", MS_RED)
            return
            
        templates[name] = description
        save_templates()
        print_colored(f"Template '{name}' added.", MS_GREEN)
        
    elif choice == "delete":
        name = input(f"{MS_YELLOW}Template name to delete:{MS_RESET} ").strip()
        if not name in templates:
            print_colored(f"Template '{name}' not found.", MS_RED)
            return
            
        del templates[name]
        save_templates()
        print_colored(f"Template '{name}' deleted.", MS_GREEN)
        
def run_template(template_name):
    """Run a command template"""
    if not template_name:
        print_colored("No template specified.", MS_RED)
        return
        
    if template_name not in templates:
        print_colored(f"Template '{template_name}' not found.", MS_RED)
        return
        
    description = templates[template_name]
    print(f"{MS_CYAN}Running template '{template_name}':{MS_RESET} {description}")
    
    # Get commands for this task from AI
    commands = get_ai_response(description)
    
    if not commands:
        print_colored("Failed to get commands for this template.", MS_RED)
        return
        
    # Execute the commands
    lines = commands.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            if "I cannot " in line or "cannot be " in line or "Sorry, " in line:
                print_styled(f"AI Response: {line}", style="yellow")
            else:
                try:
                    result = execute_command(line)
                    # If command returned error, feed it back to Gemini for possible recovery
                    if isinstance(result, dict) and result.get("return_code", 0) != 0 and result.get("error"):
                        error_feedback_prompt = f"""
                        The previous command '{line}' failed with error:
                        {result['error']}
                        
                        Please suggest a correct solution for this error or an alternative approach.
                        Respond ONLY with the exact command to fix the issue, or explain if no command can resolve it.
                        """
                        
                        print_styled("Resolving error...", style="yellow")
                        error_solution = get_ai_response(error_feedback_prompt)
                        
                        if error_solution and not any(phrase in error_solution for phrase in ["I cannot", "cannot be", "Sorry,"]):
                            print_styled("Attempting solution:", style="cyan")
                            # Try the suggested fix
                            try:
                                execute_command(error_solution.strip())
                            except Exception as e:
                                print_styled(format_error(e), style="red")
                        else:
                            print_styled(f"AI response: {error_solution}", style="yellow")
                except Exception as e:
                    print_styled(format_error(e), style="red")
            
def manage_command_groups():
    """Manage command groups"""
    print(f"{MS_CYAN}Command Groups:{MS_RESET}")
    
    for group, commands in command_groups.items():
        print(f"\n{MS_YELLOW}{group}:{MS_RESET}")
        print(", ".join(commands))
        
    print("\nOptions:")
    print("  add    - Add a new group")
    print("  delete - Delete a group")
    print("  modify - Modify a group")
    print("  exit   - Return to main prompt")
    
    choice = input(f"\n{MS_YELLOW}Action:{MS_RESET} ").strip().lower()
    
    if choice == "add":
        name = input(f"{MS_YELLOW}Group name:{MS_RESET} ").strip()
        if not name:
            print_colored("Group name cannot be empty.", MS_RED)
            return
            
        commands = input(f"{MS_YELLOW}Commands (comma-separated):{MS_RESET} ").strip()
        if not commands:
            print_colored("Commands cannot be empty.", MS_RED)
            return
            
        command_list = [cmd.strip() for cmd in commands.split(",")]
        command_groups[name] = command_list
        save_command_groups()
        print_colored(f"Group '{name}' added.", MS_GREEN)
        
    elif choice == "delete":
        name = input(f"{MS_YELLOW}Group name to delete:{MS_RESET} ").strip()
        if not name in command_groups:
            print_colored(f"Group '{name}' not found.", MS_RED)
            return
            
        del command_groups[name]
        save_command_groups()
        print_colored(f"Group '{name}' deleted.", MS_GREEN)
        
    elif choice == "modify":
        name = input(f"{MS_YELLOW}Group name to modify:{MS_RESET} ").strip()
        if not name in command_groups:
            print_colored(f"Group '{name}' not found.", MS_RED)
            return
            
        commands = input(f"{MS_YELLOW}New commands (comma-separated):{MS_RESET} ").strip()
        if not commands:
            print_colored("Commands cannot be empty.", MS_RED)
            return
            
        command_list = [cmd.strip() for cmd in commands.split(",")]
        command_groups[name] = command_list
        save_command_groups()
        print_colored(f"Group '{name}' modified.", MS_GREEN)

def run_setup_wizard():
    """Run setup wizard for first-time configuration"""
    global MODEL, VERIFY_COMMANDS, STREAM_OUTPUT, AUTO_CLEAR
    
    print_colored("Terminal AI Assistant Setup Wizard", MS_CYAN)
    print_colored("This wizard will help you configure the assistant.", MS_YELLOW)
    
    # Configure API key
    if not API_KEY:
        print_colored("\nStep 1: API Key Configuration", MS_CYAN)
        print_colored("You need a Gemini API key to use this assistant.", MS_YELLOW)
        print_colored("Visit https://ai.google.dev/ to get your key.", MS_YELLOW)
        set_api_key()
    else:
        print_colored("\nStep 1: API Key Configuration", MS_CYAN)
        print_colored("API key already configured.", MS_GREEN)
        change = input(f"{MS_YELLOW}Do you want to change it? (y/n):{MS_RESET} ").lower()
        if change == 'y':
            set_api_key()
    
    # Configure model
    print_colored("\nStep 2: Model Selection", MS_CYAN)
    print_colored(f"Current model: {MODEL}", MS_YELLOW)
    print_colored("Available models: gemini-1.5-flash, gemini-1.5-pro", MS_YELLOW)
    new_model = input(f"{MS_YELLOW}Select model (or press Enter to keep current):{MS_RESET} ").strip()
    if new_model:
        MODEL = new_model
        print_colored(f"Model set to: {MODEL}", MS_GREEN)
    
    # Configure verification
    print_colored("\nStep 3: Command Verification", MS_CYAN)
    print_colored("Command verification checks if commands are safe before execution.", MS_YELLOW)
    print_colored(f"Current setting: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_YELLOW)
    verify = input(f"{MS_YELLOW}Enable command verification? (y/n):{MS_RESET} ").lower()
    if verify:
        VERIFY_COMMANDS = verify == 'y'
        print_colored(f"Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_GREEN)
    
    # Configure streaming
    print_colored("\nStep 4: Output Streaming", MS_CYAN)
    print_colored("Output streaming shows command output in real-time.", MS_YELLOW)
    print_colored(f"Current setting: {'Enabled' if STREAM_OUTPUT else 'Disabled'}", MS_YELLOW)
    stream = input(f"{MS_YELLOW}Enable output streaming? (y/n):{MS_RESET} ").lower()
    if stream:
        STREAM_OUTPUT = stream == 'y'
        print_colored(f"Output streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}", MS_GREEN)
        
    # Configure auto-clear
    print_colored("\nStep 5: Auto-Clear Terminal", MS_CYAN)
    print_colored("Auto-clear automatically clears the terminal after each command.", MS_YELLOW)
    print_colored(f"Current setting: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_YELLOW)
    auto_clear = input(f"{MS_YELLOW}Enable auto-clear terminal? (y/n):{MS_RESET} ").lower()
    if auto_clear:
        AUTO_CLEAR = auto_clear == 'y'
        print_colored(f"Auto-clear terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_GREEN)
    
    print_colored("\nSetup complete! The assistant is ready to use.", MS_GREEN)
    print_colored("Type 'help' to see available commands or ask me to perform tasks for you.", MS_YELLOW)

def main():
    """Main function to run the terminal assistant"""
    # Check dependencies
    check_dependencies()
    
    # Load saved templates and command groups
    load_templates()
    load_command_groups()
    
    # Load token cache if enabled
    if USE_TOKEN_CACHE:
        load_token_cache()
        load_command_cache()
    
    # Set up command auto-completion
    if READLINE_AVAILABLE:
        print_styled("Setting up command auto-completion...", style="cyan")
        setup_autocomplete()
    
    # Check for API key
    if not API_KEY:
        print_colored("No API key found. Please enter your Gemini API key.", MS_YELLOW)
        set_api_key()
        
        if not API_KEY:
            print_colored("No API key provided. Some features will be disabled.", MS_RED)
    
    # Display welcome message
    print_colored("Terminal AI Assistant Lite v1.0", MS_CYAN)
    print_colored("Type 'help' for available commands or ask me to perform tasks for you.", MS_GREEN)
    
    # Main loop
    while True:
        try:
            # Check if we're using prompt_toolkit or readline
            if PROMPT_TOOLKIT_AVAILABLE:
                session = PromptSession(history=FileHistory(HISTORY_FILE))
                user_input = session.prompt("What would you like me to do? ")
            else:
                user_input = input("What would you like me to do? ")
                
            # Skip empty inputs
            if not user_input.strip():
                continue

            # Continue with processing the user input
            # Check if this looks like a command or a task description
            if user_input.startswith("!") or any(user_input.startswith(cmd) for cmd in ["help", "exit", "quit", "clear", "history", "config", "set ", "cd ", "pwd", "api-key", "templates", "groups", "verify", "chain", "auto-clear", "jobs", "kill ", "setup"]):
                # Handle as a built-in command
                try:
                    process_user_command(user_input)
                except Exception as e:
                    print_styled(format_error(e), style="red")
            else:
                # Handle as a task for the AI
                current_dir = os.getcwd()
                os_type = "Windows" if os.name == "nt" else "Unix/Linux"
                
                # Prepare the prompt for the AI
                task_prompt = f"""You are a terminal command expert. Generate executable commands for the following task.
                
                TASK: {user_input}
                CURRENT DIRECTORY: {current_dir}
                OPERATING SYSTEM: {os_type}
                
                Respond ONLY with the exact commands to execute, one per line.
                Do not include explanations, markdown formatting, or any text that is not meant to be executed.
                Ensure each command is complete and executable as-is.
                If the request cannot be satisfied with a command, respond with a single line explaining why."""
                
                # Get commands for this task from AI
                commands = get_ai_response(task_prompt)
                
                command_executed = False
                if commands:
                    # Split into individual commands and execute each one
                    lines = commands.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if "I cannot " in line or "cannot be " in line or "Sorry, " in line:
                                print_colored(f"AI Response: {line}", MS_YELLOW)
                            else:
                                execute_command(line)
                                command_executed = True
                
                # If auto-clear is enabled and no command was executed, handle it here
                if AUTO_CLEAR and not command_executed:
                    print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
                    time.sleep(2)
                    os.system("cls" if os.name == "nt" else "clear")
        
        except KeyboardInterrupt:
            print()
            print_colored("Interrupted. Press Ctrl+C again to exit.", MS_YELLOW)
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print()
                print_colored("Exiting Terminal AI Assistant.", MS_GREEN)
                break
        except Exception as e:
            print_colored(f"Error: {e}", MS_RED)
            
            # Auto-clear on error if enabled
            if AUTO_CLEAR:
                print_colored("Terminal will be cleared in 3 seconds...", MS_YELLOW)
                time.sleep(3)
                os.system("cls" if os.name == "nt" else "clear")
            
    # Save token cache before exit if enabled
    if USE_TOKEN_CACHE:
        save_token_cache()
        save_command_cache()

# Custom error classes with troubleshooting suggestions
class TerminalAIError(Exception):
    """Base class for Terminal AI Assistant errors"""
    def __init__(self, message, suggestion=None):
        self.message = message
        self.suggestion = suggestion
        super().__init__(message)

class CommandError(TerminalAIError):
    """Error related to command execution"""
    pass

class APIError(TerminalAIError):
    """Error related to API calls"""
    pass

class ConfigError(TerminalAIError):
    """Error related to configuration"""
    pass

class NetworkError(TerminalAIError):
    """Error related to network operations"""
    pass

class FileSystemError(TerminalAIError):
    """Error related to file system operations"""
    pass

def format_error(error, show_traceback=False):
    """Format an error with helpful message and suggestion"""
    error_type = type(error).__name__
    
    # Handle custom errors
    if isinstance(error, TerminalAIError):
        error_msg = f"{MS_RED}Error ({error_type}): {error.message}{MS_RESET}"
        if error.suggestion:
            error_msg += f"\n{MS_YELLOW}Suggestion: {error.suggestion}{MS_RESET}"
        return error_msg
    
    # Handle common system errors with helpful suggestions
    if isinstance(error, FileNotFoundError):
        return f"{MS_RED}Error: File or command not found - {error}{MS_RESET}\n" \
               f"{MS_YELLOW}Suggestion: Check if the file exists or if the command is installed.{MS_RESET}"
    elif isinstance(error, PermissionError):
        return f"{MS_RED}Error: Permission denied - {error}{MS_RESET}\n" \
               f"{MS_YELLOW}Suggestion: Check file permissions or try running with appropriate privileges.{MS_RESET}"
    elif isinstance(error, TimeoutError):
        return f"{MS_RED}Error: Operation timed out - {error}{MS_RESET}\n" \
               f"{MS_YELLOW}Suggestion: Check your network connection or try again later.{MS_RESET}"
    elif isinstance(error, ConnectionError):
        return f"{MS_RED}Error: Connection failed - {error}{MS_RESET}\n" \
               f"{MS_YELLOW}Suggestion: Check your internet connection or API endpoint.{MS_RESET}"
    elif isinstance(error, json.JSONDecodeError):
        return f"{MS_RED}Error: Invalid JSON - {error}{MS_RESET}\n" \
               f"{MS_YELLOW}Suggestion: The response received could not be parsed as JSON.{MS_RESET}"
    elif isinstance(error, KeyboardInterrupt):
        return f"{MS_YELLOW}Operation interrupted by user.{MS_RESET}"
    else:
        # Generic error handling
        error_msg = f"{MS_RED}Error ({error_type}): {str(error)}{MS_RESET}"
        
        # Add traceback if requested (for debugging)
        if show_traceback:
            import traceback
            error_msg += f"\n{MS_RED}Traceback:{MS_RESET}\n{traceback.format_exc()}"
            
        return error_msg

if __name__ == "__main__":
    main() 
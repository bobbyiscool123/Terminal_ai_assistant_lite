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

        # More efficient check for color name prefixes using str.startswith()
        text_lower = text.lower()
        for color_name in ["cyan", "green", "yellow", "red", "blue", "magenta", "white"]:
            if text_lower.startswith(color_name):
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

# Token cache dictionary
token_cache = {}

# History items cache for !N command execution
history_items_cache = []

# Command templates
templates = {
    "update": "Update all packages",
    "network": "Show network information",
    "disk": "Show disk usage",
    "process": "Show running processes",
    "memory": "Show memory usage",
    "backup": "Backup important files"
}

# Pre-compiled regex patterns for dangerous commands
DANGEROUS_PATTERNS = [
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

# Compile the patterns once at startup
DANGEROUS_PATTERNS_COMPILED = [re.compile(pattern, re.IGNORECASE) for pattern in DANGEROUS_PATTERNS]

# Create a single event loop for all async commands
async_loop = None
async_thread = None

# Initialize the shared asyncio event loop
def init_async_loop():
    """Initialize the shared asyncio event loop in a background thread"""
    global async_loop, async_thread

    # Only initialize if not already done
    if async_loop is not None:
        return

    # Create a new event loop
    async_loop = asyncio.new_event_loop()

    # Function to run the event loop
    def run_event_loop():
        asyncio.set_event_loop(async_loop)
        async_loop.run_forever()

    # Start the thread
    async_thread = threading.Thread(target=run_event_loop, daemon=True)
    async_thread.start()

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
            print_colored(f"Error loading token cache: {e}. Creating new cache.", MS_YELLOW)
            token_cache = {}

def save_token_cache():
    """Save token cache to file"""
    try:
        with open(TOKEN_CACHE_FILE, 'wb') as f:
            pickle.dump(token_cache, f)
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
    # Use pre-compiled patterns for better performance
    for compiled_pattern in DANGEROUS_PATTERNS_COMPILED:
        if compiled_pattern.search(command):
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
        # Show thinking animation
        if RICH_AVAILABLE:
            with console.status("[bold yellow]Thinking...", spinner="dots") as status:
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
                result = subprocess.run(curl_command, capture_output=True, text=True)
                response = result.stdout
        else:
            # Fallback for non-rich environments
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
            result = subprocess.run(curl_command, capture_output=True, text=True)
            response = result.stdout

        # Parse the response
        response_data = json.loads(response)
        return response_data["candidates"][0]["content"]["parts"][0]["text"]

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

    # Initialize the shared event loop if not already done
    if async_loop is None:
        init_async_loop()

    # Submit the coroutine to the shared event loop
    asyncio.run_coroutine_threadsafe(run_command_async(command_id, command), async_loop)

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
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
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
            result = subprocess.run(command, shell=True, capture_output=True, text=True)

            # Check for errors
            if result.stderr:
                print_colored(result.stderr, MS_RED)

            # Print output
            if result.stdout:
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

            return result.stdout

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

def show_job_details(job_id):
    """Show detailed output of a completed job"""
    if not job_id:
        print_colored("No job ID specified.", MS_YELLOW)
        return

    if job_id not in background_processes:
        print_colored(f"Job ID '{job_id}' not found.", MS_RED)
        return

    job = background_processes[job_id]
    status = job.get('status', 'unknown')

    print(f"{MS_CYAN}Job Details for ID: {job_id}{MS_RESET}")
    print(f"Command: {job.get('command', 'unknown')}")
    print(f"Status: {status}")
    print(f"Started: {job.get('start_time').strftime('%Y-%m-%d %H:%M:%S')}")

    if 'end_time' in job:
        print(f"Ended: {job.get('end_time').strftime('%Y-%m-%d %H:%M:%S')}")
        elapsed = job.get('end_time') - job.get('start_time')
        print(f"Elapsed: {elapsed}")

    if 'return_code' in job:
        print(f"Return Code: {job.get('return_code')}")

    if status in ['completed', 'failed', 'error']:
        print(f"\n{MS_CYAN}Standard Output:{MS_RESET}")
        if 'stdout' in job and job['stdout']:
            print(job['stdout'])
        else:
            print("(No output)")

        if 'stderr' in job and job['stderr']:
            print(f"\n{MS_RED}Standard Error:{MS_RESET}")
            print(job['stderr'])
    elif status == 'running':
        print(f"\n{MS_YELLOW}Job is still running. Use 'kill {job_id}' to terminate.{MS_RESET}")
    else:
        print(f"\n{MS_YELLOW}No output available for this job.{MS_RESET}")

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

    elif command.lower() == "set" or command.lower().startswith("set "):
        # Handle 'set' with or without arguments
        if command.lower() == "set":
            set_config("")
        else:
            set_config(command[4:])
        # Apply auto-clear if enabled
        if AUTO_CLEAR and not skip_auto_clear:
            print_colored("Terminal will be cleared in 2 seconds...", MS_YELLOW)
            time.sleep(2)
            os.system("cls" if os.name == "nt" else "clear")
        return

    elif command.lower() == "api-key":
        set_api_key()
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
        manage_templates()
        return

    elif command.lower() == "groups":
        manage_command_groups()
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

    elif command.lower().startswith("jobs detail "):
        show_job_details(command[12:].strip())
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
        run_template(command[1:])
        return

    elif command.lower() == "setup":
        run_setup_wizard()
        return

    # Check for command chaining
    if ALLOW_COMMAND_CHAINING and ("&&" in command or "||" in command):
        process_command_chain(command)
        return

    # Execute as shell command
    execute_command(command)

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
    """Display status of background jobs with elapsed time"""
    if not background_processes:
        print_colored("No background jobs running.", MS_YELLOW)
        return

    print(f"{MS_CYAN}Background Jobs:{MS_RESET}")
    print(f"{'ID':<10} {'Status':<15} {'Elapsed':<10} {'Start Time':<20} {'Command':<40}")
    print("-" * 95)

    current_time = datetime.datetime.now()

    for job_id, job in sorted(background_processes.items(),
                             key=lambda x: x[1].get('start_time', datetime.datetime.now()),
                             reverse=True):
        # Calculate elapsed time
        start_time = job.get('start_time')
        if job.get('status') == 'running':
            elapsed = current_time - start_time
        elif 'end_time' in job:
            elapsed = job.get('end_time') - start_time
        else:
            elapsed = datetime.timedelta(0)

        # Format elapsed time
        if elapsed.total_seconds() < 60:
            elapsed_str = f"{int(elapsed.total_seconds())}s"
        elif elapsed.total_seconds() < 3600:
            elapsed_str = f"{int(elapsed.total_seconds() / 60)}m {int(elapsed.total_seconds() % 60)}s"
        else:
            elapsed_str = f"{int(elapsed.total_seconds() / 3600)}h {int((elapsed.total_seconds() % 3600) / 60)}m"

        # Get status with color
        status = job.get('status', 'unknown')
        if status == 'running':
            status_str = f"{MS_GREEN}{status}{MS_RESET}"
        elif status == 'completed':
            status_str = f"{MS_CYAN}{status}{MS_RESET}"
        elif status in ['failed', 'error', 'terminated']:
            status_str = f"{MS_RED}{status}{MS_RESET}"
        else:
            status_str = status

        # Print job info
        print(f"{job_id:<10} {status_str:<15} {elapsed_str:<10} {start_time.strftime('%Y-%m-%d %H:%M:%S'):<20} {job.get('command', 'unknown')[:40]}")

    print(f"\n{MS_YELLOW}Use 'kill JOB_ID' to terminate a job.{MS_RESET}")
    print(f"{MS_YELLOW}Use 'jobs detail JOB_ID' to see detailed output of a completed job.{MS_RESET}")

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
    print("  history    - Show command history with line numbers")
    print("  !N         - Re-execute command number N from history")
    print("  config     - Show current configuration")
    print("  set        - Show all configuration options")
    print("  set KEY    - Interactively set a configuration value")
    print("  set KEY=VAL- Change configuration settings directly")

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
    print("  jobs       - Show running background jobs with elapsed time")
    print("  jobs detail ID - Show detailed output of a completed job")
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
    """Display command history with line numbers and allow re-execution with !N"""
    try:
        if os.path.exists(HISTORY_FILE) and PROMPT_TOOLKIT_AVAILABLE:
            with open(HISTORY_FILE, 'r') as f:
                lines = f.readlines()

            print(f"{MS_CYAN}Command History:{MS_RESET}")
            print(f"{MS_YELLOW}Use !N to re-execute a command by its number{MS_RESET}")
            print("-" * 60)

            # Display with numbers, most recent at the bottom
            history_items = []
            for i, cmd in enumerate(lines[-MAX_HISTORY:]):
                cmd_clean = cmd.strip()
                history_items.append(cmd_clean)
                print(f"{i+1:3d}: {cmd_clean}")

            # Store history items in a global variable for !N access
            global history_items_cache
            history_items_cache = history_items

            print("-" * 60)
            print(f"{MS_YELLOW}Total: {len(history_items)} commands{MS_RESET}")
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
    """Set configuration values interactively or with KEY=VALUE format"""
    global MODEL, VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, STREAM_OUTPUT, USE_CLIPBOARD, USE_ASYNC_EXECUTION, AUTO_CLEAR

    # Define available configuration options
    config_options = {
        "model": {
            "description": "AI model to use for generating commands",
            "current": MODEL,
            "type": "string",
            "options": ["gemini-1.5-flash", "gemini-1.5-pro"]
        },
        "verify": {
            "description": "Verify commands before execution",
            "current": VERIFY_COMMANDS,
            "type": "boolean"
        },
        "chain": {
            "description": "Allow command chaining with && and ||",
            "current": ALLOW_COMMAND_CHAINING,
            "type": "boolean"
        },
        "stream": {
            "description": "Stream command output in real-time",
            "current": STREAM_OUTPUT,
            "type": "boolean"
        },
        "clipboard": {
            "description": "Enable clipboard integration",
            "current": USE_CLIPBOARD,
            "type": "boolean"
        },
        "async": {
            "description": "Enable asynchronous command execution",
            "current": USE_ASYNC_EXECUTION,
            "type": "boolean"
        },
        "auto_clear": {
            "description": "Automatically clear terminal after commands",
            "current": AUTO_CLEAR,
            "type": "boolean"
        }
    }

    # If no arguments provided, show all available options
    if not config_str:
        print_colored("Available Configuration Options:", MS_CYAN)
        print(f"{'Key':<15} {'Type':<10} {'Current Value':<15} Description")
        print("-" * 80)

        for key, info in config_options.items():
            current = info["current"]
            if info["type"] == "boolean":
                current = "Enabled" if current else "Disabled"
            print(f"{key:<15} {info['type']:<10} {str(current):<15} {info['description']}")

        print("\nUsage:")
        print("  set KEY=VALUE    - Set a specific value")
        print("  set KEY          - Interactive prompt for value")
        return

    # Check if we're using KEY=VALUE format or just KEY
    if "=" in config_str:
        # Traditional KEY=VALUE format
        key, value = config_str.split("=", 1)
        key = key.strip().lower()
        value = value.strip()
    else:
        # Interactive mode - just KEY provided
        key = config_str.strip().lower()

        # Check if key exists
        if key not in config_options:
            print_colored(f"Unknown configuration key: {key}", MS_YELLOW)
            print_colored("Use 'set' without arguments to see available options.", MS_YELLOW)
            return

        # Get current value and type
        info = config_options[key]
        current = info["current"]
        if info["type"] == "boolean":
            current_str = "enabled" if current else "disabled"
            prompt_text = f"Enable {key}? Currently {current_str} (y/n): "
            response = input(f"{MS_YELLOW}{prompt_text}{MS_RESET}").lower()
            value = response.startswith("y")
        elif "options" in info:
            # Show available options
            print_colored(f"Available options for {key}:", MS_CYAN)
            for i, option in enumerate(info["options"]):
                print(f"{i+1}. {option}" + (" (current)" if option == current else ""))

            # Get user selection
            try:
                selection = input(f"{MS_YELLOW}Enter option number or value: {MS_RESET}")
                if selection.isdigit() and 1 <= int(selection) <= len(info["options"]):
                    value = info["options"][int(selection)-1]
                else:
                    value = selection
            except:
                value = selection
        else:
            # Simple string input
            value = input(f"{MS_YELLOW}Enter new value for {key} (current: {current}): {MS_RESET}")

    # Process the configuration change
    if key == "model":
        MODEL = value
        print_colored(f"Model set to: {MODEL}", MS_GREEN)
    elif key == "verify":
        if isinstance(value, bool):
            VERIFY_COMMANDS = value
        else:
            VERIFY_COMMANDS = value.lower() in ["true", "yes", "y", "1", "on", "enabled"]
        print_colored(f"Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_GREEN)
    elif key == "chain":
        if isinstance(value, bool):
            ALLOW_COMMAND_CHAINING = value
        else:
            ALLOW_COMMAND_CHAINING = value.lower() in ["true", "yes", "y", "1", "on", "enabled"]
        print_colored(f"Command chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}", MS_GREEN)
    elif key == "stream":
        if isinstance(value, bool):
            STREAM_OUTPUT = value
        else:
            STREAM_OUTPUT = value.lower() in ["true", "yes", "y", "1", "on", "enabled"]
        print_colored(f"Output streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}", MS_GREEN)
    elif key == "clipboard":
        if isinstance(value, bool):
            USE_CLIPBOARD = value
        else:
            USE_CLIPBOARD = value.lower() in ["true", "yes", "y", "1", "on", "enabled"]
        print_colored(f"Clipboard integration: {'Enabled' if USE_CLIPBOARD else 'Disabled'}", MS_GREEN)
    elif key == "async":
        if isinstance(value, bool):
            USE_ASYNC_EXECUTION = value
        else:
            USE_ASYNC_EXECUTION = value.lower() in ["true", "yes", "y", "1", "on", "enabled"]
        print_colored(f"Async execution: {'Enabled' if USE_ASYNC_EXECUTION else 'Disabled'}", MS_GREEN)
    elif key == "auto_clear" or key == "autoclear":
        if isinstance(value, bool):
            AUTO_CLEAR = value
        else:
            AUTO_CLEAR = value.lower() in ["true", "yes", "y", "1", "on", "enabled"]
        print_colored(f"Auto-clear terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_GREEN)
    else:
        print_colored(f"Unknown configuration key: {key}", MS_YELLOW)
        print_colored("Use 'set' without arguments to see available options.", MS_YELLOW)

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

        # Ask for confirmation before deleting
        confirm = input(f"{MS_YELLOW}Are you sure you want to delete template '{name}'? (y/n):{MS_RESET} ").lower()
        if confirm != 'y':
            print_colored("Deletion cancelled.", MS_YELLOW)
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
            execute_command(line)

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

        # Ask for confirmation before deleting
        confirm = input(f"{MS_YELLOW}Are you sure you want to delete group '{name}'? (y/n):{MS_RESET} ").lower()
        if confirm != 'y':
            print_colored("Deletion cancelled.", MS_YELLOW)
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

    # Initialize the shared asyncio event loop for background commands
    if USE_ASYNC_EXECUTION:
        init_async_loop()

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
            # Add visual separation between commands for better readability
            print("\n" + "-" * 60)

            # Create a persistent prompt indicator that shows background job status
            prompt_prefix = ""
            if background_processes:
                # Count running jobs
                running_jobs = sum(1 for job in background_processes.values()
                                  if job.get("status") == "running")
                if running_jobs > 0:
                    prompt_prefix = f"(bg:{running_jobs}) "

            # Simplified prompt that works in all environments
            prompt = f"{prompt_prefix}What would you like me to do? "

            if PROMPT_TOOLKIT_AVAILABLE:
                session = PromptSession(history=FileHistory(HISTORY_FILE))
                user_input = session.prompt(prompt)
            else:
                user_input = input(prompt)

            # Skip empty inputs
            if not user_input.strip():
                continue

            # Check for history execution with !N
            if user_input.startswith("!") and user_input[1:].isdigit():
                history_index = int(user_input[1:]) - 1
                if 0 <= history_index < len(history_items_cache):
                    history_command = history_items_cache[history_index]
                    print_colored(f"Executing history command: {history_command}", MS_CYAN)
                    user_input = history_command
                else:
                    print_colored(f"Invalid history index: {history_index+1}", MS_RED)
                    continue

            # Continue with the rest of the function
            # Check if this looks like a command or a task description
            if user_input.startswith("!") or any(user_input.startswith(cmd) for cmd in ["help", "exit", "quit", "clear", "history", "config", "set", "cd ", "pwd", "api-key", "templates", "groups", "verify", "chain", "auto-clear", "jobs", "kill ", "setup"]):
                # Handle as a built-in command
                process_user_command(user_input)
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

if __name__ == "__main__":
    main()
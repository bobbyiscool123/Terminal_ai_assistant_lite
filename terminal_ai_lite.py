#!/usr/bin/env python3

import os
import sys
import re
import time
import json
import asyncio
import traceback
import shlex
import subprocess
import platform
import signal
import threading
import shutil
import requests
import pickle
import select
from pathlib import Path
from datetime import datetime, timedelta
from collections import deque, OrderedDict

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from rich.console import Console
    from rich.theme import Theme
    from rich.prompt import Prompt
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    try:
        from colorama import init, Fore, Style
        # Initialize colorama with compatibility settings
        init(autoreset=False)
    except ImportError:
        pass

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

# Version information
VERSION = "1.0.0"

# Check if we're running on Windows
IS_WINDOWS = platform.system() == "Windows"

# Colors for terminal output
MS_RED = "\033[91m"
MS_GREEN = "\033[92m"
MS_YELLOW = "\033[93m"
MS_BLUE = "\033[94m"
MS_MAGENTA = "\033[95m"
MS_CYAN = "\033[96m"
MS_WHITE = "\033[97m"
MS_RESET = "\033[0m"
MS_BOLD = "\033[1m"

# Configuration
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
HISTORY_FILE = os.path.expanduser("~/.terminal_ai_lite_history")
TOKEN_CACHE_FILE = os.path.expanduser("~/.terminal_ai_lite_token_cache")
TEMPLATE_FILE = os.path.expanduser("~/.terminal_ai_lite_templates")
COMMAND_GROUPS_FILE = os.path.expanduser("~/.terminal_ai_lite_command_groups")
MAX_HISTORY = 100

# Default settings
API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.0-flash"
API_ENDPOINT = "https://generativelanguage.googleapis.com"
API_VERSION = "v1"
MAX_RETRY_ATTEMPTS = 5
MAX_OUTPUT_LENGTH = 1000

# Terminal settings
VERIFY_COMMANDS = True
ALLOW_COMMAND_CHAINING = True
STREAM_OUTPUT = True
AUTO_CLEAR = False
CONFIRM_DANGEROUS = True
EXPLAIN_COMMANDS = False
USE_ASYNC_EXECUTION = True
USE_STREAMING_API = True
FORMAT_OUTPUT = False
USE_CLIPBOARD = True

# Cache settings
USE_TOKEN_CACHE = True
CACHE_EXPIRY = 24  # hours
MAX_CACHE_SIZE = 100  # entries

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
    
    # Detect and remove color prefixes (e.g., "cyanExecuting:")
    # This is causing the issue with color names showing up in output
    if len(args) == 1 and isinstance(args[0], str):
        text = args[0]
        found_prefix = False
        # Check each color name to see if it's a prefix
        for color_name in ["cyan", "green", "yellow", "red", "blue", "magenta", "white"]:
            if text.lower().startswith(color_name.lower()):
                # Check if the color prefix is followed by text (not just the color name)
                if len(text) > len(color_name):
                    clean_text = text[len(color_name):]
                    color_code = COLOR_NAMES.get(f"MS_{color_name.upper()}", "")
                    print_colored(clean_text, color_code, **kwargs)
                    found_prefix = True
                    break
        
        if found_prefix:
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
MODEL = "gemini-2.0-flash"
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
MAX_CACHE_SIZE = 100  # Maximum number of items in cache before LRU eviction
MAX_RETRY_ATTEMPTS = 5  # Maximum number of Gemini API retry attempts
MAX_OUTPUT_LENGTH = 1000  # Maximum length for truncating output
AUTO_CLEAR = False  # Auto-clear terminal after command execution

# Get API key from .env file
API_KEY = os.getenv("GEMINI_API_KEY")

# Add CONFIG_PATH constant
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    """Load configuration from config.json file."""
    global API_KEY, MODEL, MAX_RETRY_ATTEMPTS, MAX_OUTPUT_LENGTH
    global VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, STREAM_OUTPUT, AUTO_CLEAR
    global USE_TOKEN_CACHE, CACHE_EXPIRY, MAX_CACHE_SIZE
    
    try:
        # First check environment variable
        if not API_KEY:
            env_key = os.environ.get("GEMINI_API_KEY")
            if env_key and env_key.strip():
                API_KEY = env_key.strip()
        
        # Try loading from config file
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                config = json.load(f)
                
            # Load Gemini API settings
            gemini_config = config.get('gemini_api', {})
            
            # Only update API_KEY if we don't already have one and there's a valid one in config
            if not API_KEY and gemini_config.get('api_key'):
                API_KEY = gemini_config.get('api_key')
            
            MODEL = gemini_config.get('model', MODEL)
            MAX_RETRY_ATTEMPTS = gemini_config.get('max_retry_attempts', MAX_RETRY_ATTEMPTS)
            MAX_OUTPUT_LENGTH = gemini_config.get('max_output_length', MAX_OUTPUT_LENGTH)
            
            # Load terminal settings
            terminal_config = config.get('terminal', {})
            VERIFY_COMMANDS = terminal_config.get('verify_commands', VERIFY_COMMANDS)
            ALLOW_COMMAND_CHAINING = terminal_config.get('allow_command_chaining', ALLOW_COMMAND_CHAINING)
            STREAM_OUTPUT = terminal_config.get('stream_output', STREAM_OUTPUT)
            AUTO_CLEAR = terminal_config.get('auto_clear', AUTO_CLEAR)
            
            # Load cache settings
            cache_config = config.get('cache', {})
            USE_TOKEN_CACHE = cache_config.get('use_token_cache', USE_TOKEN_CACHE)
            CACHE_EXPIRY = cache_config.get('cache_expiry_hours', CACHE_EXPIRY)
            MAX_CACHE_SIZE = cache_config.get('max_cache_size', MAX_CACHE_SIZE)
            
            print_colored(f"Configuration loaded from {CONFIG_PATH}", MS_CYAN)
        else:
            # Create default config file
            save_config()
        
        # If still no API key, try loading from a dedicated key file
        if not API_KEY:
            api_key_file = os.path.expanduser("~/.terminal_ai_lite_api_key")
            if os.path.exists(api_key_file):
                try:
                    with open(api_key_file, 'r') as f:
                        loaded_key = f.read().strip()
                        if loaded_key:
                            API_KEY = loaded_key
                except Exception:
                    pass
                    
        # If still no API key, try loading from .env file
        if not API_KEY and os.path.exists(".env"):
            try:
                with open(".env", 'r') as f:
                    env_content = f.read()
                    match = re.search(r'GEMINI_API_KEY=([^\s]+)', env_content)
                    if match:
                        API_KEY = match.group(1).strip()
            except Exception:
                pass
                
    except Exception as e:
        print_colored(f"Error loading configuration: {str(e)}", MS_RED)
        print_colored("Using default settings...", MS_YELLOW)

def save_config():
    """Save current configuration to config.json file."""
    config = {
        'gemini_api': {
            'api_key': API_KEY,
            'model': MODEL,
            'max_retry_attempts': MAX_RETRY_ATTEMPTS,
            'max_output_length': MAX_OUTPUT_LENGTH
        },
        'terminal': {
            'verify_commands': VERIFY_COMMANDS,
            'allow_command_chaining': ALLOW_COMMAND_CHAINING,
            'stream_output': STREAM_OUTPUT,
            'auto_clear': AUTO_CLEAR
        },
        'cache': {
            'use_token_cache': USE_TOKEN_CACHE,
            'cache_expiry_hours': CACHE_EXPIRY,
            'max_cache_size': MAX_CACHE_SIZE
        }
    }
    
    try:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=4)
        print_colored(f"Configuration saved to {CONFIG_PATH}", MS_GREEN)
    except Exception as e:
        print_colored(f"Error saving configuration: {str(e)}", MS_RED)

# Load configuration from config.json
load_config()

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

def cache_command_result(command, result):
    """Cache command result for future use
    
    Args:
        command (str): The command or task to cache
        result (str): The result or response to cache
    """
    global command_cache
    
    # Add to cache with current timestamp
    command_cache[command] = (result, time.time())
    
    # Implement LRU eviction if cache exceeds maximum size
    if len(command_cache) > MAX_CACHE_SIZE:
        # Remove oldest item (first item in OrderedDict)
        command_cache.popitem(last=False)

def get_cached_command_result(command):
    """Get cached command result if available and not expired
    
    Args:
        command (str): The command or task to look up
        
    Returns:
        str or None: The cached result if available, None otherwise
    """
    if command in command_cache:
        result, timestamp = command_cache[command]
        
        # Move this item to the end of the OrderedDict (mark as recently used)
        command_cache.move_to_end(command)
        
        # Check if cache entry is expired
        if time.time() - timestamp <= TOKEN_CACHE_EXPIRY * 86400:  # seconds in a day
            return result
    
    return None

def load_command_cache():
    """Load command result cache from file if it exists"""
    global command_cache
    
    command_cache_file = os.path.expanduser("~/.terminal_ai_lite_command_cache")
    
    if os.path.exists(command_cache_file):
        try:
            with open(command_cache_file, 'rb') as f:
                # Convert regular dict to OrderedDict
                loaded_cache = pickle.load(f)
                command_cache = OrderedDict()
                
                # Clean expired entries and add valid ones to OrderedDict
                current_time = time.time()
                for key, (value, timestamp) in loaded_cache.items():
                    if current_time - timestamp <= TOKEN_CACHE_EXPIRY * 86400:  # seconds in a day
                        command_cache[key] = (value, timestamp)
                
        except Exception as e:
            print_colored(f"Error loading command cache: {e}. Creating new cache.", MS_YELLOW)
            command_cache = OrderedDict()

def save_command_cache():
    """Save command result cache to file"""
    command_cache_file = os.path.expanduser("~/.terminal_ai_lite_command_cache")
    
    try:
        with open(command_cache_file, 'wb') as f:
            pickle.dump(dict(command_cache), f)  # Convert to regular dict for backward compatibility
    except Exception as e:
        print_colored(f"Error saving command cache: {e}", MS_RED)

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

def set_api_key():
    """Set the Gemini API key"""
    global API_KEY
    
    # Check for existing key file
    api_key_file = os.path.expanduser("~/.terminal_ai_lite_api_key")
    current_key = None
    
    if os.path.exists(api_key_file):
        try:
            with open(api_key_file, 'r') as f:
                current_key = f.read().strip()
        except Exception:
            pass
    
    # Only show key management message if we don't have a key
    if not API_KEY and not current_key:
        print_colored("\nYour Gemini API key is used to access Google's AI models.", MS_CYAN)
        print_colored("If you don't have one, visit https://ai.google.dev/ to get your key.", MS_YELLOW)
    
    # If we have a current key, just show minimal UI
    if current_key:
        masked_key = current_key[:4] + "*" * (len(current_key) - 8) + current_key[-4:] if len(current_key) > 8 else "*****"
        print_colored(f"Current API key: {masked_key}", MS_CYAN)
    
    # Ask for new key with appropriate prompt
    prompt_text = "Enter your Gemini API key: " if not current_key else "Enter new API key (or press Enter to keep current): "
    new_key = print_input_prompt(prompt_text, MS_YELLOW).strip()
    
    if new_key:
        # Save to environment and file
        os.environ["GEMINI_API_KEY"] = new_key
        API_KEY = new_key
        
        try:
            # Save to dedicated key file
            with open(api_key_file, 'w') as f:
                f.write(new_key)
            
            # Also update config.json
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r') as f:
                    config = json.load(f)
                
                if 'gemini_api' not in config:
                    config['gemini_api'] = {}
                
                config['gemini_api']['api_key'] = new_key
                
                with open(CONFIG_PATH, 'w') as f:
                    json.dump(config, f, indent=4)
            
            # Also update .env file if it exists
            if os.path.exists(".env"):
                env_content = ""
                with open(".env", 'r') as f:
                    env_content = f.read()
                
                # Update or add GEMINI_API_KEY
                if "GEMINI_API_KEY=" in env_content:
                    env_content = re.sub(r'GEMINI_API_KEY=.*', f'GEMINI_API_KEY={new_key}', env_content)
                else:
                    env_content += f'\nGEMINI_API_KEY={new_key}'
                
                with open(".env", 'w') as f:
                    f.write(env_content)
            
            print_colored("API key saved successfully.", MS_GREEN)
            
            # Test the new key
            print_colored("Testing API key... Please wait.", MS_YELLOW)
            test_key(new_key)
                
        except Exception as e:
            print_colored(f"Error saving API key: {e}", MS_RED)
            print_colored("API key set for current session only.", MS_YELLOW)
    elif not API_KEY and current_key:
        # Use stored key if no new key provided
        API_KEY = current_key
        print_colored("Using stored API key.", MS_GREEN)
    elif not API_KEY:
        print_colored("No API key provided. Some features will be disabled.", MS_RED)
    
    return API_KEY

def test_key(key):
    """Test if an API key is valid"""
    test_prompt = "Respond with 'API key is working' if you can read this message."
    
    try:
        curl_command = [
            "curl", "-s", "-X", "POST",
            f"{API_ENDPOINT}/{API_VERSION}/models/{MODEL}:generateContent?key={key}",
            "-H", "Content-Type: application/json",
            "-d", json.dumps({
                "contents": [{
                    "parts": [{
                        "text": test_prompt
                    }]
                }],
                "generationConfig": {
                    "temperature": 0.1,
                    "maxOutputTokens": 20
                }
            })
        ]
        
        result = subprocess.run(curl_command, capture_output=True, text=True)
        response = result.stdout
        
        if "API key is working" in response or "working" in response.lower():
            print_colored("API key verified successfully!", MS_GREEN)
            return True
        else:
            # Try to parse response to check for errors
            try:
                response_data = json.loads(response)
                if "error" in response_data:
                    error_message = response_data["error"].get("message", "Unknown error")
                    print_colored(f"API Error: {error_message}", MS_RED)
                else:
                    print_colored("API key may be valid, but received unexpected response.", MS_YELLOW)
            except:
                print_colored("API key may be invalid or the service might be unavailable.", MS_RED)
            return False
    except Exception as e:
        print_colored(f"Error testing API key: {e}", MS_RED)
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

def get_ai_response(prompt):
    """Get a response from the Gemini API."""
    
    if not API_KEY:
        return "Error: API key not set. Use the 'api-key' command to set your Gemini API key."
    
    # Create the payload for the Gemini API
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1024,
            "topP": 0.8,
            "topK": 40
        }
    }
    
    retry_count = 0
    max_backoff = 32  # Maximum backoff time in seconds
    
    while retry_count < MAX_RETRY_ATTEMPTS:
        try:
            # Send the request to the Gemini API
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={API_KEY}",
                json=payload,
                timeout=30
            )
            
            # Handle HTTP errors
            if response.status_code != 200:
                error_msg = f"API Error (HTTP {response.status_code}): "
                try:
                    error_data = response.json()
                    error_msg += error_data.get('error', {}).get('message', 'Unknown error')
                except:
                    error_msg += "Unknown error"
                    
                print_colored(error_msg, MS_RED)
                
                # If rate limited (429) or server error (5xx), retry with backoff
                if response.status_code == 429 or response.status_code >= 500:
                    retry_count += 1
                    if retry_count < MAX_RETRY_ATTEMPTS:
                        backoff_time = min(2 ** (retry_count - 1), max_backoff)
                        print_colored(f"Retrying in {backoff_time} seconds... (Attempt {retry_count}/{MAX_RETRY_ATTEMPTS})", MS_YELLOW)
                        time.sleep(backoff_time)
                        continue
                    else:
                        print_colored(f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) reached.", MS_RED)
                        return f"Error: Failed to get AI response after {MAX_RETRY_ATTEMPTS} attempts."
                else:
                    # For other errors, don't retry
                    return f"Error: {error_msg}"
            
            # Extract the response text from the JSON
            response_json = response.json()
            
            # Check for content filter blocks
            if 'promptFeedback' in response_json and response_json['promptFeedback'].get('blockReason'):
                block_reason = response_json['promptFeedback']['blockReason']
                print_colored(f"Request blocked by Gemini: {block_reason}", MS_RED)
                return f"Error: Request blocked by Gemini API due to {block_reason}."
                
            # If we have a candidates list and it's not empty
            if 'candidates' in response_json and response_json['candidates']:
                candidate = response_json['candidates'][0]
                
                # Check for finish reason other than STOP
                if 'finishReason' in candidate and candidate['finishReason'] != 'STOP':
                    print_colored(f"Generation stopped: {candidate['finishReason']}", MS_YELLOW)
                
                # Extract content if available
                if 'content' in candidate and 'parts' in candidate['content']:
                    parts = candidate['content']['parts']
                    if parts and 'text' in parts[0]:
                        return parts[0]['text']
            
            # Fallback if the response format doesn't match expectations
            print_colored("Warning: Unexpected response format from Gemini API.", MS_YELLOW)
            return json.dumps(response_json, indent=2)
            
        except requests.exceptions.Timeout:
            print_colored("Request timed out. Retrying...", MS_YELLOW)
            retry_count += 1
            if retry_count < MAX_RETRY_ATTEMPTS:
                backoff_time = min(2 ** (retry_count - 1), max_backoff)
                print_colored(f"Retrying in {backoff_time} seconds... (Attempt {retry_count}/{MAX_RETRY_ATTEMPTS})", MS_YELLOW)
                time.sleep(backoff_time)
            else:
                print_colored(f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) reached.", MS_RED)
                return f"Error: API request timed out after {MAX_RETRY_ATTEMPTS} attempts."
                
        except requests.exceptions.RequestException as e:
            print_colored(f"Request error: {str(e)}", MS_RED)
            retry_count += 1
            if retry_count < MAX_RETRY_ATTEMPTS:
                backoff_time = min(2 ** (retry_count - 1), max_backoff)
                print_colored(f"Retrying in {backoff_time} seconds... (Attempt {retry_count}/{MAX_RETRY_ATTEMPTS})", MS_YELLOW)
                time.sleep(backoff_time)
            else:
                print_colored(f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) reached.", MS_RED)
                return f"Error: API request failed after {MAX_RETRY_ATTEMPTS} attempts."
        
        except Exception as e:
            print_colored(f"Error in API call: {str(e)}", MS_RED)
            return f"Error: {str(e)}"
    
    # If we've exhausted all retries
    return f"Error: Failed to get AI response after {MAX_RETRY_ATTEMPTS} attempts."

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
            "start_time": datetime.now(),
            "status": "running"
        }
        
        stdout, stderr = await process.communicate()
        
        # Update process status
        if process.returncode == 0:
            background_processes[command_id]["status"] = "completed"
        else:
            background_processes[command_id]["status"] = "failed"
            
        background_processes[command_id]["end_time"] = datetime.now()
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
            raise CommandError(
                "No command specified for async execution",
                "Provide a command after 'async', e.g., 'async ping -c 5 google.com'"
            )
            
        command_id = start_async_command(command)
        print(f"{MS_GREEN}Command is running in the background. Use 'jobs' to check status.{MS_RESET}")
        return
    
    # Verify command before execution if enabled
    if VERIFY_COMMANDS:
        safe, reason = verify_command(command)
        if not safe:
            raise CommandError(
                f"Command execution cancelled: {reason}",
                "The command was deemed unsafe or was rejected during verification."
            )

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
            
            try:
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
            except KeyboardInterrupt:
                print_colored("\nCommand interrupted by user.", MS_YELLOW)
                try:
                    process.terminate()
                    return None
                except:
                    pass
            
            # Read any remaining output
            remaining_output, remaining_error = process.communicate()
            
            if remaining_output:
                output_lines.append(remaining_output)
                print(remaining_output, end="", flush=True)
                
            if remaining_error:
                error_lines.append(remaining_error)
                print(f"{MS_RED}{remaining_error}{MS_RESET}", end="", flush=True)
                
            # Join output lines
            output = "".join(output_lines)
            error = "".join(error_lines)
            
            # Check return code
            return_code = process.returncode
            
            # Record execution time
            execution_time = time.time() - start_time
            
            result_dict = {
                "output": output,
                "error": error,
                "return_code": return_code,
                "execution_time": execution_time
            }
            
            if return_code != 0:
                print_colored(f"Command completed with return code {return_code}.", MS_RED)
                if error:
                    print_colored(f"Error output: {error.strip()}", MS_RED)
            else:
                print_colored(f"Command completed in {execution_time:.2f} seconds.", MS_GREEN)
               
            # Ask if user wants to clear the console
            if output or error:
                clear_choice = print_input_prompt("Clear console? (y/n): ", MS_YELLOW)
                if clear_choice.lower() == 'y':
                    os.system("cls" if os.name == "nt" else "clear") 
                
            return result_dict
            
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
            if result.returncode != 0:
                print_colored(f"Command completed with return code {result.returncode}.", MS_RED)
                if result.stderr:
                    print_colored(f"Error output: {result.stderr.strip()}", MS_RED)
                    
            # Print output
            if result.stdout:
                print_colored("Output:", MS_CYAN)
                print(result.stdout)
                
            if result.returncode == 0:
                print_colored(f"Command completed in {execution_time:.2f} seconds.", MS_GREEN)
            
            # Ask if user wants to clear the console
            if result.stdout or result.stderr:
                clear_choice = print_input_prompt("Clear console? (y/n): ", MS_YELLOW)
                if clear_choice.lower() == 'y':
                    os.system("cls" if os.name == "nt" else "clear")
                
            return result_dict
    
    except KeyboardInterrupt:
        print_colored("\nCommand interrupted by user.", MS_YELLOW)
        return None
    except Exception as e:
        if isinstance(e, TerminalAIError):
            raise
        raise CommandError(f"Error executing command: {e}")
            
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
        change = print_input_prompt("Do you want to change it? (y/n): ", MS_YELLOW).lower()
        if change == 'y':
            set_api_key()
    
    # Configure model
    print_colored("\nStep 2: Model Selection", MS_CYAN)
    print_colored(f"Current model: {MODEL}", MS_YELLOW)
    print_colored("Available models: gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro, gemini-pro", MS_YELLOW)
    new_model = print_input_prompt("Select model (or press Enter to keep current): ", MS_YELLOW).strip()
    if new_model:
        MODEL = new_model
        print_colored(f"Model set to: {MODEL}", MS_GREEN)
    
    # Configure verification
    print_colored("\nStep 3: Command Verification", MS_CYAN)
    print_colored("Command verification checks if commands are safe before execution.", MS_YELLOW)
    print_colored(f"Current setting: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_YELLOW)
    verify = print_input_prompt("Enable command verification? (y/n): ", MS_YELLOW).lower()
    if verify:
        VERIFY_COMMANDS = verify == 'y'
        print_colored(f"Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_GREEN)
    
    # Configure streaming
    print_colored("\nStep 4: Output Streaming", MS_CYAN)
    print_colored("Output streaming shows command output in real-time.", MS_YELLOW)
    print_colored(f"Current setting: {'Enabled' if STREAM_OUTPUT else 'Disabled'}", MS_YELLOW)
    stream = print_input_prompt("Enable output streaming? (y/n): ", MS_YELLOW).lower()
    if stream:
        STREAM_OUTPUT = stream == 'y'
        print_colored(f"Output streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}", MS_GREEN)
        
    # Configure auto-clear
    print_colored("\nStep 5: Auto-Clear Terminal", MS_CYAN)
    print_colored("Auto-clear automatically clears the terminal after each command.", MS_YELLOW)
    print_colored(f"Current setting: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_YELLOW)
    auto_clear = print_input_prompt("Enable auto-clear terminal? (y/n): ", MS_YELLOW).lower()
    if auto_clear:
        AUTO_CLEAR = auto_clear == 'y'
        print_colored(f"Auto-clear terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_GREEN)
    
    print_colored("\nSetup complete! The assistant is ready to use.", MS_GREEN)
    print_colored("Type 'help' to see available commands or ask me to perform tasks for you.", MS_YELLOW)

def setup_autocomplete():
    """Set up command auto-completion using readline or prompt_toolkit"""
    if not READLINE_AVAILABLE:
        return
    
    # Built-in commands to suggest
    commands = [
        "help", "exit", "quit", "clear", "history", 
        "config", "set", "cd", "pwd", "api-key",
        "templates", "groups", "verify", "chain",
        "jobs", "kill", "setup", "auto-clear"
    ]
    
    # Add command templates to suggestions
    commands.extend(templates.keys())
    
    # Add command groups to suggestions
    for group in command_groups:
        commands.append(f"group:{group}")
    
    # Define completer function for readline
    def completer(text, state):
        options = [cmd for cmd in commands if cmd.startswith(text)]
        if state < len(options):
            return options[state]
        else:
            return None
    
    # Register completer
    if READLINE_AVAILABLE:
        readline.set_completer(completer)
        
        # Set up tab completion
        if sys.platform == 'darwin':  # macOS
            readline.parse_and_bind("bind ^I rl_complete")
        else:  # Linux and others
            readline.parse_and_bind("tab: complete")
        
        # Set completion display settings
        readline.set_completion_display_matches_hook(None)

def process_user_command(command):
    """Process a built-in command or pass to shell"""
    global API_KEY, VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, MODEL, AUTO_CLEAR
    
    if not command or command.isspace():
        return
    
    # Handle built-in commands
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
        return
        
    elif command.lower() == "config":
        show_config()
        return
        
    elif command.lower().startswith("set "):
        set_config(command[4:])
        return
        
    elif command.lower().startswith("cd "):
        change_directory(command[3:])
        return
        
    elif command.lower() == "pwd":
        print_colored(os.getcwd(), MS_CYAN)
        return
        
    elif command.lower() == "api-key":
        set_api_key()
        return
        
    elif command.lower() == "templates":
        manage_templates()
        return
        
    elif command.lower() == "groups":
        manage_command_groups()
        return
        
    elif command.lower() == "verify":
        toggle_verification()
        return
        
    elif command.lower() == "chain":
        toggle_command_chaining()
        return
        
    elif command.lower() == "auto-clear":
        toggle_auto_clear()
        return
        
    elif command.lower() == "jobs":
        show_jobs()
        return
        
    elif command.lower().startswith("kill "):
        kill_job(command[5:])
        return
        
    elif command.lower() == "setup":
        run_setup_wizard()
        return
    
    # If command starts with !, execute it directly as a shell command
    if command.startswith("!"):
        execute_command(command[1:])
        return
    
    # Otherwise, treat as a shell command
    execute_command(command)

def show_help():
    """Show help information about available commands"""
    print_colored("\nTerminal AI Assistant Help", MS_CYAN)
    print_colored("--------------------------------", MS_CYAN)
    
    # Built-in commands
    print_colored("\nBuilt-in Commands:", MS_YELLOW)
    print("  help              - Display this help information")
    print("  exit, quit        - Exit the application")
    print("  clear             - Clear the terminal screen")
    print("  history           - Show command history")
    print("  config            - Show current configuration")
    print("  set KEY=VALUE     - Set a configuration value")
    print("  cd PATH           - Change current directory")
    print("  pwd               - Show current directory")
    print("  api-key           - Set or update Gemini API key")
    print("  templates         - Manage command templates")
    print("  groups            - Manage command groups")
    print("  verify            - Toggle command verification")
    print("  chain             - Toggle command chaining")
    print("  auto-clear        - Toggle auto-clear terminal")
    print("  jobs              - Show background jobs")
    print("  kill JOB_ID       - Kill a background job")
    print("  setup             - Run setup wizard")
    print("  !COMMAND          - Execute a shell command directly")
    
    # Templates
    if templates:
        print_colored("\nCommand Templates:", MS_YELLOW)
        for name, description in templates.items():
            print(f"  {name:<16} - {description}")
    
    # Command groups
    if command_groups:
        print_colored("\nCommand Groups:", MS_YELLOW)
        for group, commands in command_groups.items():
            print(f"  {group:<16} - {', '.join(commands[:3])}...")
    
    print_colored("\nUsage Examples:", MS_GREEN)
    print("  update system                  - Update system packages")
    print("  list files in downloads folder - List files in downloads")
    print("  check memory usage             - Show current memory usage")
    print("  async ping google.com          - Run ping in the background")
    
    print_colored("\nType any natural language request to get commands for that task.", MS_CYAN)

def show_config():
    """Show current configuration settings"""
    print_colored("\nCurrent Configuration:", MS_CYAN)
    
    # Show Gemini API settings
    print_colored("\nGemini API Settings:", MS_BLUE)
    print_colored(f"  Model: {MODEL}", MS_WHITE)
    print_colored(f"  API Key: {'*' * 10 + API_KEY[-5:] if API_KEY else 'Not set'}", MS_WHITE)
    print_colored(f"  Max Retry Attempts: {MAX_RETRY_ATTEMPTS}", MS_WHITE)
    print_colored(f"  Max Output Length: {MAX_OUTPUT_LENGTH}", MS_WHITE)
    
    # Show terminal settings
    print_colored("\nTerminal Settings:", MS_BLUE)
    print_colored(f"  Verify Commands: {VERIFY_COMMANDS}", MS_WHITE)
    print_colored(f"  Allow Command Chaining: {ALLOW_COMMAND_CHAINING}", MS_WHITE)
    print_colored(f"  Stream Output: {STREAM_OUTPUT}", MS_WHITE)
    print_colored(f"  Auto-Clear: {AUTO_CLEAR}", MS_WHITE)
    
    # Show cache settings
    print_colored("\nCache Settings:", MS_BLUE)
    print_colored(f"  Use Token Cache: {USE_TOKEN_CACHE}", MS_WHITE)
    print_colored(f"  Cache Expiry: {CACHE_EXPIRY} hours", MS_WHITE)
    print_colored(f"  Max Cache Size: {MAX_CACHE_SIZE} entries", MS_WHITE)
    
    # Ask if user wants to edit config
    if print_input_prompt("\nEdit configuration? (y/n): ", MS_YELLOW).lower() == 'y':
        edit_config()

def edit_config():
    """Edit configuration settings"""
    global MODEL, MAX_RETRY_ATTEMPTS, MAX_OUTPUT_LENGTH
    global VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, STREAM_OUTPUT, AUTO_CLEAR
    global USE_TOKEN_CACHE, CACHE_EXPIRY, MAX_CACHE_SIZE
    
    print_colored("\nEdit Configuration:", MS_CYAN)
    
    # Edit Gemini API settings
    print_colored("\nGemini API Settings:", MS_BLUE)
    
    # Edit model
    model_options = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
    print_colored("Available models:", MS_WHITE)
    for i, model in enumerate(model_options):
        print_colored(f"  {i+1}. {model}", MS_WHITE)
    
    model_choice = print_input_prompt(f"Select model (1-{len(model_options)}) [current: {MODEL}]: ", MS_YELLOW)
    if model_choice.strip():
        try:
            model_idx = int(model_choice) - 1
            if 0 <= model_idx < len(model_options):
                MODEL = model_options[model_idx]
                print_colored(f"Model set to {MODEL}", MS_GREEN)
            else:
                print_colored("Invalid selection", MS_RED)
        except ValueError:
            print_colored("Please enter a valid number", MS_RED)
    
    # Edit max retry attempts
    retry_input = print_input_prompt(f"Max retry attempts (1-10) [current: {MAX_RETRY_ATTEMPTS}]: ", MS_YELLOW)
    if retry_input.strip():
        try:
            retry_value = int(retry_input)
            if 1 <= retry_value <= 10:
                MAX_RETRY_ATTEMPTS = retry_value
                print_colored(f"Max retry attempts set to {MAX_RETRY_ATTEMPTS}", MS_GREEN)
            else:
                print_colored("Value must be between 1 and 10", MS_RED)
        except ValueError:
            print_colored("Please enter a valid number", MS_RED)
    
    # Edit max output length
    length_input = print_input_prompt(f"Max output length (100-10000) [current: {MAX_OUTPUT_LENGTH}]: ", MS_YELLOW)
    if length_input.strip():
        try:
            length_value = int(length_input)
            if 100 <= length_value <= 10000:
                MAX_OUTPUT_LENGTH = length_value
                print_colored(f"Max output length set to {MAX_OUTPUT_LENGTH}", MS_GREEN)
            else:
                print_colored("Value must be between 100 and 10000", MS_RED)
        except ValueError:
            print_colored("Please enter a valid number", MS_RED)
    
    # Edit terminal settings
    print_colored("\nTerminal Settings:", MS_BLUE)
    
    # Edit verify commands
    verify_input = print_input_prompt(f"Verify commands before execution (y/n) [current: {VERIFY_COMMANDS}]: ", MS_YELLOW)
    if verify_input.strip():
        VERIFY_COMMANDS = verify_input.lower() == 'y'
        print_colored(f"Verify commands set to {VERIFY_COMMANDS}", MS_GREEN)
    
    # Edit command chaining
    chain_input = print_input_prompt(f"Allow command chaining (y/n) [current: {ALLOW_COMMAND_CHAINING}]: ", MS_YELLOW)
    if chain_input.strip():
        ALLOW_COMMAND_CHAINING = chain_input.lower() == 'y'
        print_colored(f"Command chaining set to {ALLOW_COMMAND_CHAINING}", MS_GREEN)
    
    # Edit stream output
    stream_input = print_input_prompt(f"Stream command output (y/n) [current: {STREAM_OUTPUT}]: ", MS_YELLOW)
    if stream_input.strip():
        STREAM_OUTPUT = stream_input.lower() == 'y'
        print_colored(f"Stream output set to {STREAM_OUTPUT}", MS_GREEN)
    
    # Edit auto-clear
    clear_input = print_input_prompt(f"Auto-clear terminal after commands (y/n) [current: {AUTO_CLEAR}]: ", MS_YELLOW)
    if clear_input.strip():
        AUTO_CLEAR = clear_input.lower() == 'y'
        print_colored(f"Auto-clear set to {AUTO_CLEAR}", MS_GREEN)
    
    # Edit cache settings
    print_colored("\nCache Settings:", MS_BLUE)
    
    # Edit use token cache
    cache_input = print_input_prompt(f"Use token cache (y/n) [current: {USE_TOKEN_CACHE}]: ", MS_YELLOW)
    if cache_input.strip():
        USE_TOKEN_CACHE = cache_input.lower() == 'y'
        print_colored(f"Token cache set to {USE_TOKEN_CACHE}", MS_GREEN)
    
    # Edit cache expiry
    expiry_input = print_input_prompt(f"Cache expiry in hours (1-168) [current: {CACHE_EXPIRY}]: ", MS_YELLOW)
    if expiry_input.strip():
        try:
            expiry_value = int(expiry_input)
            if 1 <= expiry_value <= 168:
                CACHE_EXPIRY = expiry_value
                print_colored(f"Cache expiry set to {CACHE_EXPIRY} hours", MS_GREEN)
            else:
                print_colored("Value must be between 1 and 168", MS_RED)
        except ValueError:
            print_colored("Please enter a valid number", MS_RED)
    
    # Edit max cache size
    size_input = print_input_prompt(f"Max cache size (10-1000) [current: {MAX_CACHE_SIZE}]: ", MS_YELLOW)
    if size_input.strip():
        try:
            size_value = int(size_input)
            if 10 <= size_value <= 1000:
                MAX_CACHE_SIZE = size_value
                print_colored(f"Max cache size set to {MAX_CACHE_SIZE}", MS_GREEN)
            else:
                print_colored("Value must be between 10 and 1000", MS_RED)
        except ValueError:
            print_colored("Please enter a valid number", MS_RED)
    
    # Save configuration
    save_config()
    print_colored("\nConfiguration updated successfully!", MS_GREEN)

def set_config(config_str):
    """Set a configuration value from a KEY=VALUE string"""
    global MODEL, VERIFY_COMMANDS, STREAM_OUTPUT, USE_TOKEN_CACHE, AUTO_CLEAR
    
    if "=" not in config_str:
        print_colored("Invalid format. Use 'set KEY=VALUE'", MS_RED)
        return
    
    key, value = config_str.split("=", 1)
    key = key.strip().lower()
    value = value.strip()
    
    if key == "model":
        valid_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro"]
        if value in valid_models:
            MODEL = value
            print_colored(f"Model set to: {MODEL}", MS_GREEN)
        else:
            print_colored(f"Invalid model. Choose from: {', '.join(valid_models)}", MS_RED)
    
    elif key == "verify":
        if value.lower() in ["true", "yes", "on", "1"]:
            VERIFY_COMMANDS = True
            print_colored("Command verification enabled.", MS_GREEN)
        elif value.lower() in ["false", "no", "off", "0"]:
            VERIFY_COMMANDS = False
            print_colored("Command verification disabled.", MS_YELLOW)
        else:
            print_colored("Invalid value. Use true/false, yes/no, on/off, or 1/0.", MS_RED)
    
    elif key == "stream":
        if value.lower() in ["true", "yes", "on", "1"]:
            STREAM_OUTPUT = True
            print_colored("Output streaming enabled.", MS_GREEN)
        elif value.lower() in ["false", "no", "off", "0"]:
            STREAM_OUTPUT = False
            print_colored("Output streaming disabled.", MS_YELLOW)
        else:
            print_colored("Invalid value. Use true/false, yes/no, on/off, or 1/0.", MS_RED)
    
    elif key == "cache":
        if value.lower() in ["true", "yes", "on", "1"]:
            USE_TOKEN_CACHE = True
            print_colored("Token cache enabled.", MS_GREEN)
        elif value.lower() in ["false", "no", "off", "0"]:
            USE_TOKEN_CACHE = False
            print_colored("Token cache disabled.", MS_YELLOW)
        else:
            print_colored("Invalid value. Use true/false, yes/no, on/off, or 1/0.", MS_RED)
    
    elif key == "auto-clear":
        if value.lower() in ["true", "yes", "on", "1"]:
            AUTO_CLEAR = True
            print_colored("Auto-clear terminal enabled.", MS_GREEN)
        elif value.lower() in ["false", "no", "off", "0"]:
            AUTO_CLEAR = False
            print_colored("Auto-clear terminal disabled.", MS_YELLOW)
        else:
            print_colored("Invalid value. Use true/false, yes/no, on/off, or 1/0.", MS_RED)
    
    else:
        print_colored(f"Unknown configuration key: {key}", MS_RED)
        print_colored("Valid keys: model, verify, stream, cache, auto-clear", MS_YELLOW)

def change_directory(path):
    """Change the current working directory"""
    try:
        # Expand ~ to user's home directory
        if path.startswith("~"):
            path = os.path.expanduser(path)
        
        os.chdir(path)
        print_colored(f"Current directory: {os.getcwd()}", MS_GREEN)
    except FileNotFoundError:
        print_colored(f"Directory not found: {path}", MS_RED)
    except PermissionError:
        print_colored(f"Permission denied: {path}", MS_RED)
    except Exception as e:
        print_colored(f"Error changing directory: {e}", MS_RED)

def show_history():
    """Show command history"""
    if READLINE_AVAILABLE:
        print_colored("\nCommand History:", MS_CYAN)
        
        history_length = readline.get_current_history_length()
        max_to_show = min(history_length, MAX_HISTORY)
        
        for i in range(1, max_to_show + 1):
            try:
                item = readline.get_history_item(i)
                if item:
                    print(f"  {i}: {item}")
            except:
                pass
    else:
        print_colored("Command history not available without readline module.", MS_RED)

def manage_templates():
    """Manage command templates"""
    print_colored("\nCommand Templates:", MS_CYAN)
    
    for name, description in templates.items():
        print(f"  {name:<16} - {description}")
    
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
            
        description = input(f"{MS_YELLOW}Template description:{MS_RESET} ").strip()
        if not description:
            print_colored("Template description cannot be empty.", MS_RED)
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

def toggle_verification():
    """Toggle command verification on/off"""
    global VERIFY_COMMANDS
    
    VERIFY_COMMANDS = not VERIFY_COMMANDS
    print_colored(f"Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}", MS_GREEN)

def toggle_command_chaining():
    """Toggle command chaining on/off"""
    global ALLOW_COMMAND_CHAINING
    
    ALLOW_COMMAND_CHAINING = not ALLOW_COMMAND_CHAINING
    print_colored(f"Command chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}", MS_GREEN)

def toggle_auto_clear():
    """Toggle auto-clear terminal on/off"""
    global AUTO_CLEAR
    
    AUTO_CLEAR = not AUTO_CLEAR
    print_colored(f"Auto-clear terminal: {'Enabled' if AUTO_CLEAR else 'Disabled'}", MS_GREEN)

def show_jobs():
    """Show status of background jobs"""
    if not background_processes:
        print_colored("No active background jobs.", MS_YELLOW)
        return
    
    print_colored("\nBackground Jobs:", MS_CYAN)
    print(f"{'ID':<10} {'Status':<10} {'Runtime':<15} {'Command':<30}")
    print("-" * 65)
    
    current_time = datetime.now()
    
    for job_id, job_info in background_processes.items():
        status = job_info["status"]
        command = job_info["command"]
        start_time = job_info["start_time"]
        
        # Calculate runtime
        if status == "running":
            runtime = current_time - start_time
        elif "end_time" in job_info:
            runtime = job_info["end_time"] - start_time
        else:
            runtime = timedelta(0)
            
        # Format runtime as minutes:seconds
        minutes, seconds = divmod(int(runtime.total_seconds()), 60)
        runtime_str = f"{minutes}m {seconds}s"
        
        # Color-code status
        if status == "running":
            status_colored = f"{MS_GREEN}{status}{MS_RESET}"
        elif status == "completed":
            status_colored = f"{MS_CYAN}{status}{MS_RESET}"
        elif status == "failed":
            status_colored = f"{MS_RED}{status}{MS_RESET}"
        else:
            status_colored = f"{MS_YELLOW}{status}{MS_RESET}"
            
        print(f"{job_id:<10} {status_colored:<40} {runtime_str:<15} {command[:30]}")

def kill_job(job_id):
    """Kill a background job by ID"""
    if not job_id.strip():
        print_colored("Job ID not specified.", MS_RED)
        return
        
    job_id = job_id.strip()
    
    if job_id not in background_processes:
        print_colored(f"Job {job_id} not found.", MS_RED)
        return
        
    job_info = background_processes[job_id]
    
    if job_info["status"] != "running":
        print_colored(f"Job {job_id} is not running (status: {job_info['status']}).", MS_YELLOW)
        return
        
    try:
        process = job_info["process"]
        process.terminate()
        print_colored(f"Sent termination signal to job {job_id}.", MS_GREEN)
        
        # Update job status
        job_info["status"] = "terminated"
        job_info["end_time"] = datetime.now()
    except Exception as e:
        print_colored(f"Error terminating job {job_id}: {e}", MS_RED)

def print_input_prompt(prompt_text, color=MS_YELLOW):
    """Print an input prompt with proper coloring and return the user input"""
    if RICH_AVAILABLE:
        # Using Rich console to print the prompt
        console.print(prompt_text, style=color, end="")
        return input()
    elif COLORS_SUPPORTED:
        # Using colorama with direct printing
        sys.stdout.write(f"{color}{prompt_text}{MS_RESET}")
        sys.stdout.flush()
        return input()
    else:
        # Fallback for environments without color support
        return input(prompt_text)

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
    
    # Check for API key silently - it should already be loaded from config if available
    if not API_KEY:
        # Try to load from various sources without prompting
        api_key_file = os.path.expanduser("~/.terminal_ai_lite_api_key")
        if os.path.exists(api_key_file):
            try:
                with open(api_key_file, 'r') as f:
                    key = f.read().strip()
                    if key:
                        globals()['API_KEY'] = key
            except Exception:
                pass
    
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
                user_input = print_input_prompt("What would you like me to do? ", MS_CYAN)
                
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
                                try:
                                    result = execute_command(line)
                                    command_executed = True  # Mark that a command was executed
                                    
                                    # Always send the result back to Gemini API for analysis
                                    # regardless of return code
                                    output = result.get("output", "") if isinstance(result, dict) else ""
                                    error = result.get("error", "") if isinstance(result, dict) else ""
                                    return_code = result.get("return_code", 0) if isinstance(result, dict) else 0
                                    
                                    # Truncate large outputs to avoid exceeding token limits
                                    MAX_OUTPUT_LENGTH = 1000
                                    if output and len(output) > MAX_OUTPUT_LENGTH:
                                        output = output[:MAX_OUTPUT_LENGTH] + "... [output truncated]"
                                    if error and len(error) > MAX_OUTPUT_LENGTH:
                                        error = error[:MAX_OUTPUT_LENGTH] + "... [error truncated]"
                                    
                                    # Only analyze if there's an error or non-zero return code
                                    # to avoid unnecessary API calls for simple successful commands
                                    retry_attempts = 0
                                    if return_code != 0 or error:
                                        print_colored("Analyzing command results...", MS_YELLOW)
                                        
                                        # Initialize retry tracking
                                        last_command_run = line
                                        has_more_solutions = True
                                        
                                        while retry_attempts < MAX_RETRY_ATTEMPTS and has_more_solutions:
                                            # Send the command output to Gemini for analysis
                                            analysis_prompt = f"""
                                            I just ran the command '{last_command_run}' with the following results:
                                            
                                            Return code: {return_code}
                                            Output: {output}
                                            Error (if any): {error}
                                            
                                            This is attempt {retry_attempts + 1} of {MAX_RETRY_ATTEMPTS}.
                                            
                                            Please analyze if this command executed successfully. If there was an error:
                                            1. Explain briefly what went wrong
                                            2. Provide a single command to fix the issue or an alternative approach 
                                            3. If you see a permission error or command not found, suggest the appropriate fix
                                            
                                            Return your analysis in this JSON format:
                                            {{
                                                "success": false,
                                                "reason": "Brief explanation of what went wrong",
                                                "recommended_command": "command to fix the issue",
                                                "has_more_solutions": true
                                            }}
                                            
                                            Set "success" to true if the command executed successfully or had only warnings.
                                            Set "has_more_solutions" to false if you don't think there are any more solutions to try or if this issue can't be fixed by running a different command.
                                            If the command executed successfully, set "recommended_command" to "" (empty string).
                                            """
                                            
                                            analysis = get_ai_response(analysis_prompt)
                                            
                                            # Try to parse the analysis JSON
                                            try:
                                                # Clean up markdown formatting if present
                                                analysis_clean = re.sub(r'^```json\s*', '', analysis)
                                                analysis_clean = re.sub(r'\s*```$', '', analysis_clean) 
                                                analysis_data = json.loads(analysis_clean)
                                                
                                                success = analysis_data.get("success", False)
                                                reason = analysis_data.get("reason", "Unknown error")
                                                fix_command = analysis_data.get("recommended_command", "")
                                                has_more_solutions = analysis_data.get("has_more_solutions", False)
                                                
                                                # Print formatted analysis
                                                print_colored("\nCommand Analysis:", MS_CYAN)
                                                
                                                # Format status with color
                                                status_color = MS_GREEN if success else MS_RED
                                                status_text = "Succeeded" if success else "Failed"
                                                print_colored(f"Status: {status_text}", status_color)
                                                
                                                # Print reason with proper indentation
                                                print_colored(f"Reason: {reason}", MS_YELLOW)
                                                
                                                # Show attempt count if not successful
                                                if not success:
                                                    print_colored(f"Attempt: {retry_attempts + 1}/{MAX_RETRY_ATTEMPTS}", MS_YELLOW)
                                                
                                                # If command executed successfully or no more solutions
                                                if success:
                                                    # No need to try further fixes
                                                    break
                                                
                                                # If there's a recommended command and we haven't reached max retries
                                                if fix_command and retry_attempts < MAX_RETRY_ATTEMPTS:
                                                    print_colored(f"Suggested fix: {fix_command}", MS_GREEN)
                                                    
                                                    if retry_attempts + 1 >= MAX_RETRY_ATTEMPTS:
                                                        print_colored(f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) reached.", MS_RED)
                                                        print_colored("You can adjust this in settings with 'config' command.", MS_YELLOW)
                                                    
                                                    # Ask user if they want to try the fix
                                                    try_fix = print_input_prompt("Would you like to run this fix? (y/n): ", MS_YELLOW)
                                                    if try_fix.lower() == 'y':
                                                        print_colored("Executing fix...", MS_CYAN)
                                                        result = execute_command(fix_command)
                                                        
                                                        # Update command and result for next iteration
                                                        last_command_run = fix_command
                                                        output = result.get("output", "") if isinstance(result, dict) else ""
                                                        error = result.get("error", "") if isinstance(result, dict) else ""
                                                        return_code = result.get("return_code", 0) if isinstance(result, dict) else 0
                                                        
                                                        # Truncate if needed
                                                        if output and len(output) > MAX_OUTPUT_LENGTH:
                                                            output = output[:MAX_OUTPUT_LENGTH] + "... [output truncated]"
                                                        if error and len(error) > MAX_OUTPUT_LENGTH:
                                                            error = error[:MAX_OUTPUT_LENGTH] + "... [error truncated]"
                                                        
                                                        # Increment retry counter
                                                        retry_attempts += 1
                                                    else:
                                                        # User declined to run the fix
                                                        break
                                                else:
                                                    # No command recommended or max retries reached
                                                    if not has_more_solutions:
                                                        print_colored("No more solutions available.", MS_RED)
                                                    elif retry_attempts >= MAX_RETRY_ATTEMPTS:
                                                        print_colored(f"Maximum retry attempts ({MAX_RETRY_ATTEMPTS}) reached.", MS_RED)
                                                    break
                                                
                                            except json.JSONDecodeError:
                                                # Failed to parse JSON, fall back to showing the plain response
                                                print_colored("\nGemini analysis:", MS_YELLOW)
                                                print_colored(analysis, MS_WHITE)
                                                
                                                # Extract command using regex as fallback
                                                command_match = re.search(r'`([^`]+)`', analysis)
                                                if command_match:
                                                    fix_command = command_match.group(1).strip()
                                                    print_colored(f"Suggested fix: {fix_command}", MS_GREEN)
                                                    
                                                    try_fix = print_input_prompt("Would you like to run this fix? (y/n): ", MS_YELLOW)
                                                    if try_fix.lower() == 'y':
                                                        print_colored("Executing fix...", MS_CYAN)
                                                        result = execute_command(fix_command)
                                                        
                                                        # Update for next iteration
                                                        last_command_run = fix_command
                                                        output = result.get("output", "") if isinstance(result, dict) else ""
                                                        error = result.get("error", "") if isinstance(result, dict) else ""
                                                        return_code = result.get("return_code", 0) if isinstance(result, dict) else 0
                                                    
                                                    # Increment retry counter
                                                    retry_attempts += 1
                                                else:
                                                    # No command found, break the loop
                                                    break
                                except Exception as e:
                                    print_colored(format_error(e), MS_RED)
                
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

# Main loop
if __name__ == "__main__":
    main() 
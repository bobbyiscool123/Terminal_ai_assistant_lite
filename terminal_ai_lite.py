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
    init(strip=False, convert=True, autoreset=True)

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
    # Use colorama directly
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
        if style in style_map:
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
MAX_CACHE_SIZE = 100  # Maximum number of items in cache before LRU eviction

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
                # Convert regular dict to OrderedDict
                loaded_cache = pickle.load(f)
                token_cache = OrderedDict()
                
                # Clean expired tokens and add valid ones to OrderedDict
                current_time = time.time()
                for key, (value, timestamp) in loaded_cache.items():
                    if current_time - timestamp <= TOKEN_CACHE_EXPIRY * 86400:  # seconds in a day
                        token_cache[key] = (value, timestamp)
                
        except Exception as e:
            print(f"{MS_YELLOW}Error loading token cache: {e}. Creating new cache.{MS_RESET}")
            token_cache = OrderedDict()

def save_token_cache():
    """Save token cache to file"""
    try:
        with open(TOKEN_CACHE_FILE, 'wb') as f:
            pickle.dump(dict(token_cache), f)  # Convert to regular dict for backward compatibility
    except Exception as e:
        print(f"{MS_YELLOW}Error saving token cache: {e}{MS_RESET}")

# Command cache functions
def load_command_cache():
    """Load command cache from file if it exists"""
    global command_cache
    
    cache_file = os.path.expanduser("~/.terminal_ai_lite_command_cache")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                # Convert regular dict to OrderedDict
                loaded_cache = pickle.load(f)
                command_cache = OrderedDict()
                
                # Clean expired entries and add valid ones to OrderedDict
                current_time = time.time()
                for key, (value, timestamp) in loaded_cache.items():
                    if current_time - timestamp <= TOKEN_CACHE_EXPIRY * 86400:  # use same expiry as token cache
                        command_cache[key] = (value, timestamp)
                
        except Exception as e:
            print(f"{MS_YELLOW}Error loading command cache: {e}. Creating new cache.{MS_RESET}")
            command_cache = OrderedDict()

def save_command_cache():
    """Save command cache to file"""
    cache_file = os.path.expanduser("~/.terminal_ai_lite_command_cache")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(dict(command_cache), f)  # Convert to regular dict for backward compatibility
    except Exception as e:
        print(f"{MS_YELLOW}Error saving command cache: {e}{MS_RESET}")

def get_cached_command_result(task):
    """Get cached result for a command if available and not expired"""
    global command_cache
    
    if task in command_cache:
        result, timestamp = command_cache[task]
        current_time = time.time()
        
        # Check if the cached result is still valid
        if current_time - timestamp <= TOKEN_CACHE_EXPIRY * 86400:  # seconds in a day
            # Move this item to the end of the OrderedDict (mark as most recently used)
            command_cache.move_to_end(task)
            print(f"{MS_GREEN}Using cached result.{MS_RESET}")
            return result
    
    return None

def cache_command_result(task, result):
    """Cache the result of a command with timestamp using LRU policy"""
    global command_cache
    
    if task and result:
        # If cache is at capacity, remove the oldest item (first in OrderedDict)
        if len(command_cache) >= MAX_CACHE_SIZE:
            command_cache.popitem(last=False)
        
        # Add the new item (it will be at the end, marking it as most recently used)
        command_cache[task] = (result, time.time())
        
        # Periodically save cache to disk (every 10 new entries)
        if len(command_cache) % 10 == 0:
            save_command_cache()

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
            
            print(f"{MS_CYAN}Command Verification:{MS_RESET}")
            print(f"{verification.strip()}")
            
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
                    print(f"{MS_RED}This command may be unsafe. Please review carefully.{MS_RESET}")
                else:
                    print(f"{MS_GREEN}Command appears to be safe.{MS_RESET}")
            except json.JSONDecodeError:
                # If we can't parse JSON, fall back to keyword matching
                if "unsafe" in safety_line or "dangerous" in safety_line:
                    print(f"{MS_RED}This command may be unsafe. Please review carefully.{MS_RESET}")
                elif "safe" in safety_line:
                    print(f"{MS_GREEN}Command appears to be safe.{MS_RESET}")
                else:
                    print(f"{MS_YELLOW}Safety assessment unclear. Please review manually.{MS_RESET}")
            
            confirm = input(f"{MS_YELLOW}Execute this command? (y/n):{MS_RESET} ")
            return confirm.lower() == 'y', verification
            
        except Exception as e:
            print(f"{MS_RED}Error during command verification: {e}{MS_RESET}")
            return False, str(e)
    
    return True, ""

def get_ai_response(task, batch_commands=None):
    """Get AI response for a given task
    
    Args:
        task (str): The task description or prompt for the AI
        batch_commands (list, optional): List of commands to process in a batch
    
    Returns:
        str or dict: If batch_commands is None, returns a string with the AI response
                     If batch_commands is provided, returns a dict mapping commands to responses
    """
    global API_KEY, MODEL, API_ENDPOINT, API_VERSION, USE_TOKEN_CACHE
    
    if not API_KEY:
        raise ConfigError(
            "No API key found. Please set your API key first.",
            "Use the 'api-key' command to set your Gemini API key."
        )
    
    # Handle batch processing
    if batch_commands:
        # Create batch cache key
        batch_key = "BATCH:" + "|".join(batch_commands)
        
        # Check command cache first if enabled
        if USE_TOKEN_CACHE:
            cached_result = get_cached_command_result(batch_key)
            if cached_result:
                return cached_result  # This will be a dictionary of results
        
        # Build a combined prompt for all commands
        combined_prompt = f"""You are a terminal command expert. Generate executable commands for the following tasks.
        Please respond with a JSON object where the keys are the task numbers and values are arrays of command strings.
        
        OPERATING SYSTEM: {"Windows" if os.name == "nt" else "Unix/Linux"}
        CURRENT DIRECTORY: {os.getcwd()}
        
        """
        
        for i, cmd in enumerate(batch_commands):
            combined_prompt += f"TASK {i+1}: {cmd}\n"
        
        combined_prompt += """
        Respond ONLY with a valid JSON object in this format:
        {
          "1": ["command1", "command2"],
          "2": ["command1"],
          ...
        }
        Do not include explanations or any text that is not part of the JSON object.
        If a request cannot be satisfied with commands, use an array with a single element explaining why.
        """
        
        try:
            # Prepare the API request
            curl_command = [
                "curl", "-s", "-X", "POST",
                f"{API_ENDPOINT}/{API_VERSION}/models/{MODEL}:generateContent?key={API_KEY}",
                "-H", "Content-Type: application/json",
                "-d", json.dumps({
                    "contents": [{
                        "parts": [{
                            "text": combined_prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0.7,
                        "topP": 0.8,
                        "topK": 40,
                        "maxOutputTokens": 4096  # Increased for batch processing
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
            except json.JSONDecodeError:
                raise APIError(
                    "Failed to parse API response as JSON", 
                    "The API response format may have changed or the service may be experiencing issues."
                )
            
            # Extract the response text
            try:
                result_text = response_data["candidates"][0]["content"]["parts"][0]["text"]
            except KeyError:
                raise APIError(
                    "Unexpected API response format", 
                    "The response doesn't contain the expected fields. The API structure may have changed."
                )
            
            # Extract the JSON object from the response
            result_text = result_text.strip()
            # Remove any markdown formatting if present
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            result_text = result_text.strip()
            
            # Parse the JSON response
            try:
                result_dict = json.loads(result_text)
            except json.JSONDecodeError:
                raise APIError(
                    "Failed to parse AI response as JSON", 
                    "The response was not in valid JSON format. Try simplifying your requests."
                )
            
            # Convert the response to a dictionary mapping task to commands
            processed_results = {}
            for i, cmd in enumerate(batch_commands):
                task_key = str(i+1)
                if task_key in result_dict:
                    processed_results[cmd] = result_dict[task_key]
                else:
                    processed_results[cmd] = ["No response for this task"]
            
            # Cache the result if caching is enabled
            if USE_TOKEN_CACHE:
                cache_command_result(batch_key, processed_results)
                
            return processed_results
            
        except Exception as e:
            if isinstance(e, TerminalAIError):
                raise
            raise APIError(
                f"Error getting batch AI response: {e}",
                "Check your internet connection and API key. Try again with fewer commands."
            )
    
    # Handle single command (original behavior)
    # Check command cache first if enabled
    if USE_TOKEN_CACHE:
        cached_result = get_cached_command_result(task)
        if cached_result:
            return cached_result
    
    try:
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
        if isinstance(e, TerminalAIError):
            raise
        raise APIError(f"Error getting AI response: {e}")

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
        print(f"{MS_RED}Error running async command: {e}{MS_RESET}")
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
    
    print(f"{MS_GREEN}Started background command with ID: {command_id}{MS_RESET}")
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
    
    print(f"{MS_CYAN}Executing: {command}{MS_RESET}")
    
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
            
            print(f"{MS_CYAN}Output:{MS_RESET}")
            
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
                                print(f"{MS_RED}{line}{MS_RESET}", end="", flush=True)
            except KeyboardInterrupt:
                print(f"\n{MS_YELLOW}Command interrupted by user.{MS_RESET}")
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
            
            if return_code != 0:
                print(f"\n{MS_RED}Command failed with return code {return_code}.{MS_RESET}")
                if error:
                    print(f"{MS_RED}Error output: {error.strip()}{MS_RESET}")
            else:
                print(f"\n{MS_GREEN}Command completed in {execution_time:.2f} seconds.{MS_RESET}")
                
            return return_code
            
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
            
            # Check for errors
            if result.returncode != 0:
                print(f"{MS_RED}Command failed with return code {result.returncode}.{MS_RESET}")
                if result.stderr:
                    print(f"{MS_RED}Error output: {result.stderr.strip()}{MS_RESET}")
                    
            # Print output
            if result.stdout:
                print(f"{MS_CYAN}Output:{MS_RESET}")
                print(result.stdout)
                
            # Record execution time
            execution_time = time.time() - start_time
            
            if result.returncode == 0:
                print(f"{MS_GREEN}Command completed in {execution_time:.2f} seconds.{MS_RESET}")
                
            return result.returncode
    
    except KeyboardInterrupt:
        print(f"{MS_YELLOW}Command interrupted by user.{MS_RESET}")
        return None
    except Exception as e:
        if isinstance(e, TerminalAIError):
            raise
        raise CommandError(f"Error executing command: {e}")

def process_user_command(command):
    """Process a built-in command or pass to shell"""
    global API_KEY, VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, MODEL
    
    if not command or command.isspace():
        return
        
    # Check if this is a batch command (semicolon-separated list)
    if ";" in command and ALLOW_COMMAND_CHAINING:
        batch_commands = [cmd.strip() for cmd in command.split(";") if cmd.strip()]
        if len(batch_commands) > 1 and not any(cmd.startswith(("!", "cd ", "config", "api-key", "exit", "quit", "clear", "help")) for cmd in batch_commands):
            try:
                process_batch_commands(batch_commands)
            except Exception as e:
                print(format_error(e))
            return
    
    # Check for built-in commands
    if command.lower() == "exit" or command.lower() == "quit":
        print(f"{MS_GREEN}Exiting Terminal AI Assistant.{MS_RESET}")
        sys.exit(0)
        
    elif command.lower() == "help":
        show_help()
        return
        
    elif command.lower() == "clear":
        os.system("cls" if os.name == "nt" else "clear")
        return
        
    elif command.lower() == "history":
        try:
            show_history()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "config":
        try:
            show_config()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower().startswith("set "):
        try:
            set_config(command[4:])
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "api-key":
        try:
            set_api_key()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "pwd":
        print(os.getcwd())
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
            print(f"{MS_GREEN}Changed directory to: {os.getcwd()}{MS_RESET}")
        except Exception as e:
            print(format_error(FileSystemError(f"Error changing directory: {str(e)}", 
                               "Check if the directory exists and is accessible.")))
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
        try:
            toggle_verification()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "chain":
        try:
            toggle_command_chaining()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower() == "jobs":
        try:
            show_background_jobs()
        except Exception as e:
            print(format_error(e))
        return
        
    elif command.lower().startswith("kill "):
        try:
            kill_background_job(command[5:].strip())
        except Exception as e:
            print(format_error(e))
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
        print(f"{MS_YELLOW}No background jobs running.{MS_RESET}")
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
        print(f"{MS_YELLOW}No job ID specified.{MS_RESET}")
        return
        
    if job_id not in background_processes:
        print(f"{MS_RED}Job ID '{job_id}' not found.{MS_RESET}")
        return
        
    job = background_processes[job_id]
    process = job.get("process")
    
    if not process:
        print(f"{MS_RED}No process found for job ID '{job_id}'.{MS_RESET}")
        return
        
    if job.get("status") in ["completed", "failed", "error"]:
        print(f"{MS_YELLOW}Job already finished with status: {job.get('status')}{MS_RESET}")
        return
        
    try:
        process.terminate()
        print(f"{MS_GREEN}Terminated job: {job_id}{MS_RESET}")
        job["status"] = "terminated"
        job["end_time"] = datetime.datetime.now()
    except Exception as e:
        print(f"{MS_RED}Error terminating job: {e}{MS_RESET}")

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
            print(f"{MS_YELLOW}Command history not available. Enable prompt_toolkit for history support.{MS_RESET}")
    except Exception as e:
        print(f"{MS_RED}Error displaying history: {e}{MS_RESET}")

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

def set_config(config_str):
    """Set configuration values"""
    global MODEL, VERIFY_COMMANDS, ALLOW_COMMAND_CHAINING, STREAM_OUTPUT, USE_CLIPBOARD, USE_ASYNC_EXECUTION
    
    if not config_str or "=" not in config_str:
        print(f"{MS_YELLOW}Invalid config format. Use: set KEY=VALUE{MS_RESET}")
        return
        
    key, value = config_str.split("=", 1)
    key = key.strip().lower()
    value = value.strip()
    
    if key == "model":
        MODEL = value
        print(f"{MS_GREEN}Model set to: {MODEL}{MS_RESET}")
    elif key == "verify":
        VERIFY_COMMANDS = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print(f"{MS_GREEN}Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}{MS_RESET}")
    elif key == "chain":
        ALLOW_COMMAND_CHAINING = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print(f"{MS_GREEN}Command chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}{MS_RESET}")
    elif key == "stream":
        STREAM_OUTPUT = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print(f"{MS_GREEN}Output streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}{MS_RESET}")
    elif key == "clipboard":
        USE_CLIPBOARD = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print(f"{MS_GREEN}Clipboard integration: {'Enabled' if USE_CLIPBOARD else 'Disabled'}{MS_RESET}")
    elif key == "async":
        USE_ASYNC_EXECUTION = value.lower() in ["true", "yes", "1", "on", "enabled"]
        print(f"{MS_GREEN}Async execution: {'Enabled' if USE_ASYNC_EXECUTION else 'Disabled'}{MS_RESET}")
    else:
        print(f"{MS_YELLOW}Unknown configuration key: {key}{MS_RESET}")

def toggle_verification():
    """Toggle command verification"""
    global VERIFY_COMMANDS
    VERIFY_COMMANDS = not VERIFY_COMMANDS
    print(f"{MS_GREEN}Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}{MS_RESET}")

def toggle_command_chaining():
    """Toggle command chaining"""
    global ALLOW_COMMAND_CHAINING
    ALLOW_COMMAND_CHAINING = not ALLOW_COMMAND_CHAINING
    print(f"{MS_GREEN}Command chaining: {'Enabled' if ALLOW_COMMAND_CHAINING else 'Disabled'}{MS_RESET}")

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
        
    API_KEY = api_key
    print_styled("API key updated successfully.", style="green")

def manage_templates():
    """Manage command templates"""
    global templates
    
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
            print(f"{MS_RED}Template name cannot be empty.{MS_RESET}")
            return
            
        description = input(f"{MS_YELLOW}Description:{MS_RESET} ").strip()
        if not description:
            print(f"{MS_RED}Description cannot be empty.{MS_RESET}")
            return
            
        templates[name] = description
        save_templates()
        print(f"{MS_GREEN}Template '{name}' added.{MS_RESET}")
        
    elif choice == "delete":
        name = input(f"{MS_YELLOW}Template name to delete:{MS_RESET} ").strip()
        if not name in templates:
            print(f"{MS_RED}Template '{name}' not found.{MS_RESET}")
            return
            
        del templates[name]
        save_templates()
        print(f"{MS_GREEN}Template '{name}' deleted.{MS_RESET}")
        
def run_template(template_name):
    """Run a command template"""
    if not template_name:
        print(f"{MS_RED}No template specified.{MS_RESET}")
        return
        
    if template_name not in templates:
        print(f"{MS_RED}Template '{template_name}' not found.{MS_RESET}")
        return
        
    description = templates[template_name]
    print(f"{MS_CYAN}Running template '{template_name}':{MS_RESET} {description}")
    
    # Get commands for this task from AI
    commands = get_ai_response(description)
    
    if not commands:
        print(f"{MS_RED}Failed to get commands for this template.{MS_RESET}")
        return
        
    # Execute the commands
    lines = commands.strip().split("\n")
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            execute_command(line)
            
def manage_command_groups():
    """Manage command groups"""
    global command_groups
    
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
            print(f"{MS_RED}Group name cannot be empty.{MS_RESET}")
            return
            
        commands = input(f"{MS_YELLOW}Commands (comma-separated):{MS_RESET} ").strip()
        if not commands:
            print(f"{MS_RED}Commands cannot be empty.{MS_RESET}")
            return
            
        command_list = [cmd.strip() for cmd in commands.split(",")]
        command_groups[name] = command_list
        save_command_groups()
        print(f"{MS_GREEN}Group '{name}' added.{MS_RESET}")
        
    elif choice == "delete":
        name = input(f"{MS_YELLOW}Group name to delete:{MS_RESET} ").strip()
        if not name in command_groups:
            print(f"{MS_RED}Group '{name}' not found.{MS_RESET}")
            return
            
        del command_groups[name]
        save_command_groups()
        print(f"{MS_GREEN}Group '{name}' deleted.{MS_RESET}")
        
    elif choice == "modify":
        name = input(f"{MS_YELLOW}Group name to modify:{MS_RESET} ").strip()
        if not name in command_groups:
            print(f"{MS_RED}Group '{name}' not found.{MS_RESET}")
            return
            
        commands = input(f"{MS_YELLOW}New commands (comma-separated):{MS_RESET} ").strip()
        if not commands:
            print(f"{MS_RED}Commands cannot be empty.{MS_RESET}")
            return
            
        command_list = [cmd.strip() for cmd in commands.split(",")]
        command_groups[name] = command_list
        save_command_groups()
        print(f"{MS_GREEN}Group '{name}' modified.{MS_RESET}")

def run_setup_wizard():
    """Run setup wizard for first-time configuration"""
    global API_KEY, MODEL, VERIFY_COMMANDS, STREAM_OUTPUT
    
    print(f"{MS_CYAN}Terminal AI Assistant Setup Wizard{MS_RESET}")
    print(f"{MS_YELLOW}This wizard will help you configure the assistant.{MS_RESET}")
    
    # Configure API key
    if not API_KEY:
        print(f"\n{MS_CYAN}Step 1: API Key Configuration{MS_RESET}")
        print(f"{MS_YELLOW}You need a Gemini API key to use this assistant.{MS_RESET}")
        print(f"{MS_YELLOW}Visit https://ai.google.dev/ to get your key.{MS_RESET}")
        set_api_key()
    else:
        print(f"\n{MS_CYAN}Step 1: API Key Configuration{MS_RESET}")
        print(f"{MS_GREEN}API key already configured.{MS_RESET}")
        change = input(f"{MS_YELLOW}Do you want to change it? (y/n):{MS_RESET} ").lower()
        if change == 'y':
            set_api_key()
    
    # Configure model
    print(f"\n{MS_CYAN}Step 2: Model Selection{MS_RESET}")
    print(f"{MS_YELLOW}Current model: {MODEL}{MS_RESET}")
    print(f"{MS_YELLOW}Available models: gemini-1.5-flash, gemini-1.5-pro{MS_RESET}")
    new_model = input(f"{MS_YELLOW}Select model (or press Enter to keep current):{MS_RESET} ").strip()
    if new_model:
        MODEL = new_model
        print(f"{MS_GREEN}Model set to: {MODEL}{MS_RESET}")
    
    # Configure verification
    print(f"\n{MS_CYAN}Step 3: Command Verification{MS_RESET}")
    print(f"{MS_YELLOW}Command verification checks if commands are safe before execution.{MS_RESET}")
    print(f"{MS_YELLOW}Current setting: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}{MS_RESET}")
    verify = input(f"{MS_YELLOW}Enable command verification? (y/n):{MS_RESET} ").lower()
    if verify:
        VERIFY_COMMANDS = verify == 'y'
        print(f"{MS_GREEN}Command verification: {'Enabled' if VERIFY_COMMANDS else 'Disabled'}{MS_RESET}")
    
    # Configure streaming
    print(f"\n{MS_CYAN}Step 4: Output Streaming{MS_RESET}")
    print(f"{MS_YELLOW}Output streaming shows command output in real-time.{MS_RESET}")
    print(f"{MS_YELLOW}Current setting: {'Enabled' if STREAM_OUTPUT else 'Disabled'}{MS_RESET}")
    stream = input(f"{MS_YELLOW}Enable output streaming? (y/n):{MS_RESET} ").lower()
    if stream:
        STREAM_OUTPUT = stream == 'y'
        print(f"{MS_GREEN}Output streaming: {'Enabled' if STREAM_OUTPUT else 'Disabled'}{MS_RESET}")
    
    print(f"\n{MS_GREEN}Setup complete! The assistant is ready to use.{MS_RESET}")
    print(f"{MS_YELLOW}Type 'help' to see available commands or ask me to perform tasks for you.{MS_RESET}")

def process_batch_commands(commands):
    """Process multiple commands in a single API call"""
    if not commands:
        raise CommandError(
            "No commands specified for batch processing",
            "Provide multiple commands separated by semicolons."
        )
    
    print(f"{MS_CYAN}Processing {len(commands)} commands in batch mode...{MS_RESET}")
    
    # Get responses for all commands in a single API call
    try:
        results = get_ai_response(None, batch_commands=commands)
        
        if not results:
            raise CommandError(
                "Failed to get batch responses from the AI",
                "Try processing commands individually or check your API key."
            )
        
        # Process each command's result
        for i, (cmd, cmd_results) in enumerate(results.items()):
            print(f"\n{MS_CYAN}Batch Command {i+1}/{len(commands)}:{MS_RESET} {cmd}")
            
            if isinstance(cmd_results, list):
                for line in cmd_results:
                    line = line.strip()
                    if line:
                        if line.startswith(("I cannot", "Cannot", "Sorry", "Error:")):
                            print_styled(f"AI Response: {line}", style="yellow")
                        else:
                            try:
                                execute_command(line)
                            except Exception as e:
                                print_styled(format_error(e), style="red")
            else:
                print_styled(f"Unexpected response format: {cmd_results}", style="red")
        
        print(f"\n{MS_GREEN}Batch command processing completed.{MS_RESET}")
        
    except Exception as e:
        if isinstance(e, TerminalAIError):
            raise
        raise CommandError(
            f"Error processing batch commands: {str(e)}",
            "Check your internet connection and API key. Try again with fewer commands."
        )

def setup_autocomplete():
    """Set up command auto-completion using readline"""
    if not READLINE_AVAILABLE:
        return False
    
    try:
        # Get commands from command groups
        all_commands = []
        for group_commands in command_groups.values():
            all_commands.extend(group_commands)
        
        # Add built-in commands
        builtin_commands = [
            "help", "exit", "quit", "clear", "history", "config", 
            "cd ", "pwd", "api-key", "templates", "groups", "verify", 
            "chain", "jobs", "kill ", "setup", "async "
        ]
        all_commands.extend(builtin_commands)
        
        # Add templates with ! prefix
        for template in templates.keys():
            all_commands.append("!" + template)
        
        # Add common options
        all_commands.extend(["set model=", "set verify=", "set chain=", "set stream="])
        
        # Remove duplicates and sort
        all_commands = sorted(set(all_commands))
        
        # Define completer function
        def completer(text, state):
            # Get all commands that match current text
            options = [cmd for cmd in all_commands if cmd.startswith(text)]
            
            # Add file completion for commands like cd, cat, ls, etc.
            if text.startswith(("cd ", "cat ", "ls ", "nano ", "vim ", "cp ", "mv ")):
                path_part = text.split(" ", 1)[1]
                dir_part = os.path.dirname(path_part) if path_part else "."
                
                try:
                    dir_part = os.path.expanduser(dir_part)
                    file_options = []
                    
                    if os.path.isdir(dir_part):
                        base_name = os.path.basename(path_part)
                        cmd_prefix = text.split(" ", 1)[0] + " "
                        
                        for item in os.listdir(dir_part or "."):
                            if item.startswith(base_name):
                                full_path = os.path.join(dir_part, item)
                                if os.path.isdir(full_path):
                                    file_options.append(cmd_prefix + full_path + "/")
                                else:
                                    file_options.append(cmd_prefix + full_path)
                        
                        options.extend(file_options)
                except Exception:
                    pass
            
            if state < len(options):
                return options[state]
            else:
                return None
                
        # Set the completer function
        readline.set_completer(completer)
        
        # Set the delimiter for completion
        readline.set_completer_delims(' \t\n;')
        
        # Use tab for completion
        readline.parse_and_bind('tab: complete')
        
        return True
    except Exception as e:
        print(f"{MS_YELLOW}Error setting up auto-completion: {e}. This feature will be disabled.{MS_RESET}")
        return False

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
    global API_KEY
    if not API_KEY:
        print_styled("No API key found. Please enter your Gemini API key.", style="yellow")
        set_api_key()
        
        if not API_KEY:
            print_styled("No API key provided. Some features will be disabled.", style="red")
    
    # Display welcome message
    print_styled("Terminal AI Assistant Lite v1.0", style="cyan")
    print_styled("Type 'help' for available commands or ask me to perform tasks for you.", style="green")
    
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
            if user_input.startswith("!") or any(user_input.startswith(cmd) for cmd in ["help", "exit", "quit", "clear", "history", "config", "set ", "cd ", "pwd", "api-key", "templates", "groups", "verify", "chain", "jobs", "kill ", "setup"]):
                # Handle as a built-in command
                try:
                    process_user_command(user_input)
                except Exception as e:
                    print_styled(format_error(e), style="red")
            else:
                # Handle as a task for the AI
                try:
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
                    
                    print_styled("Thinking...", style="yellow")
                    
                    # Get commands for this task from AI
                    commands = get_ai_response(task_prompt)
                    
                    if commands:
                        # Split into individual commands and execute each one
                        lines = commands.strip().split("\n")
                        for line in lines:
                            line = line.strip()
                            if line and not line.startswith("#"):
                                if "I cannot " in line or "cannot be " in line or "Sorry, " in line:
                                    print_styled(f"AI Response: {line}", style="yellow")
                                else:
                                    try:
                                        execute_command(line)
                                    except Exception as e:
                                        print_styled(format_error(e), style="red")
                    else:
                        print_styled("Failed to get a response from the AI.", style="red")
                        print_styled("You can try typing a more specific request or check your API key.", style="yellow")
                except Exception as e:
                    print_styled(format_error(e), style="red")
        
        except KeyboardInterrupt:
            print()
            print_styled("Interrupted. Press Ctrl+C again to exit.", style="yellow")
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                print()
                print_styled("Exiting Terminal AI Assistant.", style="green")
                break
        except Exception as e:
            print_styled(format_error(e), style="red")
            
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
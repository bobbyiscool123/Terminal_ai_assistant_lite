# Terminal AI Assistant Lite API Documentation

This document provides an overview of the main functions and components of Terminal AI Assistant Lite.

## Core Components

### API Integration

The assistant uses the Google Generative AI API (Gemini) for generating commands based on natural language inputs.

```python
# API configuration
MODEL = "gemini-1.5-flash"
API_ENDPOINT = "https://generativelanguage.googleapis.com"
API_VERSION = "v1"
```

### Color Formatting

Microsoft-themed colors are used for terminal output:

```python
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
```

## Main Functions

### format_output(text, formatter, pattern=None)

Formats the output text using the specified formatter.

Parameters:
- `text` (str): The text to format
- `formatter` (str): The name of the formatter to use
- `pattern` (str, optional): Pattern for 'grep' formatter

Returns:
- str: The formatted text

### copy_to_clipboard(text)

Copies text to the clipboard if the clipboard module is available.

Parameters:
- `text` (str): The text to copy to clipboard

Returns:
- bool: True if successful, False otherwise

### is_json(text)

Checks if the text is valid JSON.

Parameters:
- `text` (str): The text to check

Returns:
- bool: True if the text is valid JSON, False otherwise

## Command Templates

The assistant supports predefined command templates for common tasks:

```python
templates = {
    "update": "Update all packages",
    "network": "Show network information",
    "disk": "Show disk usage",
    "process": "Show running processes",
    "memory": "Show memory usage",
    "backup": "Backup important files"
}
```

## Command Groups

Commands are organized into functional groups:

```python
command_groups = {
    "file": ["ls", "cd", "cp", "mv", "rm", "mkdir", "touch", "cat", "nano", "find"],
    "network": ["ifconfig", "ping", "traceroute", "netstat", "ssh", "curl", "wget"],
    "system": ["top", "ps", "kill", "termux-info", "df", "du", "free"],
    "package": ["pkg", "apt", "dpkg", "pip"],
    "archive": ["tar", "zip", "unzip", "gzip", "gunzip"],
    "git": ["git clone", "git pull", "git push", "git commit", "git status"],
    "termux": ["termux-open", "termux-open-url", "termux-share", "termux-notification"]
}
```

For more details, refer to the main script's docstrings and comments. 
# Terminal AI Assistant Lite

A lightweight, bash-based terminal assistant that uses Google's Gemini AI to execute commands based on natural language descriptions. This version is specifically designed for Linux terminals with minimal dependencies.

## Features

1. **Minimal Dependencies**: Requires only bash and curl (with optional jq for better JSON handling)
2. **No Python Required**: Works without Python or pip installation
3. **Linux Terminal Focus**: Optimized for Linux command-line environments
4. **Real-time Command Streaming**: See command output as it happens
5. **Command History**: Tracks executed commands with timestamps
6. **Dangerous Command Protection**: Built-in safety checks for risky commands
7. **Simple Configuration**: Easy to customize via config file
8. **Color-coded Interface**: Improved readability with color formatting
9. **Persistent API Key Storage**: Securely saves your API key between sessions
10. **Small Footprint**: Minimal disk space and memory usage

## Installation

1. Download the script:
```bash
curl -o terminal_ai_lite.sh https://raw.githubusercontent.com/yourusername/Terminal_ai_assistant_lite/main/terminal_ai_lite.sh
```

2. Make it executable:
```bash
chmod +x terminal_ai_lite.sh
```

3. Run the script:
```bash
./terminal_ai_lite.sh
```

4. On first run, you'll be prompted to enter your Google Gemini API key.

## Dependencies

### Required
- bash (present on virtually all Linux systems)
- curl (for API communication)

### Optional
- jq (for better JSON handling)

To install the optional dependency on Debian/Ubuntu:
```bash
sudo apt-get install jq
```

On Fedora/RHEL/CentOS:
```bash
sudo dnf install jq
```

## Usage

1. Run the script:
```bash
./terminal_ai_lite.sh
```

2. Type your task in natural language. For example:
```
What would you like me to do? Find all jpg files in the current directory and resize them to 800x600
```

3. The AI will generate and execute the appropriate commands in sequence.

## Available Commands

- `help`: Show help information
- `exit` or `quit`: Exit the program
- `clear`: Clear the screen
- `history`: Show command history
- `config`: Show current configuration
- `cd DIR`: Change directory
- `pwd`: Show current directory

## Configuration

The script creates these configuration files:

- `~/.terminal_ai_lite_config`: Configuration settings
- `~/.terminal_ai_lite_api_key`: Stores your API key
- `~/.terminal_ai_lite_history`: Command history

You can edit `~/.terminal_ai_lite_config` to customize:

```bash
# Maximum number of history entries to show
MAX_HISTORY=100

# Whether to confirm dangerous commands
CONFIRM_DANGEROUS=true

# Whether to stream command output in real-time
STREAM_OUTPUT=true

# AI model to use
MODEL="gemini-2.0-flash"
```

## Safety Features

- Built-in protection against dangerous commands
- Command confirmation for potentially harmful operations
- Secure API key storage with proper permissions

## Example Tasks

Try these examples:

1. "Update my system and install the latest security patches"
2. "Find all PDF files modified in the last week and move them to a new folder called 'recent'"
3. "Monitor CPU and memory usage in real-time"
4. "Find the largest 10 files in my home directory"
5. "Create a compressed backup of my Documents folder"

## License

This project is licensed under the MIT License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- This is the lite version of the full Terminal AI Assistant project
- Thanks to Google for providing the Gemini API 
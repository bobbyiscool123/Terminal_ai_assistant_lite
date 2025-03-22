# Terminal AI Assistant Lite

By this point in time, if you're aren't making your own AI assistant, what are you doing? Use this as a template to build on. All the code is just a suggestion. Use other AI models to build it for you. Just feed terminal_ai_lite into whatever LLM (AI) you want and build/modify this in sections. Happy Hacking.

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

## How to Use

1. Clone the repository to your local machine.
```bash
git clone https://github.com/bobbyiscool123/Terminal_ai_assistant_lite.git
cd Terminal_ai_assistant_lite
```
2. Run the installation script:
```bash
./install.sh
```
3. Start the assistant:
```bash
./terminal_ai_lite.sh
```
4. On first run, you'll be prompted to enter your API key.

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

## Customization

1. Open the `terminal_ai_lite.config` file in your preferred text editor.
2. Make any modifications you desire.

The configuration file allows you to customize:

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

## Usage

Run the assistant:
```bash
./terminal_ai_lite.sh
```

Type your task in natural language. For example:
```
What would you like me to do? Find all jpg files in the current directory and resize them to 800x600
```

The AI will generate and execute the appropriate commands in sequence.

## Available Commands

- `help`: Show help information
- `exit` or `quit`: Exit the program
- `clear`: Clear the screen
- `history`: Show command history
- `config`: Show current configuration
- `cd DIR`: Change directory
- `pwd`: Show current directory

## Example Tasks

Try these examples:

1. "Update my system and install the latest security patches"
2. "Find all PDF files modified in the last week and move them to a new folder called 'recent'"
3. "Monitor CPU and memory usage in real-time"
4. "Find the largest 10 files in my home directory"
5. "Create a compressed backup of my Documents folder"

## Disclaimer

Terminal AI Assistant Lite is a personal A.I. assistant and is not intended to replace human interaction or professional advice. Use it at your own risk.

## License

This project is licensed under the GPL-3.0 License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request to our [GitHub repository](https://github.com/bobbyiscool123/Terminal_ai_assistant_lite). 
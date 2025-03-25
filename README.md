# Terminal AI Assistant Lite

By this point in time, if you're aren't making your own AI assistant, what are you doing? Use this as a template to build on. All the code is just a suggestion. Use other AI models to build it for you. Just feed terminal_ai_lite into whatever LLM (AI) you want and build/modify this in sections. Happy Hacking.

## Features

1. **Cross-Platform**: Works on Windows, macOS, and Linux
2. **Minimal Dependencies**: Only needs Python and a few standard libraries
3. **Microsoft-themed Colors**: Beautiful color formatting for improved readability
4. **Real-time Command Streaming**: See command output as it happens
5. **Command History**: Tracks executed commands with timestamps
6. **Dangerous Command Protection**: Built-in safety checks for risky commands
7. **Simple Configuration**: Easy to customize via environment variables
8. **Persistent API Key Storage**: Securely saves your API key in a .env file
9. **Small Footprint**: Minimal disk space and memory usage
10. **Smart Response Fallbacks**: Works even when API is unavailable
11. **Google Generative AI Integration**: Uses the official Google Generative AI Python library when available
12. **Termux Support**: Works on mobile devices via Termux

## How to Use

1. Clone the repository to your local machine.
```bash
git clone https://github.com/bobbyiscool123/Terminal_ai_assistant_lite.git
cd Terminal_ai_assistant_lite
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Start the assistant:
```bash
python terminal_ai_lite.py
```

4. On first run, you'll be prompted to enter your Gemini API key, which will be stored in the .env file.

## Dependencies

### Required
- Python 3.6+
- python-dotenv (for .env file support)
- colorama (for cross-platform color support)
- curl (for API communication when fallback is needed)

### Optional
- google-generativeai (for improved API interaction)
- prompt_toolkit (for enhanced command history)
- pyperclip (for clipboard integration)

### Installation on different platforms

#### Windows
```bash
pip install -r requirements.txt
# curl is usually bundled with Git for Windows
```

#### macOS
```bash
pip install -r requirements.txt
# curl is pre-installed
```

#### Linux/Termux
```bash
pip install -r requirements.txt
# curl is usually pre-installed, if not:
# apt-get install curl (Debian/Ubuntu)
# pkg install curl (Termux)
```

## Usage

Run the assistant:
```bash
python terminal_ai_lite.py
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
- `set`: Change configuration settings
- `cd DIR`: Change directory
- `pwd`: Show current directory
- `api-key`: Update your API key
- `templates`: Manage command templates
- `groups`: Manage command groups
- `format`: Format last command output
- `copy`: Copy last command output to clipboard
- `async`: Run command in background
- `jobs`: Show running background jobs
- `kill`: Kill a background job
- `!TEMPLATE`: Run a saved template
- `verify`: Toggle command verification
- `chain`: Toggle command chaining
- `setup`: Run setup wizard

## API Key Management

You can update your API key in several ways:

1. Use the built-in command: `api-key`
2. Edit the `.env` file directly
3. Delete the `.env` file to be prompted for a new key on next run

## Example Tasks

Try these examples:

1. "Update my system and install the latest security patches"
2. "Find all PDF files modified in the last week and move them to a new folder called 'recent'"
3. "Monitor CPU and memory usage in real-time"
4. "Find the largest 10 files in my home directory"
5. "Create a compressed backup of my Documents folder"

## Recent Changes

1. **Added Google Generative AI Library Support**: The assistant now uses the official Google Generative AI Python library when available, with fallback to curl-based API calls.
2. **Improved Error Handling**: Enhanced try-except blocks and error reporting throughout the codebase.
3. **Fixed Indentation Issues**: Resolved multiple Python syntax and indentation errors.
4. **Termux Support**: Added special support for Termux-specific commands and mobile environment.
5. **Updated API Endpoint Handling**: More flexible configuration of API endpoints and versions.
6. **Enhanced Command Chain Processing**: Better parsing and execution of command chains with && and || operators.

## Disclaimer

Terminal AI Assistant Lite is a personal A.I. assistant and is not intended to replace human interaction or professional advice. Use it at your own risk.

## License

This project is licensed under the GPL-3.0 License.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request to our [GitHub repository](https://github.com/bobbyiscool123/Terminal_ai_assistant_lite). 
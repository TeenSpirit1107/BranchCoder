# AI Chat Sidebar - VS Code Extension

[English](README.md) | [中文](README.zh-CN.md)

---

A powerful VS Code extension that provides AI chat functionality in the sidebar. The AI features are implemented through Python scripts, supporting RAG (Retrieval-Augmented Generation) technology, a tool calling system, automatic codebase indexing for AI context, and direct code file modification capabilities.

## Features

### Core Features

- 📱 **Sidebar Chat Interface** - Clean and beautiful conversation interface
- 💬 **Chat with AI** - Supports multi-turn conversations and history
- 🔍 **RAG Code Indexing** - Automatically indexes workspace code to provide context for AI
- 🔄 **Auto-update Index** - Detects file changes through snapshot system and automatically updates RAG index
- 📝 **Markdown Rendering** - Supports Markdown format message rendering
- 🧹 **Clear Chat History** - One-click to clear conversation records
- ⚙️ **Configurable Python Path and Script Path**
- 📊 **Output Logging** - Detailed log output for debugging and monitoring

### Intelligent Tool System

AI can call various tools to complete complex tasks:

- 🔧 **Code Patch Application** (`apply_patch`) - AI can generate and apply code patches
- 💻 **Command Execution** (`command`) - Execute system commands (such as git, npm, etc.)
- 🌐 **Web Page Fetching** (`fetch_url`) - Fetch web page content
- 🔍 **Code Linting** (`lint`) - Perform syntax checking on code
- 🌍 **Web Search** (`web_search`) - Search for information on the web
- 📚 **Workspace RAG** (`workspace_rag`) - Use RAG to retrieve code context
- 📁 **Workspace Structure** (`workspace_structure`) - Get workspace file structure
- 📤 **Send Report** (`send_report`) - Send final report to user

### Code Modification Features

- 🔀 **Patch Preview** - After AI generates code patches, automatically displays diff preview in VS Code
- ✅ **Accept/Reject Buttons** - Provides buttons in the chat panel for users to choose whether to accept changes
- 🔄 **Auto-apply Preview** - Patches are automatically applied to code after generation (preview mode)
- ↩️ **Revert Changes** - If rejected, can revert applied changes

### Flow Agent System

- 🤖 **Intelligent Agent** - Uses Flow Agent for multi-turn iterative tool calling
- 🔄 **Auto Iteration** - Supports up to 10 iterations, automatically completing complex tasks
- 💾 **Memory System** - Saves tool call history to provide context for subsequent decisions

## Installation

### Prerequisites

- Node.js and npm
- Python 3.9 or higher
- [uv](https://github.com/astral-sh/uv) (Recommended Python package manager)

### Installation Steps

1. Install Node.js dependencies:
```bash
npm install
```

2. Set up Python environment (using uv):

```bash
# Install uv (if not already installed)
# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or using pip:
# pip install uv

# Create virtual environment
uv venv

# Activate virtual environment
# macOS/Linux:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# Install Python dependencies
uv sync
```

3. Configure VS Code extension:

In VS Code settings, set `aiChat.pythonPath` to the Python interpreter path in the uv virtual environment:

- macOS/Linux: `.venv/bin/python` (relative to project root)
- Windows: `.venv\Scripts\python.exe` (relative to project root)

Or use an absolute path.

4. Compile TypeScript:
```bash
npm run compile
```

5. Press `F5` to run in Extension Development Host

## Configuration

Configure the following options in VS Code settings:

- `aiChat.pythonPath`: Python interpreter path
  - Default: `python3`
  - When using uv environment: `.venv/bin/python` (Linux/macOS) or `.venv\Scripts\python.exe` (Windows)
  - Can use absolute path or path relative to project root
- `aiChat.aiScriptPath`: AI service script path (default: `python/ai_service.py`)

### Python Environment Variables

Make sure to create a `.env` file in the `python/` directory and configure necessary environment variables:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=your_model_name  # e.g., gpt-4, gpt-3.5-turbo, etc.
OPENAI_BASE_URL=your_base_url  # Optional, for custom API endpoint
OPENAI_PROXY=your_proxy_url  # Optional, proxy configuration

# RAG Configuration
RAG_ENABLED=true  # Whether to enable RAG index building and updating, default: true. Set to false to disable RAG functionality
RAG_UPDATE_INTERVAL_SECONDS=60  # Minimum update interval for RAG update service (seconds), default: 60
RAG_DESCRIPTION_CONCURRENCY=2  # Concurrency for description generation, default: 2
RAG_INDEXING_CONCURRENCY=2  # Concurrency for index building, default: 2
```

> **Note**: The `.env` file should be placed in the `python/` directory, not the project root.

## Usage

### Run the Agent with "Run and Debug"

Run the code with `Run and Debug` mode:

![run and debug](doc/readme/run_and_debug.png)

### Access Chat Interface

1. **Via Activity Bar Icon** (Recommended):
   - Find the 💬 chat icon in the VS Code left activity bar
   - Click the icon to open the "AI Chat" view (see image below)

   ![AI Chat](doc/readme/ai_chat.png)

2. **Via Command Palette**:
   - Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (Mac)
   - Type `AI Chat: Open AI Chat` and select

### Start Conversation

1. Type a message in the input box
2. Press `Enter` or click "Send" to send the message
3. AI will process the message and return a response (supports Markdown format)

### Code Modification Workflow

When AI generates code patches:

1. **Auto Preview**: Patches are automatically applied to code and a diff preview window is displayed in VS Code
2. **View Changes**: View the differences before and after modification in the preview window
3. **Make Decision**:
   - Click **Accept** button: Keep changes, patch is officially applied
   - Click **Reject** button: Revert changes, code returns to pre-modification state
4. **Button Location**: Accept/Reject buttons are displayed above the input box in the chat panel

> **Note**: If the user doesn't click a button, the buttons will remain displayed until the user makes a choice or a new patch is generated.

### RAG Indexing

- **First Time Opening Workspace**: Extension automatically initializes RAG index, indexing the entire codebase
- **Auto Update**: Extension periodically detects file changes and automatically updates the index (interval configured by `RAG_UPDATE_INTERVAL_SECONDS`)
- **Closed Detection**: Even if files change when VS Code is closed, it will automatically detect and update when reopened
- **View Logs**: In VS Code's "Output" panel, select "AI Service" channel to view detailed logs

### Example Task: `sample_ws`

Example prompt: `Processing message: Please complete all the TODOs in the project.`

The code under `sample_ws` has some incomplete parts, marked with TODO in comments, along with implementation ideas.

The code in `sample_ws` can create a weighted directed graph, select different destination points on the graph based on user choices, use different shortest path algorithms, view paths and lengths, and display them in ASCII format in the command line.

## How It Works

### AI Service Architecture

The extension uses Python scripts to handle AI requests, main components include:

1. **Frontend** (`src/extension.ts`, `src/ChatPanel.ts`)
   - VS Code extension main program
   - Manages Webview chat interface
   - Handles user input and message display
   - Handles Patch preview and application

2. **AI Service** (`python/ai_service.py`)
   - Receives chat messages and history
   - Calls Flow Agent to process requests
   - Returns formatted AI responses

3. **Flow Agent** (`python/agents/flow.py`)
   - Intelligent agent system supporting multi-turn iteration
   - Automatically calls tools to complete tasks
   - Manages tool call history and context

4. **Tool System** (`python/tools/`)
   - Extensible tool framework
   - Supports various tools (patch application, command execution, code linting, etc.)
   - Automatic tool discovery and registration

5. **LLM Client** (`python/llm/`)
   - Encapsulates OpenAI API calls
   - Supports asynchronous processing
   - Manages API configuration and error handling

6. **RAG Service** (`python/rag/`)
   - Codebase indexing and retrieval
   - Automatic code description generation
   - Incremental index updates

### Event Stream System

The extension uses an event stream system to pass information:

- **ToolCallEvent**: Tool call event
- **ToolResultEvent**: Tool execution result event
- **ReportEvent**: Final report event (via `send_report` tool)
- **MessageEvent**: Normal message event

All events are displayed in the chat interface, preserving complete conversation history.

### RAG Indexing Flow

1. **Initialization**: When opening workspace for the first time, scans all code files and creates index
2. **Snapshot System**: Uses file hash snapshots to detect changes
3. **Incremental Update**: Only updates changed files for efficiency
4. **Context Retrieval**: When AI answers questions, RAG system retrieves relevant code context

### Patch Application Flow

1. **Generate Patch**: AI generates code patches through `apply_patch` tool
2. **Auto Apply**: Patches are automatically applied to code files (preview mode)
3. **Show Preview**: Opens diff preview window in VS Code
4. **User Choice**: User decides whether to keep changes via Accept/Reject buttons
5. **Execute Action**:
   - Accept: Keep changes (patch already applied, no additional action needed)
   - Reject: Revert changes (restore to pre-modification state)

## Customizing AI Features

### Modifying AI Service

Edit the `python/ai_service.py` file to customize AI response logic.

### Modifying Flow Agent

Edit `python/agents/flow.py` (ReAct Flow) or `planact_flow.py` (PlanAct Flow) in the same directory to:
- Adjust maximum iteration count
- Modify tool calling logic
- Customize prompts

### Adding New Tools

1. Create a new tool file in the `python/tools/` directory
2. Inherit from `MCPTool` base class
3. Implement necessary properties and methods
4. Tools are automatically discovered and registered

Example tool structure:
```python
from tools.base_tool import MCPTool

class MyCustomTool(MCPTool):
    @property
    def name(self) -> str:
        return "my_tool"
    
    @property
    def agent_tool(self) -> bool:
        return True  # Whether to expose to AI
    
    def get_tool_definition(self) -> Dict[str, Any]:
        # Return tool definition
        pass
    
    async def execute(self, ...) -> Dict[str, Any]:
        # Execute tool logic
        pass
```

### Modifying LLM Configuration

Edit the `python/llm/chat_llm.py` file to:
- Switch to different LLM providers
- Adjust model parameters
- Add custom prompts

### Adjusting RAG Behavior

Edit relevant files in the `python/rag/` directory to:
- Modify code slicing strategy
- Adjust description generation method
- Customize retrieval algorithm

## Development

### TypeScript Compilation

```bash
# Compile
npm run compile

# Watch mode compilation (auto recompile)
npm run watch
```

### Python Development

The project uses `uv` as the Python package manager:

```bash
# Install dependencies (if needed)
uv sync

# Install dependencies (dev version, required for running tests)
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows
```

### Running Tests

Running tests requires installing dev version dependencies (see above).

```bash
# Run Python tool tests
cd python
python -m pytest tests/ -v

# Or run a single test file
python tests/test_apply_patch_tool.py
```

### Debugging

1. In VS Code or code editors based on VS Code architecture (such as Cursor), press the `Run and Debug` button to start Extension Development Host (see image below)
2. Test extension functionality in the development host
3. View debug console and output panel ("AI Service" channel) for logs

![run and debug](doc/readme/run_and_debug.png)

### Project Structure

```
.
├── src/                    # TypeScript source code
│   ├── extension.ts        # Extension main entry
│   ├── ChatPanel.ts        # Chat panel logic
│   ├── patchPreview.ts     # Patch preview provider
│   ├── patchUtils.ts        # Patch utility functions
│   └── snapshot.ts         # Snapshot system
├── python/                  # Python service
│   ├── ai_service.py       # AI service main script
│   ├── agents/              # Agent system
│   │   ├── flow.py         # ReAct Flow Agent
│   │   ├── memory.py       # Memory system
│   │   └── planact_flow.py # PlanAct Flow Agent
│   ├── tools/               # Tool system
│   │   ├── base_tool.py    # Tool base class
│   │   ├── tool_factory.py # Tool factory
│   │   ├── apply_patch_tool.py
│   │   ├── command_tool.py
│   │   ├── fetch_url_tool.py
│   │   ├── lint_tool.py
│   │   ├── message_tool.py
│   │   ├── parallel_task_executor.py
│   │   ├── search_replace_tool.py
│   │   ├── send_report_tool.py
│   │   ├── web_search_tool.py
│   │   ├── workspace_rag_tool.py
│   │   └── workspace_structure_tool.py
│   ├── llm/                 # LLM client
│   │   ├── chat_llm.py
│   │   └── rag_llm.py
│   ├── rag/                 # RAG indexing service
│   │   ├── class_slicer.py
│   │   ├── description_generator.py
│   │   ├── function_slicer.py
│   │   ├── hash.py
│   │   ├── incremental_updater.py
│   │   ├── indexing.py
│   │   └── rag_service.py
│   ├── rag_init_service.py  # RAG initialization service
│   ├── rag_update_service.py # RAG update service
│   ├── models/              # Data models
│   ├── prompts/             # Prompts
│   │   └── flow_prompt.py
│   ├── utils/               # Utility functions
│   │   ├── logger.py
│   │   └── patch_parser.py
│   └── tests/               # Tests
├── media/                   # Static resources (CSS, etc.)
│   └── chat.css            # Chat interface styles
├── out/                     # TypeScript compilation output
├── doc/                     # Documentation
├── logs/                    # Log files
├── sample_ws/               # Sample workspace
├── package.json            # Node.js configuration
├── pyproject.toml          # Python project configuration
├── tsconfig.json           # TypeScript configuration
└── uv.lock                 # uv lock file
```

## License

MIT

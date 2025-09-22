# AI Manus Backend Service

English | [中文](README_zh.md)

AI Manus is an intelligent conversation agent system based on FastAPI and OpenAI API. The backend adopts Domain-Driven Design (DDD) architecture, supporting intelligent dialogue, file operations, Shell command execution, and browser automation.

## Project Architecture

The project adopts Domain-Driven Design (DDD) architecture, clearly separating the responsibilities of each layer:

```
backend/
├── app/
│   ├── domain/          # Domain layer: contains core business logic
│   │   ├── models/      # Domain model definitions
│   │   ├── services/    # Domain services
│   │   ├── external/    # External service interfaces
│   │   └── prompts/     # Prompt templates
│   ├── application/     # Application layer: orchestrates business processes
│   │   ├── services/    # Application services
│   │   └── schemas/     # Data schema definitions
│   ├── interfaces/      # Interface layer: defines external system interfaces
│   │   └── api/
│   │       └── routes.py # API route definitions
│   ├── infrastructure/  # Infrastructure layer: provides technical implementation
│   └── main.py          # Application entry
├── Dockerfile           # Docker configuration file
├── run.sh               # Production environment startup script
├── dev.sh               # Development environment startup script
├── requirements.txt     # Project dependencies
└── README.md            # Project documentation
```

## Core Features

1. **AI Agent Management**: Create and manage AI Agent instances
2. **Real-time Conversation**: Implement real-time conversation with the Agent through Server-Sent Events (SSE)
3. **Tool Invocation**: Support for various tool calls, including:
   - Browser automation operations (using Playwright)
   - Shell command execution and viewing
   - File read/write operations
4. **Sandbox Environment**: Use Docker containers to provide isolated execution environments
5. **VNC Visualization**: Support remote viewing of the sandbox environment via WebSocket connection
6. **Web Search**: Support Google search integration (optional feature)

## Requirements

- Python 3.9+
- Docker 20.10+

## Installation and Configuration

1. **Create a virtual environment**:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Environment variable configuration**:
Create a `.env` file and set the following environment variables:
```
# Model provider configuration
API_KEY=your_api_key_here                # API key for OpenAI or other model providers
API_BASE=https://api.openai.com/v1       # Base URL for the model API, can be replaced with other model provider API addresses

# Model configuration
MODEL_NAME=gpt-4o                        # Model name to use
TEMPERATURE=0.7                          # Model temperature parameter
MAX_TOKENS=2000                          # Maximum output tokens per model request

# Google search configuration
GOOGLE_SEARCH_API_KEY=                   # Google Search API key for web search functionality (optional)
GOOGLE_SEARCH_ENGINE_ID=                 # Google custom search engine ID (optional)

# Sandbox configuration
SANDBOX_IMAGE=simpleyyt/manus-sandbox          # Sandbox environment Docker image
SANDBOX_NAME_PREFIX=sandbox              # Sandbox container name prefix
SANDBOX_TTL_MINUTES=30                   # Sandbox container time-to-live (minutes)
SANDBOX_NETWORK=manus-network            # Docker network name for communication between sandbox containers

# Log configuration
LOG_LEVEL=INFO                           # Log level, options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

## Running the Service

### Development Environment
```bash
# Start the development server (with hot reload)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will start at http://localhost:8000.

### Docker Deployment
```bash
# Build Docker image
docker build -t manus-ai-agent .

# Run container
docker run -p 8000:8000 --env-file .env -v /var/run/docker.sock:/var/run/docker.sock manus-ai-agent
```

> Note: If using Docker deployment, you need to mount the Docker socket so the backend can create sandbox containers.

## API Documentation

Base URL: `/api/v1`

### 1. Create Agent

- **Endpoint**: `POST /api/v1/agents`
- **Description**: Create a new AI Agent instance
- **Request Body**: None
- **Response**:
  ```json
  {
    "code": 0,
    "msg": "success",
    "data": {
      "agent_id": "string",
      "status": "created",
      "message": "Agent created successfully"
    }
  }
  ```

### 2. Chat with Agent

- **Endpoint**: `POST /api/v1/agents/{agent_id}/chat`
- **Description**: Chat with a specified Agent
- **Request Body**:
  ```json
  {
    "message": "User message content",
    "timestamp": 1234567890
  }
  ```
- **Response**: Server-Sent Events (SSE) stream
- **Event Types**:
  - `message`: Text message
  - `title`: Title information
  - `plan`: Plan steps
  - `step`: Step status
  - `tool`: Tool invocation
  - `error`: Error information
  - `done`: Flow completion

### 3. View Shell Session Content

- **Endpoint**: `POST /api/v1/agents/{agent_id}/shell`
- **Description**: View the Shell session content of a specified Agent
- **Request Body**:
  ```json
  {
    "session_id": "shell session ID"
  }
  ```
- **Response**: Shell session content

### 4. View File Content

- **Endpoint**: `POST /api/v1/agents/{agent_id}/file`
- **Description**: View file content in the specified Agent's sandbox environment
- **Request Body**:
  ```json
  {
    "file": "file path"
  }
  ```
- **Response**: File content

### 5. VNC Connection

- **Endpoint**: `WebSocket /api/v1/agents/{agent_id}/vnc`
- **Description**: Establish a VNC WebSocket connection to the Agent's sandbox environment
- **Protocol**: WebSocket (binary mode)

## Error Handling

All APIs return responses in a unified format when errors occur:
```json
{
  "code": 400,
  "msg": "Error description",
  "data": null
}
```

Common error codes:
- `400`: Request parameter error
- `404`: Resource not found
- `500`: Server internal error

## Development Guide

### Adding New Tools

1. Define the tool interface in the `domain/external` directory
2. Implement the tool functionality in the `infrastructure` layer
3. Integrate the tool in `application/services` 
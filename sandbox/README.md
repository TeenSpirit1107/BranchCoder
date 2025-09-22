# AI Manus Sandbox Service

English | [中文](README_zh.md)

AI Manus Sandbox is an isolated execution environment based on Docker containers, providing AI Agents with secure Shell command execution, file operations, and browser automation capabilities. The service offers API interfaces through FastAPI and supports interaction with backend services.

## Technical Architecture

The sandbox service integrates multiple technologies to provide an operational environment for AI Agents:

```
sandbox/
├── app/                   # Main application directory
│   ├── api/               # API interface definitions
│   │   └── v1/            # API version v1
│   │       ├── shell.py   # Shell command execution interface
│   │       ├── file.py    # File operation interface
│   │       └── supervisor.py # Process management interface
│   ├── services/          # Service implementations
│   ├── schemas/           # FastAPI interface models
│   ├── models/            # Data models
│   ├── core/              # Core configurations
│   └── main.py            # Application entry point
├── Dockerfile             # Docker build file
├── requirements.txt       # Python dependencies
├── supervisord.conf       # Supervisor configuration
└── README.md              # Documentation
```

## Core Features

The sandbox environment provides the following core features:

1. **Shell Command Execution**: Securely execute Shell commands with session management support
2. **File Operations**: Read, write, search, and manipulate the file system
3. **Browser Environment**:
   - Built-in Google Chrome browser
   - Chrome DevTools Protocol support
   - Remote debugging interface
4. **VNC Remote Access**:
   - VNC remote desktop service
   - WebSocket interface
5. **Process Management**: Manage component processes through Supervisor

## System Requirements

- Python 3.9+
- Docker 20.10+

## Installation and Configuration

### Local Development Environment

1. **Create a virtual environment**:
```bash
python -m venv .venv
source .venv/bin/activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Start the development server**:
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### Docker Deployment

```bash
# Build the image
docker build -t manus-sandbox .

# Run the container
docker run -p 8080:8080 -p 9222:9222 -p 5900:5900 -p 5901:5901 manus-sandbox
```

## Port Information

- **8080**: FastAPI service port
- **9222**: Chrome remote debugging port
- **5900**: VNC service port
- **5901**: VNC WebSocket port

## Configuration Options

The sandbox service supports the following configuration options, which can be set through environment variables or a `.env` file:

- **ORIGINS**: List of allowed CORS origins, default is `["*"]`. Can be set as a comma-separated string or JSON array.
- **SERVICE_TIMEOUT_MINUTES**: Service timeout in minutes, default is unlimited. When set, the service will automatically terminate after the specified time.
- **LOG_LEVEL**: Log level, can be set to `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`, default is `INFO`.

Example `.env` file:
```
ORIGINS=http://localhost:3000,https://example.com
SERVICE_TIMEOUT_MINUTES=60
LOG_LEVEL=DEBUG
```

## API Documentation

Base URL: `/api/v1`

### 1. Shell-related Endpoints

#### Execute Shell Command

- **Endpoint**: `POST /api/v1/shell/exec`
- **Description**: Execute a command in the specified shell session
- **Request Body**:
  ```json
  {
    "id": "session_id",  /* Optional, automatically created if not provided */
    "exec_dir": "/path/to/dir",  /* Execution directory */
    "command": "ls -la",  /* Command to execute */
    "sudo": false  /* Optional, whether to execute with sudo */
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Command executed",
    "data": {
      "session_id": "session_id",
      "command": "ls -la",
      "status": "running"
    }
  }
  ```

#### View Shell Session Content

- **Endpoint**: `POST /api/v1/shell/view`
- **Description**: View the content of the specified shell session
- **Request Body**:
  ```json
  {
    "id": "session_id"  /* Target session ID */
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "Query successful",
    "data": {
      "content": "Session output content",
      "session_id": "session_id"
    }
  }
  ```

#### Other Shell Operations

- **Wait for Process**: `POST /api/v1/shell/wait`
- **Write Input**: `POST /api/v1/shell/write`
- **Terminate Process**: `POST /api/v1/shell/kill`

### 2. File Operation Endpoints

#### Read File

- **Endpoint**: `POST /api/v1/file/read`
- **Description**: Read the content of the specified file
- **Request Body**:
  ```json
  {
    "file": "/path/to/file",  /* File path */
    "start_line": 1,  /* Optional, start line */
    "end_line": 100,  /* Optional, end line */
    "sudo": false  /* Optional, whether to read with sudo */
  }
  ```
- **Response**:
  ```json
  {
    "success": true,
    "message": "File read successfully",
    "data": {
      "content": "File content",
      "line_count": 100,
      "file": "/path/to/file"
    }
  }
  ```

#### Write File

- **Endpoint**: `POST /api/v1/file/write`
- **Description**: Write content to the specified file
- **Request Body**:
  ```json
  {
    "file": "/path/to/file",  /* File path */
    "content": "File content",  /* Content to write */
    "sudo": false  /* Optional, whether to write with sudo */
  }
  ```

#### Other File Operations

- **Replace File Content**: `POST /api/v1/file/replace`
- **Search File Content**: `POST /api/v1/file/search`
- **Find Files**: `POST /api/v1/file/find`

### 3. Process Management Endpoints

#### Get Process Status

- **Endpoint**: `GET /api/v1/supervisor/status`
- **Description**: Get the status of all service processes

#### Restart Service

- **Endpoint**: `POST /api/v1/supervisor/restart`
- **Description**: Restart the specified service
- **Request Body**:
  ```json
  {
    "service": "chrome"  /* Service name */
  }
  ```

## Container Environment Configuration

The sandbox container includes the following environments:

- Ubuntu 22.04
- Python 3.10
- Node.js 20.18.0
- Google Chrome

## Debugging Guide

### Browser Debugging

1. Connect to `localhost:5900` using a VNC client
2. Access `http://localhost:9222/devtools/inspector.html` in your browser 
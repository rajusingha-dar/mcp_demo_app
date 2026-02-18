# 📝 Personal Notes Agent

> A production-inspired, local AI agent system that demonstrates the full Model Context Protocol (MCP) stack — from a containerized MCP server to a LangGraph reasoning agent, FastAPI backend, and Streamlit chat UI.

---

## 🧭 Table of Contents

- [Project Overview](#project-overview)
- [Why We Built This](#why-we-built-this)
- [Architecture Deep Dive](#architecture-deep-dive)
- [Tech Stack Explained](#tech-stack-explained)
- [Project Structure](#project-structure)
- [How Each Component Works](#how-each-component-works)
- [The MCP Protocol Explained](#the-mcp-protocol-explained)
- [FastMCP vs MCP SDK](#fastmcp-vs-mcp-sdk)
- [LangGraph Agent Loop](#langgraph-agent-loop)
- [Data Flow: End to End](#data-flow-end-to-end)
- [Docker and Containerization](#docker-and-containerization)
- [UV Package Manager](#uv-package-manager)
- [API Reference](#api-reference)
- [Setup and Installation](#setup-and-installation)
- [Running the Project](#running-the-project)
- [Testing the System](#testing-the-system)
- [Key Learnings](#key-learnings)
- [Future Extensions](#future-extensions)

---

## Project Overview

The **Personal Notes Agent** is a beginner-to-intermediate level project designed to demonstrate how modern AI agent systems are built using the **Model Context Protocol (MCP)**. It is a fully local system — nothing runs in the cloud except the OpenAI API call for LLM reasoning.

The user interacts with a **Streamlit chat interface**, types natural language commands like *"add a note called shopping with eggs and milk"*, and the system routes that through a **FastAPI backend**, into a **LangGraph ReAct agent**, which then calls tools exposed by a **FastMCP server running in Docker**. The notes are persisted in a simple `notes.json` file mounted as a Docker volume.

This project is intentionally simple in its domain (notes management) but complex and realistic in its architecture. Every boundary between components mirrors how real production AI agent systems are structured.

---

## Why We Built This

### The Problem MCP Solves

Before MCP, every AI assistant needed custom integration code for every tool it wanted to use. A weather tool, a database tool, a file system tool — each required a unique implementation on both the AI side and the tool side. This created an M×N integration problem: M AI assistants × N tools = M×N custom integrations.

**MCP solves this with a universal standard.** Any MCP-compatible AI client can connect to any MCP server without custom integration code. It is the USB-C of AI tooling.

### Why This Project Specifically

This project was chosen because:

1. **Zero external dependencies** — no third-party APIs, no cloud databases, no paid services beyond OpenAI
2. **Complete stack coverage** — it touches every layer: UI, API, agent reasoning, protocol communication, containerization
3. **Real architectural patterns** — the separation of concerns (UI / API / Agent / Tools) mirrors production multi-agent systems
4. **Debuggable** — a simple JSON file as the data store means you can always open `notes.json` and verify the agent actually did what it said

---

## Architecture Deep Dive

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER'S MACHINE                           │
│                                                                 │
│  ┌──────────────┐    HTTP     ┌──────────────────────────────┐  │
│  │   Streamlit  │ ─────────► │       FastAPI Backend        │  │
│  │   Frontend   │ ◄───────── │                              │  │
│  │  port: 8501  │   JSON     │  ┌────────────────────────┐  │  │
│  └──────────────┘            │  │   LangGraph ReAct      │  │  │
│                              │  │       Agent            │  │  │
│                              │  │                        │  │  │
│                              │  │  ┌──────────────────┐  │  │  │
│                              │  │  │   OpenAI GPT     │  │  │  │
│                              │  │  │   (Reasoning)    │  │  │  │
│                              │  │  └──────────────────┘  │  │  │
│                              │  └────────────────────────┘  │  │
│                              │         port: 8001           │  │
│                              └──────────────┬───────────────┘  │
│                                             │ HTTP/SSE          │
│                                             ▼                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    DOCKER CONTAINER                      │  │
│  │                                                          │  │
│  │   ┌─────────────────────────────────────────────────┐   │  │
│  │   │            FastMCP Server (port: 8000)          │   │  │
│  │   │                                                 │   │  │
│  │   │   Tools:                                        │   │  │
│  │   │   • add_note(title, content)                    │   │  │
│  │   │   • list_notes()                                │   │  │
│  │   │   • read_note(title)                            │   │  │
│  │   │   • delete_note(title)                          │   │  │
│  │   │                                                 │   │  │
│  │   └──────────────────────┬──────────────────────────┘   │  │
│  │                          │ reads/writes                  │  │
│  │                          ▼                               │  │
│  │              ┌───────────────────────┐                   │  │
│  │              │      notes.json       │ ← Docker Volume   │  │
│  │              └───────────────────────┘                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Three-Tier Architecture

The system is divided into three clean tiers:

**Presentation Tier (Streamlit)** — handles user interaction only. It knows nothing about MCP, LangGraph, or notes storage. It only knows one thing: send a message to `POST /chat` and display the response.

**Logic Tier (FastAPI + LangGraph)** — the brain. FastAPI provides the HTTP interface. LangGraph orchestrates the reasoning loop. The OpenAI LLM decides which tools to call. The MCP adapter executes those tool calls against the MCP server.

**Data/Tool Tier (FastMCP in Docker)** — the tool service. Completely isolated in a container. Exposes 4 tools over SSE. Reads and writes `notes.json`. Has no knowledge of the layers above it.

---

## Tech Stack Explained

### Python
The entire project is written in Python. Python was chosen for its rich ecosystem of AI/ML libraries, readability for learning purposes, and native support from both LangChain and the MCP SDK.

### UV (Package Manager)
UV is a next-generation Python package manager written in Rust. It replaces `pip`, `venv`, `pip-tools`, and `virtualenv` in a single tool. Key advantages:
- **Speed** — 10-100x faster than pip due to Rust implementation and parallel downloads
- **Lockfiles** — `uv.lock` guarantees reproducible installs across machines
- **No manual venv activation** — `uv run` automatically uses the project's virtual environment
- **Single `pyproject.toml`** — modern Python packaging standard

In this project, one root-level `pyproject.toml` manages all local dependencies (FastAPI, LangGraph, Streamlit, etc.). The `mcp_server/` has its own `pyproject.toml` exclusively because Docker needs to build it in isolation.

### FastMCP
FastMCP is a high-level Python framework for building MCP servers. It uses Python decorators to expose functions as MCP tools, eliminating the need to manually handle JSON-RPC protocol details. Think of it as Flask for MCP servers. The `@mcp.tool()` decorator registers a function as an MCP tool with automatic schema generation from Python type hints and docstrings.

### LangChain
LangChain provides the foundational abstractions: LLM wrappers (`ChatOpenAI`), message types (`HumanMessage`, `AIMessage`), and the tool interface. It also provides `langchain-mcp-adapters`, the bridge package that connects MCP servers to LangChain-compatible tool objects.

### LangGraph
LangGraph is a framework built on top of LangChain for building stateful, multi-step agent workflows modeled as graphs. It provides:
- **`create_react_agent`** — a prebuilt ReAct (Reasoning + Acting) agent graph
- **Stateful message passing** — maintains conversation state across reasoning steps
- **Tool execution nodes** — automatically routes tool call decisions to the appropriate tool

### FastAPI
FastAPI is a modern, high-performance Python web framework. It provides:
- **Automatic OpenAPI/Swagger documentation** at `/docs`
- **Pydantic validation** of request and response bodies
- **Async support** — critical since the LangGraph agent uses async/await throughout
- **CORS middleware** — allows Streamlit (port 8501) to call FastAPI (port 8001)

### Streamlit
Streamlit is a Python framework for building data and AI web applications with minimal frontend code. Key concepts used:
- **`st.session_state`** — persists chat history across Streamlit's rerun cycle
- **`st.chat_message`** — renders user and assistant messages in a chat UI
- **`st.chat_input`** — provides the message input box at the bottom of the screen
- **`st.cache_resource`** — caches connections across reruns

### Docker & Docker Compose
Docker containerizes the MCP server, isolating it from the host machine's Python environment. This teaches the critical real-world pattern: **tools are services, not just functions**. Docker Compose defines the service, port mappings, and volume mounts in a single `docker-compose.yml` file. The `notes.json` file is mounted as a volume so data persists across container restarts.

### OpenAI GPT
The LLM backbone. GPT-4o-mini is used for cost efficiency. The LLM does not execute tools — it only **decides** which tool to call and with what arguments. LangGraph intercepts that decision and routes it to the actual tool execution layer.

---

## Project Structure

```
personal-notes-agent/
│
├── mcp_server/                        # Isolated tool service (runs in Docker)
│   ├── server.py                      # FastMCP server with 4 tools
│   ├── notes.json                     # Persistent note storage
│   ├── pyproject.toml                 # UV config for Docker build
│   └── uv.lock                        # Lockfile for reproducible Docker builds
│
├── backend/                           # Logic tier (runs locally)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                  # FastAPI endpoint definitions
│   │   └── schemas.py                 # Pydantic request/response models
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── agent.py                   # LangGraph ReAct agent
│   │   └── tools.py                   # MCP → LangChain tool adapter
│   ├── __init__.py
│   ├── main.py                        # FastAPI application entry point
│   └── config.py                      # Environment variable management
│
├── frontend/                          # Presentation tier (runs locally)
│   ├── __init__.py
│   └── app.py                         # Streamlit chatbot UI
│
├── docker-compose.yml                 # MCP server container definition
├── Dockerfile                         # MCP server image build instructions
├── .env                               # Environment variables (not committed)
├── .gitignore
├── .python-version                    # Python version pin for UV
├── pyproject.toml                     # Root UV config (all local dependencies)
├── uv.lock                            # Root lockfile
└── README.md
```

---

## How Each Component Works

### `mcp_server/server.py`

The heart of the MCP layer. Uses FastMCP to expose 4 tools:

```
add_note(title: str, content: str) → str
list_notes() → str
read_note(title: str) → str
delete_note(title: str) → str
```

Each tool is a plain Python function decorated with `@mcp.tool()`. FastMCP automatically:
- Generates a JSON schema from the function signature
- Registers it as an MCP tool
- Handles the JSON-RPC protocol when the tool is called
- Returns the function's return value as the tool result

The server runs with Uvicorn via `uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)`. The `sse_app()` method exposes two HTTP endpoints:
- `GET /sse` — SSE stream for the MCP client to connect and receive tool list
- `POST /messages` — endpoint for the MCP client to post tool call requests

### `backend/config.py`

Reads the `.env` file using `python-dotenv` and exposes clean Python variables. Acts as a single source of truth for all configuration. Raises a `ValueError` at startup if `OPENAI_API_KEY` is missing, preventing silent failures.

### `backend/api/schemas.py`

Defines Pydantic models for API contracts:
- `Message` — a single chat message with `role` and `content`
- `ChatRequest` — the body of `POST /chat`, containing the user message and conversation history
- `ChatResponse` — the response body containing the agent's reply
- `HealthResponse` — the response body for `GET /health`

Pydantic automatically validates incoming request data and raises HTTP 422 errors if the schema is violated.

### `backend/agent/tools.py`

Uses `MultiServerMCPClient` from `langchain-mcp-adapters` to:
1. Connect to the MCP server at `http://localhost:8000/sse` via SSE transport
2. Call `tools/list` to discover available tools
3. Wrap each MCP tool as a LangChain `Tool` object that LangGraph can bind to the LLM

Also provides `check_mcp_health()` which makes a simple HTTP GET to verify the MCP server is reachable.

### `backend/agent/agent.py`

The reasoning core. On each invocation:
1. Calls `get_mcp_tools()` to fetch the current tool list from the MCP server
2. Creates a `ChatOpenAI` instance with the configured model and API key
3. Builds a LangGraph ReAct agent using `create_react_agent(llm, tools)`
4. Converts the conversation history to LangChain message format
5. Calls `agent.ainvoke()` asynchronously with the full message history
6. Extracts and returns the final assistant message content

### `backend/api/routes.py`

Defines two FastAPI routes:
- `POST /chat` — validates the request, calls `run_agent()`, returns `ChatResponse`
- `GET /health` — checks MCP server connectivity, returns system status

Both are `async` functions, compatible with FastAPI's async request handling.

### `backend/main.py`

The FastAPI application entry point. Configures:
- CORS middleware allowing requests from `http://localhost:8501` (Streamlit)
- Router inclusion from `routes.py`
- Uvicorn server startup on `BACKEND_PORT`

### `frontend/app.py`

The Streamlit UI. Key patterns:
- **Session state initialization** — `st.session_state.messages` is initialized once and persists across reruns
- **Chat rendering loop** — iterates over all messages in session state and renders them with `st.chat_message`
- **Input handling** — `st.chat_input` captures user input, appends to session state, calls `send_message()`, and appends the response
- **Error boundaries** — separate `except` blocks for connection errors, timeouts, and unexpected errors provide clear feedback

---

## The MCP Protocol Explained

MCP (Model Context Protocol) is built on **JSON-RPC 2.0** transported over either stdio or HTTP/SSE. In this project, HTTP/SSE is used because the MCP server runs in Docker (a separate network context).

### Connection Lifecycle

```
1. MCP Client opens SSE connection to GET /sse
2. Server sends "endpoint" event with the /messages URL
3. Client sends initialize request to /messages
4. Server responds with capabilities and protocol version
5. Client sends tools/list request
6. Server responds with array of tool definitions (name, description, input schema)
7. Connection stays open — client is now ready to call tools
```

### Tool Call Lifecycle

```
1. LLM returns a tool_use response (name + arguments as JSON)
2. LangGraph intercepts, routes to MCP adapter
3. MCP adapter sends tools/call request to /messages:
   {
     "jsonrpc": "2.0",
     "method": "tools/call",
     "params": {
       "name": "add_note",
       "arguments": {"title": "shopping", "content": "eggs, milk"}
     }
   }
4. MCP server executes the function
5. Server returns result:
   {
     "jsonrpc": "2.0",
     "result": {
       "content": [{"type": "text", "text": "✅ Note 'shopping' saved successfully."}]
     }
   }
6. Result flows back through LangGraph to the LLM
7. LLM generates final natural language response
```

---

## FastMCP vs MCP SDK

| Aspect | MCP SDK (raw) | FastMCP |
|---|---|---|
| Tool registration | Manual handler setup | `@mcp.tool()` decorator |
| Schema generation | Write JSON schema manually | Auto-generated from type hints |
| Protocol handling | Implement JSON-RPC manually | Handled internally |
| Server lifecycle | Configure manually | `mcp.run()` or `mcp.sse_app()` |
| Learning curve | Steep — teaches protocol details | Gentle — focuses on tool logic |
| Use case | Full control, custom protocols | Rapid development, standard use |
| Relationship | Foundation library | High-level wrapper on top of SDK |

FastMCP was originally a third-party library but was absorbed into the official MCP Python SDK as `mcp.server.fastmcp`. In this project we import it as `from mcp.server.fastmcp import FastMCP`.

---

## LangGraph Agent Loop

The project uses `create_react_agent` which implements the **ReAct (Reasoning + Acting)** pattern. The agent operates as a loop:

```
┌─────────────────────────────────────────────────┐
│                  START                          │
│           (user message + history)              │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────┐
│              REASONING NODE                     │
│    LLM receives: messages + tool schemas        │
│    LLM outputs: text OR tool_call decision      │
└──────────────────────┬──────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │                       │
    tool_call?                  final answer?
           │                       │
           ▼                       ▼
┌─────────────────────┐    ┌───────────────────┐
│   TOOL NODE         │    │      END          │
│ Execute MCP tool    │    │ Return to FastAPI │
│ Get result          │    └───────────────────┘
└──────────┬──────────┘
           │
           │ (result added to messages)
           │
           └──────────► back to REASONING NODE
```

The loop continues until the LLM produces a final text response with no tool calls. Each tool result is added to the message history so the LLM can reason about it in the next iteration.

---

## Data Flow: End to End

**Example: "add a note called shopping with eggs and milk"**

```
Step 1: User types in Streamlit
        → app.py appends to session_state.messages
        → httpx.post("http://localhost:8001/chat", json={
            "message": "add a note called shopping with eggs and milk",
            "history": []
          })

Step 2: FastAPI receives POST /chat
        → Pydantic validates ChatRequest
        → routes.py calls run_agent(message, history)

Step 3: agent.py builds LangGraph agent
        → tools.py connects to http://localhost:8000/sse
        → MCP client fetches 4 tool definitions
        → create_react_agent(llm, tools) builds graph

Step 4: agent.ainvoke({"messages": [HumanMessage("add a note...")]})
        → LangGraph enters REASONING NODE
        → Sends to OpenAI: messages + tool schemas

Step 5: OpenAI responds with tool_call:
        {
          "name": "add_note",
          "arguments": {"title": "shopping", "content": "eggs and milk"}
        }

Step 6: LangGraph enters TOOL NODE
        → MCP adapter sends tools/call to http://localhost:8000/messages
        → FastMCP server receives request
        → add_note("shopping", "eggs and milk") executes
        → notes.json written: {"shopping": "eggs and milk"}
        → Returns: "✅ Note 'shopping' saved successfully."

Step 7: Result added to messages as ToolMessage
        → LangGraph re-enters REASONING NODE
        → OpenAI sees the tool result
        → Decides: no more tools needed
        → Generates: "I have added a note called 'shopping'..."

Step 8: LangGraph exits, returns final AIMessage
        → agent.py extracts .content string
        → routes.py wraps in ChatResponse(reply="I have added...")
        → FastAPI returns JSON to Streamlit

Step 9: Streamlit receives reply
        → Appends AIMessage to session_state.messages
        → Re-renders chat history with new message
        → User sees the response
```

---

## Docker and Containerization

### Why Only the MCP Server is Containerized

The MCP server is containerized because it represents the **tool service layer** — a standalone service that should be isolated from the agent that uses it. This mirrors production patterns where tool servers (database connectors, API wrappers, file system tools) are independent services.

The backend and frontend run locally because they are development-time components that benefit from `--reload` (hot reloading) during development.

### Dockerfile Explained

```dockerfile
FROM python:3.11-slim           # Minimal Python base image

# Install UV binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY mcp_server/ .              # Copy only the mcp_server contents

RUN uv sync                     # Install dependencies from pyproject.toml

EXPOSE 8000

CMD ["uv", "run", "python", "server.py"]
```

### docker-compose.yml Explained

```yaml
services:
  mcp-server:
    build:
      context: .                # Build context is project root
      dockerfile: Dockerfile
    ports:
      - "8000:8000"             # host:container port mapping
    volumes:
      - ./mcp_server/notes.json:/app/notes.json  # Persist notes outside container
    environment:
      - PYTHONUNBUFFERED=1      # Real-time log output
    restart: unless-stopped     # Auto-restart on crash
```

The volume mount `./mcp_server/notes.json:/app/notes.json` is critical — without it, every `docker-compose up` would start with an empty notes file because containers are stateless by default.

---

## UV Package Manager

### Root pyproject.toml Dependencies

```toml
[project]
name = "personal-notes-agent"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi",
    "uvicorn",
    "langgraph",
    "langchain",
    "langchain-openai",
    "langchain-mcp-adapters",
    "streamlit",
    "httpx",
    "python-dotenv",
    "pydantic",
]
```

### Key UV Commands

```bash
uv sync                          # Install all dependencies from pyproject.toml
uv add <package>                 # Add a new dependency
uv run <command>                 # Run a command in the UV virtual environment
uv run uvicorn backend.main:app  # Run uvicorn without activating venv manually
uv run streamlit run frontend/app.py
```

---

## API Reference

### POST /chat

Send a message to the agent.

**Request Body:**
```json
{
  "message": "add a note called shopping with eggs and milk",
  "history": [
    {"role": "user", "content": "previous message"},
    {"role": "assistant", "content": "previous response"}
  ]
}
```

**Response:**
```json
{
  "reply": "I have added a note called 'shopping' with the content 'eggs and milk'."
}
```

**Status Codes:**
- `200` — Success
- `422` — Validation error (invalid request body)
- `500` — Agent or MCP server error

---

### GET /health

Check system health.

**Response:**
```json
{
  "status": "ok",
  "mcp_server": "online",
  "backend": "online"
}
```

**Status values:**
- `status`: `"ok"` (all systems up) or `"degraded"` (MCP server unreachable)
- `mcp_server`: `"online"` or `"offline"`
- `backend`: always `"online"` (if this endpoint responds, backend is up)

---

## Setup and Installation

### Prerequisites

- Python 3.11+
- UV installed (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Docker Desktop running
- OpenAI API key

### Installation Steps

```bash
# 1. Clone the repository
git clone <repository-url>
cd personal-notes-agent

# 2. Install all local dependencies
uv sync

# 3. Configure environment variables
cp .env.example .env
# Edit .env and add your OpenAI API key
```

### Environment Variables

Create a `.env` file at the project root:

```env
OPENAI_API_KEY=sk-your-openai-api-key-here
MCP_SERVER_URL=http://localhost:8000
BACKEND_PORT=8001
MODEL_NAME=gpt-4o-mini
```

---

## Running the Project

Open **three separate terminals** from the project root:

**Terminal 1 — MCP Server (Docker):**
```bash
docker-compose up --build
```
Wait for: `Uvicorn running on http://0.0.0.0:8000`

**Terminal 2 — FastAPI Backend:**
```bash
uv run uvicorn backend.main:app --port 8001 --reload
```
Wait for: `Application startup complete`

**Terminal 3 — Streamlit Frontend:**
```bash
uv run streamlit run frontend/app.py
```
Open browser at: `http://localhost:8501`

---

## Testing the System

### Health Check
Click **"Check Connection"** in the Streamlit sidebar. Expect: `Backend is online ✅`

Or via terminal:
```bash
curl http://localhost:8001/health
```

### Adding Notes
```
add a note called shopping with eggs, milk and bread
add a note called work with finish the project report by friday
add a note called fitness with morning run 5km and gym at 6pm
```

### Listing Notes
```
show me all my notes
```

### Reading a Note
```
read my note called fitness
```

### Deleting a Note
```
delete the note called work
show me all my notes
```

### Verify Persistence
Open `mcp_server/notes.json` in VS Code — you will see all saved notes in plain JSON.

---

## Key Learnings

### 1. MCP is Not for Agent-to-Agent Communication
MCP is a client-server protocol where **servers expose tools** and **clients consume them**. It is not a messaging system between agents. Agent-to-agent communication requires separate patterns.

### 2. The LLM Does Not Execute Tools
The LLM only **decides** what tool to call. LangGraph intercepts that decision and routes it to the actual tool. The LLM never directly touches `notes.json`.

### 3. SSE Transport Enables Docker Isolation
Using SSE (Server-Sent Events) transport instead of stdio means the MCP server can run in a container while the agent runs on the host. stdio transport requires both to run in the same process — impractical for real systems.

### 4. Separation of Concerns is Everything
Each layer only knows about the layer immediately below it. Streamlit doesn't know about LangGraph. FastAPI doesn't know about `notes.json`. This is what makes the system maintainable and extensible.

### 5. Docker Volumes Solve Container Statefulness
Containers are ephemeral — they lose data on restart. Docker volumes mount host directories into containers, providing persistence without changing the container architecture.

---

## Future Extensions

### Short Term
- Add a `search_notes(query)` tool that does keyword search across all note contents
- Add note timestamps (created_at, updated_at) to the JSON structure
- Add a `update_note(title, content)` tool for editing existing notes

### Medium Term
- Replace `notes.json` with SQLite for proper querying and indexing
- Add streaming responses so the Streamlit UI shows the agent "thinking" in real time
- Add authentication to the FastAPI backend

### Long Term
- **Multi-agent architecture** — add a router agent that delegates to specialized sub-agents (notes agent, calendar agent, weather agent), each backed by their own MCP server
- **Multiple MCP servers** — the `MultiServerMCPClient` already supports connecting to multiple servers simultaneously
- **MCP Resources** — expose notes as MCP Resources (readable data) in addition to tools
- **Deploy to production** — containerize all components, deploy to a cloud provider

---

## Port Reference

| Service | Transport | Port | URL |
|---|---|---|---|
| MCP Server | HTTP/SSE (Docker) | 8000 | http://localhost:8000/sse |
| FastAPI Backend | HTTP (local) | 8001 | http://localhost:8001 |
| FastAPI Swagger | HTTP (local) | 8001 | http://localhost:8001/docs |
| Streamlit UI | HTTP (local) | 8501 | http://localhost:8501 |

---

## License

MIT License — free to use, modify, and distribute.

---

*Built as a learning project to understand MCP, LangGraph, FastAPI, and modern AI agent architecture patterns.*
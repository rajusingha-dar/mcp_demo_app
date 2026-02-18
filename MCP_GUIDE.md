# 🔌 Model Context Protocol (MCP) — The Complete Guide

> A comprehensive, technical deep-dive into MCP: what it is, why it exists, how it works internally, and how to build with it. Written as a practical reference for developers building AI agent systems.

---

## 📚 Table of Contents

- [What is MCP?](#what-is-mcp)
- [The Problem MCP Solves](#the-problem-mcp-solves)
- [Core Concepts](#core-concepts)
- [Architecture Overview](#architecture-overview)
- [The Three Primitives](#the-three-primitives)
- [Transport Layer](#transport-layer)
- [The JSON-RPC Protocol](#the-json-rpc-protocol)
- [Connection Lifecycle](#connection-lifecycle)
- [Tool Call Lifecycle](#tool-call-lifecycle)
- [MCP SDK vs FastMCP](#mcp-sdk-vs-fastmcp)
- [Building an MCP Server](#building-an-mcp-server)
- [Building an MCP Client](#building-an-mcp-client)
- [MCP in Multi-Agent Systems](#mcp-in-multi-agent-systems)
- [Security Considerations](#security-considerations)
- [MCP vs Other Approaches](#mcp-vs-other-approaches)
- [Common Patterns and Best Practices](#common-patterns-and-best-practices)
- [Debugging MCP](#debugging-mcp)
- [Quick Reference](#quick-reference)

---

## What is MCP?

**Model Context Protocol (MCP)** is an open standard protocol created by Anthropic that defines how AI assistants (clients) communicate with external tools and data sources (servers). It was released in November 2024 and has since been adopted across the AI ecosystem.

Think of MCP as **USB-C for AI**. Just as USB-C is a universal standard that lets any device connect to any peripheral without custom cables, MCP is a universal standard that lets any AI connect to any tool without custom integration code.

### The One-Line Definition

> MCP is a standardized client-server protocol, built on JSON-RPC 2.0, that allows AI applications to discover and invoke tools, read resources, and use prompt templates from external servers.

### What MCP Is NOT

- ❌ Not a way for agents to talk to each other (that's a separate concern)
- ❌ Not a cloud service or SaaS product
- ❌ Not tied to any specific AI model or provider
- ❌ Not a replacement for REST APIs (it complements them)
- ❌ Not just for Claude — any AI system can implement MCP

---

## The Problem MCP Solves

### Before MCP: The M×N Problem

Imagine you have 5 AI assistants and 10 tools (Slack, GitHub, databases, file systems, etc.). Without a standard protocol, every combination needs a custom integration:

```
5 AI assistants × 10 tools = 50 custom integrations to build and maintain
```

Each integration is unique. Different authentication patterns, different data formats, different error handling, different update cycles. This is the **M×N integration problem**.

```
BEFORE MCP:

Claude ──── custom code ────► Slack
Claude ──── custom code ────► GitHub  
Claude ──── custom code ────► Database
Claude ──── custom code ────► File System

GPT ────── custom code ────► Slack
GPT ────── custom code ────► GitHub
GPT ────── custom code ────► Database
...

= M × N integrations (chaos)
```

### After MCP: M+N

With MCP, each tool is built once as an MCP server. Each AI is built once as an MCP client. They can all talk to each other through the shared standard:

```
AFTER MCP:

Claude ─────────────────────────────────────────────► MCP
GPT    ──── MCP Client ────► MCP Protocol ────────► Standard ──► Slack MCP Server
Gemini ─────────────────────────────────────────────► ──────────► GitHub MCP Server
                                                                ► Database MCP Server
                                                                ► File System MCP Server

= M + N integrations (order)
```

### Real-World Impact

- A developer builds a **GitHub MCP server** once. Every MCP-compatible AI (Claude, GPT, Gemini, local models) can use it immediately without any additional code.
- An enterprise builds a **database MCP server** once. All their AI products get database access automatically.
- The AI ecosystem moves from thousands of one-off integrations to a shared library of reusable MCP servers.

---

## Core Concepts

### 1. Hosts
The application that the user interacts with. The host creates and manages MCP clients. Examples: Claude Desktop, a custom chatbot app, an IDE plugin, your Streamlit app.

### 2. Clients
The MCP client lives inside the host application. It maintains a connection to one MCP server, manages the protocol lifecycle, and routes tool calls from the AI to the server. One client = one server connection. To connect to multiple servers, you use multiple clients.

### 3. Servers
Standalone processes (local or remote) that expose capabilities through MCP. A server can expose tools, resources, and prompts. It does not initiate connections — it waits for clients to connect. Examples: a filesystem server, a database server, a weather API wrapper.

### 4. The Protocol
The language clients and servers use to communicate. Built on JSON-RPC 2.0. Transported over stdio or HTTP/SSE.

```
┌─────────────────────────────────────────────────────┐
│                      HOST                           │
│                                                     │
│   ┌─────────┐        ┌─────────┐                   │
│   │   AI    │        │   AI    │                   │
│   │  Model  │        │  Model  │                   │
│   └────┬────┘        └────┬────┘                   │
│        │                  │                        │
│   ┌────▼────┐        ┌────▼────┐                   │
│   │  MCP    │        │  MCP    │                   │
│   │ Client  │        │ Client  │                   │
│   └────┬────┘        └────┬────┘                   │
└────────┼─────────────────┼───────────────────────-─┘
         │ MCP Protocol    │ MCP Protocol
         ▼                 ▼
  ┌─────────────┐   ┌─────────────┐
  │  MCP Server │   │  MCP Server │
  │  (notes)    │   │  (weather)  │
  └─────────────┘   └─────────────┘
```

---

## Architecture Overview

MCP follows a strict client-server architecture with clear responsibilities on each side:

### Server Responsibilities
- Expose a list of available tools, resources, and prompts
- Execute tool calls when requested
- Return results in the MCP response format
- Handle errors gracefully
- Manage its own state and data

### Client Responsibilities
- Initiate and maintain the connection
- Fetch the capability list (tools, resources, prompts)
- Pass tool schemas to the LLM
- Route LLM tool call decisions to the server
- Handle server responses and errors
- Pass results back to the LLM

### What the LLM Does (and Does NOT Do)
The LLM **decides** which tool to call and with what arguments based on the tool schemas provided. The LLM **does not** execute the tool. The MCP client intercepts the LLM's tool call decision and routes it to the server. The LLM only sees the result.

```
LLM ──► "I want to call add_note with title='shopping'" ──► Client intercepts
                                                              │
                                                              ▼
                                                        MCP Server executes
                                                              │
                                                              ▼
                                                        Result returned to LLM
```

---

## The Three Primitives

MCP servers can expose three types of capabilities:

### 1. Tools 🔧

Tools are **functions the AI can call**. They are the most commonly used MCP primitive. Tools take inputs, perform actions, and return results.

```
Characteristics:
- Have a name, description, and input schema
- Can have side effects (write to database, send email, etc.)
- Return text or structured content
- The AI decides when and how to call them

Examples:
- add_note(title, content)
- send_email(to, subject, body)
- query_database(sql)
- create_github_issue(title, description)
- get_weather(city)
```

**Schema structure the client receives:**
```json
{
  "name": "add_note",
  "description": "Add a new note with a title and content",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {
        "type": "string",
        "description": "The title of the note"
      },
      "content": {
        "type": "string", 
        "description": "The content of the note"
      }
    },
    "required": ["title", "content"]
  }
}
```

---

### 2. Resources 📄

Resources are **data the AI can read**. They are analogous to GET endpoints in REST — they expose data without side effects. Resources can be static or dynamic.

```
Characteristics:
- Identified by a URI (e.g., notes://shopping, file:///path/to/file)
- Read-only by convention (no side effects)
- Can be static files or dynamically generated content
- Support text and binary content types
- Can be listed and subscribed to

Examples:
- A file: file:///home/user/document.txt
- A database record: db://customers/12345
- A note: notes://shopping
- A webpage: https://example.com/data
- A template: template://email/welcome
```

**When to use Resources vs Tools:**
- Use **Resources** when the AI needs to read data (no side effects)
- Use **Tools** when the AI needs to perform an action (with side effects)
- A "read file" capability should be a Resource; a "write file" capability should be a Tool

---

### 3. Prompts 💬

Prompts are **pre-built message templates** that guide the AI in specific tasks. They are reusable, parameterized instructions that can be surfaced to users or used programmatically.

```
Characteristics:
- Named templates with optional parameters
- Can include multi-turn conversation starters
- Useful for standardizing common AI workflows
- Less commonly used than Tools and Resources

Examples:
- "Summarize this document" template
- "Write a commit message for these changes" template
- "Explain this error in simple terms" template
- "Generate a test for this function" template
```

---

## Transport Layer

MCP supports two transport mechanisms. The transport layer handles how bytes are physically moved between client and server. The protocol (JSON-RPC) is the same regardless of transport.

### stdio Transport

The client launches the MCP server as a **child subprocess** and communicates through standard input/output pipes.

```
┌─────────────────────────────────────┐
│           Host Process              │
│                                     │
│  ┌──────────┐    stdin/stdout    ┌──────────┐  │
│  │  Client  │ ◄────────────────► │  Server  │  │
│  └──────────┘    (same machine)  └──────────┘  │
│                                     │
└─────────────────────────────────────┘
```

**Characteristics:**
- Simple — no networking required
- Secure — process isolation, no network exposure
- Low latency — direct pipe communication
- Limitation — both client and server must run on the same machine
- Client manages server lifecycle (starts and stops the process)

**Best for:**
- Local development tools
- Desktop applications (Claude Desktop)
- IDE extensions
- CLI tools

**Example connection config (Claude Desktop):**
```json
{
  "mcpServers": {
    "notes": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

---

### HTTP/SSE Transport

The server runs as a standalone HTTP service. The client connects over the network using **Server-Sent Events (SSE)** for streaming.

```
┌──────────────────┐          ┌──────────────────┐
│   Host Machine   │          │  Server Machine  │
│                  │          │  (or Docker)     │
│  ┌────────────┐  │  HTTP    │  ┌────────────┐  │
│  │   Client   │  │◄────────►│  │   Server   │  │
│  └────────────┘  │  /sse    │  └────────────┘  │
│                  │  /msgs   │                  │
└──────────────────┘          └──────────────────┘
```

**Characteristics:**
- Client and server can run on different machines
- Server runs independently (client doesn't manage its lifecycle)
- Network overhead (slightly higher latency than stdio)
- Enables containerization (server in Docker, client on host)
- Two endpoints: `GET /sse` (stream) and `POST /messages` (tool calls)

**SSE explained:**
SSE (Server-Sent Events) is a web standard where a server pushes real-time updates to a client over a persistent HTTP connection. The client opens a `GET /sse` connection that stays open. The server sends events through this stream. Tool call responses are posted to `POST /messages`.

**Best for:**
- Containerized deployments (Docker)
- Remote servers
- Multi-tenant environments
- Production deployments

**Example connection config (Python client):**
```python
client = MultiServerMCPClient({
    "notes": {
        "url": "http://localhost:8000/sse",
        "transport": "sse"
    }
})
```

---

### Choosing Between stdio and SSE

| Situation | Use |
|---|---|
| Local development, same machine | stdio |
| Server in Docker container | SSE |
| Server on remote machine | SSE |
| Claude Desktop integration | stdio |
| Production deployment | SSE |
| Maximum simplicity | stdio |
| Maximum flexibility | SSE |

---

## The JSON-RPC Protocol

MCP uses **JSON-RPC 2.0** as its message format. JSON-RPC is a lightweight remote procedure call protocol that uses JSON for encoding. Every message between client and server is a JSON object.

### Message Types

**Request** — client asks server to do something:
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "tools/call",
  "params": {
    "name": "add_note",
    "arguments": {
      "title": "shopping",
      "content": "eggs and milk"
    }
  }
}
```

**Response** — server replies to a request:
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "content": [
      {
        "type": "text",
        "text": "✅ Note 'shopping' saved successfully."
      }
    ]
  }
}
```

**Error Response** — server signals failure:
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "error": {
    "code": -32600,
    "message": "Note not found",
    "data": {"title": "shopping"}
  }
}
```

**Notification** — one-way message, no response expected:
```json
{
  "jsonrpc": "2.0",
  "method": "notifications/tools/list_changed"
}
```

### Standard MCP Methods

| Method | Direction | Purpose |
|---|---|---|
| `initialize` | Client → Server | Start session, exchange capabilities |
| `initialized` | Client → Server | Confirm initialization complete |
| `tools/list` | Client → Server | Get available tools |
| `tools/call` | Client → Server | Execute a tool |
| `resources/list` | Client → Server | Get available resources |
| `resources/read` | Client → Server | Read a resource |
| `prompts/list` | Client → Server | Get available prompts |
| `prompts/get` | Client → Server | Get a specific prompt |
| `ping` | Either → Either | Keep-alive check |
| `notifications/tools/list_changed` | Server → Client | Notify tool list changed |

---

## Connection Lifecycle

Every MCP session follows the same lifecycle:

### Phase 1: Initialization

```
Client                                    Server
  │                                          │
  │──── initialize ──────────────────────►  │
  │     {protocolVersion, capabilities}     │
  │                                          │
  │◄─── initialized response ─────────────  │
  │     {protocolVersion, capabilities,     │
  │      serverInfo}                        │
  │                                          │
  │──── initialized (notification) ──────►  │
  │                                          │
```

The `initialize` request contains:
- `protocolVersion` — the MCP version the client supports
- `capabilities` — what the client can do (sampling, roots, etc.)
- `clientInfo` — name and version of the client

The server responds with:
- `protocolVersion` — agreed protocol version
- `capabilities` — what the server exposes (tools, resources, prompts)
- `serverInfo` — name and version of the server

---

### Phase 2: Discovery

```
Client                                    Server
  │                                          │
  │──── tools/list ──────────────────────►  │
  │                                          │
  │◄─── tools list response ───────────────  │
  │     [{name, description, inputSchema}]  │
  │                                          │
  │──── resources/list ──────────────────►  │
  │                                          │
  │◄─── resources list response ───────────  │
  │     [{uri, name, description, mimeType}]│
  │                                          │
```

After initialization, the client fetches all capabilities. These are passed to the LLM as context so it knows what tools are available.

---

### Phase 3: Operation

```
Client                                    Server
  │                                          │
  │  [LLM decides to call add_note]         │
  │                                          │
  │──── tools/call ──────────────────────►  │
  │     {name: "add_note",                  │
  │      arguments: {title, content}}       │
  │                                          │
  │◄─── tool result ───────────────────────  │
  │     {content: [{type: "text",           │
  │                 text: "✅ saved"}]}     │
  │                                          │
  │  [Result passed back to LLM]            │
  │                                          │
```

This phase repeats as many times as needed — the LLM can call multiple tools across multiple reasoning steps.

---

### Phase 4: Termination

The connection is terminated when the client disconnects (for stdio: process exits; for SSE: HTTP connection closes). MCP does not have a formal "shutdown" handshake — termination is handled at the transport level.

---

## Tool Call Lifecycle

This is the most important flow to understand — what happens when the LLM decides to call a tool:

```
┌─────────────────────────────────────────────────────────────────┐
│  1. LLM DECISION                                                │
│                                                                 │
│  LLM receives: user message + tool schemas                      │
│  LLM outputs:                                                   │
│  {                                                              │
│    "type": "tool_use",                                          │
│    "name": "add_note",                                          │
│    "input": {"title": "shopping", "content": "eggs"}           │
│  }                                                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  2. CLIENT INTERCEPTS                                           │
│                                                                 │
│  LangGraph / LangChain sees tool_use response                   │
│  Routes to MCP adapter (langchain-mcp-adapters)                 │
│  MCP adapter prepares JSON-RPC request                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  3. JSON-RPC REQUEST SENT                                       │
│                                                                 │
│  POST /messages HTTP/1.1                                        │
│  {                                                              │
│    "jsonrpc": "2.0",                                            │
│    "id": "call-001",                                            │
│    "method": "tools/call",                                      │
│    "params": {                                                  │
│      "name": "add_note",                                        │
│      "arguments": {"title": "shopping", "content": "eggs"}     │
│    }                                                            │
│  }                                                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. SERVER EXECUTES                                             │
│                                                                 │
│  FastMCP receives request                                       │
│  Routes to add_note() function                                  │
│  Function runs: loads notes.json, writes new note, saves       │
│  Function returns: "✅ Note 'shopping' saved successfully."     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  5. JSON-RPC RESPONSE                                           │
│                                                                 │
│  {                                                              │
│    "jsonrpc": "2.0",                                            │
│    "id": "call-001",                                            │
│    "result": {                                                  │
│      "content": [                                               │
│        {"type": "text",                                         │
│         "text": "✅ Note 'shopping' saved successfully."}      │
│      ],                                                         │
│      "isError": false                                           │
│    }                                                            │
│  }                                                              │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. RESULT RETURNED TO LLM                                      │
│                                                                 │
│  MCP adapter wraps result as ToolMessage                        │
│  LangGraph adds to message history                              │
│  LLM receives: original message + tool result                   │
│  LLM generates: "I have added a note called 'shopping'..."     │
└─────────────────────────────────────────────────────────────────┘
```

---

## MCP SDK vs FastMCP

### The MCP Python SDK (Raw)

The official MCP Python SDK (`mcp`) provides low-level building blocks. You manually register handlers, manage the server lifecycle, and have full control over every aspect of the protocol.

```python
# Raw MCP SDK approach
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.types as types

server = Server("my-server")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="add_note",
            description="Add a new note",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["title", "content"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "add_note":
        # implementation
        return [types.TextContent(type="text", text="saved")]
    raise ValueError(f"Unknown tool: {name}")

# Run server
async def main():
    async with mcp.server.stdio.stdio_server() as (read, write):
        await server.run(read, write, InitializationOptions(...))
```

### FastMCP (High Level)

FastMCP is a high-level wrapper on the SDK. It was originally a third-party library, later absorbed into the official SDK as `mcp.server.fastmcp`. It uses decorators and automatic schema generation.

```python
# FastMCP approach — same functionality, much less code
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Add a new note with a title and content."""
    # implementation
    return "✅ Note saved successfully."
```

FastMCP automatically handles:
- JSON schema generation from Python type hints
- Tool registration and routing
- Server lifecycle
- Error handling and formatting
- SSE/stdio transport setup

### Detailed Comparison

| Feature | MCP SDK (raw) | FastMCP |
|---|---|---|
| Code verbosity | High | Low |
| Schema definition | Manual JSON | Auto from type hints |
| Tool registration | Manual handlers | `@mcp.tool()` decorator |
| Resource definition | Manual handlers | `@mcp.resource()` decorator |
| Prompt definition | Manual handlers | `@mcp.prompt()` decorator |
| Async required | Yes | No (sync functions work) |
| Error handling | Manual | Automatic |
| Transport setup | Manual | `mcp.run(transport="sse")` |
| Learning curve | Steep | Gentle |
| Control level | Complete | High |
| Best for | Custom protocols, advanced use | Standard tool servers |
| Import path | `from mcp.server import Server` | `from mcp.server.fastmcp import FastMCP` |

### When to Use Each

Use **raw MCP SDK** when:
- You need non-standard protocol behaviour
- You're building MCP infrastructure (not just servers)
- You want to understand MCP internals deeply
- You have highly custom authentication or streaming needs

Use **FastMCP** when:
- You're building tool servers (the vast majority of use cases)
- You want rapid development
- Your tools are standard Python functions
- You're learning MCP

---

## Building an MCP Server

### Minimal Server Structure

```python
from mcp.server.fastmcp import FastMCP

# 1. Create the FastMCP instance with a server name
mcp = FastMCP("server-name")

# 2. Register tools
@mcp.tool()
def my_tool(param1: str, param2: int) -> str:
    """Clear description of what this tool does. 
    The LLM reads this to decide when to call the tool."""
    # implementation
    return "result"

# 3. Register resources (optional)
@mcp.resource("mydata://items")
def get_items() -> str:
    """Returns a list of items."""
    return "item1, item2, item3"

# 4. Register prompts (optional)
@mcp.prompt()
def my_prompt(context: str) -> str:
    """A reusable prompt template."""
    return f"Given this context: {context}\nPlease analyze..."

# 5. Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)
    # OR for stdio:
    # mcp.run(transport="stdio")
```

### Tool Design Best Practices

**Write clear, specific descriptions.** The LLM uses the description to decide when to call the tool. A vague description leads to the wrong tool being called.

```python
# ❌ Bad description
@mcp.tool()
def add(title: str, content: str) -> str:
    """Adds something."""
    pass

# ✅ Good description  
@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Save a new personal note with a title and content body. 
    Use this when the user wants to remember, store, or save any piece of information."""
    pass
```

**Use specific Python types.** FastMCP generates JSON schemas from type hints. Be specific.

```python
# ❌ Vague types
@mcp.tool()
def search(query, limit) -> str:
    pass

# ✅ Specific types with defaults
@mcp.tool()
def search_notes(query: str, limit: int = 10) -> str:
    """Search notes by keyword. Returns up to `limit` matching notes."""
    pass
```

**Return meaningful results.** The LLM reads the return value. Make it informative.

```python
# ❌ Unhelpful return
return "done"

# ✅ Helpful return
return f"✅ Note '{title}' saved successfully. You now have {len(notes)} notes total."
```

**Handle errors gracefully.** Return error information as text rather than raising exceptions.

```python
@mcp.tool()
def read_note(title: str) -> str:
    """Read the content of a note by its title."""
    notes = load_notes()
    if title not in notes:
        available = ", ".join(notes.keys()) if notes else "none"
        return f"❌ Note '{title}' not found. Available notes: {available}"
    return f"📄 {title}:\n{notes[title]}"
```

---

## Building an MCP Client

### Using langchain-mcp-adapters (Recommended for LangGraph)

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

async def build_agent():
    # 1. Create MCP client pointing to your server(s)
    client = MultiServerMCPClient({
        "notes": {
            "url": "http://localhost:8000/sse",
            "transport": "sse"
        },
        # Add more servers here
        "weather": {
            "url": "http://localhost:8001/sse", 
            "transport": "sse"
        }
    })
    
    # 2. Fetch tools from all connected servers
    tools = await client.get_tools()
    # tools is now a list of LangChain Tool objects
    
    # 3. Build agent with these tools
    llm = ChatOpenAI(model="gpt-4o-mini")
    agent = create_react_agent(llm, tools)
    
    # 4. Run the agent
    result = await agent.ainvoke({
        "messages": [{"role": "user", "content": "add a note called test"}]
    })
    
    return result["messages"][-1].content
```

### Using the Raw MCP SDK Client

```python
from mcp import ClientSession
from mcp.client.sse import sse_client

async def raw_mcp_client():
    async with sse_client("http://localhost:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize
            await session.initialize()
            
            # List tools
            tools = await session.list_tools()
            print([t.name for t in tools.tools])
            
            # Call a tool
            result = await session.call_tool(
                "add_note",
                {"title": "test", "content": "hello world"}
            )
            print(result.content[0].text)
```

---

## MCP in Multi-Agent Systems

MCP's role in multi-agent systems is specifically as the **tool layer**, not the communication layer between agents. Each agent uses MCP to access its specialized tools.

```
┌─────────────────────────────────────────────────────────────┐
│                    MULTI-AGENT SYSTEM                       │
│                                                             │
│  User Input                                                 │
│      │                                                      │
│      ▼                                                      │
│  ┌─────────────────┐                                        │
│  │   Router Agent  │  (decides which agent to delegate to) │
│  └────────┬────────┘                                        │
│           │                                                 │
│    ┌──────┼──────┐                                          │
│    │      │      │                                          │
│    ▼      ▼      ▼                                          │
│  ┌────┐ ┌────┐ ┌────┐   ← Specialized Agents               │
│  │Note│ │Wthr│ │Math│                                       │
│  │Agnt│ │Agnt│ │Agnt│                                       │
│  └──┬─┘ └──┬─┘ └──┬─┘                                       │
│     │      │      │                                         │
│     ▼      ▼      ▼                                         │
│  ┌────┐ ┌────┐ ┌────┐   ← MCP Servers (tool layer)         │
│  │Note│ │Wthr│ │Math│                                       │
│  │MCP │ │MCP │ │MCP │                                       │
│  └────┘ └────┘ └────┘                                       │
└─────────────────────────────────────────────────────────────┘
```

### Agent-to-Agent Communication (NOT MCP)

Agents communicate with each other through direct function calls, message queues, or shared state — not through MCP. MCP is only used at the boundary between an agent and its tools.

```
Router → Notes Agent:    Direct Python function call
Notes Agent → MCP Server: MCP protocol (tools/call)
```

### Benefits of MCP in Multi-Agent Systems

**Standardization** — every agent connects to its tools the same way. No special code for each agent-tool pair.

**Hot-swappability** — swap out the notes MCP server for a different implementation without changing the agent code.

**Reusability** — a weather MCP server can be shared between the weather agent, the travel agent, and the planning agent.

**Independent scaling** — each MCP server can be scaled, deployed, and updated independently.

---

## Security Considerations

### Trust Boundaries

MCP introduces new trust boundaries you must think about:

```
User → Host (trusted) → Client (trusted) → Server (semi-trusted)
```

The MCP server receives tool call requests from the client. You must decide: do you trust all clients that can reach your server?

### Authentication

MCP itself does not define authentication — that is left to the transport layer. Options:

**For SSE transport:**
- API keys in HTTP headers
- OAuth tokens
- mTLS (mutual TLS)
- Network-level access control (firewall, VPN)

**For stdio transport:**
- Process-level isolation provides implicit security
- The client controls which server processes it launches

### Input Validation

Always validate tool inputs on the server side, even though FastMCP validates types:

```python
@mcp.tool()
def read_file(path: str) -> str:
    """Read a file by path."""
    # ✅ Always validate — never trust client input
    safe_path = Path(path).resolve()
    allowed_base = Path("/safe/directory").resolve()
    
    if not str(safe_path).startswith(str(allowed_base)):
        return "❌ Access denied: path outside allowed directory"
    
    return safe_path.read_text()
```

### Prompt Injection

When MCP tools return content that gets passed back to the LLM, that content could contain **prompt injection attacks** — malicious instructions embedded in tool results. Sanitize tool outputs that come from untrusted sources (user data, web content, etc.).

### Tool Capability Principle of Least Privilege

Only expose the tools your server actually needs. If an agent only reads notes, don't give it the delete tool. Separate read and write servers if needed.

---

## MCP vs Other Approaches

### MCP vs Direct API Calls

| Aspect | Direct API | MCP |
|---|---|---|
| Integration effort | Per-tool custom code | Write once, use anywhere |
| Standardization | None | Universal |
| Tool discovery | Hardcoded in prompts | Dynamic via tools/list |
| Schema validation | Manual | Automatic |
| Reusability | Low | High |
| Complexity | Low (for 1 tool) | Low (for many tools) |

**When to use direct API:** Simple scripts, one-off tools, prototypes with 1-2 tools.
**When to use MCP:** Multiple tools, multiple AI clients, production systems, shared tool libraries.

### MCP vs Function Calling (OpenAI)

OpenAI's function calling and MCP solve similar problems but at different levels:

| Aspect | OpenAI Function Calling | MCP |
|---|---|---|
| Scope | LLM-level feature | System-level protocol |
| Portability | OpenAI only | Any MCP-compatible AI |
| Tool server | Not standardized | Standardized MCP server |
| Discovery | Static (defined per-call) | Dynamic (tools/list) |
| Transport | API call | stdio or SSE |

MCP and function calling complement each other. MCP defines how tools are served and discovered. Function calling is how the LLM decides to invoke them. LangChain's MCP adapters bridge both — MCP tools are exposed as function calling tools to the LLM.

### MCP vs LangChain Tools

| Aspect | LangChain Tools | MCP Tools |
|---|---|---|
| Scope | Python-only | Language-agnostic |
| Portability | LangChain ecosystem | Any MCP client |
| Deployment | In-process | Separate process/container |
| Reusability | Within LangChain | Across any AI system |
| Discovery | Static code | Dynamic protocol |

**MCP tools via LangChain:** `langchain-mcp-adapters` converts MCP tools into LangChain tools, giving you both portability (MCP) and LangChain integration.

---

## Common Patterns and Best Practices

### Pattern 1: One Server Per Domain

Keep MCP servers focused on a single domain. Don't build a "do everything" server.

```
✅ Good:
- notes-server (manages notes)
- weather-server (provides weather)
- calendar-server (manages calendar)

❌ Bad:
- everything-server (notes + weather + calendar + email + ...)
```

### Pattern 2: Stateless Tools When Possible

Design tools to be stateless — they receive all needed input as parameters and return all output as return values. State lives in the backing store (file, database), not in the server process.

```python
# ✅ Stateless — all state in notes.json
@mcp.tool()
def add_note(title: str, content: str) -> str:
    notes = load_notes()    # read state
    notes[title] = content
    save_notes(notes)       # write state
    return "saved"

# ❌ Stateful — state in memory, lost on restart
class NoteServer:
    def __init__(self):
        self.notes = {}  # in-memory state
    
    @mcp.tool()
    def add_note(self, title: str, content: str) -> str:
        self.notes[title] = content  # lost on restart!
```

### Pattern 3: Descriptive Return Values

The LLM reads tool return values. Return enough context for the LLM to generate a good response.

```python
# ❌ Too terse
return "ok"

# ✅ Contextual and informative
return f"✅ Added '{title}'. You now have {total} notes: {', '.join(all_titles)}"
```

### Pattern 4: Health Endpoint

Always add a health check endpoint to SSE servers for monitoring and debugging:

```python
from fastapi import FastAPI
app = FastAPI()
app.mount("/", mcp.sse_app())

@app.get("/health")
def health():
    return {"status": "ok", "server": "notes-mcp-server"}
```

### Pattern 5: Environment-Based Configuration

Never hardcode paths, credentials, or URLs. Use environment variables:

```python
import os
NOTES_FILE = Path(os.getenv("NOTES_FILE", "./notes.json"))
MAX_NOTES = int(os.getenv("MAX_NOTES", "100"))
```

---

## Debugging MCP

### Debugging Tool Registration

Add a startup log to verify tools are registered:

```python
if __name__ == "__main__":
    # List registered tools before starting
    print("Registered tools:")
    for tool in mcp._tool_manager.list_tools():
        print(f"  - {tool.name}: {tool.description}")
    
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)
```

### Debugging Tool Calls

Add logging to your tools to trace execution:

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Add a new note."""
    logger.info(f"add_note called: title='{title}', content='{content}'")
    # implementation
    logger.info(f"add_note succeeded: saved '{title}'")
    return f"✅ Note '{title}' saved."
```

### Testing Tools Directly

Test your MCP server tools independently before connecting an agent:

```python
# test_server.py
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def test():
    async with sse_client("http://localhost:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # Test list tools
            tools = await session.list_tools()
            print("Available tools:", [t.name for t in tools.tools])
            
            # Test add_note
            result = await session.call_tool("add_note", {
                "title": "test",
                "content": "test content"
            })
            print("add_note result:", result.content[0].text)
            
            # Test list_notes
            result = await session.call_tool("list_notes", {})
            print("list_notes result:", result.content[0].text)

asyncio.run(test())
```

### Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `Connection refused` | Server not running | Start the MCP server first |
| `Expecting value: line 1 column 1` | Empty JSON file | Initialize file with `{}` |
| `Tool not found` | Tool not registered | Check `@mcp.tool()` decorator |
| `TypeError: unexpected keyword argument` | Wrong FastMCP API | Check FastMCP version docs |
| `CORS error` | Missing CORS headers | Add CORS middleware to FastAPI |
| `Timeout` | Server too slow | Increase client timeout |
| `127.0.0.1` instead of `0.0.0.0` | Wrong host binding | Use `host="0.0.0.0"` in uvicorn |

---

## Quick Reference

### MCP Server Skeleton (FastMCP + SSE)

```python
from mcp.server.fastmcp import FastMCP
import uvicorn

mcp = FastMCP("server-name")

@mcp.tool()
def my_tool(param: str) -> str:
    """What this tool does."""
    return f"Result for {param}"

if __name__ == "__main__":
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)
```

### MCP Client Skeleton (LangGraph)

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

async def run(message: str) -> str:
    client = MultiServerMCPClient({
        "myserver": {"url": "http://localhost:8000/sse", "transport": "sse"}
    })
    tools = await client.get_tools()
    agent = create_react_agent(ChatOpenAI(model="gpt-4o-mini"), tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": message}]})
    return result["messages"][-1].content
```

### MCP Primitives Cheat Sheet

```
Tools      → functions AI can CALL  → @mcp.tool()
Resources  → data AI can READ       → @mcp.resource("uri://path")
Prompts    → templates AI can USE   → @mcp.prompt()
```

### Transport Cheat Sheet

```
stdio  → same machine, subprocess, simple, secure
SSE    → different machines/containers, HTTP, flexible, production-ready
```

### Port Conventions

```
MCP Server:     8000 (tool service)
FastAPI:        8001 (agent API)
Streamlit:      8501 (UI)
```

### JSON-RPC Methods Cheat Sheet

```
initialize        → start session
tools/list        → get available tools
tools/call        → execute a tool
resources/list    → get available resources
resources/read    → read a resource
prompts/list      → get available prompts
prompts/get       → get a prompt
ping              → keep-alive
```

---

## Further Reading

- [Official MCP Documentation](https://modelcontextprotocol.io)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [LangChain MCP Adapters](https://github.com/langchain-ai/langchain-mcp-adapters)
- [MCP Server Examples](https://github.com/modelcontextprotocol/servers)
- [FastMCP Documentation](https://gofastmcp.com)
- [JSON-RPC 2.0 Specification](https://www.jsonrpc.org/specification)

---

*This guide covers MCP as of early 2026. The protocol is actively evolving — check the official documentation for the latest updates.*
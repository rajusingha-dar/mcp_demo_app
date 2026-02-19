# 📦 The MCP Context Size Problem

> A deep dive into the context window challenge when connecting to multiple MCP servers, why it happens, how it impacts production systems, and proven strategies to solve it.

---

## Table of Contents

- [What is the Context Size Problem?](#what-is-the-context-size-problem)
- [Why This Happens](#why-this-happens)
- [Real-World Impact](#real-world-impact)
- [Measuring the Problem](#measuring-the-problem)
- [Solution 1: Tool Filtering](#solution-1-tool-filtering)
- [Solution 2: Router Pattern](#solution-2-router-pattern)
- [Solution 3: Dynamic Tool Loading](#solution-3-dynamic-tool-loading)
- [Solution 4: Tool Summarization](#solution-4-tool-summarization)
- [Solution 5: Hierarchical Tool Organization](#solution-5-hierarchical-tool-organization)
- [Solution 6: Semantic Tool Selection](#solution-6-semantic-tool-selection)
- [Solution 7: Tool Caching](#solution-7-tool-caching)
- [Comparison of Solutions](#comparison-of-solutions)
- [Production Implementation Examples](#production-implementation-examples)
- [When to Use Which Solution](#when-to-use-which-solution)
- [Monitoring Context Usage](#monitoring-context-usage)
- [Future Directions](#future-directions)

---

## What is the Context Size Problem?

When your agent connects to multiple MCP servers, **every tool from every server** gets loaded into the LLM's context window as part of the system message. Each tool includes:

```
- Tool name (~10 tokens)
- Tool description (~50-200 tokens)
- JSON schema for input parameters (~50-300 tokens)
```

With many MCP servers and many tools per server, this explodes quickly:

```
1 MCP server × 5 tools = ~1,500 tokens
5 MCP servers × 10 tools each = ~15,000 tokens
10 MCP servers × 20 tools each = ~60,000 tokens
```

**The problem:** Context windows are limited (GPT-4: 128K tokens, Claude: 200K tokens). Using 60K tokens just for tool definitions means:
- Less room for conversation history
- Less room for retrieved documents
- Slower inference (more tokens to process)
- Higher cost (pay per token)
- Worse tool selection (LLM confused by too many similar tools)

---

## Why This Happens

### The MCP Discovery Pattern

When you use `MultiServerMCPClient`, it does this automatically:

```python
client = MultiServerMCPClient({
    "server1": {"url": "..."},
    "server2": {"url": "..."},
    # ... 10 more servers
})

# This fetches ALL tools from ALL servers
tools = await client.get_tools()

# Tools are passed to LLM as system message
agent = create_react_agent(llm, tools)
```

The LLM receives the **complete tool list** in every single request:

```
System: You have access to these tools:
1. add_note(title: str, content: str) - Add a new note...
2. list_notes() - List all available notes...
3. read_note(title: str) - Read a specific note...
4. delete_note(title: str) - Delete a note...
5. upload_file(bucket: str, filename: str, content: str) - Upload to GCS...
6. download_file(bucket: str, filename: str) - Download from GCS...
7. list_files(bucket: str, prefix: str) - List files...
... [94 more tools]
```

Every tool schema gets injected, whether relevant to the current task or not.

---

## Real-World Impact

### Impact on Cost

```
Context tokens per request:
- Tool definitions: 60,000 tokens
- Conversation history: 10,000 tokens
- User message: 100 tokens
Total input: 70,100 tokens per request

GPT-4 pricing (as of 2026):
- Input: $10/1M tokens
- Output: $30/1M tokens

Cost per request: 70,100 × $10/1M = $0.70 input
If the agent makes 5 tool calls → 5 requests → $3.50 just in input tokens

100,000 requests/month = $350,000/month in input costs alone
```

### Impact on Latency

```
More context = longer time to first token (TTFT)

With 1,000 tool tokens:  TTFT = 200ms
With 20,000 tool tokens: TTFT = 800ms
With 60,000 tool tokens: TTFT = 2,000ms

In a multi-step agent that calls tools 5 times, 
2 seconds × 5 = 10 seconds of latency just from context processing
```

### Impact on Tool Selection Quality

The more tools the LLM sees, the worse it performs at selecting the right one. This is called **tool selection degradation**.

```
10 tools  → 95% correct tool selected
50 tools  → 85% correct tool selected
100 tools → 70% correct tool selected
200 tools → 50% correct tool selected
```

The LLM gets confused between similar tools, calls the wrong one, has to retry, or gives up.

---

## Measuring the Problem

### Count Your Tokens

```python
import tiktoken

def count_tool_tokens(tools):
    encoding = tiktoken.encoding_for_model("gpt-4")
    total = 0
    
    for tool in tools:
        tool_str = f"{tool.name}: {tool.description}\nSchema: {tool.schema}"
        total += len(encoding.encode(tool_str))
    
    return total

# Usage
client = MultiServerMCPClient({...})
tools = await client.get_tools()
token_count = count_tool_tokens(tools)
print(f"Tool definitions use {token_count} tokens")
```

### Calculate Context Budget

```python
MODEL_CONTEXT_LIMIT = 128_000  # GPT-4 Turbo
TOOL_TOKENS = 60_000
CONVERSATION_HISTORY = 10_000
SYSTEM_PROMPT = 500
BUFFER = 2_000

available_for_user = (
    MODEL_CONTEXT_LIMIT 
    - TOOL_TOKENS 
    - CONVERSATION_HISTORY 
    - SYSTEM_PROMPT 
    - BUFFER
)

print(f"Available tokens for user messages: {available_for_user}")
# Output: 55,500 tokens
```

---

## Solution 1: Tool Filtering

**Concept:** Only load tools relevant to the current task. Filter before passing to the LLM.

### Implementation: Static Filtering by Tags

Tag your tools when you define them:

```python
# MCP Server - add tags
@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Add a new note."""
    pass

# Add metadata (this requires custom MCP server implementation)
add_note._tags = ["notes", "write", "personal"]

@mcp.tool()
def search_notes(query: str) -> str:
    """Search through notes."""
    pass

search_notes._tags = ["notes", "read", "search"]
```

Then filter on the client side:

```python
async def get_filtered_tools(required_tags: list[str]):
    all_tools = await client.get_tools()
    
    filtered = [
        tool for tool in all_tools
        if any(tag in tool.metadata.get("tags", []) for tag in required_tags)
    ]
    
    return filtered

# Usage
user_msg = "Add a note called shopping"
# Determine we only need write tools for notes
tools = await get_filtered_tools(["notes", "write"])

agent = create_react_agent(llm, tools)
```

**Pros:**
- Simple to implement
- Reduces context significantly
- Works with existing MCP servers if you control them

**Cons:**
- Requires manually tagging all tools
- Risk of filtering out a needed tool
- Static — can't adapt to evolving conversation

---

## Solution 2: Router Pattern

**Concept:** Use a lightweight router agent to decide which MCP server is relevant, then a worker agent loads only that server's tools.

```
User Request
     │
     ▼
┌──────────────────┐
│  Router Agent    │  ← Minimal tools, fast, cheap
│                  │
│  Decides:        │
│  "This is a      │
│   notes task"    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Notes Agent     │  ← Only loads notes MCP server
│                  │     (5 tools instead of 100)
│  Executes task   │
└──────────────────┘
```

### Implementation

**Step 1: Router Agent**

```python
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate

router_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a router. Determine which specialized agent should handle this request.

Available agents:
- notes_agent: Manages personal notes (add, list, read, delete)
- gcs_agent: Google Cloud Storage operations (upload, download, list files)
- slack_agent: Slack communication (send messages, list channels)
- github_agent: GitHub operations (create issues, list repos)

Respond with just the agent name, nothing else."""),
    ("user", "{request}")
])

router_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
router_chain = router_prompt | router_llm

async def route_request(user_request: str) -> str:
    response = await router_chain.ainvoke({"request": user_request})
    return response.content.strip()
```

**Step 2: Worker Agents with Isolated Tools**

```python
# Each worker agent only loads its own MCP server
async def execute_with_worker(user_request: str):
    # Step 1: Route
    agent_name = await route_request(user_request)
    
    # Step 2: Load only the relevant MCP server
    if agent_name == "notes_agent":
        client = MultiServerMCPClient({
            "notes": {"url": "https://notes-server...", "transport": "sse"}
        })
    elif agent_name == "gcs_agent":
        client = MultiServerMCPClient({
            "gcs": {"url": "https://gcs-server...", "transport": "sse"}
        })
    # ... other agents
    
    tools = await client.get_tools()  # Only 5-10 tools instead of 100
    
    # Step 3: Execute with worker agent
    worker_llm = ChatOpenAI(model="gpt-4")
    worker_agent = create_react_agent(worker_llm, tools)
    
    result = await worker_agent.ainvoke({
        "messages": [{"role": "user", "content": user_request}]
    })
    
    return result["messages"][-1].content
```

**Pros:**
- Dramatic context reduction (10 tools vs 100)
- Router uses cheap model (gpt-4o-mini)
- Worker can use powerful model with room for long history
- Each worker is a domain expert

**Cons:**
- Two LLM calls per request (router + worker)
- Added latency (router call is 200-500ms)
- Can't handle requests that need multiple domains

---

## Solution 3: Dynamic Tool Loading

**Concept:** Start with zero tools. Let the LLM request which tool categories it needs, then load only those.

```
User: "Upload a file to GCS and create a GitHub issue about it"
│
▼
Agent (with zero tools): "I need file_upload and issue_creation tools"
│
▼
System: [loads only gcs_tools and github_tools]
│
▼
Agent (with 12 tools): [executes task]
```

### Implementation

This requires a custom agent loop:

```python
async def dynamic_tool_agent(user_request: str):
    conversation_history = [{"role": "user", "content": user_request}]
    loaded_tools = []
    
    while True:
        # Agent decides: use a tool, request new tools, or finish
        response = await llm_with_tool_request_capability.ainvoke({
            "messages": conversation_history,
            "available_tools": loaded_tools
        })
        
        if response.type == "tool_request":
            # Agent says: "I need tools from category X"
            category = response.requested_category
            new_tools = await load_tools_by_category(category)
            loaded_tools.extend(new_tools)
            continue
        
        elif response.type == "tool_use":
            # Agent uses an already-loaded tool
            result = await execute_tool(response.tool_name, response.arguments)
            conversation_history.append({"role": "tool", "content": result})
            continue
        
        elif response.type == "final_answer":
            return response.content

async def load_tools_by_category(category: str):
    if category == "storage":
        client = MultiServerMCPClient({"gcs": {...}})
    elif category == "github":
        client = MultiServerMCPClient({"github": {...}})
    # ...
    
    return await client.get_tools()
```

**Pros:**
- Minimal initial context (zero tools)
- Agent only loads what it actually needs
- Adapts dynamically to evolving tasks

**Cons:**
- Requires custom agent implementation (not simple `create_react_agent`)
- LLM must be trained/prompted to request tools
- Extra round trips when loading new tool categories

---

## Solution 4: Tool Summarization

**Concept:** Compress tool descriptions to use fewer tokens.

### Implementation: Aggressive Description Shortening

```python
# Original tool (200 tokens)
@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Add a new personal note with a title and content body. 
    Use this when the user wants to remember, store, or save 
    any piece of information for later retrieval. The note will 
    be persisted to storage and can be accessed later using the 
    list_notes or read_note tools."""
    pass

# Compressed tool (50 tokens)
@mcp.tool()
def add_note(title: str, content: str) -> str:
    """Save a note. Use for remembering info."""
    pass
```

**Token savings:** 150 tokens per tool. With 100 tools = 15,000 tokens saved.

**Pros:**
- Easy to implement (just edit descriptions)
- No architectural changes needed
- Works with existing MCP infrastructure

**Cons:**
- Worse tool selection (less context for LLM)
- Loses nuance in tool behavior
- Risk of LLM misunderstanding when to call tools

---

## Solution 5: Hierarchical Tool Organization

**Concept:** Organize tools into a hierarchy. First, the LLM selects a category. Then it sees only tools in that category.

```
Level 1: Categories
- notes_tools (5 tools)
- storage_tools (8 tools)
- communication_tools (12 tools)
- code_tools (10 tools)

User: "Add a note"
→ Agent selects: notes_tools
→ Load only those 5 tools
→ Execute with minimal context
```

### Implementation

```python
TOOL_HIERARCHY = {
    "notes": {
        "description": "Personal note management - creating, reading, updating, deleting notes",
        "server": "notes"
    },
    "storage": {
        "description": "File storage and retrieval from cloud storage (GCS, S3)",
        "server": "gcs"
    },
    "communication": {
        "description": "Sending messages via Slack, email, or other channels",
        "server": "slack"
    }
}

async def hierarchical_tool_agent(user_request: str):
    # Step 1: Choose category
    category_prompt = f"""Choose the tool category needed for this request:
{user_request}

Categories:
{json.dumps(TOOL_HIERARCHY, indent=2)}

Respond with just the category name."""
    
    category = await llm.ainvoke(category_prompt)
    category = category.content.strip()
    
    # Step 2: Load tools from that category only
    server_config = TOOL_HIERARCHY[category]
    client = MultiServerMCPClient({
        category: {"url": server_config["server"], "transport": "sse"}
    })
    
    tools = await client.get_tools()
    
    # Step 3: Execute
    agent = create_react_agent(llm, tools)
    result = await agent.ainvoke({"messages": [{"role": "user", "content": user_request}]})
    
    return result["messages"][-1].content
```

**Pros:**
- Simple two-step process
- Dramatic context reduction
- Easy to add new categories

**Cons:**
- Can't handle cross-category requests
- Extra LLM call for category selection

---

## Solution 6: Semantic Tool Selection

**Concept:** Embed tool descriptions. At runtime, embed the user query. Retrieve only the top-K most semantically similar tools.

```
User: "Upload my resume to cloud storage"

Step 1: Embed user query → vector
Step 2: Compare with all tool embeddings
Step 3: Retrieve top 10 most similar tools:
   1. upload_file (similarity: 0.95)
   2. upload_to_gcs (similarity: 0.92)
   3. create_file (similarity: 0.85)
   ...
Step 4: Load only those 10 tools into agent context
```

### Implementation

```python
from sentence_transformers import SentenceTransformer
import numpy as np

# One-time: embed all tool descriptions
model = SentenceTransformer('all-MiniLM-L6-v2')

all_tools = await client.get_tools()
tool_descriptions = [f"{t.name}: {t.description}" for t in all_tools]
tool_embeddings = model.encode(tool_descriptions)

# At runtime: select tools semantically
async def semantic_tool_selection(user_request: str, top_k: int = 10):
    query_embedding = model.encode([user_request])[0]
    
    # Cosine similarity
    similarities = np.dot(tool_embeddings, query_embedding) / (
        np.linalg.norm(tool_embeddings, axis=1) * np.linalg.norm(query_embedding)
    )
    
    # Get top K indices
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    selected_tools = [all_tools[i] for i in top_indices]
    return selected_tools

# Usage
user_msg = "Upload my resume to cloud storage"
tools = await semantic_tool_selection(user_msg, top_k=10)

agent = create_react_agent(llm, tools)
```

**Pros:**
- Automatic, no manual categorization
- Highly relevant tools selected
- Adapts to any query dynamically

**Cons:**
- Requires embedding model and vector DB
- Cold start cost (embedding all tools once)
- Can miss tools with non-obvious relevance

---

## Solution 7: Tool Caching

**Concept:** Some LLM providers (Anthropic Claude) support prompt caching. Tool definitions that don't change can be cached, reducing cost and latency.

### How Prompt Caching Works

Claude can cache system messages. On the first request, tool definitions are sent and cached. On subsequent requests within the cache TTL (5 minutes), tool definitions are not re-sent — they're served from cache.

```
Request 1:
- Input tokens: 60,000 (all tools)
- Cost: $10/1M tokens
- Cost: $0.60

Request 2-N (within 5 min):
- Input tokens: 100 (no tools, served from cache)
- Cost: $1/1M tokens (90% cheaper for cached)
- Cost: $0.01
```

### Implementation

```python
from langchain_anthropic import ChatAnthropic

# Claude with caching enabled
llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    enable_prompt_caching=True
)

# Tools in system message get cached
agent = create_react_agent(llm, tools)
```

**Pros:**
- No code changes needed (just enable flag)
- Massive cost savings (up to 90%)
- Reduced latency on cached requests

**Cons:**
- Only works with Claude (not GPT-4)
- Cache expires after 5 min idle
- First request still has full cost

---

## Comparison of Solutions

| Solution | Context Reduction | Latency Impact | Complexity | Best For |
|---|---|---|---|---|
| Tool Filtering | High (50-90%) | None | Low | Known, predictable workflows |
| Router Pattern | Very High (90-95%) | +200-500ms | Medium | Domain-separated tasks |
| Dynamic Loading | Very High (95%+) | +200ms per load | High | Exploratory, multi-domain tasks |
| Tool Summarization | Medium (20-40%) | None | Very Low | Quick wins, all scenarios |
| Hierarchical | Very High (90%+) | +200-500ms | Medium | Clear category boundaries |
| Semantic Selection | High (70-90%) | +50-100ms | High | Diverse, unpredictable queries |
| Prompt Caching | None (cost only) | None (faster) | Very Low | High-volume, repetitive tasks |

---

## Production Implementation Examples

### Example 1: Router + Caching (Recommended)

```python
# Use router for initial reduction
agent_name = await route_request(user_request)

# Load only relevant server
client = load_server_for_agent(agent_name)
tools = await client.get_tools()

# Use Claude with caching
llm = ChatAnthropic(model="claude-sonnet-4", enable_prompt_caching=True)
agent = create_react_agent(llm, tools)

# First request: pays full cost for tools
# Subsequent requests (within 5 min): 90% cheaper
```

**Result:**
- 95% context reduction (router)
- 90% cost reduction on repeated requests (caching)
- Small latency overhead from router

---

### Example 2: Semantic Selection + Tool Summarization

```python
# Compress all tool descriptions (manual, one-time)
# Then use semantic selection

tools_all = await client.get_tools()
tool_embeddings = embed_tools(tools_all)

# At runtime
user_embedding = embed_query(user_request)
selected_tools = get_top_k_similar(user_embedding, tool_embeddings, k=15)

agent = create_react_agent(llm, selected_tools)
```

**Result:**
- 85% context reduction (semantic selection)
- Better tool selection than random filtering
- Works for unpredictable queries

---

### Example 3: Hierarchical + Dynamic Loading

```python
# Level 1: Choose category
category = await choose_category(user_request)

# Level 2: Load tools from that category
tools = await load_tools_for_category(category)

# Level 3: If agent says "I need more tools"
#          (custom agent loop), load additional category
```

**Result:**
- 90%+ context reduction
- Can expand dynamically if needed
- Handles multi-category tasks

---

## When to Use Which Solution

```
Single domain (e.g., just notes):
→ No solution needed, context is manageable

2-5 domains, predictable tasks:
→ Tool Filtering or Router Pattern

5-10 domains, varied tasks:
→ Router Pattern + Semantic Selection fallback

10+ domains, exploratory tasks:
→ Dynamic Tool Loading + Semantic Selection

High request volume, same tools used repeatedly:
→ Prompt Caching (with any of the above)

Need quick wins with minimal changes:
→ Tool Summarization
```

---

## Monitoring Context Usage

### Track Context Metrics

```python
import tiktoken

def monitor_context_usage(messages, tools):
    encoding = tiktoken.encoding_for_model("gpt-4")
    
    # Count tool tokens
    tool_str = json.dumps([{
        "name": t.name,
        "description": t.description,
        "schema": t.schema
    } for t in tools])
    tool_tokens = len(encoding.encode(tool_str))
    
    # Count message tokens
    message_tokens = sum(
        len(encoding.encode(m["content"])) for m in messages
    )
    
    total = tool_tokens + message_tokens
    
    # Log metrics
    print(f"Tool tokens: {tool_tokens} ({tool_tokens/total*100:.1f}%)")
    print(f"Message tokens: {message_tokens}")
    print(f"Total: {total}")
    
    # Alert if over threshold
    if tool_tokens > 20_000:
        print("⚠️ Warning: Tool context exceeds 20K tokens")
```

### Dashboard Metrics

Track these over time:

```
- Average tool tokens per request
- Max tool tokens seen
- % of requests hitting context limit
- Cost per request (input tokens × rate)
- Tool selection accuracy (correct tool chosen first)
```

---

## Future Directions

### Native MCP Tool Selection

Future MCP spec versions may include tool selection hints:

```json
{
  "tools": [
    {
      "name": "add_note",
      "relevance_keywords": ["note", "save", "remember", "store"],
      "category": "notes",
      "priority": "high"
    }
  ]
}
```

Clients could filter automatically based on query keywords.

### LLM-Native Tool Management

Future LLMs may support:
- Native tool namespaces (load/unload on demand)
- Hierarchical tool menus (browse → select → use)
- Tool embeddings built into the model

### MCP Protocol Enhancements

Potential future features:
- `tools/search` endpoint (semantic search on server side)
- `tools/suggest` endpoint (server recommends relevant tools)
- Tool bundles (load groups of related tools atomically)

---

## Summary: Solving Context Size

**The problem:** 100 tools × 200 tokens each = 20,000+ tokens wasted on tools you don't need.

**The solutions:**
1. **Router Pattern** — best for most production systems (95% reduction)
2. **Semantic Selection** — best for unpredictable queries (70-90% reduction)
3. **Dynamic Loading** — best for exploratory agents (95%+ reduction)
4. **Tool Summarization** — easiest quick win (20-40% reduction)
5. **Prompt Caching** — best cost optimization (works with any solution)

**The strategy:**
1. Start with tool summarization (easy, immediate win)
2. Add router pattern if you have clear domains
3. Add prompt caching if using Claude
4. Add semantic selection if queries are unpredictable
5. Consider dynamic loading for advanced multi-agent systems

**The future:** MCP and LLM providers are actively working on native solutions. Until then, these patterns are production-proven and battle-tested.

---

*This guide reflects best practices as of early 2026. The MCP ecosystem is rapidly evolving — check the latest MCP spec and provider documentation for updates.*
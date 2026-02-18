import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient
from backend.config import MCP_SERVER_URL

async def get_mcp_tools():
    client = MultiServerMCPClient(
        {
            "notes": {
                "url": f"{MCP_SERVER_URL}/sse",
                "transport": "sse",
            }
        }
    )
    tools = await client.get_tools()
    return tools, client

async def check_mcp_health() -> bool:
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{MCP_SERVER_URL}/health", timeout=5.0)
            return response.status_code == 200
    except Exception:
        return False
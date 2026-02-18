from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, AIMessage
from backend.config import OPENAI_API_KEY, MODEL_NAME
from backend.agent.tools import get_mcp_tools
from typing import List

async def run_agent(user_message: str, history: List[dict]) -> str:

    # Get tools fresh from MCP server
    tools, mcp_client = await get_mcp_tools()

    # Build the LLM
    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        temperature=0
    )

    # Build LangGraph react agent
    agent = create_react_agent(llm, tools)

    # Convert history to LangChain message format
    messages = []
    for msg in history:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # Add current user message
    messages.append(HumanMessage(content=user_message))

    # Run the agent
    result = await agent.ainvoke({"messages": messages})

    # Extract final response
    final_message = result["messages"][-1]
    return final_message.content
from fastapi import APIRouter, HTTPException
from backend.api.schemas import ChatRequest, ChatResponse, HealthResponse
from backend.agent.agent import run_agent
from backend.agent.tools import check_mcp_health

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        reply = await run_agent(
            user_message=request.message,
            history=[msg.model_dump() for msg in request.history]
        )
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health():
    mcp_ok = await check_mcp_health()
    return HealthResponse(
        status="ok" if mcp_ok else "degraded",
        mcp_server="online" if mcp_ok else "offline",
        backend="online"
    )
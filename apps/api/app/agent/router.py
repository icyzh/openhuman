from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.build import build_graph
from app.agent.schemas import AgentResponse, MessageInput
from app.agent.tools import BUILT_IN_TOOLS
from app.auth.models import User
from app.core.database import get_db
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Compile the agent graph once at startup
agent_graph = build_graph(BUILT_IN_TOOLS)


@router.post("/run", response_model=AgentResponse)
async def run_agent(
    data: MessageInput,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> AgentResponse:
    """Execute the authenticated internal AI agent test route.

    Requires a valid JWT bearer token. The route is intended for dashboard
    testing and development — production bot gateways call the graph
    in-process.
    """
    # Construct initial LangGraph state.
    # MessagesState (via AgentState) uses ``total=False`` semantics so
    # we only need to seed the keys that have meaningful initial values.
    initial_state = {
        "messages": [HumanMessage(content=data.content)],
        "platform": data.platform,
        "employee_id": str(data.employee_id),
        "tool_round": 0,
    }

    # Pass the async database session and employee context in configuration
    config = {
        "configurable": {
            "db": db,
            "employee_id": str(data.employee_id),
        }
    }

    try:
        # Run graph execution loop
        result_state = await agent_graph.ainvoke(initial_state, config=config)

        # Extract final formatted response, tool-round counter and error
        response_text = result_state.get("response")
        tool_rounds = result_state.get("tool_round", 0)
        error = result_state.get("error")

        return AgentResponse(
            response=response_text,
            tool_calls_count=tool_rounds,
            error=error,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent graph execution failed: {exc}",
        ) from exc

from uuid import UUID

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import get_llm
from app.agent.state import AgentState
from app.agent.tools import BUILT_IN_TOOLS
from app.employees.models import Employee
from app.employees.templates import get_template


async def llm_call_node(state: AgentState, config: RunnableConfig) -> dict:
    """Invoke LLM on current messages, binding only the tools allowed for
    this employee.

    If the employee / template specifies no tools the LLM is called without
    any bound tools — there is NO implicit fallback to the full built-in set.
    """
    configurable = config.get("configurable", {})
    db: AsyncSession | None = configurable.get("db")
    employee_id_str = configurable.get("employee_id")

    # Determine allowed tools for this specific employee
    allowed_tools: list = []
    if db and employee_id_str:
        emp = await db.scalar(
            select(Employee).where(Employee.id == UUID(employee_id_str))
        )
        if emp:
            template = get_template(emp.specialization or "general")
            allowed_names = template.allowed_tools
            allowed_tools = [
                t for t in BUILT_IN_TOOLS if t.name in allowed_names
            ]

    # Initialise LLM — when allowed_tools is empty the model runs with no
    # bound tools, which is the correct behaviour for a restricted employee.
    llm = get_llm(tools=allowed_tools)

    # Call LLM
    response = await llm.ainvoke(state["messages"], config=config)

    # Extract raw text (may be empty when the response contains only
    # tool_calls)
    raw_text = ""
    if isinstance(response, AIMessage):
        content = response.content
        raw_text = str(content) if content else ""

    # MessagesState handles appending the response message automatically
    return {
        "messages": [response],
        "tools": [t.name for t in allowed_tools],
        "raw_response": raw_text,
    }

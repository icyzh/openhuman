from uuid import UUID

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.state import AgentState
from app.employees.models import Employee
from app.employees.templates import get_template
from app.organizations.models import Organization


async def build_prompt_node(state: AgentState, config: RunnableConfig) -> dict:
    """Load employee and organization metadata, assemble system prompt, and
    prepend a single SystemMessage.

    Only returns the new SystemMessage — MessagesState's ``add_messages``
    reducer handles merging with existing messages, so we must NOT copy
    the existing message list into the return value.
    """
    configurable = config.get("configurable", {})
    db: AsyncSession | None = configurable.get("db")
    employee_id_str = configurable.get("employee_id")

    if not db or not employee_id_str:
        # Fallback to generic assistant when no DB connection is available
        system_prompt = (
            "You are a helpful AI assistant. Help team members with research, "
            "information lookup, calculations, and general tasks."
        )
        return {
            "system_prompt": system_prompt,
            "tool_round": 0,
            "guardrail_config": {},
            "citations": [],
            "messages": [SystemMessage(content=system_prompt)],
        }

    employee_id = UUID(employee_id_str)

    # Fetch employee and organisation details
    emp = await db.scalar(select(Employee).where(Employee.id == employee_id))
    if not emp:
        system_prompt = "You are a helpful AI assistant."
        return {
            "system_prompt": system_prompt,
            "tool_round": 0,
            "guardrail_config": {},
            "citations": [],
            "messages": [SystemMessage(content=system_prompt)],
        }

    org = await db.scalar(select(Organization).where(Organization.id == emp.org_id))
    org_name = org.name if org else "the Organization"

    # Use built-in template based on specialisation
    template = get_template(emp.specialization or "general")

    # Format the template system prompt
    system_prompt = template.system_prompt_template.format(
        name=emp.name, org_name=org_name
    )

    # Append custom personality settings if present
    if emp.personality:
        traits = emp.personality.get("traits", [])
        tone = emp.personality.get("tone")
        parts: list[str] = []
        if traits:
            parts.append(f"Your traits are: {', '.join(traits)}.")
        if tone:
            parts.append(f"Your communication tone should be {tone}.")
        if parts:
            system_prompt += "\nPersonality Profile: " + " ".join(parts)

    # Append custom duties if present
    custom_duties = emp.duties or []
    duties = list(set(template.suggested_duties + custom_duties))
    if duties:
        system_prompt += (
            "\nYour specific duties and core responsibilities include:\n"
            + "\n".join(f"- {duty}" for duty in duties)
        )

    # Return ONLY the new SystemMessage — MessagesState's add_messages reducer
    # prepends/appends it correctly. Returning the full message list would
    # cause duplicates because the reducer treats the return value as *new*
    # messages to append.
    return {
        "system_prompt": system_prompt,
        "tool_round": 0,
        "guardrail_config": template.guardrail_config,
        "citations": [],
        "messages": [SystemMessage(content=system_prompt)],
    }

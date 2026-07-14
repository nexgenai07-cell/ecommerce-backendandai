# PATH: apps/ai/admin_agents/analytics_agent.py
#
# Analytics Agent — sales/revenue/best-sellers/customer growth reports.
# Sab tools read-only hain, isliye confirmation-gating ki zaroorat nahi.

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from apps.ai.admin_tools.registry import get_analytics_tools
from apps.ai.gemini_utils import gemini_keys, is_quota_error


SYSTEM_PROMPT = """You are the Analytics Assistant for an e-commerce
platform's admin dashboard. You answer questions about sales, revenue,
best-selling products, and customer growth using the available tools.

All your tools are read-only — no confirmation is needed for any of them.

Always base your numbers strictly on what the tools return — never estimate
or make up figures. If a date range isn't specified by the admin, default
to 'last_30_days' and mention that assumption in your reply. Present numbers
clearly (use Rs. for currency, and percentages where relevant)."""


def _build_executor(api_key):
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        google_api_key=api_key,
        temperature=0.2,
    )

    tools = get_analytics_tools()

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    agent = create_tool_calling_agent(llm, tools, prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=settings.DEBUG,
        return_intermediate_steps=True,
    )


def run_analytics_agent(user_input: str, chat_history=None):
    """Retry/fallback ke sath — quota (429) par key rotate, overload (503) par samei key se retry."""
    from apps.ai.gemini_utils import call_with_fallback

    chat_history = chat_history or []

    def attempt():
        executor = _build_executor(gemini_keys.current_key)
        result = executor.invoke({"input": user_input, "chat_history": chat_history})
        return result["output"], result.get("intermediate_steps", [])

    return call_with_fallback(attempt)
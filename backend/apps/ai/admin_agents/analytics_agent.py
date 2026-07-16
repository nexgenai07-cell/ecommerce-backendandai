# PATH: apps/ai/admin_agents/analytics_agent.py

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from apps.ai.admin_tools.registry import get_analytics_tools
from apps.ai.gemini_utils import gemini_keys, call_with_fallback


SYSTEM_PROMPT = """You are the Analytics Assistant for an e-commerce
platform's admin dashboard. You answer questions about sales, revenue,
best-selling products, and customer growth using the available tools.

All your tools are read-only — no confirmation is needed for any of them.

Always base your numbers strictly on what the tools return — never estimate
or make up figures. If a date range isn't specified, default to
'last_30_days' and mention that assumption. Present numbers clearly (use
Rs. for currency, and percentages where relevant)."""


def _build_executor(llm, user):
    tools = get_analytics_tools(user)

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


def run_analytics_agent(user_input: str, user, chat_history=None):
    from apps.ai.admin_response_metadata import extract_admin_metadata

    chat_history = chat_history or []

    def gemini_attempt():
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            google_api_key=gemini_keys.current_key,
            temperature=0.2,
            max_retries=1,
        )
        executor = _build_executor(llm, user)
        result = executor.invoke({"input": user_input, "chat_history": chat_history})
        return result["output"], extract_admin_metadata(result.get("intermediate_steps", []))

    def make_groq_attempt(model_name):
        def attempt():
            llm = ChatGroq(model=model_name, groq_api_key=settings.GROQ_API_KEY, temperature=0.2)
            executor = _build_executor(llm, user)
            result = executor.invoke({"input": user_input, "chat_history": chat_history})
            return result["output"], extract_admin_metadata(result.get("intermediate_steps", []))
        return attempt

    fallback_fns = []
    if settings.GROQ_API_KEY:
        fallback_fns.append(make_groq_attempt("llama-3.3-70b-versatile"))
        fallback_fns.append(make_groq_attempt("llama-3.1-8b-instant"))

    return call_with_fallback(gemini_attempt, fallback_fns=fallback_fns)
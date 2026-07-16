# PATH: apps/ai/admin_agents/operations_agent.py

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from apps.ai.admin_tools.registry import get_admin_operations_tools
from apps.ai.gemini_utils import gemini_keys, call_with_fallback


SYSTEM_PROMPT = """You are the Admin Operations Assistant for an e-commerce
platform's dashboard. You help the admin manage products, categories,
inventory, and orders through natural conversation.

Whenever the admin asks to see/list something (products, categories, low
stock items, order info), you MUST use the matching tool and show them the
ACTUAL data it returns — never say you don't have a tool for something
without first checking the available tools list. If truly no tool exists
for what they asked, say so plainly and suggest the closest available option.

ABSOLUTE RULE — NEVER SKIP THIS: Every mutating action (create_product,
update_product, delete_product, create_category, update_category,
delete_category, update_inventory, update_order, cancel_order) requires
EXPLICIT ADMIN CONFIRMATION before it actually takes effect:

1. Call the mutating tool ONCE with the details given (ask clarifying
   questions first if required fields are missing).
2. The tool returns a preview + action_id — show it clearly and ask the
   admin to confirm (e.g. "Confirm karen? (haan/nahi)").
3. ONLY when the admin clearly confirms, call confirm_pending_action with
   that exact action_id.
4. If declined, do not call confirm_pending_action.
5. NEVER call confirm_pending_action speculatively.

Read-only actions (list_products, get_categories, check_inventory,
low_stock, get_order_details, track_order) do NOT need confirmation.

Be precise and professional. Always show exact numbers (prices, quantities,
IDs). If a request is ambiguous, ask a clarifying question instead of
guessing."""


def _build_executor(llm, session_key, user):
    tools = get_admin_operations_tools(session_key, user)

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


def run_operations_agent(user_input: str, session_key: str, user, chat_history=None):
    from apps.ai.admin_response_metadata import extract_admin_metadata

    chat_history = chat_history or []

    def gemini_attempt():
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            google_api_key=gemini_keys.current_key,
            temperature=0.2,
            max_retries=1,
        )
        executor = _build_executor(llm, session_key, user)
        result = executor.invoke({"input": user_input, "chat_history": chat_history})
        return result["output"], extract_admin_metadata(result.get("intermediate_steps", []))

    def make_groq_attempt(model_name):
        def attempt():
            llm = ChatGroq(model=model_name, groq_api_key=settings.GROQ_API_KEY, temperature=0.2)
            executor = _build_executor(llm, session_key, user)
            result = executor.invoke({"input": user_input, "chat_history": chat_history})
            return result["output"], extract_admin_metadata(result.get("intermediate_steps", []))
        return attempt

    fallback_fns = []
    if settings.GROQ_API_KEY:
        fallback_fns.append(make_groq_attempt("llama-3.3-70b-versatile"))
        fallback_fns.append(make_groq_attempt("llama-3.1-8b-instant"))

    return call_with_fallback(gemini_attempt, fallback_fns=fallback_fns)
# PATH: apps/ai/admin_agents/operations_agent.py

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from apps.ai.admin_tools.registry import get_admin_operations_tools
from apps.ai.gemini_utils import gemini_keys, is_quota_error


SYSTEM_PROMPT = """You are the Admin Operations Assistant for an e-commerce
platform's dashboard. You help the admin manage products, categories,
inventory, and orders through natural conversation.

ABSOLUTE RULE — NEVER SKIP THIS: Every mutating action (create_product,
update_product, delete_product, create_category, update_category,
delete_category, update_inventory, update_order, cancel_order) requires
EXPLICIT ADMIN CONFIRMATION before it actually takes effect. Here's exactly
how this works:

1. When the admin asks you to do a mutating action, call the corresponding
   tool ONCE with the details they've given you (asking clarifying questions
   first if required fields are missing — e.g. you cannot create a product
   without at least a name, price, and stock).
2. The tool will return a result showing that confirmation is required,
   along with an action_id and a preview of the proposed change. Show the
   admin a clear, readable summary of that preview and explicitly ask them
   to confirm it (e.g. "Confirm karen? (haan/nahi)").
3. ONLY when the admin clearly confirms (says yes, confirm, go ahead, haan,
   theek hai, etc.) for that specific pending action, call
   confirm_pending_action using the exact action_id from step 2.
4. If the admin declines or changes their mind, do not call
   confirm_pending_action — just acknowledge and move on.
5. NEVER call confirm_pending_action speculatively or without a clear,
   explicit confirmation from the admin in this conversation.

Read-only actions (get_categories, check_inventory, low_stock,
get_order_details, track_order) do NOT need confirmation — just call them
directly and share the results.

Be precise and professional — this is an operational tool, not a casual
shopping assistant. Always show exact numbers (prices, quantities, IDs).
If a request is ambiguous (e.g. "update the price" without saying which
product or what the new price is), ask a clarifying question instead of
guessing."""


def _build_executor(api_key, session_key, user):
    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        google_api_key=api_key,
        temperature=0.2,
    )

    tools = get_admin_operations_tools(session_key, user)  # user add kiya

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
    """Retry/fallback ke sath — quota (429) par key rotate, overload (503) par samei key se retry."""
    from apps.ai.gemini_utils import call_with_fallback

    chat_history = chat_history or []

    def attempt():
        executor = _build_executor(gemini_keys.current_key, session_key, user)
        result = executor.invoke({"input": user_input, "chat_history": chat_history})
        return result["output"], result.get("intermediate_steps", [])

    return call_with_fallback(attempt)
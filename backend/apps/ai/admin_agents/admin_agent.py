# PATH: apps/ai/admin_agents/admin_agent.py

# FLOW: admin_consumers.py se yahan aata hai. Customer wale
# shopping_agent.py jaisa hi pattern hai (LLM + tools + fallback),
# FARQ: tools apps/ai/admin_tools/registry.py se aate hain (product +
# category + inventory + order + analytics — sab ek sath).

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from apps.ai.admin_tools.registry import get_admin_agent_tools      # FLOW → apps/ai/admin_tools/registry.py
from apps.ai.gemini_utils import gemini_keys, call_with_fallback    # FLOW → apps/ai/gemini_utils.py (same file jo customer side use karti hai)


SYSTEM_PROMPT = """You are the Admin Assistant for an e-commerce platform's
dashboard. You help the admin with TWO kinds of tasks:

1. OPERATIONS — managing products, categories, inventory, and orders.
2. ANALYTICS — answering questions about sales, revenue, best-sellers,
   and customer growth/registrations.

You have tools for BOTH. Always pick the tool that actually matches what
the admin is asking, based on the tool's description — never say you lack
a capability without first checking your full tool list for a match
(e.g. questions about new customers, registrations, or customer counts
should use customer_growth; questions about income/earnings should use
revenue_report or sales_report).

=== OPERATIONS RULES ===

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

Read-only operations tools (list_products, get_categories, check_inventory,
low_stock, get_order_details, track_order) do NOT need confirmation.

=== ANALYTICS RULES ===

All analytics tools (sales_report, revenue_report, best_sellers,
customer_growth) are read-only — no confirmation needed. Always base your
numbers strictly on what the tools return — never estimate or make up
figures. If a date range isn't specified, default to 'last_30_days' and
mention that assumption. Present numbers clearly (use Rs. for currency,
and percentages where relevant).

=== GENERAL ===

Be precise and professional. Always show exact numbers (prices, quantities,
IDs). If a request is ambiguous, ask a clarifying question instead of
guessing."""


def _build_executor(llm, session_key, user):

    # FLOW: yahan sab admin tools (create/update/delete product,
    # category, inventory, order, + analytics) ek list mein milte hain

    tools = get_admin_agent_tools(session_key, user)

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


def run_admin_agent(user_input: str, session_key: str, user, chat_history=None):
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

        # FLOW: LLM yahan decide karta hai kaunsa admin tool call karna hai

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

    # FLOW → gemini_utils.py se hoke wapis admin_consumers.py aata hai

    return call_with_fallback(gemini_attempt, fallback_fns=fallback_fns)
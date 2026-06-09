import json
import logging
import os
from django.conf import settings
import httpx
from openai import OpenAI
from .analytics_tools import TOOL_REGISTRY

logger = logging.getLogger(__name__)

OPENAI_MODEL = getattr(settings, 'OPENAI_MODEL', 'gpt-4o-mini')
MAX_ITERATIONS = 6

SYSTEM_PROMPT = """You are an expert Sales Analytics AI for Best Marine Private Limited, 
a marine safety equipment company. You analyze ERP sales data and provide actionable 
business intelligence.

Data available: Sales Orders, Sales Order Details, Sales Invoices (Apr-May 2026).

Rules:
- Always call the relevant tool(s) before answering — never guess from memory.
- If a question involves top-N, extract the exact number N from the query.
- For trend questions, use get_trend_direction — only report GROWING or DECLINING entities, skip STABLE.
- For health questions, only flag customers with LOW or MEDIUM scores unless specifically asked.
- For discontinuation: always provide the 'reason' field in your explanation.
- For missing data (payments, returns): clearly state what data is needed.
- Structure answers with: Summary → Key Findings → Recommendations.
- Use ₹ for currency. Be direct and business-focused.
- Do not invent data. Only use what the tools return."""

# ── tool definitions ─────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        'name': 'get_top_n',
        'description': (
            'Get top N customers or products ranked by revenue, qty sold, or order count. '
            'Use when user asks for top/best/highest performers. N can be any number.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'entity':  {'type': 'string', 'enum': ['customer', 'product'], 'description': 'What to rank'},
                'n':       {'type': 'integer', 'description': 'How many results to return', 'minimum': 1},
                'metric':  {'type': 'string', 'enum': ['revenue', 'qty', 'orders'], 'default': 'revenue'},
            },
            'required': ['entity', 'n'],
        },
    },
    {
        'name': 'get_customer_health_scores',
        'description': (
            'Multi-factor health score (0-100) per customer based on revenue, order frequency, '
            'product diversity, and recency. Use for overall customer quality assessment.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'customer_name': {'type': 'string', 'description': 'Optional: filter to one customer'},
            },
        },
    },
    {
        'name': 'get_discontinuation_candidates',
        'description': (
            'Identify products or customers to consider discontinuing based on low revenue, '
            'low order frequency, and inactivity. Provides reason for each candidate.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'entity_type': {'type': 'string', 'enum': ['customer', 'product', 'both'], 'default': 'both'},
            },
        },
    },
    {
        'name': 'get_volume_growth_alerts',
        'description': (
            'Detect customers or products whose volume/revenue grew significantly '
            'from first half to second half of the period. Returns recommendations to increase focus.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'entity_type':    {'type': 'string', 'enum': ['customer', 'product', 'both'], 'default': 'both'},
                'threshold_pct':  {'type': 'number', 'description': 'Min growth % to flag', 'default': 20.0},
            },
        },
    },
    {
        'name': 'get_trend_direction',
        'description': (
            'Weekly revenue trend per customer or product — GROWING, DECLINING, or STABLE. '
            'Use for trend analysis, declining orders, increasing customers questions. '
            'Only GROWING and DECLINING are returned (STABLE is silent).'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'entity_type':  {'type': 'string', 'enum': ['customer', 'product', 'both'], 'default': 'both'},
                'entity_name':  {'type': 'string', 'description': 'Optional: filter to one entity name'},
            },
        },
    },
    {
        'name': 'get_order_to_invoice_analysis',
        'description': (
            'Compare Sales Order value vs actual Invoice value per customer. '
            'Detects under-invoiced or unfulfilled orders. Use for fulfilment gap questions.'
        ),
        'input_schema': {
            'type': 'object',
            'properties': {
                'customer_name': {'type': 'string', 'description': 'Optional: filter to one customer'},
            },
        },
    },
    {
        'name': 'get_low_volume_analysis',
        'description': 'Bottom N products by qty sold. Identifies slow-moving or dead stock.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'top_n': {'type': 'integer', 'description': 'How many low-volume items to return', 'default': 20},
            },
        },
    },
    {
        'name': 'get_revenue_summary',
        'description': (
            'Overall business summary: total revenue, orders, customers, products, '
            'weekly breakdown, top categories. Use as a starting point for general questions.'
        ),
        'input_schema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'get_customer_deep_dive',
        'description': 'Full breakdown for a single named customer: orders, products, trend, recommendation.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'customer_name': {'type': 'string', 'description': 'Customer name or partial name'},
            },
            'required': ['customer_name'],
        },
    },
    {
        'name': 'get_product_deep_dive',
        'description': 'Full breakdown for a single named product: customers, revenue, qty, trend.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'product_name': {'type': 'string', 'description': 'Product name or partial name'},
            },
            'required': ['product_name'],
        },
    },
    {
        'name': 'get_payment_behavior',
        'description': 'Analyze payment delays and part-payment behavior. Requires payment data upload.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'customer_name': {'type': 'string', 'description': 'Optional: filter to one customer'},
            },
        },
    },
    {
        'name': 'get_return_analysis',
        'description': 'Analyze sales returns and return rates. Requires returns data upload.',
        'input_schema': {
            'type': 'object',
            'properties': {
                'customer_name': {'type': 'string', 'description': 'Optional: filter to one customer'},
            },
        },
    },
]


def _openai_tools():
    return [
        {
            'type': 'function',
            'function': {
                'name': tool['name'],
                'description': tool['description'],
                'parameters': tool['input_schema'],
            },
        }
        for tool in TOOL_DEFINITIONS
    ]


def _tool_call_message(tool_call):
    return {
        'id': tool_call.id,
        'type': 'function',
        'function': {
            'name': tool_call.function.name,
            'arguments': tool_call.function.arguments,
        },
    }


# ── agent runner ──────────────────────────────────────────────────────────────

def _legacy_anthropic_run_agent(query: str, conversation_history: list = None, api_key: str = None) -> dict:
    """
    Runs the agent loop: sends query → Claude picks tools → tools execute
    → results fed back → Claude generates final answer.

    Returns:
        {
            'answer': str,
            'tools_used': list[str],
            'raw_tool_results': dict,
            'error': str | None,
        }
    """
    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        raise ValueError(
            'Anthropic API key is missing. Set ANTHROPIC_API_KEY on the server '
            'or enter your key in the dashboard API config.'
        )

    client = anthropic.Anthropic(api_key=api_key)

    messages = list(conversation_history or [])
    messages.append({'role': 'user', 'content': query})

    tools_used = []
    raw_results = {}
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # append assistant response to history
        messages.append({'role': 'assistant', 'content': response.content})

        if response.stop_reason == 'end_turn':
            # extract final text
            answer = next(
                (block.text for block in response.content if hasattr(block, 'text')),
                'No response generated.'
            )
            return {
                'answer': answer,
                'tools_used': tools_used,
                'raw_tool_results': raw_results,
                'error': None,
            }

        if response.stop_reason == 'tool_use':
            tool_results = []

            for block in response.content:
                if block.type != 'tool_use':
                    continue

                tool_name = block.name
                tool_input = block.input
                tools_used.append(tool_name)

                logger.info(f'Tool call: {tool_name}({tool_input})')

                if tool_name not in TOOL_REGISTRY:
                    result = {'error': f'Unknown tool: {tool_name}'}
                else:
                    try:
                        result = TOOL_REGISTRY[tool_name](**tool_input)
                    except Exception as e:
                        logger.exception(f'Tool {tool_name} failed')
                        result = {'error': str(e)}

                raw_results[tool_name] = result
                tool_results.append({
                    'type': 'tool_result',
                    'tool_use_id': block.id,
                    'content': json.dumps(result),
                })

            messages.append({'role': 'user', 'content': tool_results})
            continue

        # unexpected stop reason
        break

    return {
        'answer': 'Agent reached max iterations without final answer.',
        'tools_used': tools_used,
        'raw_tool_results': raw_results,
        'error': 'max_iterations_reached',
    }


def run_agent(query: str, conversation_history: list = None, api_key: str = None) -> dict:
    """
    Runs the agent loop: sends query -> OpenAI picks tools -> tools execute
    -> results fed back -> OpenAI generates final answer.
    """
    api_key = api_key or getattr(settings, 'OPENAI_API_KEY', '') or os.environ.get('OPENAI_API_KEY')
    if not api_key or api_key == 'your_openai_api_key_here':
        raise ValueError(
            'OpenAI API key is missing. Add OPENAI_API_KEY to llm_project/.env '
            'and restart the Django server.'
        )

    client = OpenAI(
        api_key=api_key,
        http_client=httpx.Client(trust_env=False, timeout=60.0),
    )

    messages = [{'role': 'system', 'content': SYSTEM_PROMPT}]
    messages.extend(conversation_history or [])
    messages.append({'role': 'user', 'content': query})

    tools_used = []
    raw_results = {}

    for _ in range(MAX_ITERATIONS):
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=_openai_tools(),
            tool_choice='auto',
            max_tokens=4096,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            return {
                'answer': message.content or 'No response generated.',
                'tools_used': tools_used,
                'raw_tool_results': raw_results,
                'error': None,
            }

        messages.append({
            'role': 'assistant',
            'content': message.content,
            'tool_calls': [_tool_call_message(tool_call) for tool_call in tool_calls],
        })

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            try:
                tool_input = json.loads(tool_call.function.arguments or '{}')
            except json.JSONDecodeError:
                tool_input = {}

            tools_used.append(tool_name)
            logger.info(f'Tool call: {tool_name}({tool_input})')

            if tool_name not in TOOL_REGISTRY:
                result = {'error': f'Unknown tool: {tool_name}'}
            else:
                try:
                    result = TOOL_REGISTRY[tool_name](**tool_input)
                except Exception as e:
                    logger.exception(f'Tool {tool_name} failed')
                    result = {'error': str(e)}

            raw_results[tool_name] = result
            messages.append({
                'role': 'tool',
                'tool_call_id': tool_call.id,
                'name': tool_name,
                'content': json.dumps(result),
            })

    return {
        'answer': 'Agent reached max iterations without final answer.',
        'tools_used': tools_used,
        'raw_tool_results': raw_results,
        'error': 'max_iterations_reached',
    }

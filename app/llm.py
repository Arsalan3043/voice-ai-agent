# llm.py
# Handles all communication with OpenAI GPT-4o mini.
# Streams tokens back to the caller via the WebSocket in main.py.
# Handles tool calls mid-stream and resumes response after tool result.

import json
import os
from openai import AsyncOpenAI
from prompt import SYSTEM_PROMPT
from tools import TOOL_DEFINITIONS, run_tool

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"

# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------
# Called by main.py on every response_required event from Retell.
# Yields either:
#   ("text", str)        — a token chunk to stream to Retell
#   ("tool_call", dict)  — a tool was called; result already appended to history
#   ("done", None)       — response complete, no more chunks

async def stream_response(conversation_history: list):
    """
    Takes the full conversation history from Retell and streams a response.
    Handles tool calls transparently — executes them and continues streaming.

    Yields tuples of ("text", chunk) or ("done", None).
    """

    # Build the messages array for OpenAI.
    # Retell sends history in OpenAI format already — role + content pairs.
    # We just prepend the system prompt.
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *conversation_history,
    ]

    # Keep looping to handle chained tool calls.
    # Most turns: one pass. Occasionally: tool → result → continue → tool → result → continue.
    while True:
        stream = await client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",       # model decides when to call tools
            stream=True,
            temperature=0.4,          # low temp = consistent clinical tone
            max_tokens=300,           # keep responses short — this is voice, not text
        )

        # Accumulators for the current streamed turn
        text_buffer = ""              # collects text tokens as they arrive
        tool_calls_buffer = {}        # collects tool call chunks — keyed by index

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            finish_reason = chunk.choices[0].finish_reason if chunk.choices else None

            if delta is None:
                continue

            # --- TEXT TOKEN ---
            if delta.content:
                text_buffer += delta.content
                yield ("text", delta.content)   # stream immediately to Retell

            # --- TOOL CALL CHUNK ---
            # OpenAI streams tool calls in fragments — name arrives first,
            # then arguments JSON is streamed character by character.
            # We accumulate all fragments before executing.
            if delta.tool_calls:
                for tc_chunk in delta.tool_calls:
                    idx = tc_chunk.index
                    if idx not in tool_calls_buffer:
                        tool_calls_buffer[idx] = {
                            "id": "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc_chunk.id:
                        tool_calls_buffer[idx]["id"] += tc_chunk.id
                    if tc_chunk.function.name:
                        tool_calls_buffer[idx]["name"] += tc_chunk.function.name
                    if tc_chunk.function.arguments:
                        tool_calls_buffer[idx]["arguments"] += tc_chunk.function.arguments

            # --- TURN COMPLETE ---
            if finish_reason == "stop":
                # Normal text response finished — we are done
                yield ("done", None)
                return

            if finish_reason == "tool_calls":
                # Model wants to call one or more tools.
                # Build the assistant message with tool_calls for history.
                assistant_tool_message = {
                    "role": "assistant",
                    "content": text_buffer or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                        for tc in tool_calls_buffer.values()
                    ],
                }
                messages.append(assistant_tool_message)

                # Execute each tool and append results to messages
                for tc in tool_calls_buffer.values():
                    tool_name = tc["name"]
                    try:
                        args = json.loads(tc["arguments"])
                    except json.JSONDecodeError:
                        args = {}

                    result = run_tool(tool_name, args)

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": json.dumps(result),
                    })

                    yield ("tool_call", {"tool": tool_name, "args": args, "result": result})

                # Reset accumulators and loop — model will now continue its response
                text_buffer = ""
                tool_calls_buffer = {}
                break   # break inner for-loop, outer while continues with updated messages
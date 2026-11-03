"""
agent.py - a minimal agent harness, written to be read top to bottom.

An "agent" is just this loop:

    1. Send the conversation (plus the list of tools) to the model.
    2. If the model asks to use tools, run them and append the results.
    3. Go back to step 1.
    4. Stop when the model answers without asking for a tool.

Everything else in a real harness (Claude Code, etc.) is built on top of
this loop: permissions, more tools, memory, context management, sub-agents...

Run it:
    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=sk-ant-...
    python agent.py
"""

import anthropic

from tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

MODEL = "claude-opus-5-5"
MAX_STEPS = 10  # safety net: never let one request loop forever

SYSTEM_PROMPT = (
    "You are a helpful assistant running inside a small learning harness. "
    "Use the tools you are given whenever they help you answer accurately."
)


def run_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run one tool call. Returns (result_text, is_error).

    Errors are NOT raised to the user. We send them back to the model as a
    tool result marked is_error=True, so Claude can read the message and
    try again (e.g. fix a typo in a file path). This is how agents recover.
    """
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return f"Unknown tool: {name}", True
    try:
        return func(**tool_input), False
    except Exception as e:
        return f"{type(e).__name__}: {e}", True


def agent_turn(client, messages: list) -> str:
    """Handle ONE user message: loop until Claude gives a final answer.

    `messages` is the whole conversation so far and is updated in place,
    so the agent remembers earlier turns.
    """
    for step in range(MAX_STEPS):
        # --- 1. Ask the model --------------------------------------------
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
            output_config={"effort": "medium"},
        )

        # Always append the model's FULL reply (all content blocks, not just
        # the text). It can contain thinking and tool_use blocks that the
        # API expects to see again on the next request.
        messages.append({"role": "assistant", "content": response.content})

        # --- 2. Did the model ask for tools? -----------------------------
        # `stop_reason` tells us WHY the model stopped talking.
        if response.stop_reason != "tool_use":
            if response.stop_reason == "max_tokens":
                print("[harness] warning: reply was cut off by max_tokens")
            elif response.stop_reason == "refusal":
                return "[the model declined this request]"
            # "end_turn" (or anything else): this is the final answer.
            return "".join(b.text for b in response.content if b.type == "text")

        # --- 3. Run every tool the model asked for -----------------------
        # The model can ask for several tools at once. We run them all and
        # send ALL results back together in a single user message.
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result, is_error = run_tool(block.name, block.input)
            print(f"[tool] {block.name}({block.input}) -> {result[:200]}")
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,  # links this result to the request
                    "content": result,
                    "is_error": is_error,
                }
            )

        # Tool results go back as a "user" message. From the API's point of
        # view, the harness is speaking on the user's side of the table.
        messages.append({"role": "user", "content": tool_results})
        # ...and loop: the model now sees the results and continues.

    return f"[harness] stopped after {MAX_STEPS} steps without a final answer"


def main():
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    messages = []  # the conversation: our agent's only "memory"

    print("Basic agent harness. Type 'exit' to quit.")
    while True:
        user_input = input("\nyou> ").strip()
        if user_input in {"exit", "quit"}:
            break
        if not user_input:
            continue
        messages.append({"role": "user", "content": user_input})
        print(f"\nclaude> {agent_turn(client, messages)}")


if __name__ == "__main__":
    main()

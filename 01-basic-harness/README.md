# Level 1: A basic agent harness

The goal of this level is to see that an "agent" is not magic. It is a
language model, a few tools, and a short `while` loop that connects them.
That loop is the **harness**.

## Files

| File | What it is |
|---|---|
| `agent.py` | The harness: the loop, tool dispatch, and a simple chat REPL (~120 lines) |
| `tools.py` | Three tools: `calculator`, `get_current_time`, `read_file` |
| `test_agent.py` | Tests the loop with a fake model, so no API key or cost is needed |

## Run it

```bash
cd 01-basic-harness
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py
```

Things to try:

- `What is 1234 * 5678 / 3?` (uses `calculator`)
- `What day of the week is it?` (uses `get_current_time`)
- `Summarize README.md` (uses `read_file`)
- `Read secrets.txt` (the file doesn't exist; watch Claude recover from the error)
- `How many days until New Year?` (often uses two tools in one turn)

Run the offline tests with `python test_agent.py`.

## The core idea: the agent loop

```
          ┌──────────────────────────────────────────────┐
          │                                              │
user ──▶  messages ──▶  Claude  ──▶ stop_reason?         │
                                     │                   │
                       "end_turn" ◀──┤                   │
                       print answer  │ "tool_use"        │
                                     ▼                   │
                         harness runs the tools          │
                         appends tool_result blocks ─────┘
```

In code (`agent.py`, `agent_turn`):

1. **Call the model** with the whole conversation and the tool schemas.
2. **Append the model's full reply** to `messages`.
3. **Check `stop_reason`.** If it isn't `"tool_use"`, the model is done and
   we return its text.
4. Otherwise, **run every requested tool** and append the results as one
   `user` message of `tool_result` blocks.
5. **Go back to 1.** The model now sees the results and either asks for more
   tools or answers.

## Key concepts

**The model never runs anything.** Claude only *asks* for a tool by returning
a `tool_use` block (`name`, `input`, `id`). Your harness decides whether and
how to run it. That makes the harness the place where safety lives: the
`read_file` tool refuses paths outside its folder, and the `calculator`
parses math instead of calling `eval()`.

**A tool = schema + function.** The schema (name, description, JSON Schema
for inputs) is all the model sees. Write the description as if for a new
colleague: when should they use it, and what goes in each argument?

**`tool_use_id` links request and result.** Every `tool_result` must carry
the `id` of the `tool_use` it answers. With parallel calls, that's how the
model knows which result is which.

**Errors go back to the model, not to the user.** When a tool fails, we send
the error text with `is_error: true`. The model reads it and usually fixes
its mistake. This self-correction is a big part of what makes agents useful.

**`messages` is the agent's memory.** Nothing is remembered between calls
except what you send. The API is stateless; the harness owns the state.
Every turn the full history is re-sent, which is why long sessions get slow
and expensive (a later level will deal with this).

**Always append the full `response.content`.** Not just the text. The reply
can contain `tool_use` blocks (which the matching `tool_result` must follow)
and thinking blocks (which the API expects back unchanged).

**Have a step limit.** `MAX_STEPS` stops a confused model from looping
forever and spending money.

## `stop_reason` cheat sheet

| Value | Meaning | What the harness does |
|---|---|---|
| `end_turn` | Model finished its answer | Return the text |
| `tool_use` | Model wants tools run | Run them, loop |
| `max_tokens` | Reply hit the length cap | Warn, return what we got |
| `refusal` | Model declined the request | Tell the user |

## What this harness does NOT do yet

These are the topics for the next levels:

- **Streaming**: print the reply as it is generated.
- **Permissions**: ask the user before running a risky tool (write file, shell).
- **More powerful tools**: write/edit files, run shell commands, search.
- **Context management**: what to do when `messages` gets too long.
- **Retries and fallbacks**: rate limits, network errors, refusals.
- **Sub-agents and planning**: one agent delegating to others.

## Exercises

1. Add a `list_files` tool that lists files in the workspace.
2. Print the number of steps each turn took. Which questions need more than one?
3. Remove the description from the `calculator` schema. Does Claude still use it?
4. Make `run_tool` ask `Run this tool? [y/N]` before each call. You just built
   a permission system.

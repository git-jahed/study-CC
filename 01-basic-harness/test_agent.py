"""
test_agent.py - check the loop without calling the real API.

We swap the Anthropic client for a fake one that replays a scripted
conversation. This is a useful habit: the harness logic (looping, running
tools, wiring results back) can be tested for free and deterministically.

Run: python -m pytest test_agent.py   (or just: python test_agent.py)
"""

from types import SimpleNamespace as NS

from agent import agent_turn
from tools import calculator, read_file


class FakeClient:
    """Returns pre-written responses, one per call, and records requests."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = self  # so `client.messages.create(...)` works

    def create(self, **kwargs):
        # Snapshot the list: the harness keeps appending to the same object.
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        return self.responses.pop(0)


def test_tool_call_then_answer():
    client = FakeClient([
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t1", name="calculator", input={"expression": "6 * 7"}),
        ]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="It is 42.")]),
    ])
    messages = [{"role": "user", "content": "What is 6 * 7?"}]

    answer = agent_turn(client, messages)

    assert answer == "It is 42."
    assert len(client.requests) == 2
    # The second request must carry the tool result, linked by id.
    tool_result = client.requests[1]["messages"][-1]["content"][0]
    assert tool_result == {"type": "tool_result", "tool_use_id": "t1", "content": "42", "is_error": False}


def test_tool_error_is_sent_back_not_raised():
    client = FakeClient([
        NS(stop_reason="tool_use", content=[
            NS(type="tool_use", id="t1", name="read_file", input={"path": "../../etc/passwd"}),
        ]),
        NS(stop_reason="end_turn", content=[NS(type="text", text="I can't read that.")]),
    ])
    agent_turn(client, [{"role": "user", "content": "read /etc/passwd"}])
    tool_result = client.requests[1]["messages"][-1]["content"][0]
    assert tool_result["is_error"] is True
    assert "outside the workspace" in tool_result["content"]


def test_calculator_rejects_code():
    assert calculator("2 ** 10") == "1024"
    try:
        calculator("__import__('os').system('ls')")
    except ValueError:
        pass
    else:
        raise AssertionError("calculator ran arbitrary code")


def test_read_file_inside_workspace():
    assert "agent harness" in read_file("README.md").lower()


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")

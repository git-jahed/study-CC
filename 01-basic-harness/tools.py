"""
tools.py - the "hands" of our agent.

A tool has two halves:

  1. A SCHEMA that we send to the model. It tells Claude the tool's name,
     what it does, and what arguments it takes (as JSON Schema). The model
     never sees our Python code - only this description.

  2. A FUNCTION that we run on our own machine when the model asks for it.

The harness glues the two together: when Claude replies with a `tool_use`
block naming "calculator", the harness looks up the matching Python function,
runs it with the arguments Claude chose, and sends the result back.
"""

import ast
import datetime
import operator
from pathlib import Path

# The agent may only read files inside this folder. Even a basic harness
# should put a fence around what tools can touch.
WORKSPACE = Path(__file__).parent.resolve()


# ---------------------------------------------------------------------------
# Tool 1: calculator
# ---------------------------------------------------------------------------
# LLMs are bad at exact arithmetic, so we give them a calculator.
# We deliberately do NOT use eval(): it would let the model run any Python.
# Instead we parse the expression and allow only a few math operators.

_ALLOWED_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def _eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPS:
        return _ALLOWED_OPS[type(node.op)](_eval_node(node.operand))
    raise ValueError("only numbers and + - * / ** % are allowed")


def calculator(expression: str) -> str:
    tree = ast.parse(expression, mode="eval")
    return str(_eval_node(tree.body))


# ---------------------------------------------------------------------------
# Tool 2: get_current_time
# ---------------------------------------------------------------------------
# The model has no clock. Anything about "now" has to come from a tool.

def get_current_time() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Tool 3: read_file
# ---------------------------------------------------------------------------
# Lets the agent look at real data. This is the first step toward a coding
# agent: once it can read files, it can reason about a project.

def read_file(path: str) -> str:
    target = (WORKSPACE / path).resolve()
    if not target.is_relative_to(WORKSPACE):
        raise PermissionError(f"{path} is outside the workspace")
    if not target.is_file():
        raise FileNotFoundError(f"{path} does not exist")
    return target.read_text()[:10_000]  # cap the size so we don't flood the context


# ---------------------------------------------------------------------------
# The schemas we send to Claude
# ---------------------------------------------------------------------------
# Good descriptions matter a lot: they are the only way the model knows
# WHEN to use a tool and HOW to fill in its arguments.

TOOL_SCHEMAS = [
    {
        "name": "calculator",
        "description": "Evaluate an arithmetic expression exactly. Use this for any math instead of computing in your head.",
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "An arithmetic expression, e.g. '(17 * 23) / 4'",
                }
            },
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Get the current local date and time in ISO 8601 format.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_file",
        "description": "Read a text file from the agent's workspace folder. Paths are relative to that folder, e.g. 'README.md'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Relative path of the file to read"}
            },
            "required": ["path"],
        },
    },
]

# Name -> Python function. The harness uses this to dispatch tool calls.
TOOL_FUNCTIONS = {
    "calculator": calculator,
    "get_current_time": get_current_time,
    "read_file": read_file,
}

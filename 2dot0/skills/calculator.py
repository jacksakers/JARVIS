import ast
import math
import operator
from typing import Any

from pydantic import BaseModel, Field

from skills.base_skill import BaseSkill


class CalculatorInput(BaseModel):
    expression: str = Field(
        description=(
            "A mathematical expression to evaluate. Supports +, -, *, /, **, "
            "parentheses, and common functions: sqrt, abs, round, floor, ceil, log, log10. "
            "Examples: '2 + 2', '(15 * 3) / 2', 'sqrt(144)', '2 ** 10'."
        )
    )


class CalculatorSkill(BaseSkill):
    name = "calculate"
    description = (
        "Safely evaluates a mathematical expression and returns the result. "
        "Use for arithmetic, percentages, powers, roots, and basic maths."
    )
    input_model = CalculatorInput

    # Allowed binary operators
    _BIN_OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.FloorDiv: operator.floordiv,
    }

    # Allowed unary operators
    _UNARY_OPS = {
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    # Allowed safe functions (no builtins that could be abused)
    _SAFE_FUNCS = {
        "sqrt": math.sqrt,
        "abs": abs,
        "round": round,
        "floor": math.floor,
        "ceil": math.ceil,
        "log": math.log,
        "log10": math.log10,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "pi": math.pi,
        "e": math.e,
    }

    def execute(self, params: CalculatorInput) -> str:
        try:
            result = self._safe_eval(params.expression.strip())
            # Format nicely: drop .0 for whole numbers
            if isinstance(result, float) and result.is_integer():
                formatted = str(int(result))
            else:
                formatted = f"{result:.10g}"
            return f"{params.expression} = {formatted}"
        except ZeroDivisionError:
            return "Error: division by zero."
        except Exception as exc:
            return f"Could not evaluate '{params.expression}': {exc}"

    def _safe_eval(self, expr: str) -> Any:
        tree = ast.parse(expr, mode="eval")
        return self._eval_node(tree.body)

    def _eval_node(self, node: ast.AST) -> Any:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise ValueError(f"Unsupported literal: {node.value!r}")
            return node.value

        if isinstance(node, ast.BinOp):
            op_fn = self._BIN_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op_fn(self._eval_node(node.left), self._eval_node(node.right))

        if isinstance(node, ast.UnaryOp):
            op_fn = self._UNARY_OPS.get(type(node.op))
            if op_fn is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return op_fn(self._eval_node(node.operand))

        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("Only simple function calls are allowed.")
            func_name = node.func.id
            func = self._SAFE_FUNCS.get(func_name)
            if func is None:
                raise ValueError(f"Function '{func_name}' is not allowed.")
            args = [self._eval_node(a) for a in node.args]
            return func(*args)

        if isinstance(node, ast.Name):
            # Allow named constants like pi, e
            const = self._SAFE_FUNCS.get(node.id)
            if isinstance(const, (int, float)):
                return const
            raise ValueError(f"Unknown name: '{node.id}'")

        raise ValueError(f"Unsupported expression node: {type(node).__name__}")

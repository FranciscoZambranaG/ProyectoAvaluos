"""Evaluador seguro de expresiones almacenadas en config.formula_versions."""

from __future__ import annotations

import ast
import operator
from decimal import Decimal, InvalidOperation
from typing import Mapping


class FormulaError(ValueError):
    pass


_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _dec(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise FormulaError("Booleano no permitido en fórmulas")
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise FormulaError(f"Valor no numérico: {value!r}") from exc


def _flatten(expression: str, variables: Mapping[str, object]) -> tuple[str, dict[str, object]]:
    """Sustituye nombres con punto (zone.valor_m2) por alias válidos para AST."""
    keys = sorted((str(k) for k in variables), key=len, reverse=True)
    expr = expression
    flat: dict[str, object] = {}
    for i, key in enumerate(keys):
        alias = f"_v{i}"
        if key in expr:
            expr = expr.replace(key, alias)
        flat[alias] = variables[key]
        flat[key] = variables[key]
    return expr, {**{k: variables[k] for k in variables}, **flat}


class _SafeEval(ast.NodeVisitor):
    def __init__(self, variables: Mapping[str, object]):
        self.variables = dict(variables)

    def visit(self, node):  # type: ignore[override]
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_BinOp(self, node: ast.BinOp):
        op = _BINOPS.get(type(node.op))
        if not op:
            raise FormulaError(f"Operador no permitido: {type(node.op).__name__}")
        return _dec(op(self.visit(node.left), self.visit(node.right)))

    def visit_UnaryOp(self, node: ast.UnaryOp):
        op = _UNARY.get(type(node.op))
        if not op:
            raise FormulaError(f"Operador unario no permitido: {type(node.op).__name__}")
        return _dec(op(self.visit(node.operand)))

    def visit_Name(self, node: ast.Name):
        if node.id not in self.variables:
            raise FormulaError(f"Variable desconocida: {node.id}")
        return _dec(self.variables[node.id])

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, (int, float, Decimal)):
            return _dec(node.value)
        raise FormulaError(f"Constante no numérica: {node.value!r}")

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Name) or node.keywords:
            raise FormulaError("Solo se permiten funciones SUM, MAX, MIN, ABS")
        name = node.func.id.upper()
        args = [self.visit(a) for a in node.args]
        if name == "SUM":
            total = Decimal("0")
            for a in args:
                total += _dec(a)
            return total
        if name == "MAX":
            return _dec(max(args)) if args else Decimal("0")
        if name == "MIN":
            return _dec(min(args)) if args else Decimal("0")
        if name == "ABS":
            if len(args) != 1:
                raise FormulaError("ABS requiere un argumento")
            return abs(_dec(args[0]))
        raise FormulaError(f"Función no permitida: {node.func.id}")

    def generic_visit(self, node: ast.AST):
        raise FormulaError(f"Expresión no permitida: {type(node).__name__}")


def eval_expression(expression: str, variables: Mapping[str, object] | None = None) -> Decimal:
    """Evalúa una expresión aritmética. Sin acceso a builtins ni atributos."""
    if not expression or not str(expression).strip():
        raise FormulaError("Expresión vacía")
    expr, flat = _flatten(str(expression).strip(), variables or {})
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"Sintaxis inválida: {expression}") from exc
    result = _SafeEval(flat).visit(tree)
    return _dec(result).quantize(Decimal("0.0001"))

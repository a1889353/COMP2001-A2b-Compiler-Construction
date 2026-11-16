"""Pitwall optimiser (phase 4: constant folding and dead-code elimination)"""
# The purpose of this file is to simplify the AST before code generation (this phase is skipped with the flag --no-opt).
# It uses the same functions as the VM (operations.py) -> so unit and type errors between literals are caught before the program runs.
#
# It does two things:
# -> constant folding -> works out literal maths at compile time (ex: 2 + 3 * 4 -> 14)
# -> dead-code elimination -> removes code that can never run (ex: if false { })

from core import ast_nodes as A
from core.operations import binary_op, convert, unary_op
from core.values import Quantity

LITERALS = (A.Number, A.String, A.Bool)


# Function that turns a literal node into the value it stands for
# (ex: Number(50, L) -> Quantity(50, L))
def node_value(node):
    if isinstance(node, A.Number):
        return node.value if node.unit is None else Quantity(node.value, node.unit)
    return node.value


# Function that turns a folded value back into a literal node
def value_node(value, line):
    # checks for true / false first -> in Python a bool also counts as an int
    if isinstance(value, bool):
        return A.Bool(value, line)
    if isinstance(value, Quantity):
        return A.Number(value.value, value.unit, line)
    if isinstance(value, str):
        return A.String(value, line)
    return A.Number(value, None, line)


# Optimiser class -> rebuilds the tree with constants folded and dead code removed
class Optimiser:
    # relies on the unit table to fold "to" conversions
    def __init__(self, units):
        self.units = units

    ## Statements
    # Function that optimises a list of statements
    # -> drops anything after a return / break / continue as it can never run
    def statements(self, body):
        result = []
        for stmt in body:
            new = self.statement(stmt)
            # checks if the statement was removed completely (ex: if false { })
            if new is None:
                continue
            result.append(new)
            if isinstance(new, (A.Return, A.Break, A.Continue)):
                break
        return result

    # Function that optimises one statement -> returns it or None if removed
    def statement(self, node):
        if isinstance(node, A.If):
            return self.optimise_if(node)
        # checks for while false -> the loop never runs -> so it is removed
        if isinstance(node, A.While):
            node.cond = self.expr(node.cond)
            if isinstance(node.cond, A.Bool) and not node.cond.value:
                return None
            node.body = self.block(node.body)
            return node
        # for / repeat loops -> optimises the list/count -> then the body
        if isinstance(node, (A.ForIn, A.Repeat)):
            if isinstance(node, A.ForIn):
                node.iterable = self.expr(node.iterable)
            else:
                node.count = self.expr(node.count)
            node.body = self.block(node.body)
            return node
        if isinstance(node, A.Block):
            return self.block(node)
        if isinstance(node, A.FnDecl):
            node.body = self.block(node.body)
            return node
        # var / let / assignment -> optimises the value being stored
        if isinstance(node, (A.Declare, A.Assign)):
            node.value = self.expr(node.value)
            return node
        # checks for list[i] = value -> optimises the list -> the index and the value
        if isinstance(node, A.IndexAssign):
            node.target = self.expr(node.target)
            node.index = self.expr(node.index)
            node.value = self.expr(node.value)
            return node
        if isinstance(node, A.Return):
            if node.value is not None:
                node.value = self.expr(node.value)
            return node
        if isinstance(node, A.Check):
            node.cond = self.expr(node.cond)
            return node
        if isinstance(node, A.ExprStmt):
            node.expr = self.expr(node.expr)
            return node
        # anything else (break/continue/unit declarations) -> nothing left to optimise
        return node

    # Function that optimises a blocks statements
    # -> the block itself is kept so it still makes a new scope
    def block(self, node):
        node.body = self.statements(node.body)
        return node

    # Function that optimises an if / elif / else chain
    # -> branches with a false condition are dropped and a true one ends the chain
    def optimise_if(self, node):
        branches = []
        for cond, body in node.branches:
            cond = self.expr(cond)
            # checks for a false condition -> the branch can never run -> so its dropped
            if isinstance(cond, A.Bool) and not cond.value:
                continue
            # checks for a true condition -> always runs -> ends the chain here
            if isinstance(cond, A.Bool) and cond.value:
                # checks if it is the first live branch -> the if becomes just its block
                if not branches:
                    return self.block(body)
                node.branches = branches
                node.else_body = self.block(body)
                return node
            branches.append((cond, self.block(body)))
        else_body = self.block(node.else_body) if node.else_body is not None else None
        # checks if every branch was dropped -> only the else is left (or nothing)
        if not branches:
            return else_body
        node.branches = branches
        node.else_body = else_body
        return node

    ## Expressions
    # Function that optimises an expression -> folds it when every part is a literal
    def expr(self, node):
        if isinstance(node, A.BinOp):
            node.left = self.expr(node.left)
            node.right = self.expr(node.right)
            # checks both sides are literals -> works the result out now
            # (unit / type errors are raised here -> prior to program runtime)
            if isinstance(node.left, LITERALS) and isinstance(node.right, LITERALS):
                left, right = node_value(node.left), node_value(node.right)
                return value_node(binary_op(node.op, left, right, node.line), node.line)
            return node
        # checks for - or not on a literal (ex: -5, not true) -> folds it
        if isinstance(node, A.Unary):
            node.operand = self.expr(node.operand)
            if isinstance(node.operand, LITERALS):
                value = unary_op(node.op, node_value(node.operand), node.line)
                return value_node(value, node.line)
            return node
        # checks for a "to" conversion on a literal (ex: 1[km] to [m] -> 1000.0 m)
        if isinstance(node, A.Convert):
            node.expr = self.expr(node.expr)
            if isinstance(node.expr, LITERALS):
                value = convert(node_value(node.expr), node.unit, node.line, self.units)
                return value_node(value, node.line)
            return node
        # checks for and / or -> handled separately -> the left side can decide it
        if isinstance(node, A.Logical):
            return self.optimise_logical(node)
        # ranges, lists, calls and indexing -> folds the parts inside -> the node stays
        if isinstance(node, A.Range):
            node.start = self.expr(node.start)
            node.end = self.expr(node.end)
            return node
        if isinstance(node, A.ListLit):
            node.items = [self.expr(item) for item in node.items]
            return node
        if isinstance(node, A.Call):
            node.args = [self.expr(arg) for arg in node.args]
            return node
        if isinstance(node, A.Index):
            node.target = self.expr(node.target)
            node.index = self.expr(node.index)
            return node
        # literals and names stay as they are
        return node

    # Function that folds and/or when the answer is already known
    # -> "false and x" / "true or x" -> the answer is the left side
    # -> "true and x" / "false or x" -> the answer is x (folded only if x is a literal)
    def optimise_logical(self, node):
        node.left = self.expr(node.left)
        node.right = self.expr(node.right)
        left, right = node.left, node.right
        if isinstance(left, A.Bool):
            if (node.op == "and") != left.value:
                return left
            if isinstance(right, A.Bool):
                return right
        return node


# Function that runs this optimiser on a program and returns the optimised program
def optimise(program, units):
    optimiser = Optimiser(units)
    program.body = optimiser.statements(program.body)
    return program

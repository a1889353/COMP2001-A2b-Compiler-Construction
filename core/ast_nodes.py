"""Pitwall AST nodes (built by the parser)"""
# The purpose of this file is to define the nodes of the AST that the parser builds.
# The semantic analyser, optimiser and code generator all walk this tree -> where each node only keeps what matters for context (ie doesn't count brackets/commas etc)
# Every node stores its source line so later phases are able to point to the exact line of where the error is located.
#
# Every node shares two methods that the --ast dump uses -> label() returns the one line of text shown for that node,
# and children() returns the nodes that sit underneath it, so dump() can start at the top of the tree and print every node indented by its depth.

from core.values import format_number, quote_string


# Base class for every AST node
class Node:
    is_statement = False  # statements show their line number in the dump

    # display text for the node -> the class name by default
    def label(self):
        return type(self).__name__

    # child nodes shown underneath it -> none by default
    def children(self):
        return []


## STATEMENTS
# The whole program -> a list of statements
class Program(Node):
    def __init__(self, body):
        self.body = body
        self.line = 1

    def children(self):
        return [(None, s) for s in self.body]


# { ... } -> statements in their own scope
class Block(Node):
    is_statement = True

    def __init__(self, body, line):
        self.body = body
        self.line = line

    def children(self):
        return [(None, s) for s in self.body]


# var / let declaration -> kind is "var" or "let"
class Declare(Node):
    is_statement = True

    def __init__(self, kind, name, value, line):
        self.kind = kind
        self.name = name
        self.value = value
        self.line = line

    def label(self):
        return "Declare {} {}".format(self.kind, self.name)

    def children(self):
        return [(None, self.value)]


# x = e, x += e or x -= e -> op refers to the operator used
class Assign(Node):
    is_statement = True

    def __init__(self, name, op, value, line):
        self.name = name
        self.op = op
        self.value = value
        self.line = line

    def label(self):
        return "Assign {} {}".format(self.name, self.op)

    def children(self):
        return [(None, self.value)]


# list item assignment (ex: grid[i][j] = 5)
class IndexAssign(Node):
    is_statement = True

    def __init__(self, target, index, value, line):
        self.target = target
        self.index = index
        self.value = value
        self.line = line

    def children(self):
        return [("list", self.target), ("index", self.index), ("value", self.value)]


# if / elif / else -> branches is a list of (condition, block) pairs -> else_body can be None
class If(Node):
    is_statement = True

    def __init__(self, branches, else_body, line):
        self.branches = branches
        self.else_body = else_body
        self.line = line

    def children(self):
        result = []
        # first branch is tagged "if" -> the rest are tagged "elif"
        for i, (cond, body) in enumerate(self.branches):
            result.append(("if" if i == 0 else "elif", cond))
            result.append(("then", body))
        # else block goes last if there is one
        if self.else_body is not None:
            result.append(("else", self.else_body))
        return result


# while loop
class While(Node):
    is_statement = True

    def __init__(self, cond, body, line):
        self.cond = cond
        self.body = body
        self.line = line

    def children(self):
        return [("cond", self.cond), ("body", self.body)]


# for loop -> iterates over a list or a range
class ForIn(Node):
    is_statement = True

    def __init__(self, var, iterable, body, line):
        self.var = var
        self.iterable = iterable
        self.body = body
        self.line = line

    def label(self):
        return "ForIn {}".format(self.var)

    def children(self):
        return [("in", self.iterable), ("body", self.body)]


# repeat n times loop
class Repeat(Node):
    is_statement = True

    def __init__(self, count, body, line):
        self.count = count
        self.body = body
        self.line = line

    def children(self):
        return [("times", self.count), ("body", self.body)]


# break -> leaves the loop
class Break(Node):
    is_statement = True

    def __init__(self, line):
        self.line = line


# continue -> skips to the next loop iteration
class Continue(Node):
    is_statement = True

    def __init__(self, line):
        self.line = line


# function declaration -> params is a list of names
class FnDecl(Node):
    is_statement = True

    def __init__(self, name, params, body, line):
        self.name = name
        self.params = params
        self.body = body
        self.line = line

    def label(self):
        return "FnDecl {}({})".format(self.name, ", ".join(self.params))

    def children(self):
        return [(None, self.body)]


# return -> value is None when nothing is returned
class Return(Node):
    is_statement = True

    def __init__(self, value, line):
        self.value = value
        self.line = line

    def children(self):
        return [] if self.value is None else [(None, self.value)]


# unit declaration (ex: unit stint = 25 lap)
class UnitDecl(Node):
    is_statement = True

    def __init__(self, name, scale, unit, line):
        self.name = name
        self.scale = scale
        self.unit = unit
        self.line = line

    def label(self):
        return "UnitDecl {} = {} {}".format(
            self.name, format_number(self.scale), self.unit
        )


# check -> stops with "check failed" if false
class Check(Node):
    is_statement = True

    def __init__(self, cond, line):
        self.cond = cond
        self.line = line

    def children(self):
        return [(None, self.cond)]


# expression used as a statement (ex: print(...))
class ExprStmt(Node):
    is_statement = True

    def __init__(self, expr, line):
        self.expr = expr
        self.line = line

    def children(self):
        return [(None, self.expr)]


## EXPRESSIONS
# number literal with an optional unit (ex: 42, 50[L], 1:32.318)
class Number(Node):
    def __init__(self, value, unit, line):
        self.value = value
        self.unit = unit
        self.line = line

    def label(self):
        text = "Number " + format_number(self.value)
        # shows the unit in brackets after the number if there is one
        if self.unit is not None:
            text += " [{}]".format(self.unit)
        return text


# string literal
class String(Node):
    def __init__(self, value, line):
        self.value = value
        self.line = line

    def label(self):
        return "String " + quote_string(self.value)


# true / false literal
class Bool(Node):
    def __init__(self, value, line):
        self.value = value
        self.line = line

    def label(self):
        return "Bool " + ("true" if self.value else "false")


# name being read -> a variable, constant or function
class Name(Node):
    def __init__(self, name, line):
        self.name = name
        self.line = line

    def label(self):
        return "Name " + self.name


# list literal (ex: [a, b, c])
class ListLit(Node):
    def __init__(self, items, line):
        self.items = items
        self.line = line

    def label(self):
        return "List ({} items)".format(len(self.items))

    def children(self):
        return [(None, item) for item in self.items]


# arithmetic or comparison (ex: +, *, <)
class BinOp(Node):
    def __init__(self, op, left, right, line):
        self.op = op
        self.left = left
        self.right = right
        self.line = line

    def label(self):
        return "BinOp " + self.op

    def children(self):
        return [(None, self.left), (None, self.right)]


# and / or -> kept separate from BinOp as they short-circuit
class Logical(Node):
    def __init__(self, op, left, right, line):
        self.op = op
        self.left = left
        self.right = right
        self.line = line

    def label(self):
        return "Logical " + self.op

    def children(self):
        return [(None, self.left), (None, self.right)]


# -x or not x -> op is "-" or "not"
class Unary(Node):
    def __init__(self, op, operand, line):
        self.op = op
        self.operand = operand
        self.line = line

    def label(self):
        return "Unary " + self.op

    def children(self):
        return [(None, self.operand)]


# unit conversion (ex: x to [km/h])
class Convert(Node):
    def __init__(self, expr, unit, line):
        self.expr = expr
        self.unit = unit
        self.line = line

    def label(self):
        return "Convert to [{}]".format(self.unit)

    def children(self):
        return [(None, self.expr)]


# range class (start..end) -> runs from start up to end - 1
class Range(Node):
    def __init__(self, start, end, line):
        self.start = start
        self.end = end
        self.line = line

    def children(self):
        return [("from", self.start), ("upto", self.end)]


# function call -> a built-in or user function
class Call(Node):
    def __init__(self, name, args, line):
        self.name = name
        self.args = args
        self.line = line

    def label(self):
        return "Call {}".format(self.name)

    def children(self):
        return [(None, a) for a in self.args]


# list / string index (ex: xs[i])
class Index(Node):
    def __init__(self, target, index, line):
        self.target = target
        self.index = index
        self.line = line

    def children(self):
        return [(None, self.target), ("index", self.index)]


# Function that returns the whole tree as indented text for --ast dumps
def dump(node):
    lines = []

    # prints a node -> then its children one level deeper
    def walk(n, depth, tag):
        prefix = "  " * depth + (tag + ": " if tag else "")
        header = prefix + n.label()
        if n.is_statement:
            header += "  (line {})".format(n.line)
        lines.append(header)
        for child_tag, child in n.children():
            walk(child, depth + 1, child_tag)

    walk(node, 0, None)
    return "\n".join(lines)

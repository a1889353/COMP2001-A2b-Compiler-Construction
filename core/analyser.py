"""Pitwall semantic analyser (phase 3: semantic analysis)"""
# The purpose of this file is to check the AST for mistakes that can be found before the program runs.
# It walks the tree with a symbol table -> a stack of scopes -> one per block -> each mapping a name to what it is (var, let or fn).
#
# It checks that:
# -> names are declared before they are used
# -> constants are never changed
# -> a name isn't declared twice in the same block
# -> break / continue only appear inside loops
# -> return only appears inside functions
# -> calls to known functions have the right number of arguments
#
# adds unit declarations to the unit table at compile time -> for the optimiser and VM

from core.builtins import BUILTINS, arity_message
from core.errors import PitwallError


# Symbol class -> what the symbol table knows about one name
class Symbol:
    # kind is "var", "let" or "fn" -> arity is the number of parameters for a user function
    def __init__(self, kind, arity=None):
        self.kind = kind
        self.arity = arity


# Analyser class -> walks the AST and checks the semantic rules
class Analyser:
    # the unit table, the scopes (built-ins then globals) and how many loops / functions we're inside (for break, continue and return)
    def __init__(self, units):
        self.units = units
        self.scopes = [
            {name: Symbol("fn") for name in BUILTINS},
            {},
        ]
        self.loop_depth = 0
        self.function_depth = 0

    ## Symbol table helpers
    # adds a name to the innermost scope -> declaring the same name twice in one block is an error
    def declare(self, name, symbol, line):
        if name in self.scopes[-1]:
            raise PitwallError(
                line, "{} is already declared in this block".format(name)
            )
        self.scopes[-1][name] = symbol

    # finds a name in the nearest scope that has it -> undeclared names result in an error
    def lookup(self, name, line):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise PitwallError(line, "{} is not defined".format(name))

    # runs a list of statements in a new scope
    def visit_in_scope(self, statements):
        self.scopes.append({})
        for stmt in statements:
            self.visit(stmt)
        self.scopes.pop()

    ## Walking the tree
    # checks the whole program
    def analyse(self, program):
        for stmt in program.body:
            self.visit(stmt)

    # Function that finds the check for this node type (ex: Assign -> visit_Assign)
    # and runs it -> a node type with no visit_ method just has its child nodes visited
    def visit(self, node):
        method = getattr(self, "visit_" + type(node).__name__, None)
        if method is None:
            for _tag, child in node.children():
                self.visit(child)
        else:
            method(node)

    # Function that checks a { } block in its own scope
    def visit_Block(self, node):
        self.visit_in_scope(node.body)

    # var/let -> the value is checked first -> so "var x = x" cant use the new value of x
    def visit_Declare(self, node):
        self.visit(node.value)
        self.declare(node.name, Symbol(node.kind), node.line)

    # x = e, x += e -> x must exist and must not be a constant (let) or a function (fn)
    def visit_Assign(self, node):
        self.visit(node.value)
        symbol = self.lookup(node.name, node.line)
        if symbol.kind != "var":
            raise PitwallError(node.line, "cannot change constant {}".format(node.name))

    # for x in list -> the loop variable lives in its own scope around the body
    def visit_ForIn(self, node):
        self.visit(node.iterable)
        self.scopes.append({node.var: Symbol("var")})
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1
        self.scopes.pop()

    # while -> checks the condition, then the body counts as a loop
    def visit_While(self, node):
        self.visit(node.cond)
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1

    # repeat -> checks the count, then the body counts as a loop
    def visit_Repeat(self, node):
        self.visit(node.count)
        self.loop_depth += 1
        self.visit(node.body)
        self.loop_depth -= 1

    # break / continue -> only allowed inside a loop
    def visit_Break(self, node):
        if self.loop_depth == 0:
            raise PitwallError(node.line, "break outside a loop")

    def visit_Continue(self, node):
        if self.loop_depth == 0:
            raise PitwallError(node.line, "continue outside a loop")

    # return -> only allowed inside a function
    def visit_Return(self, node):
        if self.function_depth == 0:
            raise PitwallError(node.line, "return outside a function")
        if node.value is not None:
            self.visit(node.value)

    # fn -> the name is declared before the body is checked -> which allows the function to call itself
    def visit_FnDecl(self, node):
        self.declare(node.name, Symbol("fn", len(node.params)), node.line)
        params = {}
        # checks every parameter name is different -> f(a, a) is an error
        for param in node.params:
            if param in params:
                raise PitwallError(node.line, "parameter {} is repeated".format(param))
            params[param] = Symbol("var")
        self.scopes.append(params)
        # a loop outside the function doesnt count inside it -> saves the loop depth and resets it
        saved_loops = self.loop_depth
        self.loop_depth = 0
        self.function_depth += 1
        self.visit(node.body)
        self.function_depth -= 1
        self.loop_depth = saved_loops
        self.scopes.pop()

    # unit declaration -> added to the unit table now (redefining a unit is an error)
    def visit_UnitDecl(self, node):
        self.units.define(node.name, node.scale, node.unit, node.line)

    # Function that checks a name being used -> it must be declared first
    def visit_Name(self, node):
        self.lookup(node.name, node.line)

    # Function that checks a call -> the function must exist
    # and must be passed the correct number of arguments
    def visit_Call(self, node):
        symbol = self.lookup(node.name, node.line)
        got = len(node.args)
        # checks for a built-in (not a user defined one) -> checks its argument limits
        if node.name in BUILTINS and symbol is self.scopes[0][node.name]:
            builtin = BUILTINS[node.name]
            too_many = builtin.max_args is not None and got > builtin.max_args
            if got < builtin.min_args or too_many:
                message = arity_message(
                    node.name, builtin.min_args, builtin.max_args, got
                )
                raise PitwallError(node.line, message)
        # checks for a user function -> needs one argument per parameter
        elif symbol.kind == "fn" and symbol.arity is not None and got != symbol.arity:
            message = arity_message(node.name, symbol.arity, symbol.arity, got)
            raise PitwallError(node.line, message)
        # checks each argument expression too
        for arg in node.args:
            self.visit(arg)


# Function that runs the semantic analyser on a program
# -> raises a PitwallError for the first mistake found
def analyse(program, units):
    Analyser(units).analyse(program)

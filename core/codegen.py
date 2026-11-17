"""Pitwall code generator (phase 5: code generation)"""
# The purpose of this file is to turn the checked AST into bytecode -> a flat list of simple instructions for the stack VM (vm.py).
# The main program and every function each get their own CodeObject -> every instruction keeps its source line for error messages.
#
# Jumps are filled in with backpatching:
# -> a jump is emitted with an empty target -> then patched once the address is known.
# -> used for if/elif/else, loops, break/continue and short-circuit and/or.

from core import ast_nodes as A
from core.values import NOTHING, Quantity, format_value, quote_string

# OpCode name mapping for each operator
BINARY_OPCODES = {
    "+": "ADD",
    "-": "SUB",
    "*": "MUL",
    "/": "DIV",
    "%": "MOD",
    "==": "EQ",
    "!=": "NE",
    "<": "LT",
    "<=": "LE",
    ">": "GT",
    ">=": "GE",
}


# Instruction class -> one bytecode instruction (ex: CONST 14, JUMP 7)
# -> op is the opcode name (ex: "ADD") and arg is its argument (or None)
# -> line is the source line it came from (for error messages)
class Instruction:
    def __init__(self, op, arg, line):
        self.op = op
        self.arg = arg
        self.line = line


# CodeObject class -> the bytecode for the main program or for one function
class CodeObject:
    def __init__(self, name, params):
        self.name = name
        self.params = params
        self.instructions = []


# LoopInfo class -> what break / continue need to know about the loop they are in
# -> where continue jumps to -> the scope depth outside the loop and any iterator
# -> plus the break jumps that get patched once the end of the loop is known
class LoopInfo:
    def __init__(self, continue_target, scope_depth, has_iterator):
        self.continue_target = continue_target
        self.scope_depth = scope_depth
        self.has_iterator = has_iterator
        self.break_jumps = []


# CodeGenerator class -> walks the AST and emits instructions
# -> keeps the code object being written
# -> how many scopes are open and the loops it is in
# -> plus every functions code object (for --bytecode)
class CodeGenerator:
    def __init__(self):
        self.code = None
        self.scope_depth = 0
        self.loops = []
        self.functions = []

    ## Emitting instructions
    # Function that adds an instruction -> returns its address (its index in the list)
    def emit(self, op, arg, line):
        self.code.instructions.append(Instruction(op, arg, line))
        return len(self.code.instructions) - 1

    # Function that gives the address the next instruction will get
    def here(self):
        return len(self.code.instructions)

    # Function that backpatches -> fills in a jumps target once the address is known
    def patch(self, address, target):
        self.code.instructions[address].arg = target

    ## Programs and statements
    # Function that compiles the main program -> returns its CodeObject
    def generate(self, program):
        self.code = CodeObject("<main>", [])
        for stmt in program.body:
            self.statement(stmt)
        last_line = program.body[-1].line if program.body else 1
        self.emit("HALT", None, last_line)
        return self.code

    # Function that finds the compile method for this node type
    # (ex: Assign -> stmt_Assign) and runs it
    def statement(self, node):
        getattr(self, "stmt_" + type(node).__name__)(node)

    # { } block -> runs its statements inside a new scope
    # -> ENTER_SCOPE opens it and EXIT_SCOPE closes it -> so its names are gone after
    def stmt_Block(self, node):
        self.emit("ENTER_SCOPE", None, node.line)
        self.scope_depth += 1
        for stmt in node.body:
            self.statement(stmt)
        self.scope_depth -= 1
        self.emit("EXIT_SCOPE", None, node.line)

    # var / let -> compiles the value
    # -> then DEFINE stores it as a new name within the scope
    # -> the DEFINE argument also records whether it is a constant (let)
    def stmt_Declare(self, node):
        self.expr(node.value)
        self.emit("DEFINE", (node.name, node.kind == "let"), node.line)

    # x = value -> compiles the value -> then STORE puts it in the existing variable
    # -> x += value -> LOAD x -> compile the value -> ADD -> then STORE (-= uses SUB)
    def stmt_Assign(self, node):
        if node.op == "=":
            self.expr(node.value)
        else:
            self.emit("LOAD", node.name, node.line)
            self.expr(node.value)
            self.emit("ADD" if node.op == "+=" else "SUB", None, node.line)
        self.emit("STORE", node.name, node.line)

    # list[i] = value -> compiles the list -> the index and the value
    # -> then STORE_INDEX changes that item in the list itself
    def stmt_IndexAssign(self, node):
        self.expr(node.target)
        self.expr(node.index)
        self.expr(node.value)
        self.emit("STORE_INDEX", None, node.line)

    # if / elif / else -> each condition jumps past its block when false
    # -> each block jumps to the end when done (the last one does not need to)
    # -> backpatching then fills in every end jump once the end address is known
    def stmt_If(self, node):
        end_jumps = []
        for i, (cond, body) in enumerate(node.branches):
            self.expr(cond)
            skip = self.emit("JUMP_IF_FALSE", None, cond.line)
            self.statement(body)
            is_last = i == len(node.branches) - 1 and node.else_body is None
            if not is_last:
                end_jumps.append(self.emit("JUMP", None, node.line))
            self.patch(skip, self.here())
        if node.else_body is not None:
            self.statement(node.else_body)
        for address in end_jumps:
            self.patch(address, self.here())

    # while -> tests the condition -> runs the body -> then jumps back to the test
    # -> the exit jump and every break are backpatched to just after the loop
    def stmt_While(self, node):
        start = self.here()
        self.expr(node.cond)
        exit_jump = self.emit("JUMP_IF_FALSE", None, node.line)
        loop = LoopInfo(start, self.scope_depth, False)
        self.loops.append(loop)
        self.statement(node.body)
        self.loops.pop()
        self.emit("JUMP", start, node.line)
        self.patch(exit_jump, self.here())
        for address in loop.break_jumps:
            self.patch(address, self.here())

    # for x in list -> GET_ITER makes an iterator over the list
    # -> then the shared loop code runs the body once per item
    def stmt_ForIn(self, node):
        self.expr(node.iterable)
        self.emit("GET_ITER", None, node.line)
        self.compile_iterator_loop(node, node.var)

    # repeat n times -> REPEAT_ITER makes an iterator over n steps
    # -> which works the same as a for loop with no variable
    def stmt_Repeat(self, node):
        self.expr(node.count)
        self.emit("REPEAT_ITER", None, node.line)
        self.compile_iterator_loop(node, None)

    # Function with the code shared by (for / repeat) loops
    # -> each pass gets a fresh scope where the item goes into the loop variable
    # -> (repeat has none, so it gets dropped) -> FOR_ITER and every break
    # are backpatched to jump to just after the loop once its end is known
    def compile_iterator_loop(self, node, var):
        start = self.emit("FOR_ITER", None, node.line)
        loop = LoopInfo(start, self.scope_depth, True)
        self.loops.append(loop)
        self.emit("ENTER_SCOPE", None, node.line)
        self.scope_depth += 1
        if var is not None:
            self.emit("DEFINE", (var, False), node.line)
        else:
            self.emit("POP", None, node.line)
        self.statement(node.body)
        self.scope_depth -= 1
        self.emit("EXIT_SCOPE", None, node.line)
        self.emit("JUMP", start, node.line)
        self.loops.pop()
        self.patch(start, self.here())
        for address in loop.break_jumps:
            self.patch(address, self.here())

    # Function that closes every scope opened inside the loop body
    # -> break / continue jump out of them -> so the VM must leave them first
    def exit_loop_scopes(self, loop, line):
        for _ in range(self.scope_depth - loop.scope_depth):
            self.emit("EXIT_SCOPE", None, line)

    # break -> leaves the loops scopes and drops the iterator if there is one
    # -> then jumps past the end of the loop (backpatched once the end is known)
    def stmt_Break(self, node):
        loop = self.loops[-1]
        self.exit_loop_scopes(loop, node.line)
        if loop.has_iterator:
            self.emit("POP", None, node.line)
        loop.break_jumps.append(self.emit("JUMP", None, node.line))

    # continue -> leaves the loops scopes
    # -> then jumps back to the start of the loop
    def stmt_Continue(self, node):
        loop = self.loops[-1]
        self.exit_loop_scopes(loop, node.line)
        self.emit("JUMP", loop.continue_target, node.line)

    # fn -> saves the current state -> then compiles the body into its own CodeObject
    # -> a body that ends without a return gives back nothing
    # -> then MAKE_FUNCTION turns it into a value and DEFINE stores it as a constant
    def stmt_FnDecl(self, node):
        outer = (self.code, self.scope_depth, self.loops)
        self.code = CodeObject(node.name, node.params)
        self.scope_depth = 0
        self.loops = []
        self.statement(node.body)
        self.emit("CONST", NOTHING, node.line)
        self.emit("RETURN", None, node.line)
        function_code = self.code
        self.functions.append(function_code)
        self.code, self.scope_depth, self.loops = outer
        self.emit("MAKE_FUNCTION", function_code, node.line)
        self.emit("DEFINE", (node.name, True), node.line)

    # return -> compiles the value (or nothing if there is none)
    def stmt_Return(self, node):
        if node.value is None:
            self.emit("CONST", NOTHING, node.line)
        else:
            self.expr(node.value)
        self.emit("RETURN", None, node.line)

    # unit -> already handled by the analyser at compile time -> so no code is needed
    def stmt_UnitDecl(self, node):
        pass

    # check -> compiles the condition -> then CHECK raises "check failed" if false
    def stmt_Check(self, node):
        self.expr(node.cond)
        self.emit("CHECK", None, node.line)

    # expression statement (ex: print(x)) -> its value is not needed -> so it is popped
    # -> calls are told used=False so a function with no return is not an error here
    def stmt_ExprStmt(self, node):
        if isinstance(node.expr, A.Call):
            self.compile_call(node.expr, used=False)
        else:
            self.expr(node.expr)
        self.emit("POP", None, node.line)

    ## Expressions
    # Function that compiles an expression -> leaves its value on top of the stack
    # -> literals become CONST and names become LOAD -> operators compile their parts
    # first -> then emit their opcode -> (and / or) and calls use their own functions
    def expr(self, node):
        if isinstance(node, A.Number):
            value = node.value if node.unit is None else Quantity(node.value, node.unit)
            self.emit("CONST", value, node.line)
        elif isinstance(node, (A.String, A.Bool)):
            self.emit("CONST", node.value, node.line)
        elif isinstance(node, A.Name):
            self.emit("LOAD", node.name, node.line)
        elif isinstance(node, A.ListLit):
            for item in node.items:
                self.expr(item)
            self.emit("BUILD_LIST", len(node.items), node.line)
        elif isinstance(node, A.BinOp):
            self.expr(node.left)
            self.expr(node.right)
            self.emit(BINARY_OPCODES[node.op], None, node.line)
        elif isinstance(node, A.Logical):
            self.compile_logical(node)
        elif isinstance(node, A.Unary):
            self.expr(node.operand)
            self.emit("NEG" if node.op == "-" else "NOT", None, node.line)
        elif isinstance(node, A.Convert):
            self.expr(node.expr)
            self.emit("CONVERT", node.unit, node.line)
        elif isinstance(node, A.Range):
            self.expr(node.start)
            self.expr(node.end)
            self.emit("RANGE", None, node.line)
        elif isinstance(node, A.Call):
            self.compile_call(node, used=True)
        elif isinstance(node, A.Index):
            self.expr(node.target)
            self.expr(node.index)
            self.emit("INDEX", None, node.line)

    # Function that compiles (and / or) with short circuiting ->
    # if the left side already decides the answer -> jumps over the right side
    # -> otherwise the right side runs and CHECK_BOOL makes sure it is true / false
    def compile_logical(self, node):
        self.expr(node.left)
        op = "JUMP_IF_FALSE_OR_POP" if node.op == "and" else "JUMP_IF_TRUE_OR_POP"
        jump = self.emit(op, None, node.line)
        self.expr(node.right)
        self.emit("CHECK_BOOL", None, node.line)
        self.patch(jump, self.here())

    # Function that compiles a call -> loads the function -> then each argument
    # -> CALL gets the name -> the argument count and whether the result is used
    def compile_call(self, node, used):
        self.emit("LOAD", node.name, node.line)
        for arg in node.args:
            self.expr(arg)
        self.emit("CALL", (node.name, len(node.args), used), node.line)


# Function that compiles a program
def generate(program):
    generator = CodeGenerator()
    main = generator.generate(program)
    return main, generator.functions


# Function that turns an instructions argument into readable text for (--bytecode)
# -> strings get quotes -> quantities show as 50[L] -> DEFINE marks constants ->
# CALL shows its argument count and functions are shown as <fn name>
def format_arg(instr):
    arg = instr.arg
    if arg is None:
        return ""
    if instr.op == "CONST":
        if isinstance(arg, str):
            return quote_string(arg)
        if isinstance(arg, Quantity):
            return "{}[{}]".format(format_value(arg.value), arg.unit)
        return format_value(arg)
    if instr.op == "DEFINE":
        return "{}{}".format(arg[0], " (const)" if arg[1] else "")
    if instr.op == "CALL":
        return "{} {} arg{}".format(arg[0], arg[1], "" if arg[1] == 1 else "s")
    if instr.op == "MAKE_FUNCTION":
        return "<fn {}>".format(arg.name)
    return str(arg)


# Function that builds the full listing for (--bytecode) -> one section per code object
# -> <main> first -> then each function with its parameters
# -> each row shows the line -> address -> opcode & argument
def format_bytecode(main, functions):
    sections = []
    for code in [main] + functions:
        if code is main:
            title = "== <main> =="
        else:
            title = "== fn {}({}) ==".format(code.name, ", ".join(code.params))
        lines = [title, "line  addr  opcode                argument"]
        for address, instr in enumerate(code.instructions):
            row = "{:>4}  {:>4}  {:<20}  {}".format(
                instr.line, address, instr.op, format_arg(instr)
            )
            lines.append(row.rstrip())
        sections.append("\n".join(lines))
    return "\n\n".join(sections)

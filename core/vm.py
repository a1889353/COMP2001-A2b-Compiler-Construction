"""Pitwall virtual machine (phase 6: running the bytecode)"""
# The purpose of this file is to run the bytecode from codegen.py on a stack machine.
#
# How it works:
# -> a fetch-decode-execute loop runs one instruction at a time
# -> values are pushed onto and popped off an operand stack
# -> every function call gets a Frame (its code, position and scope)
# -> scopes are chained dictionaries (Env) -> a name is looked up in the current
#    scope, then its parent, out to the built-ins
#
# Run-time checks happen here:
# -> unit and type mismatches, division by zero and index out of range
# -> conditions must be true / false, check statements and recursion depth

from core.builtins import BUILTINS, arity_message
from core.errors import PitwallError
from core.operations import binary_op, convert, require_bool, unary_op
from core.values import NOTHING, Builtin, Function, describe

# max number of nested calls -> any more is reported as "too much recursion"
MAX_FRAMES = 500
# marker that FOR_ITER gets back when an iterator has no items left
FINISHED = object()

# maps each binary opcode to its operator symbol -> these all go through binary_op
BINARY_OPS = {
    "ADD": "+",
    "SUB": "-",
    "MUL": "*",
    "DIV": "/",
    "MOD": "%",
    "EQ": "==",
    "NE": "!=",
    "LT": "<",
    "LE": "<=",
    "GT": ">",
    "GE": ">=",
}


# Env class -> one scope -> a dictionary of names (vars)
# -> plus its parent, the scope around it (None for the built-ins)
class Env:
    def __init__(self, parent):
        self.vars = {}
        self.parent = parent

    # Function that finds the scope holding a name -> starts here and moves outwards
    # -> returns None if no scope has it
    def find(self, name):
        env = self
        while env is not None:
            if name in env.vars:
                return env
            env = env.parent
        return None


# Frame class -> one running function (or the main program)
# -> code is the CodeObject being run -> ip is the address of the next instruction
# -> env is the current scope -> stack_base is the stack size when the call started
class Frame:
    def __init__(self, code, env, stack_base):
        self.code = code
        self.ip = 0
        self.env = env
        self.stack_base = stack_base


# VM class -> runs the bytecode
# -> keeps the unit table (for to / laptime), the operand stack and the call frames
# -> plus the line being run (for errors) -> globals sits inside the built-ins scope
class VM:
    def __init__(self, units):
        self.units = units
        self.stack = []
        self.frames = []
        self.line = 0
        builtins = Env(None)
        builtins.vars.update(BUILTINS)
        self.globals = Env(builtins)

    ## Stack helpers
    # Function that pushes a value onto the operand stack
    def push(self, value):
        self.stack.append(value)

    # Function that pops the top value off the operand stack
    def pop(self):
        return self.stack.pop()

    # Function that raises a run-time error on the line being run
    def error(self, message):
        raise PitwallError(self.line, message)

    ## The fetch-decode-execute loop
    # Function that runs the main program until HALT -> each pass of the loop:
    # -> fetch -> takes the next instruction and moves the instruction pointer on
    # -> decode + execute -> binary operators share one path through binary_op
    # -> every other opcode runs its own op_ method (ex: LOAD -> op_LOAD)
    def run(self, main):
        self.frames.append(Frame(main, self.globals, 0))
        while True:
            frame = self.frames[-1]
            instr = frame.code.instructions[frame.ip]
            frame.ip += 1
            self.line = instr.line
            if instr.op == "HALT":
                return
            if instr.op in BINARY_OPS:
                right = self.pop()
                left = self.pop()
                self.push(binary_op(BINARY_OPS[instr.op], left, right, self.line))
            else:
                getattr(self, "op_" + instr.op)(frame, instr.arg)

    ## Values and variables
    # CONST -> pushes a constant
    def op_CONST(self, frame, value):
        self.push(value)

    # LOAD -> pushes the value of a variable -> from the nearest scope that has it
    def op_LOAD(self, frame, name):
        env = frame.env.find(name)
        if env is None:
            self.error("{} is not defined".format(name))
        self.push(env.vars[name])

    # STORE -> pops a value into an existing variable -> the nearest scope with it
    def op_STORE(self, frame, name):
        env = frame.env.find(name)
        if env is None:
            self.error("{} is not defined".format(name))
        env.vars[name] = self.pop()

    # DEFINE -> pops a value into a new variable in this scope
    # -> arg is (name, is_constant)
    def op_DEFINE(self, frame, arg):
        frame.env.vars[arg[0]] = self.pop()

    # ENTER_SCOPE -> opens a new scope inside the current one
    def op_ENTER_SCOPE(self, frame, arg):
        frame.env = Env(frame.env)

    # EXIT_SCOPE -> closes the current scope -> back to its parent
    def op_EXIT_SCOPE(self, frame, arg):
        frame.env = frame.env.parent

    # POP -> throws away the top value
    def op_POP(self, frame, arg):
        self.pop()

    ## Operators
    # NEG -> negates the top value (-)
    def op_NEG(self, frame, arg):
        self.push(unary_op("-", self.pop(), self.line))

    # NOT -> flips the top value (not)
    def op_NOT(self, frame, arg):
        self.push(unary_op("not", self.pop(), self.line))

    # CONVERT -> converts the top value to another unit (to)
    def op_CONVERT(self, frame, unit):
        self.push(convert(self.pop(), unit, self.line, self.units))

    # CHECK_BOOL -> checks the top value is true / false (the right side of and / or)
    # -> leaves it on the stack
    def op_CHECK_BOOL(self, frame, arg):
        require_bool(self.stack[-1], self.line)

    ## Jumps
    # JUMP -> jumps straight to the target address
    def op_JUMP(self, frame, target):
        frame.ip = target

    # JUMP_IF_FALSE -> pops a condition -> jumps if it is false (used by if / while)
    def op_JUMP_IF_FALSE(self, frame, target):
        if not require_bool(self.pop(), self.line):
            frame.ip = target

    # JUMP_IF_FALSE_OR_POP (and) -> a false left side is kept as the answer
    # -> and jumps over the right side -> otherwise it is popped
    def op_JUMP_IF_FALSE_OR_POP(self, frame, target):
        if not require_bool(self.stack[-1], self.line):
            frame.ip = target
        else:
            self.pop()

    # JUMP_IF_TRUE_OR_POP (or) -> a true left side is kept as the answer
    # -> and jumps over the right side -> otherwise it is popped
    def op_JUMP_IF_TRUE_OR_POP(self, frame, target):
        if require_bool(self.stack[-1], self.line):
            frame.ip = target
        else:
            self.pop()

    ## Lists, ranges and loops
    # BUILD_LIST -> pops n values into a new list (in the order they were written)
    def op_BUILD_LIST(self, frame, count):
        items = self.stack[len(self.stack) - count :]
        del self.stack[len(self.stack) - count :]
        self.push(items)

    # INDEX -> pops an index and a list / string -> pushes the item at that index
    def op_INDEX(self, frame, arg):
        index = self.pop()
        target = self.pop()
        self.push(target[self.check_index(target, index)])

    # STORE_INDEX -> pops a value -> an index and a list
    # -> changes that item in place so every variable holding the list sees the change
    def op_STORE_INDEX(self, frame, arg):
        value = self.pop()
        index = self.pop()
        target = self.pop()
        if isinstance(target, str):
            self.error("cannot change a character of a string")
        target[self.check_index(target, index)] = value

    # Function that checks an index is a whole number inside the list / string
    # -> returns it if so -> otherwise raises the matching error
    def check_index(self, target, index):
        if not isinstance(target, (list, str)):
            self.error("cannot index {}".format(describe(target)))
        if isinstance(index, bool) or not isinstance(index, int):
            self.error("index must be a whole number, not {}".format(describe(index)))
        if index < 0 or index >= len(target):
            size = len(target)
            noun = "item" if isinstance(target, list) else "character"
            self.error(
                "index {} out of range ({} has {} {}{})".format(
                    index,
                    "list" if isinstance(target, list) else "string",
                    size,
                    noun,
                    "" if size == 1 else "s",
                )
            )
        return index

    # RANGE -> pops the end and the start -> pushes [start, start + 1, ..., end - 1]
    def op_RANGE(self, frame, arg):
        end = self.pop()
        start = self.pop()
        for value in (start, end):
            if isinstance(value, bool) or not isinstance(value, int):
                self.error(
                    "a range needs whole numbers, not {}".format(describe(value))
                )
        self.push(list(range(start, end)))

    # GET_ITER -> pops a list / string -> pushes an iterator over its items
    def op_GET_ITER(self, frame, arg):
        target = self.pop()
        if not isinstance(target, (list, str)):
            self.error("cannot loop over {}".format(describe(target)))
        self.push(iter(target))

    # REPEAT_ITER -> pops a count -> pushes an iterator that runs that many times
    def op_REPEAT_ITER(self, frame, arg):
        count = self.pop()
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            self.error("repeat needs a whole number of times that isn't negative")
        self.push(iter(range(count)))

    # FOR_ITER -> pushes the next item from the iterator
    # -> when it runs out -> pops the iterator and jumps past the loop
    def op_FOR_ITER(self, frame, target):
        item = next(self.stack[-1], FINISHED)
        if item is FINISHED:
            self.pop()
            frame.ip = target
        else:
            self.push(item)

    ## Functions
    # MAKE_FUNCTION -> makes a function value that remembers the scope it was made in
    # -> so it can read outer variables
    def op_MAKE_FUNCTION(self, frame, code):
        self.push(Function(code.name, code.params, code, frame.env))

    # CALL -> arg is (name, argument count, whether the result is used)
    # -> a built-in runs its Python function straight away
    # -> a user function gets its argument count and recursion depth checked
    # -> then a new Frame with a scope where each parameter holds its argument
    def op_CALL(self, frame, arg):
        name, count, used = arg
        args = self.stack[len(self.stack) - count :]
        del self.stack[len(self.stack) - count :]
        func = self.pop()

        if isinstance(func, Builtin):
            too_many = func.max_args is not None and count > func.max_args
            if count < func.min_args or too_many:
                self.error(arity_message(name, func.min_args, func.max_args, count))
            result = func.func(args, self.line, self)
            self.finish_call(result, name, used)
            return

        if not isinstance(func, Function):
            self.error("{} is not a function".format(name))
        if count != len(func.params):
            self.error(arity_message(name, len(func.params), len(func.params), count))
        if len(self.frames) >= MAX_FRAMES:
            self.error("too much recursion")

        env = Env(func.env)
        for param, value in zip(func.params, args):
            env.vars[param] = value
        new_frame = Frame(func.code, env, len(self.stack))
        new_frame.used = used
        new_frame.name = name
        new_frame.call_line = self.line
        self.frames.append(new_frame)

    # RETURN -> pops the return value and ends the frame -> pushes it for the caller
    # -> clears anything the function left on the stack (ex: a loop iterator)
    # -> errors about the result point at the call line -> not the return
    def op_RETURN(self, frame, arg):
        result = self.pop()
        del self.stack[frame.stack_base :]
        self.frames.pop()
        self.line = frame.call_line
        self.finish_call(result, frame.name, frame.used)

    # Function that pushes the result of a call
    # -> using nothing (from a function with no return) is an error
    def finish_call(self, result, name, used):
        if result is NOTHING and used:
            self.error("{} did not return a value".format(name))
        self.push(result)

    ## check
    # CHECK -> pops a condition -> stops with "check failed" if it is false
    def op_CHECK(self, frame, arg):
        if not require_bool(self.pop(), self.line):
            self.error("check failed")


# Function that runs a compiled program
def run(main, units):
    VM(units).run(main)

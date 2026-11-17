"""Pitwall command-line entry point"""
# The purpose of this file is to run the compiler on a .pit file and catch every error.
#
# How it works:
# -> source -> lexer -> parser -> analyser -> optimiser -> code generator -> VM
# -> each phase is its own file in core/ (phase 1 to phase 6)
# -> every error prints as "Error line N: message" with exit code 1 (never a traceback)
#
# Usage:
#   python pitwall.py FILE.pit                       runs a program
#   python pitwall.py FILE.pit --tokens              prints the tokens and stops
#   python pitwall.py FILE.pit --ast                 prints the syntax tree and stops
#   python pitwall.py FILE.pit --bytecode            prints the bytecode and stops
#   python pitwall.py FILE.pit --bytecode --no-opt   the same, with no optimiser

import sys

from core.analyser import analyse
from core.ast_nodes import dump
from core.codegen import format_bytecode, generate
from core.errors import PitwallError
from core.lexer import Lexer
from core.optimiser import optimise
from core.parser import Parser
from core.tokens import format_tokens
from core.units import UnitTable
from core.vm import VM

# the flags pitwall.py accepts
FLAGS = ("--tokens", "--ast", "--bytecode", "--no-opt")
# shown when pitwall.py is run the wrong way
USAGE = "usage: python pitwall.py FILE.pit [--tokens | --ast | --bytecode] [--no-opt]"


# Pipeline class -> runs the compiler phases in order on one piece of source text
# -> keeps the source and the flags given
# -> phase is the part running now (used to find the line for internal errors)
class Pipeline:
    def __init__(self, source, flags):
        self.source = source
        self.flags = flags
        self.phase = None

    # Function that runs each phase in order
    # -> stops early if a dump flag was given (--tokens, --ast or --bytecode)
    def run(self):
        # phase 1 -> lexical analysis
        lexer = Lexer(self.source)
        self.phase = lexer
        tokens = lexer.tokenize()
        if "--tokens" in self.flags:
            print(format_tokens(tokens))
            return

        # phase 2 -> syntax analysis
        parser = Parser(tokens)
        self.phase = parser
        program = parser.parse_program()
        if "--ast" in self.flags:
            print(dump(program))
            return

        # phase 3 -> semantic analysis (also adds unit declarations to the unit table)
        units = UnitTable()
        analyse(program, units)

        # phase 4 -> optimisation (constant folding + dead-code elimination)
        # -> skipped with --no-opt
        if "--no-opt" not in self.flags:
            program = optimise(program, units)

        # phase 5 -> code generation
        main, functions = generate(program)
        if "--bytecode" in self.flags:
            print(format_bytecode(main, functions))
            return

        # phase 6 -> virtual machine (runs the bytecode)
        vm = VM(units)
        self.phase = vm
        vm.run(main)

    # Function that gives a best guess at the line being processed
    # -> only used for internal errors (a bug in Pitwall itself)
    def current_line(self):
        if isinstance(self.phase, Lexer):
            return self.phase.line
        if isinstance(self.phase, Parser):
            return self.phase.peek().line
        if isinstance(self.phase, VM):
            return self.phase.line
        return 1


# Function that reads the command line -> runs the pipeline
# -> returns the exit code (0 = success, 1 = error)
def main(argv):
    files = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]

    # checks for an unknown flag or the wrong number of files -> prints the usage
    for flag in flags:
        if flag not in FLAGS:
            print("Error: unknown option {}\n{}".format(flag, USAGE), file=sys.stderr)
            return 1
    if len(files) != 1:
        print(USAGE, file=sys.stderr)
        return 1

    # reads the source file -> a missing or unreadable file gives a clean error message
    path = files[0]
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except (OSError, UnicodeDecodeError) as e:
        print(
            "Error: cannot read file {} ({})".format(path, e.__class__.__name__),
            file=sys.stderr,
        )
        return 1

    pipeline = Pipeline(source, flags)
    try:
        pipeline.run()
    # an error in the program -> earlier output is flushed so it stays in order
    # -> then "Error line N: message" is printed
    except PitwallError as e:
        sys.stdout.flush()
        print(e, file=sys.stderr)
        return 1
    # a bug in Pitwall itself -> still a clean message -> never a traceback
    except Exception as e:
        sys.stdout.flush()
        print(
            "Error line {}: internal error ({}: {})".format(
                pipeline.current_line(), e.__class__.__name__, e
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

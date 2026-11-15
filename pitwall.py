"""Pitwall command-line entry point"""
# The purpose of this file is to run the compiler pipeline on a .pit file and catch every error.
# source -> lexer -> tokens -> parser -> AST -> semantic analyser -> optimiser -> code generator -> bytecode -> VM -> output
# Every error is printed as a clean "Error line N: message" with exit code 1 -> so the user never sees a Python traceback.
#
# Usage:
#   python pitwall.py FILE.pit              runs a program
#   python pitwall.py FILE.pit --tokens     prints the token stream and stops
#   python pitwall.py FILE.pit --ast        prints the syntax tree and stops
#   python pitwall.py FILE.pit --bytecode   prints the bytecode and stops
#   python pitwall.py FILE.pit --no-opt     turns off the optimiser

import sys

from core.ast_nodes import dump
from core.errors import PitwallError
from core.lexer import Lexer
from core.parser import Parser
from core.tokens import format_tokens

# the flags pitwall.py accepts -> and the message shown when it is run the wrong way
FLAGS = ("--tokens", "--ast", "--bytecode", "--no-opt")

USAGE = "usage: python pitwall.py FILE.pit [--tokens | --ast | --bytecode] [--no-opt]"


# Pipeline class that runs the compiler phases in order on one piece of source text
class Pipeline:
    # stores the source and flags -> phase is the part of the compiler currently running (used to find the line for internal errors)
    def __init__(self, source, flags):
        self.source = source
        self.flags = flags
        self.phase = None

    # runs each phase in order -> stops early if a dump flag was given
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

        # phases 3-6 (semantic analysis, optimisation, code generation and the VM) are next on the build list
        raise PitwallError(
            0,
            "the code generator and VM aren't built yet (use --tokens or --ast for now)",
        )

    # best guess at the line being processed -> used if Pitwall itself hits an unexpected error
    def current_line(self):
        if isinstance(self.phase, Lexer):
            return self.phase.line
        if isinstance(self.phase, Parser):
            return self.phase.peek().line
        return 1


# Function that reads the command line -> runs the pipeline and returns the exit code (0 = success, 1 = error)
def main(argv):
    files = [a for a in argv if not a.startswith("--")]
    flags = [a for a in argv if a.startswith("--")]

    # an unknown flag or the wrong number of files -> prints the usage and stops
    for flag in flags:
        if flag not in FLAGS:
            print("Error: unknown option {}\n{}".format(flag, USAGE), file=sys.stderr)
            return 1
    if len(files) != 1:
        print(USAGE, file=sys.stderr)
        return 1

    # reads the source file -> a missing or unreadable file results in a clean error message
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
    # an error in the user's program -> earlier output is flushed first so it stays in order -> then "Error line N: message" is printed
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

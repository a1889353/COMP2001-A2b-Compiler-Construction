"""Pitwall lexer (phase 1: lexical analysis)"""
# The purpose of this file is to turn the source text of a .pit file into a list of Token objects, ending with an EOF token.
# The current character decides which kind of token is starting -> each reader then acts like a small finite state machine until it reaches the end of the current token.
# It always takes the longest token possible (maximal munch) -> "<=" is one token and "2.7[L/lap]" is one QUANTITY token.
# Newlines end statements so NEWLINE tokens are added -> except inside ( ) or [ ] where the statement isn't finished yet.
#
# Number state machine used by scan_number() -> each row is: state --character--> next state
#   INT       --digit-->       INT        (whole-number digits)
#   INT       --"." + digit--> FRAC       (decimal point)
#   INT       --":"-->         LAP_COLON  (start of a lap time)
#   FRAC      --digit-->       FRAC
#   LAP_COLON --two digits-->  LAP_SECS   (seconds 00-59)
#   LAP_SECS  --"." + digit--> LAP_FRAC
#   LAP_FRAC  --digit-->       LAP_FRAC
#   any other character ends the number (DONE) -> a "[" straight after it then starts a unit (ex: 50[L])
# A "." only continues a number if a digit follows it -> so 0..10 is 0, "..", 10 (a range)

import string

from core import tokens as T
from core.errors import PitwallError
from core.units import Unit, parse_unit_text

# character sets the scanners check against
DIGITS = "0123456789"
NAME_START = string.ascii_letters + "_"
NAME_CHARS = NAME_START + DIGITS

# string escapes -> ex: \n -> newline
ESCAPES = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


# Function that checks for a digit -> also rules out "" (the end of the text) -> which Python counts as "in" every string
def is_digit(ch):
    return ch != "" and ch in DIGITS


# Function that checks a character can be part of a name
def is_name_char(ch):
    return ch != "" and ch in NAME_CHARS


# Function that turns source text into a list of tokens
def tokenize(source):
    return Lexer(source).tokenize()


# Lexer class that scans source text into tokens one character at a time
class Lexer:
    # sets up the scanner -> position in the text, current line, open bracket count (newlines inside ( ) or [ ] are ignored) and the token list
    def __init__(self, source):
        self.src = source
        self.pos = 0
        self.line = 1
        self.depth = 0
        self.tokens = []

    # returns the character offset places ahead -> "" at the end of the text
    def peek(self, offset=0):
        i = self.pos + offset
        return self.src[i] if i < len(self.src) else ""

    # consumes and returns the current character
    def advance(self):
        ch = self.src[self.pos]
        self.pos += 1
        return ch

    # adds a token -> on the current line unless another line is given
    def add(self, kind, text, value=None, unit=None, line=None):
        self.tokens.append(T.Token(kind, text, line or self.line, value, unit))

    # raises a lexer error on the current line
    def error(self, message):
        raise PitwallError(self.line, message)

    # scans the whole source and returns the tokens
    def tokenize(self):
        # the current character decides which reader runs -> whitespace is skipped
        while self.pos < len(self.src):
            ch = self.peek()
            if ch in " \t\r":
                self.advance()
            elif ch == "#":
                self.skip_comment()
            elif ch == "\n":
                self.scan_newline()
            elif ch in DIGITS:
                self.scan_number()
            elif ch in NAME_START:
                self.scan_name()
            elif ch == '"':
                self.scan_string()
            else:
                self.scan_operator()

        # EOF goes on the last tokens line -> so EOF errors point at the right line
        last_line = self.tokens[-1].line if self.tokens else 1
        self.add(T.EOF, "", line=last_line)
        return self.tokens

    # skips comments
    def skip_comment(self):
        while self.pos < len(self.src) and self.peek() != "\n":
            self.advance()

    # reads a newline -> adds a NEWLINE token unless inside brackets or on a blank line
    def scan_newline(self):
        self.advance()
        if self.depth == 0 and self.tokens and self.tokens[-1].kind != T.NEWLINE:
            self.add(T.NEWLINE, "\\n")
        self.line += 1

    # reads a NUMBER, QUANTITY or LAPTIME -> refer to the state machine shown in the header
    def scan_number(self):
        start = self.pos
        state = "INT"

        # runs the state machine until DONE -> each state reads one character and picks the next state
        while state != "DONE":
            ch = self.peek()
            # INT -> whole-number digits
            if state == "INT":
                if is_digit(ch):
                    self.advance()
                elif ch == "." and is_digit(self.peek(1)):
                    self.advance()
                    state = "FRAC"
                elif ch == ":":
                    self.advance()
                    state = "LAP_COLON"
                else:
                    state = "DONE"
            # FRAC -> digits after the decimal point
            elif state == "FRAC":
                if is_digit(ch):
                    self.advance()
                else:
                    state = "DONE"
            # LAP_COLON -> needs exactly two digits of seconds (ex: 1:32)
            elif state == "LAP_COLON":
                if is_digit(self.peek()) and is_digit(self.peek(1)):
                    self.advance()
                    self.advance()
                    state = "LAP_SECS"
                else:
                    self.error("invalid lap time")
            # LAP_SECS -> a third digit is an error, "." + digit starts the fraction
            elif state == "LAP_SECS":
                if is_digit(ch):
                    self.error("invalid lap time")
                elif ch == "." and is_digit(self.peek(1)):
                    self.advance()
                    state = "LAP_FRAC"
                else:
                    state = "DONE"
            # LAP_FRAC -> digits after the lap time decimal point
            elif state == "LAP_FRAC":
                if is_digit(ch):
                    self.advance()
                else:
                    state = "DONE"

        text = self.src[start : self.pos]

        # checks for a lap time -> converts it to seconds (60 or more seconds is an error)
        if ":" in text:
            minutes_text, seconds_text = text.split(":")
            seconds = float(seconds_text)
            if seconds >= 60:
                self.error("invalid lap time")
            # round() removes float noise (ex: 92.31800000000001 -> 92.318)
            value = round(int(minutes_text) * 60 + seconds, 9)
            self.add(T.LAPTIME, text, value, Unit({"s": 1}, "s"))
            return

        # plain number -> int if there's no "." -> otherwise float
        value = float(text) if "." in text else int(text)

        # checks for a "[" straight after the number -> reads it all as one QUANTITY token
        if self.peek() == "[":
            unit_text = self.scan_unit_bracket()
            unit = parse_unit_text(unit_text, self.line)
            self.add(T.QUANTITY, text + "[" + unit_text + "]", value, unit)
            return

        self.add(T.NUMBER, text, value)

    # reads the unit text inside [ ] after a number -> a missing "]" -> results in an error
    def scan_unit_bracket(self):
        self.advance()
        start = self.pos
        while self.peek() != "]":
            # checks for the end of the line or file before "]" -> raises an error
            if self.peek() in ("", "\n"):
                self.error("unclosed unit bracket (missing ])")
            self.advance()
        text = self.src[start : self.pos]
        self.advance()
        return text

    # reads a name -> keywords get their own kind (ex: WHILE) -> anything else is a NAME
    def scan_name(self):
        start = self.pos
        while is_name_char(self.peek()):
            self.advance()
        text = self.src[start : self.pos]
        self.add(T.KEYWORDS.get(text, T.NAME), text)

    # reads a string with escapes defined earlier as (\n \t \" \\)
    def scan_string(self):
        start = self.pos
        self.advance()
        chars = []
        while True:
            ch = self.peek()
            # checks for the end of the line/file before the closing quote -> raises an unterminated string error
            if ch in ("", "\n"):
                self.error("unterminated string")
            self.advance()
            if ch == '"':
                break
            # checks for a backslash -> swaps the escape for its real character -> unknown string escapes are an error
            if ch == "\\":
                esc = self.peek()
                if esc == "" or esc not in ESCAPES:
                    self.error("unknown escape \\{} in string".format(esc))
                self.advance()
                chars.append(ESCAPES[esc])
            else:
                chars.append(ch)
        self.add(T.STRING, self.src[start : self.pos], "".join(chars))

    # reads an operator -> two character operators are tried first (follows maximal munch)
    def scan_operator(self):
        two = self.src[self.pos : self.pos + 2]
        # checks for a two character operator (ex: <=) -> adds it as one token
        if two in T.TWO_CHAR_OPERATORS:
            self.pos += 2
            self.add(T.TWO_CHAR_OPERATORS[two], two)
            return

        ch = self.peek()
        # checks for a one character operator -> tracks bracket depth for newline handling
        if ch in T.ONE_CHAR_OPERATORS:
            self.advance()
            if ch in "([":
                self.depth += 1
            elif ch in ")]" and self.depth > 0:
                self.depth -= 1
            self.add(T.ONE_CHAR_OPERATORS[ch], ch)
            return

        self.error("unexpected character '{}'".format(ch))

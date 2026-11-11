"""Pitwall tokens -> shared among the lexer and parser"""
# The purpose of this file is to define the token class, token kinds, keyword and operator tables.
# This lets the lexer turn source text into a list of Token objects, which the parser then reads.

from core.values import format_number, quote_string

# Token kind definitions -> each kind is kept as a string which keeps the token dump readable as it prints the kind name directly
NUMBER = "NUMBER"  # 42, 3.5
QUANTITY = "QUANTITY"  # a number with a unit attached: 50[L], 2.7[L/lap]
LAPTIME = "LAPTIME"  # 1:32.318 (stored as 92.318 seconds)
STRING = "STRING"  # "GT3"
NAME = "NAME"  # identifiers: fuel, race_laps, print
NEWLINE = "NEWLINE"  # end of a line
EOF = "EOF"  # end of the file

# Reserved keyword list (22)
KEYWORD_LIST = [
    "var",
    "let",
    "fn",
    "return",
    "if",
    "elif",
    "else",
    "while",
    "for",
    "in",
    "repeat",
    "times",
    "break",
    "continue",
    "unit",
    "to",
    "check",
    "and",
    "or",
    "not",
    "true",
    "false",
]
KEYWORDS = {word: word.upper() for word in KEYWORD_LIST}

# Operators and punctuation -> the two-char table is checked first (maximal munch: "<=" beats "<" then "=")
TWO_CHAR_OPERATORS = {
    "==": "EQ",
    "!=": "NE",
    "<=": "LE",
    ">=": "GE",
    "+=": "PLUS_ASSIGN",
    "-=": "MINUS_ASSIGN",
    "..": "DOTDOT",
}

ONE_CHAR_OPERATORS = {
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "%": "PERCENT",
    "<": "LT",
    ">": "GT",
    "=": "ASSIGN",
    "(": "LPAREN",
    ")": "RPAREN",
    "[": "LBRACKET",
    "]": "RBRACKET",
    "{": "LBRACE",
    "}": "RBRACE",
    ",": "COMMA",
    ";": "SEMI",
    "^": "CARET",  # only meaningful when inside a unit (ex: [m/s^2])
}


# Class of tokens produced by the lexer
class Token:
    def __init__(self, kind, text, line, value=None, unit=None):
        self.kind = kind  # token kind (ex: NUMBER, NAME, "WHILE", "PLUS")
        self.text = text  # source text of the token (ex: 2.7[L/lap])
        self.line = line  # source line it appeared on (used in error messages)
        self.value = value  # Python value for literals (ex: int/float for numbers, seconds for lap times and decoded text for strings)
        self.unit = unit  # the unit (ex: L/lap) for QUANTITY and LAPTIME tokens -> otherwise None

    # Formats how a token shows up when printed while debugging (ex: Token(NAME, 'fuel', line 3))
    def __repr__(self):
        return "Token({}, {!r}, line {})".format(self.kind, self.text, self.line)

    # Short description for parser error messages (ex: "unexpected token ')'")
    def describe(self):
        if self.kind == NEWLINE:
            return "end of line"
        if self.kind == EOF:
            return "end of file"
        return "token '{}'".format(self.text)


# Formats and returns the token stream as a table
def format_tokens(tokens):
    lines = ["line  kind          value"]
    for token in tokens:
        if token.kind == QUANTITY:
            shown = "{} [{}]".format(format_number(token.value), token.unit)
        elif token.kind == LAPTIME:
            shown = "{}  = {} s".format(token.text, format_number(token.value))
        elif token.kind == STRING:
            shown = quote_string(token.value)
        elif token.kind == NEWLINE:
            shown = "\\n"
        elif token.kind == EOF:
            shown = ""
        else:
            shown = token.text
        lines.append("{:>4}  {:<12}  {}".format(token.line, token.kind, shown).rstrip())
    return "\n".join(lines)

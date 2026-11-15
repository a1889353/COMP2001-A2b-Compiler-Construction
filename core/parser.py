"""Pitwall parser (phase 2: syntax analysis)"""
# The purpose of this file is to turn the list of tokens from the lexer into an AST (a Program node from ast_nodes.py).
# It's a recursive descent parser -> one method per kind of statement and one per precedence level, each calling the methods for the parts inside it.
# It stops at the first syntax error and reports the line number it happened on.
#
# Expression precedence (lowest first) -> each level calls the next one down -> so higher precedence operators end up deeper in the tree
#   parse_or             or               (left associative)
#   parse_and            and              (left associative)
#   parse_not            not              (prefix)
#   parse_compare        == != < <= > >=  (no chaining)
#   parse_range          ..               (no chaining)
#   parse_convert        x to [unit]      (postfix)
#   parse_additive       + -              (left associative)
#   parse_multiplicative * / %            (left associative)
#   parse_unary          -x               (prefix)
#   parse_postfix        f(x)  xs[i]
#   parse_primary        literals, names, ( ), [ ]
# This is why track / pace to [km/h] parses as (track / pace) to [km/h] -> "to" sits above "/" in the list.

from core import ast_nodes as A
from core import tokens as T
from core.errors import PitwallError
from core.units import parse_unit_text

# token kinds that end a simple statement
STATEMENT_ENDS = (T.NEWLINE, "SEMI", "RBRACE", T.EOF)

# comparison operator token kinds
COMPARISONS = ("EQ", "NE", "LT", "LE", "GT", "GE")

# statements ending in "}" -> they don't need a newline or ";" after them
COMPOUND = (A.If, A.While, A.ForIn, A.Repeat, A.FnDecl, A.Block)


# Function that turns a list of tokens into a Program AST
def parse(tokens):
    return Parser(tokens).parse_program()


# Parser class -> the recursive descent parser for Pitwall
class Parser:
    # sets up the parser -> the token list and the position of the current token
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    ## TOKEN HELPERS
    # returns the current token without moving past it
    def peek(self):
        return self.tokens[self.pos]

    # checks if the current token is one of the given kinds
    def at(self, *kinds):
        return self.peek().kind in kinds

    # moves past the current token and returns it -> never moves past EOF
    def advance(self):
        tok = self.tokens[self.pos]
        if tok.kind != T.EOF:
            self.pos += 1
        return tok

    # moves past a token of the given kind -> otherwise raises "expected <what>"
    def expect(self, kind, what):
        if self.at(kind):
            return self.advance()
        raise PitwallError(self.peek().line, "expected " + what)

    # raises an error as the current token can't appear here
    def unexpected(self):
        tok = self.peek()
        raise PitwallError(tok.line, "unexpected " + tok.describe())

    # skips newlines and ";" -> blank lines are allowed anywhere
    def skip_separators(self):
        while self.at(T.NEWLINE, "SEMI"):
            self.advance()

    ## STATEMENTS
    # parses the whole program -> statements until the end of the file
    def parse_program(self):
        try:
            body = []
            self.skip_separators()
            while not self.at(T.EOF):
                body.append(self.parse_statement())
                self.skip_separators()
            return A.Program(body)
        # code nested hundreds deep -> a clean error instead of a Python crash
        except RecursionError:
            raise PitwallError(self.peek().line, "program is nested too deeply")

    # parses one statement -> a simple statement must then end properly
    def parse_statement(self):
        stmt = self.parse_statement_body()
        if not isinstance(stmt, COMPOUND):
            self.end_statement()
        return stmt

    # checks a simple statement ends at a newline, ";", "}" or the end of the file
    def end_statement(self):
        if self.at(T.NEWLINE, "SEMI"):
            self.advance()
        elif not self.at("RBRACE", T.EOF):
            tok = self.peek()
            raise PitwallError(
                tok.line, "expected a new line or ; before {}".format(tok.describe())
            )

    # looks at the first token to pick the right statement parser
    def parse_statement_body(self):
        kind = self.peek().kind
        if kind in ("VAR", "LET"):
            return self.parse_declare()
        if kind == "IF":
            return self.parse_if()
        if kind == "WHILE":
            return self.parse_while()
        if kind == "FOR":
            return self.parse_for()
        if kind == "REPEAT":
            return self.parse_repeat()
        if kind == "BREAK":
            return A.Break(self.advance().line)
        if kind == "CONTINUE":
            return A.Continue(self.advance().line)
        if kind == "FN":
            return self.parse_fn()
        if kind == "RETURN":
            return self.parse_return()
        if kind == "UNIT":
            return self.parse_unit_decl()
        if kind == "CHECK":
            line = self.advance().line
            return A.Check(self.parse_expression(), line)
        if kind == "LBRACE":
            return self.parse_block()
        # checks for an elif / else with no if before it -> raises an error
        if kind in ("ELIF", "ELSE"):
            raise PitwallError(
                self.peek().line, "{} without a matching if".format(self.peek().text)
            )
        return self.parse_expression_statement()

    # parses a { } block -> each block is a new scope
    def parse_block(self):
        open_tok = self.expect("LBRACE", "{")
        body = []
        self.skip_separators()
        while not self.at("RBRACE"):
            # end of file before the "}" -> the error names the line of the "{"
            if self.at(T.EOF):
                raise PitwallError(
                    self.peek().line,
                    "unexpected end of file (the {{ on line {} is never closed)".format(
                        open_tok.line
                    ),
                )
            body.append(self.parse_statement())
            self.skip_separators()
        self.advance()
        return A.Block(body, open_tok.line)

    # parses a var / let declaration
    def parse_declare(self):
        keyword = self.advance()
        name = self.expect(T.NAME, "a name after " + keyword.text).text
        self.expect("ASSIGN", "= after " + name)
        value = self.parse_expression()
        return A.Declare(keyword.text, name, value, keyword.line)

    # parses an if statement with any elif / else branches
    def parse_if(self):
        line = self.advance().line
        cond = self.parse_expression()
        branches = [(cond, self.parse_block())]
        else_body = None

        # elif / else can start on the line after the "}" -> so newlines are skipped first
        while True:
            saved = self.pos
            while self.at(T.NEWLINE):
                self.advance()
            if self.at("ELIF"):
                self.advance()
                cond = self.parse_expression()
                branches.append((cond, self.parse_block()))
            elif self.at("ELSE"):
                self.advance()
                if self.at("IF"):
                    raise PitwallError(
                        self.peek().line, "expected { (write elif, not else if)"
                    )
                else_body = self.parse_block()
                break
            # no elif / else -> puts the position back to before the skipped newlines
            else:
                self.pos = saved
                break
        return A.If(branches, else_body, line)

    # parses a while loop
    def parse_while(self):
        line = self.advance().line
        cond = self.parse_expression()
        return A.While(cond, self.parse_block(), line)

    # parses a for loop over a list or a range
    def parse_for(self):
        line = self.advance().line
        var = self.expect(T.NAME, "a loop variable name after for").text
        self.expect("IN", "in")
        iterable = self.parse_expression()
        return A.ForIn(var, iterable, self.parse_block(), line)

    # parses a repeat n times loop
    def parse_repeat(self):
        line = self.advance().line
        count = self.parse_expression()
        self.expect("TIMES", "times")
        return A.Repeat(count, self.parse_block(), line)

    # parses a function declaration
    def parse_fn(self):
        line = self.advance().line
        name = self.expect(T.NAME, "a function name after fn").text
        self.expect("LPAREN", "( after " + name)
        params = []
        if not self.at("RPAREN"):
            while True:
                params.append(self.expect(T.NAME, "a parameter name").text)
                if not self.at("COMMA"):
                    break
                self.advance()
        self.expect("RPAREN", ")")
        return A.FnDecl(name, params, self.parse_block(), line)

    # parses a return -> with or without a value
    def parse_return(self):
        line = self.advance().line
        if self.at(*STATEMENT_ENDS):
            return A.Return(None, line)
        return A.Return(self.parse_expression(), line)

    # parses a unit declaration (ex: unit stint = 25 lap or unit stint = 25[lap])
    def parse_unit_decl(self):
        line = self.advance().line
        name = self.expect(T.NAME, "a unit name after unit").text
        self.expect("ASSIGN", "= after " + name)
        # 25[lap] -> the lexer has already read the unit
        if self.at(T.QUANTITY):
            tok = self.advance()
            return A.UnitDecl(name, tok.value, tok.unit, line)
        if not self.at(T.NUMBER):
            raise PitwallError(
                self.peek().line, "expected a number, e.g. unit stint = 25 lap"
            )
        scale = self.advance().value
        unit = self.parse_unit_tokens(STATEMENT_ENDS, "a unit after the number")
        return A.UnitDecl(name, scale, unit, line)

    # parses an assignment (x = 1, x += 1, xs[i] = 1) or an expression used as a statement
    def parse_expression_statement(self):
        line = self.peek().line
        expr = self.parse_expression()

        # checks the left side of an assignment is a name or a list item
        if self.at("ASSIGN", "PLUS_ASSIGN", "MINUS_ASSIGN"):
            op_tok = self.advance()
            value = self.parse_expression()
            if isinstance(expr, A.Name):
                return A.Assign(expr.name, op_tok.text, value, line)
            # list items only allow plain "="
            if isinstance(expr, A.Index):
                if op_tok.text != "=":
                    raise PitwallError(
                        op_tok.line, "{} only works on a variable".format(op_tok.text)
                    )
                return A.IndexAssign(expr.target, expr.index, value, line)
            raise PitwallError(
                op_tok.line, "can only assign to a variable or a list item"
            )

        return A.ExprStmt(expr, line)

    ## EXPRESSIONS (one method per precedence level -> lowest first)
    # entry point for any expression
    def parse_expression(self):
        return self.parse_or()

    # parses or
    def parse_or(self):
        left = self.parse_and()
        while self.at("OR"):
            line = self.advance().line
            left = A.Logical("or", left, self.parse_and(), line)
        return left

    # parses and
    def parse_and(self):
        left = self.parse_not()
        while self.at("AND"):
            line = self.advance().line
            left = A.Logical("and", left, self.parse_not(), line)
        return left

    # parses not
    def parse_not(self):
        if self.at("NOT"):
            line = self.advance().line
            return A.Unary("not", self.parse_not(), line)
        return self.parse_compare()

    # parses a single comparison -> chaining (a < b < c) is an error as it would compare true / false with a number
    def parse_compare(self):
        left = self.parse_range()
        if self.at(*COMPARISONS):
            op_tok = self.advance()
            right = self.parse_range()
            if self.at(*COMPARISONS):
                raise PitwallError(self.peek().line, "comparisons cannot be chained")
            return A.BinOp(op_tok.text, left, right, op_tok.line)
        return left

    # parses a range (start..end) -> can't be chained
    def parse_range(self):
        left = self.parse_convert()
        if self.at("DOTDOT"):
            line = self.advance().line
            right = self.parse_convert()
            if self.at("DOTDOT"):
                raise PitwallError(self.peek().line, "ranges cannot be chained")
            return A.Range(left, right, line)
        return left

    # parses unit conversions (ex: x to [km/h])
    def parse_convert(self):
        expr = self.parse_additive()
        while self.at("TO"):
            line = self.advance().line
            self.expect("LBRACKET", "[ after to, e.g. x to [km/h]")
            unit = self.parse_unit_tokens(("RBRACKET",), "a unit inside [ ]")
            self.expect("RBRACKET", "]")
            expr = A.Convert(expr, unit, line)
        return expr

    # parses + and -
    def parse_additive(self):
        left = self.parse_multiplicative()
        while self.at("PLUS", "MINUS"):
            op_tok = self.advance()
            left = A.BinOp(op_tok.text, left, self.parse_multiplicative(), op_tok.line)
        return left

    # parses *, / and %
    def parse_multiplicative(self):
        left = self.parse_unary()
        while self.at("STAR", "SLASH", "PERCENT"):
            op_tok = self.advance()
            left = A.BinOp(op_tok.text, left, self.parse_unary(), op_tok.line)
        return left

    # parses a leading minus (ex: -x)
    def parse_unary(self):
        if self.at("MINUS"):
            line = self.advance().line
            return A.Unary("-", self.parse_unary(), line)
        return self.parse_postfix()

    # parses calls and indexing after a value (ex: f(x), xs[i])
    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            # calls are only allowed straight after a name
            if self.at("LPAREN"):
                if not isinstance(expr, A.Name):
                    raise PitwallError(
                        self.peek().line, "only named functions can be called"
                    )
                self.advance()
                args = self.parse_comma_list("RPAREN", ")")
                expr = A.Call(expr.name, args, expr.line)
            elif self.at("LBRACKET"):
                line = self.advance().line
                index = self.parse_expression()
                self.expect("RBRACKET", "]")
                expr = A.Index(expr, index, line)
            else:
                return expr

    # parses a single value -> literals, names, ( ) groups and [ ] lists
    def parse_primary(self):
        tok = self.peek()
        if tok.kind == T.NUMBER:
            self.advance()
            return A.Number(tok.value, None, tok.line)
        if tok.kind in (T.QUANTITY, T.LAPTIME):
            self.advance()
            return A.Number(tok.value, tok.unit, tok.line)
        if tok.kind == T.STRING:
            self.advance()
            return A.String(tok.value, tok.line)
        if tok.kind in ("TRUE", "FALSE"):
            self.advance()
            return A.Bool(tok.kind == "TRUE", tok.line)
        if tok.kind == T.NAME:
            self.advance()
            return A.Name(tok.text, tok.line)
        if tok.kind == "LPAREN":
            self.advance()
            expr = self.parse_expression()
            self.expect("RPAREN", ")")
            return expr
        if tok.kind == "LBRACKET":
            self.advance()
            return A.ListLit(self.parse_comma_list("RBRACKET", "]"), tok.line)
        self.unexpected()

    ## SHARED HELPERS
    # reads expressions separated by commas up to the closing ) or ] -> used for call arguments & lists
    def parse_comma_list(self, close_kind, close_text):
        items = []
        while not self.at(close_kind):
            items.append(self.parse_expression())
            if not self.at("COMMA"):
                break
            self.advance()
        self.expect(close_kind, close_text)
        return items

    # reads the tokens of a unit after "to [" or in a unit declaration -> joins their text so parse_unit_text checks it as 50[L]
    def parse_unit_tokens(self, stop_kinds, what):
        line = self.peek().line
        parts = []
        while not self.at(*stop_kinds):
            tok = self.peek()
            ok = tok.text.isidentifier() or tok.kind in (
                T.NUMBER,
                "STAR",
                "SLASH",
                "CARET",
                "MINUS",
            )
            # checks each token can be part of a unit
            if tok.kind in (T.EOF, T.NEWLINE) or not ok:
                if parts:
                    closing = "]" if "RBRACKET" in stop_kinds else "end of unit"
                    raise PitwallError(tok.line, "expected " + closing)
                raise PitwallError(tok.line, "expected " + what)
            parts.append(self.advance().text)
        if not parts:
            raise PitwallError(self.peek().line, "expected " + what)
        return parse_unit_text("".join(parts), line)

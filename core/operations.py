"""Pitwall operations -> arithmetic, comparisons and conversions with the unit rules"""
# The purpose of this file is to apply Pitwall's type and unit rules to values.
# Both the optimiser and the VM use these functions -> so a result worked out before running always matches the result during run time.
# Units must match exactly for + - % and comparisons, * and / combine units, and "to" converts between units that share the same dimensions.

from core.errors import PitwallError
from core.units import divide, multiply, unit_name
from core.values import Quantity, describe

# verbs used in error messages
# (ex output: cannot add L and s)
VERBS = {
    "+": "add",
    "-": "subtract",
    "*": "multiply",
    "/": "divide",
    "%": "use % on",
    "==": "compare",
    "!=": "compare",
    "<": "compare",
    "<=": "compare",
    ">": "compare",
    ">=": "compare",
}

COMPARISONS = ("==", "!=", "<", "<=", ">", ">=")


# Function that checks if a value is a number -> a plain int / float or a Quantity
def is_number(value):
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float, Quantity))


# Function that splits a number into (value, unit) -> unit is None for a plain number
def split_number(value):
    if isinstance(value, Quantity):
        return value.value, value.unit
    return value, None


# Function that builds a number from a value and a unit -> a Quantity if there's a unit -> otherwise plain number
def make_number(value, unit):
    return value if unit is None else Quantity(value, unit)


# Function that checks that the two units are identical -> two plain numbers also count as identical
def same_unit(a, b):
    if a is None or b is None:
        return a is None and b is None
    return a.same_as(b)


# Function that checks a value is true or false -> anything else results in an error
def require_bool(value, line):
    if not isinstance(value, bool):
        raise PitwallError(line, "condition must be true or false")
    return value


# Function that compares two values with each comparison operator -> returns true or false
def compare(op, a, b):
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    return a >= b


# Function that applies a binary operator (ex: +, *, <) to two values -> raises an error if the types/units dont fit
def binary_op(op, left, right, line):
    # checks for two strings -> + joins them -> comparisons compare them in alphabetical order
    if isinstance(left, str) and isinstance(right, str):
        if op == "+":
            return left + right
        if op in COMPARISONS:
            return compare(op, left, right)

    # checks for == / != on two values that aren't both numbers -> their types must match (ex: two lists, two bools)
    if op in ("==", "!=") and not (is_number(left) and is_number(right)):
        if describe(left) != describe(right):
            raise PitwallError(
                line, "cannot compare {} and {}".format(describe(left), describe(right))
            )
        return compare(op, left, right)

    # every other operation needs two numbers -> anything else is an error ->
    # (ex output: cannot add a string and a number)
    if not (is_number(left) and is_number(right)):
        raise PitwallError(
            line,
            "cannot {} {} and {}".format(VERBS[op], describe(left), describe(right)),
        )
    a, unit_a = split_number(left)
    b, unit_b = split_number(right)

    # checks for * or / -> the units combine (powers are added or subtracted depending on the operation)
    if op == "*":
        return make_number(a * b, multiply(unit_a, unit_b))
    if op == "/":
        if b == 0:
            raise PitwallError(line, "division by zero")
        return make_number(a / b, divide(unit_a, unit_b))

    # + - % and comparisons -> the units must be identical -> without any silent conversions
    if not same_unit(unit_a, unit_b):
        raise PitwallError(
            line,
            "cannot {} {} and {}".format(
                VERBS[op], unit_name(unit_a), unit_name(unit_b)
            ),
        )
    if op == "+":
        return make_number(a + b, unit_a)
    if op == "-":
        return make_number(a - b, unit_a)
    if op == "%":
        if b == 0:
            raise PitwallError(line, "division by zero")
        return make_number(a % b, unit_a)
    return compare(op, a, b)


# Function that applies a unary operator (- or not) to a value
def unary_op(op, value, line):
    # checks for not -> the value must be true or false
    if op == "not":
        return not require_bool(value, line)
    # for - -> only numbers can be negated and the unit stays the same
    if not is_number(value):
        raise PitwallError(line, "cannot negate {}".format(describe(value)))
    number, unit = split_number(value)
    return make_number(-number, unit)


# Function that converts a number to another unit (the "to" operator) -> the result will always be a float with a new unit attached
def convert(value, unit, line, table):
    if not is_number(value):
        raise PitwallError(
            line, "cannot convert {} to {}".format(describe(value), unit)
        )
    number, from_unit = split_number(value)
    return Quantity(table.convert(number, from_unit, unit, line), unit)

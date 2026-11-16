"""Pitwall built-in functions"""
# The purpose of this file is to implement the built-in functions -> print, input, len, push, round, ceil, num and laptime.
# Each one takes (args, line, vm) -> the list of argument values -> the line of the call (for errors) and the VM (for the unit table).
# BUILTINS maps each name to a Builtin with the number of arguments it accepts -> the semantic analyser then uses this to check calls before running any code.

import math
import sys
from decimal import ROUND_HALF_UP, Decimal

from core.errors import PitwallError
from core.operations import is_number, make_number, split_number
from core.units import Unit
from core.values import NOTHING, Builtin, describe, format_value

SECONDS = Unit({"s": 1}, "s")


# prints the arguments separated by spaces -> then a newline
def builtin_print(args, line, vm):
    print(" ".join(format_value(arg) for arg in args))
    return NOTHING


# prints the prompt (no newline) and returns the line the user types as a string
def builtin_input(args, line, vm):
    if args:
        if not isinstance(args[0], str):
            raise PitwallError(line, "input needs a string prompt")
        print(args[0], end="", flush=True)
    text = sys.stdin.readline()
    return text.rstrip("\r\n")


# returns the number of items in a list or characters in a string
def builtin_len(args, line, vm):
    value = args[0]
    if not isinstance(value, (list, str)):
        raise PitwallError(
            line, "len needs a list or a string, not {}".format(describe(value))
        )
    return len(value)


# adds a value to the end of a list -> updates the list in place -> so the change is seen everywhere its used
def builtin_push(args, line, vm):
    target, value = args
    if not isinstance(target, list):
        raise PitwallError(line, "push needs a list, not {}".format(describe(target)))
    target.append(value)
    return NOTHING


# rounds a number the way you would by hand (0.5 rounds up) -> keeps the unit -> round(x) results in an integer value
def builtin_round(args, line, vm):
    value = args[0]
    places = args[1] if len(args) == 2 else 0
    if not is_number(value):
        raise PitwallError(line, "round needs a number, not {}".format(describe(value)))
    # checks the number of decimal places is a whole number from 0 up -> otherwise an error
    if isinstance(places, bool) or not isinstance(places, int) or places < 0:
        raise PitwallError(line, "round needs a whole number of decimal places")
    number, unit = split_number(value)
    # Decimal(repr(...)) rounds the number as its written (ex: 2.675 -> 2.68)
    rounded = Decimal(repr(number)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)
    result = int(rounded) if places == 0 else float(rounded)
    return make_number(result, unit)


# rounds a number up to the next whole number -> keeps the unit and gives an integer value
def builtin_ceil(args, line, vm):
    value = args[0]
    if not is_number(value):
        raise PitwallError(line, "ceil needs a number, not {}".format(describe(value)))
    number, unit = split_number(value)
    return make_number(math.ceil(number), unit)


# turns a string into an int or float (ex: "2.5" -> 2.5) -> raises an error if the entered text is not a number
def builtin_num(args, line, vm):
    text = args[0]
    if not isinstance(text, str):
        raise PitwallError(line, "num needs a string, not {}".format(describe(text)))
    cleaned = text.strip()
    try:
        return int(cleaned)
    except ValueError:
        pass
    try:
        return float(cleaned)
    except ValueError:
        raise PitwallError(line, 'cannot turn "{}" into a number'.format(text))


# formats a time as a lap time m:ss.sss (ex: 92.318[s] -> 1:32.318)
def builtin_laptime(args, line, vm):
    value = args[0]
    # checks the value is a number with a unit -> a plain number has no time unit attached
    if not is_number(value) or split_number(value)[1] is None:
        raise PitwallError(line, "laptime needs a time (ex: 92.318[s])")
    number, unit = split_number(value)
    # converts the time to seconds -> raises an error if the supplied unit isnt a time
    try:
        seconds = vm.units.convert(number, unit, SECONDS, line)
    except PitwallError:
        raise PitwallError(line, "laptime needs a time, not {}".format(unit))
    if seconds < 0:
        raise PitwallError(line, "laptime needs a time that isn't negative")
    # works in whole milliseconds so 59.9996 s rounds to 1:00.000 rather than 0:60.000
    millis = int(
        Decimal(repr(seconds)).quantize(Decimal("0.001"), ROUND_HALF_UP) * 1000
    )
    minutes, millis = divmod(millis, 60000)
    return "{}:{:06.3f}".format(minutes, millis / 1000)


# every built-in function -> name: Builtin(name, function, min args, max args) ->
# None means the function can take any number of arguments
BUILTINS = {
    "print": Builtin("print", builtin_print, 0, None),
    "input": Builtin("input", builtin_input, 0, 1),
    "len": Builtin("len", builtin_len, 1, 1),
    "push": Builtin("push", builtin_push, 2, 2),
    "round": Builtin("round", builtin_round, 1, 2),
    "ceil": Builtin("ceil", builtin_ceil, 1, 1),
    "num": Builtin("num", builtin_num, 1, 1),
    "laptime": Builtin("laptime", builtin_laptime, 1, 1),
}


# Function that formats the correct error message for a wrong number of arguments
# (ex output: round expects 1 or 2 arguments but got 3)
def arity_message(name, min_args, max_args, got):
    if max_args == min_args:
        expected = "{} argument{}".format(min_args, "" if min_args == 1 else "s")
    elif max_args is None:
        expected = "at least {} argument{}".format(
            min_args, "" if min_args == 1 else "s"
        )
    else:
        expected = (
            "{} or {} arguments".format(min_args, max_args)
            if max_args == min_args + 1
            else "{} to {} arguments".format(min_args, max_args)
        )
    return "{} expects {} but got {}".format(name, expected, got)

"""Pitwall value formatting"""
# This controls how Pitwall displays its values. For now the implementation holds two helpers that the token and AST dumps rely on.
# The final implementation will contain the run-time Quantity type and the full print() formatting, once the VM is added.


# Formatting rules for Pitwall
def format_number(x):
    if isinstance(x, int):  # Ints get printed as they are written ex: 42.
        return str(x)
    return repr(round(x, 9))  # Floats are rounded to 9 decimal places ex: 82.7 or 82.0


# Wraps text in quotation marks and puts its escapes back (ex: FL -> "FL")
# Used when a string is shown inside a list or in an AST/token dump.
def quote_string(text):
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return '"' + escaped + '"'


# Quantity class -> a number with a unit attached (ex: 50[L] is Quantity(50, L))
# plain numbers stay as Python ints/floats -> so only numbers with a unit use this class
class Quantity:
    # value is an int or float -> unit is a units.Unit
    def __init__(self, value, unit):
        self.value = value
        self.unit = unit

    # two quantities are equal if their values and units match -> used for comparing lists
    def __eq__(self, other):
        return (
            isinstance(other, Quantity)
            and self.value == other.value
            and self.unit.same_as(other.unit)
        )

    def __repr__(self):
        return "Quantity({}, {})".format(self.value, self.unit)


# Nothing class -> the value a function gives back when it has no return value (using it results in an error)
class Nothing:
    def __repr__(self):
        return "nothing"


NOTHING = Nothing()


# Function class -> a user function made by fn -> plus the scope it was defined in so it can read outer variables
class Function:
    # params are the parameter names -> code is the compiled bytecode -> env is the scope the function was defined in
    def __init__(self, name, params, code, env):
        self.name = name
        self.params = params
        self.code = code
        self.env = env


# Builtin class -> a built-in function (ex: print) with the number of arguments it accepts
class Builtin:
    # func is the Python function that does the work -> max_args of None means no limit (print)
    def __init__(self, name, func, min_args, max_args):
        self.name = name
        self.func = func
        self.min_args = min_args
        self.max_args = max_args


# Function that describes a values type for error messages
def describe(value):
    if isinstance(value, bool):
        return "true/false"
    if isinstance(value, (int, float, Quantity)):
        return "a number"
    if isinstance(value, str):
        return "a string"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, (Function, Builtin)):
        return "a function"
    return "nothing"


# Function that formats a value the way print() shows it -> strings inside a list are shown in quotes
def format_value(value, in_list=False):
    # checks for true / false first -> in Python a bool also counts as an int
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return format_number(value)
    if isinstance(value, Quantity):
        return format_number(value.value) + " " + str(value.unit)
    if isinstance(value, str):
        return quote_string(value) if in_list else value
    if isinstance(value, list):
        return "[" + ", ".join(format_value(item, True) for item in value) + "]"
    if isinstance(value, Function):
        return "<fn {}>".format(value.name)
    if isinstance(value, Builtin):
        return "<built-in {}>".format(value.name)
    return "nothing"

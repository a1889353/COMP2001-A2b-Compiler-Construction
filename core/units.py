"""Pitwall units of measure"""
# The purpose of this file is to define how units are stored, combined, cancelled and converted.
# Each unit is stored as a dictionary of name -> power (ex: L/lap -> {"L": 1, "lap": -1}).
# Units only cancel when their names match (min and s never cancel) -> converting between scales is done with 'to', using the UnitTable.
# The UnitTable caches every unit it works out, so each one is only resolved once, which is one of the optimisations promised in Part A's plan.

import re

from core.errors import PitwallError

# Regexes for unit names and power values
NAME_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
POWER_PATTERN = re.compile(r"-?[0-9]+")


# Function adds a power to a units total -> remove unit if it cancels out
def add_power(powers, name, power):
    total = powers.get(name, 0) + power

    # checks if total is 0 -> unit is cancelled -> remove from dictionary
    if total == 0:
        powers.pop(name, None)
    else:
        powers[name] = total  # otherwise store the new total


# Function to covert a powers dictionary to text -> ex: {"m": 1, "s": -2} -> m/s^2
def format_powers(powers):
    top = []  # units with postive powers
    bottom = []  # units with negative powers

    # loops over every unit and sorts it into positive and negative powers
    for name, power in powers.items():
        if power > 0:
            top.append(name if power == 1 else "{}^{}".format(name, power))
        else:
            bottom.append(name if power == -1 else "{}^{}".format(name, -power))

    # joins the top units with "*" or uses "1" if there are none
    top_text = "*".join(top) if top else "1"

    # checks how many bottom units there are -> none: top only, one: top/unit, several: top/(unit*unit)
    if not bottom:
        return top_text
    if len(bottom) == 1:
        return top_text + "/" + bottom[0]
    return top_text + "/(" + "*".join(bottom) + ")"


# Unit class that stores powers + display text
class Unit:
    # stores a copy of the powers -> then builds the text from them if none is given
    def __init__(self, powers, text=None):
        self.powers = dict(powers)
        self.text = text if text else format_powers(self.powers)

    # same_as comparison -> both units must have the same names and powers (ex: L vs L -> True, km vs m -> False)
    def same_as(self, other):
        return other is not None and self.powers == other.powers

    # show unit text
    def __str__(self):
        return self.text

    # show unit text inside Unit(...) for debugging
    def __repr__(self):
        return "Unit({})".format(self.text)


# Display text for a unit that might be None -> None means a plain number
def unit_name(unit):
    return "a plain number" if unit is None else unit.text


# Function that turns unit text (ex: "L/lap") into a defined Unit
def parse_unit_text(text, line):
    # removes whitespace -> checks if the brackets are empty -> raises an error
    s = text.replace(" ", "").replace("\t", "")
    if s == "":
        raise PitwallError(line, "empty unit []")

    # one error reused for all badly written units
    bad_unit = PitwallError(line, "invalid unit '{}'".format(text.strip()))

    powers = {}
    seen = set()
    repeated = False  # true if a name appears twice
    sign = 1  # +1 after "*" or at the start -> -1 after "/"
    i = 0  # current position in the text
    first = True  # true until the first term is read

    # loops through the text one term at a time -> stops at the end or raises an error on bad text
    while True:
        # checks for a leading "1/" (ex: 1/s) -> skips the 1 as it adds nothing
        if first and s.startswith("1/"):
            i += 1
        else:
            # otherwise reads a unit name -> raises an error if there isn't one
            match = NAME_PATTERN.match(s, i)
            if not match:
                raise bad_unit
            name = match.group()
            i = match.end()
            power = 1

            # checks for "^" after the name -> reads the power -> raises an error if it's missing or 0
            if s[i : i + 1] == "^":
                match = POWER_PATTERN.match(s, i + 1)
                if not match or int(match.group()) == 0:
                    raise bad_unit
                power = int(match.group())
                i = match.end()

            # checks if the name was already seen -> marks it repeated -> then adds its power (negative after "/")
            if name in seen:
                repeated = True
            seen.add(name)
            add_power(powers, name, sign * power)
        first = False

        # checks if the end of the text is reached -> stops the loop
        if i == len(s):
            break
        # checks the operator after the term -> "*" adds the next power, "/" subtracts it -> anything else results in an error
        if s[i] == "*":
            sign = 1
        elif s[i] == "/":
            sign = -1
        else:
            raise bad_unit
        i += 1
        # checks if the text ends straight after an operator (ex: L/) -> raises an error
        if i == len(s):
            raise bad_unit

    # checks if every unit cancelled out (ex: L/L) -> raises an error
    if not powers:
        raise PitwallError(line, "unit '{}' cancels out completely".format(s))
    # returns the Unit -> keeps the users spelling unless a name was repeated (ex: m/s/s is shown as m/s^2)
    return Unit(powers, None if repeated else s)


# Function that combines two units for multiply (sign 1) and divide (sign -1) -> returns the resulting unit
def combine(a, b, sign):
    # checks if the right side is a plain number -> returns the left unit unchanged (ex: x * 2, x / 2)
    if b is None:
        return a
    # checks if the left side is a plain number when multiplying -> returns the right unit unchanged (ex: 2 * x)
    if a is None and sign == 1:
        return b

    powers = {}
    # checks if the left side has a unit -> adds its powers
    if a is not None:
        for name, power in a.powers.items():
            add_power(powers, name, power)
    # loops over the right sides powers -> added when multiplying, subtracted when dividing
    for name, power in b.powers.items():
        add_power(powers, name, sign * power)
    # checks if every power cancelled -> returns None (a plain number)
    if not powers:
        return None
    return Unit(powers)


# Function for the unit x * y -> powers are added
def multiply(a, b):
    return combine(a, b, 1)


# Function for the unit x / y -> powers are subtracted
def divide(a, b):
    return combine(a, b, -1)


# UnitTable class that knows what every unit name means -> used for 'to' conversions
# definitions maps each unit name to (dimensions, scale) -> dimensions is a powers dictionary of base units
class UnitTable:
    # base units with scale 1 -> any unknown name also becomes a base unit when first used (ex: [stint])
    BASE_UNITS = ["m", "s", "L", "lap", "kPa"]

    # built-in scaled units from Part A -> (name, scale, unit text)
    BUILTIN_UNITS = [
        ("km", 1000, "m"),
        ("min", 60, "s"),
        ("h", 3600, "s"),
        ("mph", 0.44704, "m/s"),
        ("psi", 6.894757, "kPa"),
    ]

    # sets up the table with the base units first -> followed by built-in units
    def __init__(self):
        self.definitions = {}
        self.cache = {}  # resolved units -> each one is only worked out once
        for name in self.BASE_UNITS:
            self.definitions[name] = ({name: 1}, 1)
        for name, scale, text in self.BUILTIN_UNITS:
            self.define(name, scale, parse_unit_text(text, 0), 0)

    # checks if a unit name is already in the table
    def is_defined(self, name):
        return name in self.definitions

    # adds a user unit -> ex: unit stint = 25 lap -> define("stint", 25, lap)
    def define(self, name, scale, unit, line):
        # redefining an existing unit results in an error
        if name in self.definitions:
            raise PitwallError(line, "unit {} is already defined".format(name))

        # works out the new units dimensions and scale from the unit its based on
        dims, unit_scale = self.resolve(unit)
        self.definitions[name] = (dims, scale * unit_scale)

    # fetch the dimensions and scale of a given unit name -> an unknown name becomes a new base unit of its own
    def lookup(self, name):
        if name not in self.definitions:
            self.definitions[name] = ({name: 1}, 1)
        return self.definitions[name]

    # works out (dimensions, scale) for a whole Unit -> None refers to a plain number
    # ex: km/h -> km is ({m: 1}, 1000) and h is ({s: 1}, 3600) -> so km/h is ({m: 1, s: -1}, 1000 / 3600)
    def resolve(self, unit):
        if unit is None:
            return {}, 1

        # returns the cached result if this unit has already been assigned
        key = tuple(sorted(unit.powers.items()))
        if key in self.cache:
            return self.cache[key]

        # combines every names dimensions and scale -> each raised to that names power
        dims = {}
        scale = 1
        for name, power in unit.powers.items():
            name_dims, name_scale = self.lookup(name)
            for base, base_power in name_dims.items():
                add_power(dims, base, base_power * power)
            scale *= name_scale**power
        self.cache[key] = (dims, scale)  # stores the result for next time
        return dims, scale

    # Function to convert a value from one unit to another -> 'to' operator
    def convert(self, value, from_unit, to_unit, line):
        from_dims, from_scale = self.resolve(from_unit)
        to_dims, to_scale = self.resolve(to_unit)

        # the dimensions must match -> so the value can be multiplied by the scale of from_unit / scale of to_unit
        if from_dims != to_dims:
            message = "cannot convert {} to {}".format(
                unit_name(from_unit), unit_name(to_unit)
            )
            raise PitwallError(line, message)
        return float(value) * from_scale / to_scale  # return result as float

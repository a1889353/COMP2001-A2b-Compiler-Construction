# Pitwall language reference

This document is the full reference sheet for Pitwall, covering its syntax, semantic rules and error messages. I wrote it so that anyone can write their own Pitwall program from scratch, or modify one of the provided examples, using only this file. Every example has been run through the compiler, so the output shown is exactly what Pitwall prints.

To run any Pitwall program, use:

```
python pitwall.py FILE.pit
```

---

## 1. Example program: laps on one tank

This short program works out how many laps a full tank of fuel will last, based on a fixed burn rate per lap.

```
# fuel for one stint
let tank = 50[L]
let burn = 2.7[L/lap]
var laps = 0[lap]
var fuel = tank
while fuel >= burn * 1[lap] {
    fuel -= burn * 1[lap]
    laps += 1[lap]
}
print("Laps on one tank:", laps)
print("Fuel left:", round(fuel, 2))
```

Output:

```
Laps on one tank: 18 lap
Fuel left: 1.4 L
```

Every number in Pitwall can carry a unit (`50[L]`, `2.7[L/lap]`), and the compiler checks those units whenever two values are combined. This means `L/lap * lap` gives `L`, while adding litres to seconds is caught as an error. Apart from units, I deliberately kept the rest of the syntax familiar, using `var`, `let`, C-style operators, `{ }` blocks, `if`, `while` and `for`.

---

## 2. Lexical rules

### 2.1 Files, lines and comments

Pitwall programs are saved as `.pit` files and read as UTF-8. A `#` starts a comment, which runs to the end of the line.

Each statement ends at a new line or a `;`, so several statements can sit on one line if they are separated by `;`. New lines inside `( )` and `[ ]` are ignored, which means a long call or list can be split over several lines. New lines inside `{ }` still end statements, while indentation and blank lines are ignored completely.

### 2.2 Names and keywords

A name must start with a letter or `_`, followed by any mix of letters, digits or `_` (for example `fuel`, `race_laps` or `S1`). Names are case-sensitive, so `fuel` and `Fuel` are two different variable names.

These 22 words are reserved by the language and cannot be used as names:

```
var let fn return if elif else while for in repeat times
break continue unit to check and or not true false
```

### 2.3 Literals

| Literal | Examples | Notes |
|---|---|---|
| Integer | `42`, `0` | a whole number |
| Decimal | `3.5`, `0.25` | needs a digit on both sides of the `.`, so `.5` and `5.` are not allowed |
| Number with a unit | `50[L]`, `2.7[L/lap]`, `9.81[m/s^2]` | the `[` must come **straight after** the number with no space (see section 6) |
| Lap time | `1:32.318`, `2:01.345`, `1:31.0` | minutes, then `:`, then two-digit seconds with an optional fraction. Stored as seconds with unit `s`, so `1:32.318` becomes `92.318 s`. Seconds must be 00 to 59 |
| String | `"GT3"`, `"line\n"` | double quotes only, with the escapes `\n` `\t` `\"` `\\` |
| Boolean | `true`, `false` | |
| List | `[1, 2, 3]`, `[]`, `[[1, 2], [3, 4]]` | items can be any type, and a trailing comma is allowed |

Pitwall does not support scientific notation, so `1e3` is not a valid number.

### 2.4 Operators and punctuation

```
+  -  *  /  %  ==  !=  <  <=  >  >=  =  +=  -=  ..  ( )  [ ]  { }  ,  ;
```

The lexer uses maximal munch, which means it always takes the longest operator it can. For example, `<=` is read as one token rather than `<` followed by `=`. A `.` only belongs to a number when a digit comes after it, which is how `0..10` is read as `0`, `..` and `10` instead of a decimal.

To see the tokens the lexer produces for any program, run it with the `--tokens` flag:

```
python pitwall.py FILE.pit --tokens
```

---

## 3. Statements

Each statement in Pitwall does one job, and the table below lists every statement with its form and any rules to know.

| Statement | Form | Notes |
|---|---|---|
| Variable | `var name = expression` | can be changed later |
| Constant | `let name = expression` | changing it is an error, although the contents of a `let` list can still change with `push` or `list[i] = value` |
| Assignment | `name = expression` | the variable must already exist |
| Add / subtract and assign | `name += expression`, `name -= expression` | only works on a plain variable, so `list[i] += 1` is not allowed |
| List item assignment | `list[i] = expression`, `grid[i][j] = expression` | changes the list itself |
| If | `if cond { } elif cond { } else { }` | `elif` and `else` are optional and can start on the line after the `}`. Write `elif`, not `else if` |
| While | `while cond { }` | |
| For | `for item in list { }`, `for i in 0..n { }` | also works over the characters of a string |
| Repeat | `repeat n times { }` | `n` must be a whole number that is not negative |
| Break / continue | `break`, `continue` | only allowed inside a loop |
| Function | `fn name(a, b) { }` | see section 5 |
| Return | `return expression`, `return` | only allowed inside a function |
| Unit declaration | `unit name = 25 lap` or `unit name = 25[lap]` | see section 6.4 |
| Check | `check cond` | stops the program with `check failed` if the condition is false |
| Block | `{ }` | starts a new scope |
| Expression | `print(x)`, `push(xs, 1)` | usually a function call |

The `{ }` around a body is always required, even if it only holds one statement.

### 3.1 Scope

Every `{ }` block creates a new scope. A name declared inside a block only exists until that block ends, and it can hide a name with the same name outside it. In this example, the inner `x` is only used inside the block:

```
var x = 1
{ var x = 2; print(x) }
print(x)
```

Output:

```
2
1
```

Declaring the same name twice in one block is an error. Each pass of a `for` or `repeat` loop also gets a fresh scope, which is where the loop variable lives.

### 3.2 Loops

This loop shows `continue` and `break` working together. It skips every even number with `continue`, then stops once `i` goes past 7 with `break`:

```
var i = 0
while true {
    i += 1
    if i % 2 == 0 { continue }
    if i > 7 { break }
    print(i)
}
```

This prints `1`, `3`, `5` and `7` on separate lines.

A range `a..b` creates the list of whole numbers from `a` up to `b - 1`. This means `for i in 0..3` runs three times, with `i` set to 0, 1 and 2.

---

## 4. Expressions

### 4.1 Precedence

The table below lists every operator from highest precedence (binds tightest) to lowest:

| Level | Operators | Meaning | Associativity |
|---|---|---|---|
| 1 | `f(x)`, `xs[i]` | call, index | left |
| 2 | `-x` | negate | prefix |
| 3 | `*` `/` `%` | multiply, divide, remainder | left |
| 4 | `+` `-` | add, subtract | left |
| 5 | `x to [unit]` | unit conversion | postfix |
| 6 | `a..b` | range | cannot be chained |
| 7 | `==` `!=` `<` `<=` `>` `>=` | compare | cannot be chained |
| 8 | `not` | logical not | prefix |
| 9 | `and` | logical and (short-circuit) | left |
| 10 | `or` | logical or (short-circuit) | left |

This means `2 + 3 * 4 - 6 / 3` gives `12.0`, since multiplication and division happen first. In the same way, `track / pace to [km/h]` is read as `(track / pace) to [km/h]`, so the whole division is converted. A `not` also applies to the whole comparison after it, so `not a == b` means `not (a == b)`.

Comparisons cannot be chained, so `a < b < c` gives the error `comparisons cannot be chained`. This is because the first comparison would give `true` or `false`, which would then be compared with a number. To check a range, write `a < b and b < c` instead. To see how any program is grouped, run it with `--ast`.

### 4.2 Values and types

Pitwall is dynamically typed, which means the type of a value is checked as the program runs rather than declared in the code. It has five types of value:

| Type | Examples |
|---|---|
| number | `42`, `3.5`, `50[L]`, `1:32.318` (a number can have a unit) |
| string | `"FL"` |
| boolean | `true`, `false` |
| list | `[1, 2]`, `[[30.4[s], 34.1[s]], [30.2[s], 34.3[s]]]` |
| function | made by `fn` |

**Whole numbers and decimals.** A number like `42` is a whole number, while `3.5` is a decimal, and lap times are always decimals. Using `/` always gives a decimal, so `6 / 3` is `2.0` and `10 / 4` is `2.5`. The other operators (`+`, `-`, `*` and `%`) give a whole number when both sides are whole numbers. `round(x)` and `ceil(x)` also give a whole number, while `round(x, n)` and `to` always give a decimal.

**Conditions must be true or false.** The `if`, `while` and `check` statements, along with the `and`, `or` and `not` operators, only accept `true` or `false`. Unlike some languages, a `0` or an empty list does not count as false, so `if 5 { }` is an error.

**Strings.** Using `+` on two strings joins them together, while comparing two strings orders them alphabetically. Mixing a string and a number gives the error `cannot add a string and a number`. Indexing a string gives a one-character string, but a string itself cannot be changed.

**Equality.** `==` and `!=` work on any two values of the same type, including lists. Comparing values of different types, such as a number and a string, is an error.

**Lists.** Lists are passed by reference, which means if a function changes a list it was given, the caller sees that change. Every other type is passed by value. Indexes start at 0, so an index outside the list, or one that is not a whole number, is an error.

### 4.3 Short-circuit `and` / `or`

Both `and` and `or` stop early once the answer is known. For `a and b`, the right side `b` is only worked out if `a` is `true`. For `a or b`, it is only worked out if `a` is `false`.

---

## 5. Functions

Functions are declared with `fn`, and they can call themselves. This example works out a factorial using recursion:

```
fn fact(n) {
    if n <= 1 { return 1 }
    return n * fact(n - 1)
}
print(fact(5))
```

This prints `120`.

A function must be declared before it is called, since Pitwall does not support forward references. This also means two functions cannot call each other. A function can call itself, but more than 500 nested calls stops the program with `too much recursion`.

A function can read and change any variable declared outside it, as long as that variable is declared above the function. Calling a function with the wrong number of arguments is an error, which is caught before the program runs. A function name is also treated as a constant, so it cannot be reassigned.

When a function ends without a `return`, it gives back nothing. Calling it as a statement is fine, but trying to use its result (for example `var y = f()`) gives the error `f did not return a value`.

---

## 6. Units of measure

### 6.1 Writing units

A unit is written in square brackets straight after a number, such as `50[L]`, `2.7[L/lap]`, `250[km/h]` or `9.81[m/s^2]`.

Inside the brackets, a unit is made up of one or more names joined by `*` or `/`, read from left to right. A name can also have a whole-number power, such as `m/s^2` or `s^-1`, and `1/s` is accepted as well.

### 6.2 The unit table

Pitwall comes with a small set of units built in, and any new name becomes a unit automatically:

| Kind | Units |
|---|---|
| Base units | `m`, `s`, `L`, `lap`, `kPa` |
| Built-in scaled units | `km` = 1000 m, `min` = 60 s, `h` = 3600 s, `mph` = 0.44704 m/s, `psi` = 6.894757 kPa |
| New names | any other name in brackets automatically becomes a new base unit (`50[tyres]` works) |
| Your own units | `unit stint = 25 lap` (section 6.4) |

### 6.3 Unit rules

Every operation on numbers with units follows these rules:

| Operation | Rule | Example | Result |
|---|---|---|---|
| `+` `-` `%` and comparisons | the units must be **exactly the same**. There is no silent conversion, and a unit against a plain number is also an error | `40[L] + 2.7[s]` | `Error line 1: cannot add L and s` |
| | | `1[km] + 1[m]` | `Error line 1: cannot add km and m` |
| `*` `/` | powers are added (`*`) or subtracted (`/`) **by name**, and names that reach a power of 0 cancel out | `31[lap] * 2.7[L/lap]` | `83.7 L` |
| | | `50[L] / 2.7[L/lap]` | `18.518518519 lap` |
| | if every name cancels, the result is a plain number | `83.7[L] / 50[L]` | `1.674` |
| number times unit | the unit is kept | `2 * 2.7[L]` | `5.4 L` |
| `x to [unit]` | the two units must measure the same thing, then the value is scaled and the result is a decimal in the new unit | `27.4[psi] to [kPa]` | `188.9163418 kPa` |
| | | `250[km/h] to [mph]` | `155.342798059 mph` |
| | | `5[L] to [s]` | `Error line 1: cannot convert L to s` |

The most important rule is that units only cancel **by name**. For example, `min` and `s` both measure time, but because they have different names they do not cancel on their own:

```
print(45[min] / (92.318[s] / 1[lap]))
print(45[min] / (92.318[s] / 1[lap]) to [lap])
```

Output:

```
0.487445569 min*lap/s
29.246734115 lap
```

This is why `to` exists. It is how you tell Pitwall to convert between scales, since it never converts on its own. This means to add two lengths in different units, one has to be converted first, so `(1[km] to [m]) + 1[m]` gives `1001.0 m`.

**How units are shown.** A unit you write keeps your spelling, so `km/h` stays as `km/h`. When Pitwall builds a unit itself, it puts the positive powers first, then a `/`, then the negative powers, with brackets when there is more than one (`L/(lap*s)`). A unit with only negative powers is shown as `1/s`.

### 6.4 Declaring units

New units can be declared with `unit`:

```
unit stint = 25 lap
print(2[stint] to [lap])
```

This prints `50.0 lap`. The number is how many of the right-hand unit make up one of the new unit, and it can also be written with brackets (`unit tank_full = 50[L]`). Unit declarations are handled before the program runs, which means a new unit can be used anywhere in the file. Defining the same unit twice is an error.

### 6.5 Lap times

A lap time literal like `1:32.318` is stored as a number of seconds with the unit `s`, so it follows the same unit rules as any other time. This means `1:30.0 < 1:31.0` is `true`, and `laptime(30[s] + 1:00.000)` gives `1:30.000`.

The `laptime(t)` function turns any time into `m:ss.sss` text. It converts minutes or hours into seconds first, so `laptime(1.5[min])` also gives `1:30.000`.

---

## 7. Built-in functions

Pitwall has eight built-in functions, which can be used anywhere in a program:

| Built-in | What it does | Example | Result |
|---|---|---|---|
| `print(a, b, ...)` | prints its arguments separated by spaces, then a new line | `print("Fuel:", 83.7[L])` | `Fuel: 83.7 L` |
| `input(prompt)` | prints the prompt (no new line) and returns the line typed as a string | `input("Laps? ")` | `"30"` |
| `len(x)` | the number of items in a list or characters in a string | `len([1, 2, 3])` | `3` |
| `push(list, value)` | adds a value to the end of a list (changes the list itself) | `push(stint, 1:32.3)` | |
| `round(x)` / `round(x, n)` | rounds half away from zero and keeps the unit | `round(2.675, 2)`, `round(2.5)` | `2.68`, `3` |
| `ceil(x)` | rounds up to the next whole number and keeps the unit | `ceil(2.1[lap])` | `3 lap` |
| `num(text)` | turns a string into a number | `num("2.5") * 2` | `5.0` |
| `laptime(t)` | formats a time as `m:ss.sss` | `laptime(121.345[s])` | `2:01.345` |

Built-in names can also be reused for your own variables or functions. When this happens, your declaration hides the built-in version.

### 7.1 How values are printed

Each type of value is printed in its own format:

| Value | Printed as |
|---|---|
| whole number | `42` |
| decimal | rounded to 9 decimal places: `83.7`, `12.0`, `18.518518519` |
| number with a unit | value, space, unit: `83.7 L`, `30 lap` |
| boolean | `true` / `false` |
| string | its text, without quotes |
| list | `[1, "FL", true, 2.5 L]` (strings inside a list keep their quotes) |

---

## 8. Errors

Every error is printed as a single line on stderr, and the program stops straight away with exit code 1:

```
Error line N: message
```

Pitwall never shows a Python traceback. Each error is caught by the earliest phase that can see it:

| Phase | When | Example messages |
|---|---|---|
| Lexer | reading characters | `unexpected character '@'` / `unterminated string` / `invalid lap time` / `unclosed unit bracket (missing ])` / `unknown escape \q in string` / `invalid unit 'L/'` |
| Parser | checking the grammar | `expected {` / `expected )` / `unexpected end of file (the { on line 3 is never closed)` / `comparisons cannot be chained` / `expected { (write elif, not else if)` / `+= only works on a variable` / `only named functions can be called` |
| Semantic analysis | before running | `x is not defined` / `cannot change constant tank` / `a is already declared in this block` / `break outside a loop` / `continue outside a loop` / `return outside a function` / `f expects 1 argument but got 0` / `unit stint is already defined` |
| Optimiser | before running, on values that are already known | `cannot add L and s` / `division by zero` |
| Virtual machine | while running | `cannot add km and m` / `cannot add a string and a number` / `division by zero` / `index 2 out of range (list has 2 items)` / `condition must be true or false` / `check failed` / `f did not return a value` / `cannot turn "abc" into a number` / `too much recursion` |

Since the optimiser works out expressions made only of literals before the program runs, a mistake like `print(2.7[L] + 1:32.318)` is reported before anything is printed. This even applies inside a function that is never called. Running with `--no-opt` turns this off.

---

## 9. Grammar (EBNF)

This section gives the full grammar of Pitwall in EBNF. In it, `{ x }` means zero or more, `[ x ]` means optional and `|` separates choices. Words in capitals are tokens that come from the lexer.

### 9.1 Tokens

```
NAME     = letter_ { letter_ | digit } ;            (not a keyword)
NUMBER   = digit { digit } [ "." digit { digit } ] ;
QUANTITY = NUMBER "[" unit "]" ;                    (no space before "[")
LAPTIME  = digit { digit } ":" digit digit [ "." digit { digit } ] ;
STRING   = '"' { character | escape } '"' ;
escape   = "\n" | "\t" | '\"' | "\\" ;
NEWLINE  = end of line ;                            (ignored inside ( ) and [ ])
```

### 9.2 Statements

```
program     = { separator } { statement { separator } } ;
separator   = NEWLINE | ";" ;
block       = "{" { separator } { statement { separator } } "}" ;

statement   = declare | if | while | for | repeat | fn | return
            | unit_decl | check | block | assignment | expression
            | "break" | "continue" ;

declare     = ( "var" | "let" ) NAME "=" expression ;
assignment  = NAME ( "=" | "+=" | "-=" ) expression
            | postfix "[" expression "]" "=" expression ;
if          = "if" expression block { "elif" expression block } [ "else" block ] ;
while       = "while" expression block ;
for         = "for" NAME "in" expression block ;
repeat      = "repeat" expression "times" block ;
fn          = "fn" NAME "(" [ NAME { "," NAME } ] ")" block ;
return      = "return" [ expression ] ;
unit_decl   = "unit" NAME "=" ( NUMBER unit | QUANTITY ) ;
check       = "check" expression ;
```

### 9.3 Expressions (lowest precedence first)

```
expression     = or ;
or             = and { "or" and } ;
and            = not { "and" not } ;
not            = "not" not | compare ;
compare        = range [ ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) range ] ;
range          = convert [ ".." convert ] ;
convert        = additive { "to" "[" unit "]" } ;
additive       = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative = unary { ( "*" | "/" | "%" ) unary } ;
unary          = "-" unary | postfix ;
postfix        = primary { "(" [ arguments ] ")" | "[" expression "]" } ;
                                                    (a call must follow a NAME)
primary        = NUMBER | QUANTITY | LAPTIME | STRING | "true" | "false"
               | NAME | "(" expression ")" | "[" [ arguments ] "]" ;
arguments      = expression { "," expression } [ "," ] ;
```

### 9.4 Units

```
unit      = [ "1" "/" ] unit_term { ( "*" | "/" ) unit_term } ;
unit_term = NAME [ "^" [ "-" ] digit { digit } ] ;  (the power cannot be 0)
```

---

## 10. Design decisions worth knowing

While building Pitwall I had to settle a number of details that my Part A design left open, and most of these choices came down to keeping the language predictable for someone planning a race rather than making it as flexible as possible. I decided that unit declarations should be handled at compile time, so a unit like `stint` can be used anywhere in the file, even above the line where it is declared, whereas functions can only see names declared above them, which is also why Pitwall does not support two functions calling each other. For `round` I chose to round half away from zero, which is how I would naturally round by hand when working out fuel, instead of the round-half-to-even approach that Python uses, so `round(2.5)` gives `3` while `round(2.675, 2)` gives `2.68`. I kept `+=` and `-=` limited to plain variables to keep the parser simple, meaning a list item has to be updated with the longer form `xs[i] = xs[i] + 1`, and for the same reason only named functions can be called, so something like `f(x)(y)` is treated as an error. Units only cancel by name because I wanted every change of scale to be deliberate, which is exactly what the `to` keyword is for, and I left out scientific notation entirely since race data never needs numbers that large or small, so `1e3` is not accepted as a number. Finally, because the optimiser works out literal values before the program runs, a division by a literal zero such as `1 / 0` is caught straight away, even when it sits inside a function that is never called.

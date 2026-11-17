# Pitwall

Pitwall is a small and lightweight programming language I developed for the specific purpose of planning race stints. It allows users to easily calculate fuel requirements, race laps and pit stops from their lap times. It can also check additional stint information, such as tyre pressures and theoretical best laps. Every number carries its unit, so the compiler catches mistakes like adding litres to seconds before the program even runs.

The idea came from a problem I deal with before every race. I race in the iRacing IMSA series in the BMW M4 GT3 EVO, and IMSA races are timed rather than run over a set number of laps. That means before each race I need to work out how many laps I will actually do, how much fuel that takes and whether I will need to pit. Doing that maths by hand is where mistakes creep in, because it is easy to mix up units without noticing.

To show how this works, I have included `examples/fuel_planner.pit`, which plans a real race from week 4 at the Red Bull Ring. I chose this race because it is the most recent data I have for this project: the race was 45 minutes, my average lap was 1:32.318 and BoP capped the tank at 50 L. Running `python pitwall.py examples/fuel_planner.pit` shows the full plan, including the race laps, the fuel needed and the number of stops. The same program works for any week, since I only need to swap in the race length, lap time and fuel cap for that week. Pitwall then does the rest of the calculations for me.

The full language reference is in **[LANGUAGE.md](LANGUAGE.md)**.

---

## 1. Requirements

- Python 3.8 or newer (tested on Python 3.12)
- Nothing to install: the compiler only uses the Python standard library

## 2. Quick start

1. Unzip the folder and open a terminal inside it (the folder with `pitwall.py`).
2. Run the fuel planner example:

   ```
   python pitwall.py examples/fuel_planner.pit
   ```

   You should see:

   ```
   Race laps: 30 lap
   Fuel needed: 83.7 L
   Laps per tank: 18.5 lap
   Fuel stops: 1
   ```

3. Run the full test suite:

   ```
   python run_tests.py
   ```

   The last line should read `TOTAL 81/81`.

## 3. Command-line options

```
python pitwall.py FILE.pit                       runs a program
python pitwall.py FILE.pit --tokens              prints the token stream and stops (lexer)
python pitwall.py FILE.pit --ast                 prints the syntax tree and stops (parser)
python pitwall.py FILE.pit --bytecode            prints the bytecode and stops (code generator)
python pitwall.py FILE.pit --bytecode --no-opt   the same, but with the optimiser turned off
```

Any error is printed as `Error line N: message` with exit code 1, so you never see a Python traceback.

## 4. Writing your first program

Save this as `stint.pit`:

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

Then run `python pitwall.py stint.pit`:

```
Laps on one tank: 18 lap
Fuel left: 1.4 L
```

- `let` makes a constant and `var` makes a variable.
- `50[L]` is 50 litres. `burn * 1[lap]` is `L/lap` times `lap`, which gives `L`, so it can be taken away from `fuel`.
- Blocks use `{ }`, and conditions must be `true` or `false`.

LANGUAGE.md contains the full syntax and rules of the language, including the unit rules, built-in functions, error messages and EBNF grammar.

The `examples/` folder contains three separate example programs you can run or edit:

| File | What it does |
|---|---|
| `fuel_planner.pit` | race laps, fuel needed and pit stops for a 45-minute race (shows: functions, units, `to`, `ceil`, `check`) |
| `theoretical_best.pit` | best possible lap from the best sector times (shows: 2D lists, nested `for` loops, `laptime`) |
| `tyre_check.pit` | tyre pressures checked against a window and converted from psi to kPa (shows: `if` / `elif` / `else`, lists, `to`) |

## 5. Running the tests

```
python run_tests.py                   runs every test and prints a summary
python run_tests.py units             only runs tests whose path contains "units"
python run_tests.py --update NAME     rewrites the expected output for tests matching NAME
```

Sample output:

```
group         passed
codegen        5/5   ok
errors         4/4   ok
lexer         11/11  ok
optimiser      7/7   ok
parser        11/11  ok
programs       3/3   ok
runtime       18/18  ok
semantic      10/10  ok
units         12/12  ok
TOTAL         81/81
```

If a test fails, the runner will show the difference between the expected and actual output.

**What the test groups cover:**

| Group | Tests |
|---|---|
| `lexer` | the token stream is correct, including unit literals, lap times vs ranges, maximal munch, new lines inside brackets and lexical errors |
| `parser` | the syntax tree is built correctly, including precedence, if / elif / else, functions, loops, assignments, how `to` binds and syntax errors |
| `semantic` | programs are checked before running, including scope, constants, shadowing, argument counts, unit redefinition and where `break`, `continue` or `return` can appear |
| `optimiser` | constant folding and dead-code elimination work, with and without `--no-opt`, including errors caught before the program runs |
| `codegen` | the right bytecode is generated, including if / else, while loops with break / continue, for loops, function calls and short-circuit `and` / `or` |
| `units` | unit maths works, including combining, cancelling, converting and displaying units, lap-time sums and unit errors |
| `runtime` | programs run correctly, including loops, recursion, scope, lists, strings, logic, built-ins, `input` and run-time errors |
| `programs` | the three example programs from my Part A report give the expected output |
| `errors` | bad input is handled cleanly, including an empty file, random symbols, deep recursion and an unclosed `{` |

All 22 tests from the Part A test table are implemented, with a prefix from `a01_` to `a22_`.

## 6. How the compiler works

```
source text -> Lexer -> tokens -> Parser -> AST -> Semantic analyser -> checked AST -> Optimiser -> Code generator -> bytecode -> Virtual machine -> output
```

The compiler is split into six phases, and `pitwall.py` runs them in order while catching every error along the way.

1. **Lexer** (`core/lexer.py`, `core/tokens.py`). The lexer reads the source one character at a time and groups the characters into tokens, always taking the longest token it can (maximal munch). I wrote the number scanner as a small finite state machine with the states INT, FRAC, LAP_COLON, LAP_SECS and LAP_FRAC. This is how it decides whether `1:32.318` is a lap time, `50[L]` is a number with a unit, or `0..3` is a range. New lines inside `( )` and `[ ]` are dropped, so long lines can be split.
2. **Parser** (`core/parser.py`, `core/ast_nodes.py`). The parser is a recursive descent parser with one method per statement, plus one method per precedence level from `parse_or` down to `parse_primary`. It builds an abstract syntax tree where every node keeps its line number.
3. **Semantic analyser** (`core/analyser.py`). The analyser walks the tree using a symbol table, which is a stack of scopes. Before anything runs, it checks that names are declared before use, constants are never changed and no name is declared twice in one block. It also checks that `break` / `continue` are inside loops, `return` is inside a function and every call has the right number of arguments. Any `unit` declarations are added to the unit table by this point.
4. **Optimiser** (`core/optimiser.py`). Constant folding works out expressions made only of literals at compile time, so `2 + 3 * 4` becomes `14`. It uses the same unit rules as the VM (`core/operations.py`), which means unit mistakes between literals are caught before the program runs. Dead-code elimination then removes `if false` branches, `while false` loops and any statements after `return` / `break` / `continue`. This whole phase can be turned off with `--no-opt`.
5. **Code generator** (`core/codegen.py`). The code generator turns the tree into bytecode, a flat list of instructions such as `CONST 14`, `LOAD fuel` and `JUMP_IF_FALSE 9`. The main program and each function get their own list. Jumps are filled in using backpatching, which is used for `if`, loops, `break` / `continue` and short-circuit `and` / `or`. Every instruction keeps its source line so errors can report it.
6. **Virtual machine** (`core/vm.py`). The VM is a stack machine with a fetch-decode-execute loop. It has an operand stack, a frame for each function call and scopes stored as chained dictionaries. This means functions can read variables declared outside them. The VM handles the checks that can only happen at run time, such as unit mismatches between variables, division by zero, list indexes, true / false conditions, `check` and recursion depth.

Supporting files:
- `core/units.py`: the unit table, plus multiplying, dividing, cancelling and converting units. The scale of each unit is worked out once and then cached.
- `core/operations.py`: the operators shared by the optimiser and the VM, so both follow the same unit and type rules.
- `core/values.py`: the value types (numbers with units, functions, built-ins) and how they are printed.
- `core/builtins.py`: `print`, `input`, `len`, `push`, `round`, `ceil`, `num` and `laptime`.
- `core/errors.py`: `PitwallError`, the only error a user ever sees.

The dump flags make it easy to see what each phase does. For example, with `let fuel = 2 + 3 * 4`:

```
python pitwall.py t.pit --bytecode --no-opt      python pitwall.py t.pit --bytecode
   1     0  CONST                 2                 1     0  CONST                 14
   1     1  CONST                 3                 1     1  DEFINE                fuel (const)
   1     2  CONST                 4
   1     3  MUL
   1     4  ADD
   1     5  DEFINE                fuel (const)
```

Without the optimiser, the generator emits each constant and operator separately. With it on, the whole expression is folded into a single `CONST 14` before code generation.

## 7. Project structure

```
assignment2b/
├── pitwall.py          command-line entry point
├── run_tests.py        runs every test and prints a summary
├── README.md           this file
├── LANGUAGE.md         the language reference
├── core/
│   ├── errors.py       PitwallError (line + message)
│   ├── tokens.py       token kinds, keywords and operator tables
│   ├── lexer.py        phase 1: lexical analysis
│   ├── ast_nodes.py    AST node classes and the --ast dump
│   ├── parser.py       phase 2: syntax analysis
│   ├── analyser.py     phase 3: semantic analysis
│   ├── optimiser.py    phase 4: constant folding and dead-code elimination
│   ├── codegen.py      phase 5: code generation and the --bytecode listing
│   ├── vm.py           phase 6: the stack virtual machine
│   ├── units.py        unit table and unit maths
│   ├── operations.py   operators shared by the optimiser and the VM
│   ├── values.py       value types and printing
│   └── builtins.py     built-in functions
├── examples/           fuel_planner.pit, theoretical_best.pit, tyre_check.pit
└── tests/              codegen, errors, lexer, optimiser, parser, programs, runtime, semantic, units
```

## 8. Changes from the design (Part A)

The biggest change from my Part A design is how the programs actually run. In Part A I planned for an interpreter to run the syntax tree directly, but I changed this so the compiler now has a real code generation phase. Programs are compiled to bytecode for the stack virtual machine, which also gave me room to add optimisation passes. The `--bytecode` flag shows the result.

I also moved most of the semantic checking to before the program runs. In my original Part A plan every check happened at run time, but anything that does not depend on run-time values is now handled by a separate analysis pass. This covers names, constants, where `break` and `return` can appear, and argument counts. Type and unit checks on variables still happen in the VM, since Pitwall is dynamically typed.

On top of the cached unit table from Part A, I added constant folding (with unit checking) and dead-code elimination. Because of this, Part A test 17 (`4.318[km] / 0[s]`) is now caught before the program even runs. Every error now shows a line number, so I updated the expected outputs of the Part A tests to include them. I also added the `--tokens`, `--ast`, `--bytecode` and `--no-opt` flags so each phase of the compiler can be tested individually.

A few smaller details were settled while building. I added `^` to support the functionality of including powers inside units (`9.81[m/s^2]`), and `1/s` is also accepted. Unit declarations can be written as `25 lap` or `25[lap]`, since Pitwall accepts either. The `round` function rounds half away from zero. The rest of the design decisions are listed in section 10 of LANGUAGE.md.

## 9. Known limitations

Pitwall has a few limitations I chose to leave out of scope. For one, there is no interactive mode, so programs are always run from a `.pit` file. Functions must be declared before they are called, which means two functions cannot call each other. Only `+=` and `-=` are supported, and they only work on plain variables, so there is no support for the `*=` or `/=` operators. Units only cancel by name, so `min` and `s` will not cancel without using `to`. Scientific notation is not supported, and only the first error in a program is reported.

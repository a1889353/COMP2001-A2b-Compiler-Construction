"""Pitwall test runner"""
# The purpose of this file is to run every test under tests/ and print a pass/fail summary grouped by compiler phase.
# Each test is a name.pit program and a name.out file with the expected output -> optional name.args holds flags (ex: --tokens) and optional name.in holds text fed to input().
# The output compared is everything printed to stdout -> stderr -> "[exit N]" if the exit code wasn't 0 -> so error tests are also checked.
#
# Usage:
#   python run_tests.py                 runs every test and prints a summary
#   python run_tests.py lexer           only runs tests whose path contains "lexer"
#   python run_tests.py --update NAME   rewrites the expected output for tests whose path contains NAME -> then shows it

import difflib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.join(ROOT, "tests")


# Function that returns a file's text -> None if it doesn't exist
def read_if_exists(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


# Function that finds every .pit file under tests/ -> sorted and filtered by pattern
def find_tests(pattern):
    found = []
    for folder, _dirs, files in os.walk(TESTS_DIR):
        for name in files:
            if name.endswith(".pit"):
                path = os.path.join(folder, name)
                if pattern in os.path.relpath(path, ROOT).replace(os.sep, "/"):
                    found.append(path)
    return sorted(found)


# Function that runs one test program as its own process and returns its combined output
def run_one(pit_path):
    # reads the optional .args flags and .in input that sit next to the test
    base = pit_path[:-4]
    args = (read_if_exists(base + ".args") or "").split()
    stdin_text = read_if_exists(base + ".in") or ""
    rel = os.path.relpath(pit_path, ROOT)

    # runs pitwall.py on the test as a separate process -> anything over 20 seconds counts as timed out
    try:
        result = subprocess.run(
            [sys.executable, "pitwall.py", rel] + args,
            cwd=ROOT,
            input=stdin_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=20,
        )
    except subprocess.TimeoutExpired:
        return "[timed out after 20 seconds]\n"

    # combines stdout, stderr and a non-zero exit code into the one output that gets compared
    output = result.stdout + result.stderr
    if result.returncode != 0:
        output += "[exit {}]\n".format(result.returncode)
    return output.replace("\r\n", "\n")


# Function that runs the tests (or updates their expected output) and returns an exit code
def main(argv):
    # reads the command line -> an optional --update and an optional name pattern
    update = "--update" in argv
    words = [a for a in argv if a != "--update"]
    pattern = words[0] if words else ""
    tests = find_tests(pattern)
    if not tests:
        print("No tests match '{}'.".format(pattern))
        return 1

    # checks for --update -> writes the current output as the expected output
    if update:
        for path in tests:
            output = run_one(path)
            with open(path[:-4] + ".out", "w", encoding="utf-8", newline="\n") as f:
                f.write(output)
            print("updated {}\n{}".format(os.path.relpath(path, ROOT), output))
        return 0

    # runs every test and compares its output with its .out file -> keeps a [passed, total] count per folder & list of failures
    groups = {}
    failures = []
    for path in tests:
        group = os.path.relpath(os.path.dirname(path), TESTS_DIR).replace(os.sep, "/")
        groups.setdefault(group, [0, 0])
        groups[group][1] += 1

        expected = read_if_exists(path[:-4] + ".out")
        actual = run_one(path)
        if expected is not None and actual == expected.replace("\r\n", "\n"):
            groups[group][0] += 1
        else:
            failures.append((path, expected, actual))

    # prints each failure first -> a diff of the expected vs actual output
    for path, expected, actual in failures:
        print("FAIL " + os.path.relpath(path, ROOT))
        if expected is None:
            name = os.path.basename(path)[:-4]
            print(
                "  no .out file (create one with: python run_tests.py --update {})".format(
                    name
                )
            )
            continue
        diff = difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            "expected",
            "actual",
            lineterm="",
        )
        for line in diff:
            print("  " + line)
        print()

    # prints the summary table -> one row per folder -> then the tally
    print("{:<12} {:>7}".format("group", "passed"))
    total_pass = total = 0
    for group in sorted(groups):
        passed, count = groups[group]
        total_pass += passed
        total += count
        status = "ok" if passed == count else "FAILING"
        print("{:<12} {:>3}/{:<3} {}".format(group, passed, count, status))
    print("{:<12} {:>3}/{:<3}".format("TOTAL", total_pass, total))
    return 0 if total_pass == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

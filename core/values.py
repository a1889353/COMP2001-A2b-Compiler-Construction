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

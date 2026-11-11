"""Pitwall errors"""
# Any problem that Pitwall finds within a program in any stage of its compilation gets reported by raising a PitwallError.
# The entry point pitwall.py catches these errors, prints "Error line N: message" to stderr and exits with code 1.
# As every phase of compilation shares this one class, the user will never see a Python traceback.


class PitwallError(Exception):
    def __init__(self, line, message):
        super().__init__(message)
        self.line = line  # source line number of the error
        self.message = message  # readable plain text description of the error

    # Called when the error is printed
    def __str__(self):
        return "Error line {}: {}".format(self.line, self.message)

import os
import sys


class Foo:
    pass


class Bar(Foo):
    def __init__(self):
        super().__init__()


x = {}
y = []
z = ()
s = set()
f = frozenset()
d = {"b": 2, "a": 3}
v = f"{os.sep} {sys.path}"
if "a" in d:
    print("hello", x, y, z, s, f, d, v)
with open("file.txt") as fh:
    print("data", fh.read())


def long_function(
    argument_one, argument_two, argument_three, argument_four, argument_five, argument_six
):
    return argument_one

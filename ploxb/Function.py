from ploxb.Chunk import Chunk
from typing import TYPE_CHECKING, Optional

from termcolor import colored

if TYPE_CHECKING:
    from ploxb.VM import StackValueType


class Function:
    def __init__(self, name: str | None):
        self.chunk = Chunk()
        self.name = name
        self.arity = 0
        self.upvalue_count = 0

    def dis(self):
        if not self.name:
            print(colored("== COMPILETIME ==", "light_green"))
            print(colored("==SCRIPT==", "light_green"))
        else:
            print(colored(f"==FUNCTION {self.name}==", "light_green"))
        self.chunk.dis()
        for c in self.chunk.constants:
            if isinstance(c, Function):
                c.dis()

    def __repr__(self):
        if self.name is None:
            return "<script>"
        return f"<fn {self.name}()>"


class ClosureUpValue:
    def __init__(self, location: int | None):
        self.location = location
        self.closed: Optional["StackValueType"] = None

    def __repr__(self):
        return f"{self.location}-{self.closed}"


class Closure:
    def __init__(self, function: Function):
        self.function = function
        self.upvalues: list["ClosureUpValue"] = []

    def __repr__(self):
        return f"{str(self.function)}+{str(self.upvalues)}"


class CallFrame:
    def __init__(self, closure: Closure, stack_slot: int):
        self.closure = closure
        self.ip = 0
        self.stack_slot = stack_slot

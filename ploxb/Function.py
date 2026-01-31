from ploxb.Chunk import Chunk

from termcolor import colored


class Function:
    def __init__(self, name: str | None):
        self.chunk = Chunk()
        self.name = name
        self.arity = 0

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


class CallFrame:
    def __init__(self, function: Function, stack_slot: int):
        self.function = function
        self.ip = 0
        self.stack_slot = stack_slot

from ploxb.Chunk import Chunk


class Function:
    def __init__(self, name: str | None):
        self.chunk = Chunk()
        self.name = name
        self.arity = 0

    def __repr__(self):
        if self.name is None:
            return "<script>"
        return f"<fn {self.name}()>"


class CallFrame:
    def __init__(self, function: Function, stack_slot: int):
        self.function = function
        self.ip = 0
        self.stack_slot = stack_slot

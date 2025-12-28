from ploxb.Token import ValueType
from ploxb.Chunk import Chunk, OpCode


class VM:
    def __init__(self):
        # El instruction pointer
        # siempre apunta a la siguiente instrucción a ejecutar
        self.ip = 0
        # El stack de la máquina virtual
        # almacena todos los valores intermedios que se van produciendo
        self.values: list[ValueType] = []
        self.globals: dict[str, ValueType] = {}

    def peek(self, distance=0):
        return self.values[-1 - distance] if len(self.values) > distance else None

    def push(self, value: ValueType):
        # Agrega un resultado al tope del stack
        self.values.append(value)

    def pop(self):
        # Si el stack está vacío y llame a pop, es un error
        if not self.values:
            raise RuntimeError("STACK UNDERFLOW")

        # Devuelve el tope del stack, y lo elimina
        return self.values.pop()

    def run(self, chunk: Chunk):
        while self.ip < len(chunk.bytes):
            # print(f"{self.ip:04d} - STACK {self.values} - GLOBALS {self.globals}")
            byte = chunk.bytes[self.ip]
            self.ip += 1
            match byte:
                case OpCode.OP_PRINT:
                    print(self.pop())
                case OpCode.OP_POP:
                    self.pop()
                case OpCode.OP_RETURN:
                    return
                case OpCode.OP_JUMP_IF_FALSE:
                    offset1, offset2 = chunk.bytes[self.ip], chunk.bytes[self.ip + 1]
                    offset = (offset1 << 8) | offset2
                    self.ip += 2
                    if not self.is_truthy(self.peek()):
                        self.ip += offset
                case OpCode.OP_JUMP:
                    offset1, offset2 = chunk.bytes[self.ip], chunk.bytes[self.ip + 1]
                    offset = (offset1 << 8) | offset2
                    self.ip += 2
                    self.ip += offset
                case OpCode.OP_LOOP:
                    offset1, offset2 = chunk.bytes[self.ip], chunk.bytes[self.ip + 1]
                    offset = (offset1 << 8) | offset2
                    self.ip -= offset
                case OpCode.OP_DEFINE_GLOBAL:
                    var_index = chunk.bytes[self.ip]
                    var_name = chunk.constants[var_index]
                    var_value = self.pop()
                    self.globals[str(var_name)] = var_value
                    self.ip += 1
                case OpCode.OP_GET_GLOBAL:
                    var_index = chunk.bytes[self.ip]
                    var_name = chunk.constants[var_index]
                    if var_name not in self.globals:
                        raise RuntimeError(f"Undefined variable '{var_name}'")
                    var_value = self.globals[str(var_name)]
                    self.push(var_value)
                    self.ip += 1
                case OpCode.OP_SET_GLOBAL:
                    var_index = chunk.bytes[self.ip]
                    var_name = chunk.constants[var_index]
                    if var_name not in self.globals:
                        raise RuntimeError(f"Undefined variable '{var_name}'")
                    self.globals[str(var_name)] = self.peek()
                    self.ip += 1
                case OpCode.OP_GET_LOCAL:
                    var_index = chunk.bytes[self.ip]
                    var_value = self.values[var_index]
                    self.push(var_value)
                    self.ip += 1
                case OpCode.OP_SET_LOCAL:
                    var_index = chunk.bytes[self.ip]
                    self.values[var_index] = self.peek()
                    self.ip += 1
                case OpCode.OP_CONSTANT:
                    constant_index = chunk.bytes[self.ip]
                    constant_value = chunk.constants[constant_index]
                    # La instrucción de constante es "cargar" la constante en memoria:
                    # es solamente producir el resultado y pushearlo al tope del stack!
                    self.push(constant_value)
                    # Salteamos el índice de la constante en el ip
                    self.ip += 1
                case OpCode.OP_NEGATE:
                    if not self.is_number(self.peek()):
                        raise RuntimeError(
                            f"Operand of OP_NEGATE must be a number, got: `{self.peek()}`"
                        )
                    value = self.pop()
                    self.push(-value)
                case OpCode.OP_ADD:
                    b = self.pop()
                    a = self.pop()
                    if not self.is_number(a, b) and not self.is_string(a, b):
                        raise RuntimeError(
                            f"Operands of OP_ADD must be numbers or strings, got: `{a}, {b}`"
                        )
                    self.push(a + b)
                case OpCode.OP_SUBTRACT:
                    b = self.pop()
                    a = self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_SUBTRACT must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a - b)
                case OpCode.OP_MULTIPLY:
                    b = self.pop()
                    a = self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_MULTIPLY must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a * b)
                case OpCode.OP_DIVIDE:
                    b = self.pop()
                    a = self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_DIVIDE must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a / b)
                case OpCode.OP_NIL:
                    self.push(None)
                case OpCode.OP_TRUE:
                    self.push(True)
                case OpCode.OP_FALSE:
                    self.push(False)
                case OpCode.OP_NOT:
                    value = self.pop()
                    self.push(not self.is_truthy(value))
                case OpCode.OP_EQUAL:
                    b = self.pop()
                    a = self.pop()
                    self.push(a == b)
                case OpCode.OP_GREATER:
                    b = self.pop()
                    a = self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_GREATER must be numbers, got: `{a} - {b}`"
                        )
                    self.push(a > b)
                case OpCode.OP_LESS:
                    b = self.pop()
                    a = self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_LESS must be numbers, got: `{a} - {b}`"
                        )
                    self.push(a < b)
                case _:
                    raise RuntimeError(f"UNKNOWN {byte}")

    # ---------- Helpers ---------- #

    def is_truthy(self, value):
        if value is None or value is False:
            return False
        return True

    def is_number(self, *values):
        return all(type(value) is int or type(value) is float for value in values)

    def is_string(self, *values):
        return all(type(value) is str for value in values)

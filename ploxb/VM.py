from ploxb.Chunk import Chunk, OpCode

from typing import Union
from termcolor import colored

# Los valores que pueden almacenarse en el stack
StackValueType = Union[str, float, bool, None]

# Sentinela para indicarle al loop principal que corte la ejecución
_HALT = object()


class VM:
    def __init__(self):
        # El instruction pointer
        # siempre apunta a la siguiente instrucción a ejecutar
        self.ip = 0

        # El stack de la máquina virtual
        # almacena todos los valores intermedios que se van produciendo
        self.stack: list[StackValueType] = []

        # Bindings de variables globales
        # todo lo que se almacena en el stack puede utilizarse como variable global
        self.globals: dict[str, StackValueType] = {}

    def push(self, value: StackValueType):
        # Agrega un resultado al tope del stack
        self.stack.append(value)

    def pop(self):
        # Si el stack está vacío y llame a pop, es un error
        # No debería pasar nunca!!
        if not self.stack:
            raise RuntimeError("STACK UNDERFLOW")

        # Saca el tope del stack, y lo devuelve
        return self.stack.pop()

    def peek(self, distance=0):
        # Se fija el valor a N posiciones del tope del stack
        # O sea, con distance=0, devuelve el tope del stack (sin sacarlo)
        return self.stack[-1 - distance] if len(self.stack) > distance else None

    def run(self, chunk: Chunk, debug=False):
        # Cada vez que consumo un byte tengo que avanzar mi ip
        def READ():
            byte = chunk.bytes[self.ip]
            self.ip += 1
            return byte

        # Consumir una WORD es consumir dos bytes
        # (lo hacemos en big-endian)
        def READ_WORD():
            highbyte, lowbyte = READ(), READ()
            return (highbyte << 8) | lowbyte

        # ---------- Handlers de cada instrucción ---------- #
        def op_return():
            if debug:
                print(colored("THE END", "light_blue"))
            if len(self.stack):
                raise RuntimeError(
                    "Inconsistent Stack Height: should be empty at exit"
                )
            return _HALT

        def op_constant():
            constant_index = READ()
            self.push(chunk.constants[constant_index])

        def op_nil():
            self.push(None)

        def op_true():
            self.push(True)

        def op_false():
            self.push(False)

        def op_not():
            self.push(not self.is_truthy(self.pop()))

        def op_negate():
            if not self.is_number(self.peek()):
                raise RuntimeError(
                    f"Operand of OP_NEGATE must be a number, got: `{self.peek()}`"
                )
            self.push(-self.pop())

        def op_add():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b) and not self.is_string(a, b):
                raise RuntimeError(
                    f"Operands of OP_ADD must be numbers or strings, got: `{a}, {b}`"
                )
            self.push(a + b)

        def op_subtract():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b):
                raise RuntimeError(
                    f"Operands of OP_SUBTRACT must be numbers, got: `{a}, {b}`"
                )
            self.push(a - b)

        def op_multiply():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b):
                raise RuntimeError(
                    f"Operands of OP_MULTIPLY must be numbers, got: `{a}, {b}`"
                )
            self.push(a * b)

        def op_divide():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b):
                raise RuntimeError(
                    f"Operands of OP_DIVIDE must be numbers, got: `{a}, {b}`"
                )
            self.push(a / b)

        def op_modulo():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b):
                raise RuntimeError(
                    f"Operands of OP_MODULO must be numbers, got: `{a}, {b}`"
                )
            self.push(a % b)

        def op_equal():
            b, a = self.pop(), self.pop()
            self.push(a == b)

        def op_greater():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b):
                raise RuntimeError(
                    f"Operands of OP_GREATER must be numbers, got: `{a} - {b}`"
                )
            self.push(a > b)

        def op_less():
            b, a = self.pop(), self.pop()
            if not self.is_number(a, b):
                raise RuntimeError(
                    f"Operands of OP_LESS must be numbers, got: `{a} - {b}`"
                )
            self.push(a < b)

        def op_print():
            val = self.pop()
            if debug:
                return
            print(val)

        def op_print_dec():
            dec = int(str(self.pop()), 2)
            if debug:
                return
            print(dec)

        def op_pop():
            self.pop()

        def op_define_global():
            var_index = READ()
            var_name = chunk.constants[var_index]

            self.globals[str(var_name)] = self.pop()

        def op_set_global():
            var_index = READ()
            var_name = chunk.constants[var_index]

            if var_name not in self.globals:
                raise RuntimeError(f"Undefined variable '{var_name}'")

            self.globals[str(var_name)] = self.peek()

        def op_get_global():
            var_index = READ()
            var_name = chunk.constants[var_index]

            if var_name not in self.globals:
                raise RuntimeError(f"Undefined variable '{var_name}'")

            self.push(self.globals[str(var_name)])

        def op_set_local():
            slot = READ()
            self.stack[slot] = self.peek()

        def op_get_local():
            slot = READ()
            self.push(self.stack[slot])

        def op_jump():
            offset = READ_WORD()
            self.ip += offset

        def op_jump_if_false():
            offset = READ_WORD()
            is_falsey = not self.is_truthy(self.peek())
            self.ip += offset * is_falsey

        def op_loop():
            offset = READ_WORD()
            self.ip -= offset

        dispatch = {
            OpCode.OP_RETURN: op_return,
            OpCode.OP_CONSTANT: op_constant,
            OpCode.OP_NIL: op_nil,
            OpCode.OP_TRUE: op_true,
            OpCode.OP_FALSE: op_false,
            OpCode.OP_NOT: op_not,
            OpCode.OP_NEGATE: op_negate,
            OpCode.OP_ADD: op_add,
            OpCode.OP_SUBTRACT: op_subtract,
            OpCode.OP_MULTIPLY: op_multiply,
            OpCode.OP_DIVIDE: op_divide,
            OpCode.OP_MODULO: op_modulo,
            OpCode.OP_EQUAL: op_equal,
            OpCode.OP_GREATER: op_greater,
            OpCode.OP_LESS: op_less,
            OpCode.OP_PRINT: op_print,
            OpCode.OP_PRINT_DEC: op_print_dec,
            OpCode.OP_POP: op_pop,
            OpCode.OP_DEFINE_GLOBAL: op_define_global,
            OpCode.OP_SET_GLOBAL: op_set_global,
            OpCode.OP_GET_GLOBAL: op_get_global,
            OpCode.OP_SET_LOCAL: op_set_local,
            OpCode.OP_GET_LOCAL: op_get_local,
            OpCode.OP_JUMP: op_jump,
            OpCode.OP_JUMP_IF_FALSE: op_jump_if_false,
            OpCode.OP_LOOP: op_loop,
        }

        if debug:
            print(colored("== RUNTIME ==", "light_green"))

        while self.ip < len(chunk.bytes):
            debug_prefix = f"{self.ip:04d}"
            if debug:
                print(colored(f"{debug_prefix}|", "light_blue"), end=" ")

            byte = READ()
            handler = dispatch.get(byte)
            if handler is None:
                raise RuntimeError(f"UNKNOWN {byte}")

            result = handler()
            if result is _HALT:
                return

            if debug:
                print(colored(f"STACK {self.stack}", "light_blue"))
                if len(self.globals) > 0:
                    print(
                        colored(
                            f"{' ' * len(debug_prefix)}| GLOBALS {self.globals}",
                            "light_blue",
                        )
                    )

    # ---------- Helpers ---------- #

    def is_truthy(self, value):
        return not (value is None or value is False)

    def is_number(self, *stack):
        return all(type(value) is int or type(value) is float for value in stack)

    def is_string(self, *stack):
        return all(type(value) is str for value in stack)

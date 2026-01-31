from ploxb.Chunk import Chunk, OpCode

from typing import Union
from termcolor import colored

# Los valores que pueden almacenarse en el stack
StackValueType = Union[str, float, bool, None]


class VM:
    def __init__(self):
        # El instruction pointer
        # siempre apunta a la siguiente instrucción a ejecutar
        self._ip = 0

        # El stack de la máquina virtual
        # almacena todos los valores intermedios que se van produciendo
        self.stack: list[StackValueType] = []

        # Bindings de variables globales
        # todo lo que se almacena en el stack puede utilizarse como variable global
        self.globals: dict[str, StackValueType] = {}

    # Encapsulamos nuestro ip para cuando agreguemos funciones
    @property
    def ip(self):
        return self._ip

    @ip.setter
    def ip(self, new_ip):
        self._ip = new_ip

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

        if debug:
            print(colored("== RUNTIME ==", "light_green"))

        while self.ip < len(chunk.bytes):
            debug_prefix = f"{self.ip:04d}"
            if debug:
                print(colored(f"{debug_prefix}|", "light_blue"), end=" ")

            byte = READ()
            # TODO: creo que este match esta haciendo muchisimo heavy lifting
            # con overhead. si lo cambio a un dispatch table tal vez va
            # más rápido?
            match byte:
                # Final de la ejecución
                case OpCode.OP_RETURN:
                    if debug:
                        print(colored("THE END", "light_blue"))
                    if len(self.stack):
                        raise RuntimeError(
                            "Inconsistent Stack Height: should be empty at exit"
                        )
                    return

                # Instrucción de constante
                case OpCode.OP_CONSTANT:
                    # La instrucción de constante es "cargar" la constante en memoria:
                    # es solamente buscar el resultado en el pool de constantes del chunk
                    # y pushearlo al tope del stack
                    constant_index = READ()
                    constant_value = chunk.constants[constant_index]
                    self.push(constant_value)

                # Instrucciones de valores literales
                # Directamente pushean el valor al tope del stack
                case OpCode.OP_NIL:
                    self.push(None)
                case OpCode.OP_TRUE:
                    self.push(True)
                case OpCode.OP_FALSE:
                    self.push(False)

                # Instrucciones unarias
                # Popean el último valor del stack, hacen la operación,
                # y pushean el resultado
                case OpCode.OP_NOT:
                    value = self.pop()
                    self.push(not self.is_truthy(value))
                case OpCode.OP_NEGATE:
                    if not self.is_number(self.peek()):
                        raise RuntimeError(
                            f"Operand of OP_NEGATE must be a number, got: `{self.peek()}`"
                        )
                    value = self.pop()
                    self.push(-value)

                # Instrucciones binarias
                # Popean los últimos dos valores del stack, hacen la operación,
                # y pushean el resultado
                case OpCode.OP_ADD:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b) and not self.is_string(a, b):
                        raise RuntimeError(
                            f"Operands of OP_ADD must be numbers or strings, got: `{a}, {b}`"
                        )
                    self.push(a + b)
                case OpCode.OP_SUBTRACT:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_SUBTRACT must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a - b)
                case OpCode.OP_MULTIPLY:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_MULTIPLY must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a * b)
                case OpCode.OP_DIVIDE:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_DIVIDE must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a / b)
                case OpCode.OP_MODULO:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_MODULO must be numbers, got: `{a}, {b}`"
                        )
                    self.push(a % b)
                case OpCode.OP_EQUAL:
                    b, a = self.pop(), self.pop()
                    self.push(a == b)
                case OpCode.OP_GREATER:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_GREATER must be numbers, got: `{a} - {b}`"
                        )
                    self.push(a > b)
                case OpCode.OP_LESS:
                    b, a = self.pop(), self.pop()
                    if not self.is_number(a, b):
                        raise RuntimeError(
                            f"Operands of OP_LESS must be numbers, got: `{a} - {b}`"
                        )
                    self.push(a < b)

                # Instrucción de print
                # solamente popear el tope del stack y mostrarlo
                case OpCode.OP_PRINT:
                    if debug:
                        print(
                            colored(f"SCREEN OUTPUT {self.pop()}", "light_magenta"),
                        )
                        continue
                    else:
                        print(self.pop())

                # Instrucción de pop
                # solamente descartar el tope del stack
                case OpCode.OP_POP:
                    self.pop()

                # Instrucciones de variables globales
                # Definir una variable es obtener su nombre, su valor
                # y agregarlo a la tabla
                case OpCode.OP_DEFINE_GLOBAL:
                    # El nombre de la variable vive en el pool de constantes
                    var_index = READ()
                    var_name = chunk.constants[var_index]

                    # El último valor pusheado al stack es el
                    # valor de la variable
                    var_value = self.pop()

                    # Agregamos el binding a nuestra tabla de globales
                    self.globals[str(var_name)] = var_value

                # Asignar el valor es muy similar, pero no hace el pop final:
                # como las asignaciones son una expresión que devuelven el valor,
                # lo dejamos en la pila para que quien venga lo pueda usar
                case OpCode.OP_SET_GLOBAL:
                    var_index = READ()
                    var_name = chunk.constants[var_index]

                    if var_name not in self.globals:
                        raise RuntimeError(f"Undefined variable '{var_name}'")

                    # peek, no pop!
                    self.globals[str(var_name)] = self.peek()

                # Obtener el valor es simplemente agarrarlo de la tabla
                # y pushearlo al tope del stack
                case OpCode.OP_GET_GLOBAL:
                    var_index = READ()
                    var_name = chunk.constants[var_index]

                    if var_name not in self.globals:
                        raise RuntimeError(f"Undefined variable '{var_name}'")

                    var_value = self.globals[str(var_name)]
                    self.push(var_value)

                # Instrucciones de variables locales
                # Una asignación es tomar el tope del stack, que fue
                # la última expresión resuelta, y asignarla al slot
                # indicado en el stack (que viene como operando de la instrucción)
                case OpCode.OP_SET_LOCAL:
                    slot = READ()
                    self.stack[slot] = self.peek()

                # Obtener el valor es solamente re-pushearlo al stack desde su slot
                # indicado, al tope
                case OpCode.OP_GET_LOCAL:
                    slot = READ()
                    var_value = self.stack[slot]
                    self.push(var_value)

                # Instrucciones de saltos
                # Salto incondicional
                case OpCode.OP_JUMP:
                    offset = READ_WORD()
                    self.ip += offset
                # Salto solo si el tope del stack es falso
                case OpCode.OP_JUMP_IF_FALSE:
                    offset = READ_WORD()
                    is_falsey = not self.is_truthy(self.peek())
                    self.ip += offset * is_falsey
                # Salta hacia atrás N instrucciones
                case OpCode.OP_LOOP:
                    offset = READ_WORD()
                    self.ip -= offset

                case _:
                    raise RuntimeError(f"UNKNOWN {byte}")

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

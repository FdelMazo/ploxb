from ploxb.Chunk import OpCode
from ploxb.Function import Function, CallFrame, Closure, ClosureUpValue

from typing import Union
from termcolor import colored

# Los valores que pueden almacenarse en el stack
StackValueType = Union[str, float, bool, Closure, None]


class VM:
    def __init__(self):
        self.frames: list[CallFrame] = []
        self.current_frame: CallFrame | None = None

        # El stack de la máquina virtual
        # almacena todos los valores intermedios que se van produciendo
        self.stack: list[StackValueType] = []

        # Bindings de variables globales
        # todo lo que se almacena en el stack puede utilizarse como variable global
        self.globals: dict[str, StackValueType] = {}
        self.open_upvalues: list[ClosureUpValue] = []

    # Encapsulamos nuestro ip para cuando agreguemos funciones
    @property
    def ip(self):
        if not self.current_frame:
            raise RuntimeError("DETACHED VM")
        return self.current_frame.ip

    @ip.setter
    def ip(self, new_ip):
        if not self.current_frame:
            raise RuntimeError("DETACHED VM")
        self.current_frame.ip = new_ip

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

    def run(self, function: Function, debug=False):
        main_script = Closure(function)
        self.push(main_script)

        frame = CallFrame(main_script, 0)
        self.frames.append(frame)
        self.current_frame = self.frames[-1]

        if debug:
            print(colored("== RUNTIME ==", "light_green"))

        while self.frames:
            chunk = self.current_frame.closure.function.chunk

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

            debug_prefix = f"{'+' * (len(self.frames) - 1)}{self.ip:04d}"
            if debug:
                print(colored(f"{debug_prefix}|", "light_blue"), end=" ")

            byte = READ()
            # TODO: creo que este match esta haciendo muchisimo heavy lifting
            # con overhead. si lo cambio a un dispatch table tal vez va
            # más rápido?
            match byte:
                # Final de la ejecución
                case OpCode.OP_RETURN:
                    result = self.pop()
                    finished_frame = self.frames.pop()
                    self.close_upvalues(finished_frame.stack_slot)

                    if not self.frames:
                        self.pop()

                        if debug:
                            print(colored("THE END", "light_blue"))

                        if len(self.stack):
                            raise RuntimeError(
                                "Inconsistent Stack Height: should be empty at exit"
                            )
                        return

                    self.stack = self.stack[: finished_frame.stack_slot]
                    self.push(result)
                    self.current_frame = self.frames[-1]

                    if debug:
                        print(
                            colored(
                                f"EXITING CALLFRAME {finished_frame.closure.function}",
                                "light_magenta",
                            )
                        )
                        continue

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
                    self.stack[self.current_frame.stack_slot + slot] = self.peek()

                # Obtener el valor es solamente re-pushearlo al stack desde su slot
                # indicado, al tope
                case OpCode.OP_GET_LOCAL:
                    slot = READ()
                    var_value = self.stack[self.current_frame.stack_slot + slot]
                    self.push(var_value)

                # Instrucciones de upvalues
                case OpCode.OP_GET_UPVALUE:
                    slot = READ()
                    upvalue = self.current_frame.closure.upvalues[slot]
                    if upvalue.closed is not None:
                        self.push(upvalue.closed)
                    else:
                        self.push(self.stack[upvalue.location])
                case OpCode.OP_SET_UPVALUE:
                    slot = READ()
                    upvalue = self.current_frame.closure.upvalues[slot]
                    if upvalue.closed is not None:
                        upvalue.closed = self.peek()
                    else:
                        self.stack[upvalue.location] = self.peek()
                case OpCode.OP_CLOSE_UPVALUE:
                    self.close_upvalues(len(self.stack) - 1)
                    self.pop()

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

                # Instrucciones de funciones
                # Llamados a funciones
                case OpCode.OP_CALL:
                    arg_count = READ()
                    closure = self.peek(arg_count)

                    if not isinstance(closure, Closure):
                        raise RuntimeError("Can only call functions inside closures")

                    if closure.function.arity != arg_count:
                        raise RuntimeError(
                            f"Expected {closure.function.arity} arguments, got {arg_count}"
                        )

                    fn_callframe = CallFrame(closure, len(self.stack) - arg_count - 1)
                    self.frames.append(fn_callframe)
                    self.current_frame = self.frames[-1]

                    if debug:
                        print(
                            colored(
                                f"ENTERING CALLFRAME {closure.function}",
                                "light_magenta",
                            )
                        )
                        continue

                case OpCode.OP_CLOSURE:
                    fun_index = READ()
                    fun = chunk.constants[fun_index]
                    closure = Closure(fun)
                    self.push(closure)

                    for _ in range(fun.upvalue_count):
                        is_local = READ() == 1
                        index = READ()
                        if is_local:
                            closure.upvalues.append(
                                self.capture_upvalue(
                                    self.current_frame.stack_slot + index
                                )
                            )
                        else:
                            closure.upvalues.append(
                                self.current_frame.closure.upvalues[index]
                            )

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

    # ---------- Helpers de Closures ---------- #

    def capture_upvalue(self, location: int) -> ClosureUpValue:
        for upvalue in self.open_upvalues:
            if upvalue.location and upvalue.location == location:
                return upvalue

        created_upvalue = ClosureUpValue(location)

        insert_pos = 0
        for i, upvalue in enumerate(self.open_upvalues):
            if not upvalue.location or upvalue.location < location:
                insert_pos = i
                break
        else:
            insert_pos = len(self.open_upvalues)

        self.open_upvalues.insert(insert_pos, created_upvalue)
        return created_upvalue

    def close_upvalues(self, last: int):
        i = 0
        while i < len(self.open_upvalues):
            upvalue = self.open_upvalues[i]
            if upvalue.location and upvalue.location >= last:
                upvalue.closed = self.stack[upvalue.location]
                upvalue.location = None
                i += 1
            else:
                break

    # ---------- Helpers ---------- #

    def is_truthy(self, value):
        return not (value is None or value is False)

    def is_number(self, *stack):
        return all(type(value) is int or type(value) is float for value in stack)

    def is_string(self, *stack):
        return all(type(value) is str for value in stack)

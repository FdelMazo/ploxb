from ploxb.Chunk import OpCode
from ploxb.Function import Function, CallFrame, Closure

from typing import Union
from termcolor import colored

# Los valores que pueden almacenarse en el stack
StackValueType = Union[str, float, bool, Closure, None]


class VM:
    def __init__(self):
        # A medida que se van llamando funciones, se van apilando
        # callframes acá, lo cual sirve para que al retornar de una función
        # sepamos a dónde volver
        self.frames: list[CallFrame] = []

        # El stack de la máquina virtual
        # almacena todos los valores intermedios que se van produciendo
        self.stack: list[StackValueType] = []

        # Bindings de variables globales
        # todo lo que se almacena en el stack puede utilizarse como variable global
        self.globals: dict[str, StackValueType] = {}

        # Variables locales que fueron capturadas por closures y siguen abiertas
        # (o sea, por ahora pueden ser accedidas desde el stack)
        self.open_upvalues: list = []

    # El frame actual es el tope de la pila de callframes
    @property
    def current_frame(self):
        return self.frames[-1] if self.frames else None

    # Devuelve el ip del frame actual
    @property
    def ip(self):
        if not self.current_frame:
            raise RuntimeError("DETACHED VM")
        return self.current_frame.ip

    # Setea el ip del frame actual
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
        # Lo primero que hacemos en la ejecución es crear el
        # primer call frame, el del main script, apuntando al
        # índice 0 del stack, donde vive el clojure del main script
        main_script = Closure(function)
        self.push(main_script)
        self.frames.append(CallFrame(main_script, 0))

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
                # Retorno de un callframe
                case OpCode.OP_RETURN:
                    # Obtenemos el resultado de la función, en el tope del stack
                    # antes de descartar el stack del callframe enteramente
                    result = self.pop()

                    # Sacamos el frame actual
                    finished_frame = self.frames.pop()

                    # Cerramos todos los upvalues que hayan quedado abiertos en este frame
                    self.close_upvalues(finished_frame.stack_slot)

                    # Si me quedé sin frames, estoy en el final de la ejecución
                    if not self.frames:
                        # Popeo el último valor del stack (el closure del main script)
                        self.pop()

                        # El stack me debería haber quedado vacío al finalizar la ejecución
                        if len(self.stack):
                            raise RuntimeError(
                                "Inconsistent Stack Height: should be empty at exit"
                            )

                        if debug:
                            print(colored("THE END", "light_blue"))

                        # Fin
                        return

                    # Reseteamos el stack a como estaba antes de llamar a la función
                    # y pusheamos el resultado de la función al nuevo tope
                    self.stack = self.stack[: finished_frame.stack_slot]
                    self.push(result)

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
                    # Ahora, el valor de las variables se va a buscar en el stack
                    # relativo al puntero base del callframe actual
                    self.stack[self.current_frame.stack_slot + slot] = self.peek()

                # Obtener el valor es solamente re-pushearlo al stack desde su slot
                # indicado, al tope
                case OpCode.OP_GET_LOCAL:
                    slot = READ()
                    # Al igual que en SET_LOCAL, el índice es relativo al frame actual
                    var_value = self.stack[self.current_frame.stack_slot + slot]
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

                # Instrucciones de funciones
                # Llamados a funciones
                case OpCode.OP_CALL:
                    # Obtenemos la cantidad de argumentos de la función
                    arg_count = READ()
                    # La función en sí debería estar a N posiciones del tope del stack
                    closure = self.peek(arg_count)

                    # Si el llamado no es una función, levantamos un error
                    if not isinstance(closure, Closure):
                        raise RuntimeError(
                            f"Cannot call non-callable object: `{closure}`"
                        )

                    # Si no se cumple la aridad, levantamos un error
                    if closure.function.arity != arg_count:
                        raise RuntimeError(
                            f"Expected {closure.function.arity} arguments, got {arg_count}"
                        )

                    # Ahora que llamamos a una función, nos adentramos en un nuevo callframe
                    fn_ip = len(self.stack) - arg_count - 1
                    fn_callframe = CallFrame(closure, fn_ip)

                    # Con solo ponerlo en el tope de la pila, ya pasa a ser nuestro frame actual
                    self.frames.append(fn_callframe)

                    if debug:
                        print(
                            colored(
                                f"ENTERING CALLFRAME {closure.function}",
                                "light_magenta",
                            )
                        )
                        continue
                # Declaración de funciones:
                # dada la función cruda, en el pool de constantes,
                # vamos a instanciar un closure
                case OpCode.OP_CLOSURE:
                    # Tomamos la función en si y la usamos como base para el closure
                    fun_index = READ()
                    fun = chunk.constants[fun_index]
                    closure = Closure(fun)

                    # Parecido a OP_CONSTANT: "cargamos en memoria" la función
                    # vemos un valor en el pool de constantes y lo empujamos al stack.
                    self.push(closure)

                    # Tomamos todos los upvalues que utilizará la función, viendo el
                    # count que conocemos de su compilación, y tomando los operandos
                    for _ in range(fun.upvalue_count):
                        # El primer byte indica que tipo de upvalue es:
                        # local   -> es una variable local del enclosing
                        # upvalue -> es un upvalue del enclosing

                        # El segundo byte es el slot en sí, que puede ser
                        # del stack del enclosing (si es local) o de sus upvalues (si es upvalue)
                        is_local, slot = READ() == 1, READ()
                        if is_local:
                            # Si es local en el padre, la capturamos desde su valor en el stack
                            stack_index = self.current_frame.stack_slot + slot
                            upvalue = self.capture_upvalue(stack_index)
                        else:
                            # Si es un upvalue, lo tomamos de la lista de upvalues del closure padre
                            upvalue = self.current_frame.closure.upvalues[slot]

                        # Una vez que tenemos el upvalue, lo agregamos al nuevo closure
                        closure.upvalues.append(upvalue)

                # Instrucciones de upvalues
                # Obtener el valor de un upvalue
                case OpCode.OP_GET_UPVALUE:
                    # Toma el slot del upvalue, busca el valor en la lista de
                    # upvalues y lo pushea al stack
                    slot = READ()
                    upvalue = self.current_frame.closure.upvalues[slot]

                    # Si la variable ya esta cerrada, tomamos el valor que esta
                    # guardado internamente.
                    # Si no esta cerrada, todavía tenemos acceso a ella en el stack
                    if upvalue.closed_value is not None:
                        self.push(upvalue.closed_value)
                    else:
                        self.push(self.stack[upvalue.stack_index])
                # Asignarle un nuevo valor a un upvalue
                case OpCode.OP_SET_UPVALUE:
                    # Toma el slot del upvalue, busca el valor en la lista de
                    # upvalues y lo pushea al stack
                    slot = READ()
                    upvalue = self.current_frame.closure.upvalues[slot]

                    # El mismo juego que en el getter
                    if upvalue.closed_value is not None:
                        upvalue.closed_value = self.peek()
                    else:
                        self.stack[upvalue.stack_index] = self.peek()
                # Cerrar un upvalue
                case OpCode.OP_CLOSE_UPVALUE:
                    # Una vez terminada la ejecución de la función que creó
                    # la variable, si la variable fue capturada y sigue siendo
                    # utilizada por un closure, tenemos que "cerrarla":
                    # - Guardarnos su valor actual
                    # - Sacarla del stack
                    self.close_upvalues(len(self.stack) - 1)
                    self.pop()

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

    # ---------- Helpers de Closures y Upvalues ---------- #

    # Capturar un upvalue es asegurarse de que exista en la lista de upvalues abiertos
    # ya sea devolviéndolo si ya está, o creándolo
    def capture_upvalue(self, stack_index: int):
        # Si el valor a capturar ya está en la lista de upvalues abiertos,
        # lo devolvemos
        for upvalue in self.open_upvalues:
            if upvalue.stack_index == stack_index:
                return upvalue

        # Si no, creamos uno nuevo, con el stack index en el que vive
        created_upvalue = Closure.Capture(stack_index)

        # Lo insertamos en la lista de upvalues abiertos, manteniendo el orden
        # por stack index (de menor a mayor)
        insert_pos = 0
        for i, upvalue in enumerate(self.open_upvalues):
            if not upvalue.stack_index or upvalue.stack_index < stack_index:
                insert_pos = i
                break
        else:
            insert_pos = len(self.open_upvalues)

        self.open_upvalues.insert(insert_pos, created_upvalue)
        return created_upvalue

    # Cerrar un upvalue es sacarlo de la lista de upvalues abiertos, que viven en el stack
    # y pasar su valor a que viva internamente dentro del closure
    def close_upvalues(self, last: int):
        # Dado un stack index, cerramos todos los upvalues
        # que vivan en posiciones iguales o mayores a ese índice
        while self.open_upvalues:
            upvalue = self.open_upvalues[0]
            if upvalue.stack_index is not None and upvalue.stack_index >= last:
                # Tomamos el valor del stack y lo guardamos internamente
                # y le sacamos la referencia al stack
                upvalue.closed_value = self.stack[upvalue.stack_index]
                upvalue.stack_index = None

                # Lo sacamos de la lista de upvalues abiertos
                self.open_upvalues.pop(0)
            else:
                break

    # ---------- Helpers ---------- #

    def is_truthy(self, value):
        return not (value is None or value is False)

    def is_number(self, *stack):
        return all(type(value) is int or type(value) is float for value in stack)

    def is_string(self, *stack):
        return all(type(value) is str for value in stack)

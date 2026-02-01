class Local:
    # Una variable local es su nombre, cuan anidada está
    # y saber si ya fue inicializada.
    # También, necesitamos una referencia a si fue capturada
    # para no eliminarla del stack, (es decir, queremos saber
    # si la utiliza una función interna a esta).
    def __init__(self, name: str, depth: int):
        self.name = name
        self.depth = depth
        self.initialized = False
        self.is_captured = False

    def __repr__(self):
        return f"{self.name}"


class Upvalue:
    # Un upvalue es una variable local externa: variables que no son
    # locales a la función, pero que fueron capturadas por una closure.
    # Un upvalue es el índice de la variable sobre el stack
    # y si es una variable local del contexto padre o un upvalue
    # ahí también
    def __init__(self, index: int, is_local: bool):
        self.index = index
        self.is_local = is_local


class CompilerContext:
    def __init__(self):
        # El contexto del compilador se ocupa
        # de orquestar que nivel de anidación esta
        # siendo compilada, y que variables contiene.

        # scope_depth = 0 -> scope global
        # scope_depth = 1 -> un scope local anidado
        self.scope_depth = 0

        # Las variables locales se almacenan en el mismo
        # orden que son declaradas, funcionando efectivamente como
        # un stack: cuando obtengamos el índice de `self.locals`,
        # lo vamos a poder usar como índice del stack de la VM
        self.locals: list[Local] = []

        # Los upvalues también se almacenan en el orden en que
        # son referenciados en la función
        self.upvalues: list[Upvalue] = []

        # Reservamos siempre el slot 0 de las variables locales
        # para el valor "self" de la función, para tener un puntero
        # referencia desde el cual acceder a las variables locales
        self.declare("")
        self.mark_initialized()

    def begin_scope(self):
        self.scope_depth += 1

    def end_scope(self):
        self.scope_depth -= 1

        # Al terminar un scope, tenemos que devolver todas las variables
        # que contenía, para que el compilador pueda eliminarlas o cerrarlas
        removed: list[Local] = []
        while self.locals and self.locals[-1].depth > self.scope_depth:
            removed.append(self.locals.pop())
        return removed

    def declare(self, name: str):
        self.locals.append(Local(name, self.scope_depth))

    def mark_initialized(self):
        # Marca la última variable declarada como inicializada
        # Sirve para atrapar referencias en su misma declaración
        # (es decir, `var x = x` tiene que devolver error)
        self.locals[-1].initialized = True

    def add_upvalue(self, index: int, is_local: bool):
        # Simplemente agrega una nueva entrada a la lista de upvalues
        self.upvalues.append(Upvalue(index, is_local))
        return len(self.upvalues) - 1

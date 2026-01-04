from functools import reduce


class Local:
    # Una variable local es su nombre, cuan anidada está
    # y saber si ya fue inicializada
    def __init__(self, name: str, depth: int):
        self.name = name
        self.depth = depth
        self.initialized = False

    def __repr__(self):
        return f"{self.name}"


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
        self.locals = []

    def begin_scope(self):
        self.scope_depth += 1

    def end_scope(self):
        self.scope_depth -= 1

        # Al terminar un scope, tenemos que eliminar todas las variables
        # que contenía
        vars_removed = 0
        while self.locals and self.locals[-1].depth > self.scope_depth:
            vars_removed += 1
            self.locals.pop()
        return vars_removed

    def declare(self, name: str):
        if self.scope_depth == 0:
            # No debería pasar nunca!!
            raise SyntaxError("Declaring a global variable in the local ")
        self.locals.append(Local(name, self.scope_depth))

    def mark_initialized(self):
        # Marca la última variable declarada como inicializada
        # Sirve para atrapar referencias en su misma declaración
        # (es decir, `var x = x` tiene que devolver error)
        self.locals[-1].initialized = True

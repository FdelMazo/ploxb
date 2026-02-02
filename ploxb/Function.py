from ploxb.Chunk import Chunk
from typing import TYPE_CHECKING, Optional

from termcolor import colored

if TYPE_CHECKING:
    from ploxb.VM import StackValueType


# Las funciones crudas son como cualquier otro literal:
# info que se sabe en tiempo de compilación y se puede pasar entre la VM
# y el compilador sin problema.
class Function:
    def __init__(self, name: str | None):
        # El nombre de la función, o nulo si es el main script
        self.name = name
        # El chunk de bytecode de la función
        self.chunk = Chunk()
        # Cantidad de argumentos que recibe la función
        self.arity = 0
        # Cantidad de upvalues que captura la función
        self.upvalue_count = 0

    def __repr__(self):
        if self.name is None:
            return "<script>"
        return f"<fn {self.name}()>"

    def dis(self):
        if not self.name:
            print(colored("== COMPILETIME ==", "light_green"))
            print(colored("= SCRIPT =", "light_green"))
        else:
            print(colored(f"= FUNCTION {self.name} =", "light_green"))
        self.chunk.dis()
        for c in self.chunk.constants:
            if isinstance(c, Function):
                c.dis()


# La declaración de una función tiene un componente de runtime: captura variables del
# scope padre en la que fue declarada.
# En un closure nos guardamos esa información: la función cruda, y las variables capturadas
class Closure:
    # Un capture es un upvalue en tiempo de ejecución:
    # Cuando una declaración captura una variable externa local (un upvalue), tiene que tener todo el
    # tiempo acceso a su valor actual, por lo que se la guarda internamente (ya sea directa o indirectamente).
    class Capture:
        # Una variable capturada puede estar abierta o cerrada:
        # - Abierta: si la función que instanció la variable sigue en ejecución, la variable sigue viviendo en el stack, por lo
        # que nos tenemos que guardar el índice para accederla, en `stack_index`
        # - Cerrada: Si la función original terminó su ejecución, necesitamos seguir teniendo acceso al valor, por lo que
        # la variable se guarda internamente (una suerte de heap)

        def __init__(self, stack_index: int | None):
            # Si la variable esta abierta -> tiene stack_index
            # Si la variable esta cerrada -> tiene closed_value

            # Si esta definido, es el índice sobre el stack de la VM
            self.stack_index = stack_index
            # Si la variable ya fue cerrada, el valor queda acá
            self.closed_value: Optional["StackValueType"] = None

    def __init__(self, function: Function):
        self.function = function
        self.upvalues: list["Closure.Capture"] = []

    def __repr__(self):
        return str(self.function)


# Las variables ya no tienen un valor absoluto dentro del stack de la VM,
# pero sí un índice relativo al comienzo de la función actual.
# Con un callframe podemos encapsular cada invocación de una función,
# guardandonos una referencia al slot en el que comienza, para que cada
# vez que referenciemos una variable local, lo utilicemos en la resolución
class CallFrame:
    def __init__(self, closure: Closure, stack_slot: int):
        self.closure = closure
        self.ip = 0
        self.stack_slot = stack_slot

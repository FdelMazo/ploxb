from enum import IntEnum, auto
from ploxb.Token import ValueType


class OpCode(IntEnum):
    # Instrucción con operandos:
    # después del opcode, hay un byte que es el índice de la constante referenciada
    OP_CONSTANT = auto()
    # Todo el resto son operaciones sin operandos.
    # Operan directamente sobre el tope del stack de la máquina virtual.
    OP_NIL = auto()
    OP_TRUE = auto()
    OP_FALSE = auto()
    OP_RETURN = auto()
    OP_NEGATE = auto()
    OP_ADD = auto()
    OP_SUBTRACT = auto()
    OP_MULTIPLY = auto()
    OP_DIVIDE = auto()
    OP_NOT = auto()
    OP_EQUAL = auto()
    OP_GREATER = auto()
    OP_LESS = auto()


class Chunk(object):
    def __init__(self):
        # Todos los bytes del chunk.
        # Hay dos tipos de bytes:
        # - Instrucciones de bytecode (OpCode)
        # - Referencias a constantes (índices en el pool de constantes)
        self.bytes: bytearray = bytearray()

        # Pool de constantes
        self.constants: list[ValueType] = []

    # Escribe un byte al chunk
    def write(self, byte: int):
        self.bytes.append(byte)

    # Agrega una constante al pool y devuelve el índice
    def add_constant(self, value: ValueType):
        self.constants.append(value)
        return len(self.constants) - 1

    # Desensambla el chunk (muchos bytes) para imprimirlo en un formato legible (el nombre de las instrucciones)
    # (es la operación inversa a ensamblar instrucciones assembly a código máquina)
    def dis(self):
        print(f"== CHUNK ==")
        i = 0
        while i < len(self.bytes):
            byte = self.bytes[i]
            print(f"{i:04d}", end=" ")
            match byte:
                case OpCode.OP_CONSTANT:
                    constant_index = self.bytes[i + 1]
                    constant_value = self.constants[constant_index]
                    print(f"OP_CONSTANT<{constant_value}>")
                    # Hay que saltar el byte de la constante!
                    i += 2
                # All simple instructions
                case _:
                    print(OpCode(byte).name)
                    i += 1
        print(f"== CHUNK ==")

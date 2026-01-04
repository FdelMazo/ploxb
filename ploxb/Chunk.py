from enum import IntEnum, auto
from typing import Union

ConstantType = Union[str, float]


class OpCode(IntEnum):
    # Instrucciones sin operandos:
    # operan directamente sobre el tope del stack de la máquina virtual.
    OP_NIL = auto()
    OP_TRUE = auto()
    OP_FALSE = auto()
    OP_RETURN = auto()
    OP_PRINT = auto()
    OP_POP = auto()
    OP_NEGATE = auto()
    OP_ADD = auto()
    OP_SUBTRACT = auto()
    OP_MULTIPLY = auto()
    OP_DIVIDE = auto()
    OP_MODULO = auto()
    OP_NOT = auto()
    OP_EQUAL = auto()
    OP_GREATER = auto()
    OP_LESS = auto()

    # Instrucciones con operandos: constantes
    # después del opcode, hay un byte que es el índice de la constante referenciada
    OP_CONSTANT = auto()
    OP_DEFINE_GLOBAL = auto()
    OP_GET_GLOBAL = auto()
    OP_SET_GLOBAL = auto()

    # Instrucciones con operandos: slots del stack
    # después del opcode, hay un byte que es el índice de la variable
    # sobre el stack de la VM (no sobre el pool de constantes!)
    OP_GET_LOCAL = auto()
    OP_SET_LOCAL = auto()

    # Instrucciones con operandos: saltos
    # después del opcode, hay dos bytes que forman un entero de 16 bits
    # que es el offset de cuanto debe saltar el ip
    OP_LOOP = auto()
    OP_JUMP_IF_FALSE = auto()
    OP_JUMP = auto()


class Chunk:
    def __init__(self):
        # Una secuencia de todos los bytes del chunk.
        # Hay distintos tipos de bytes:
        # - Instrucciones de bytecode (OpCode)
        # - Operandos de las instrucciones:
        #   - 1 byte: Referencias a constantes (índices en el pool de constantes)
        #   - 1 byte: Referencias a valores de variables locales (índices en el stack de la VM)
        #   - 2 bytes: Cuantas instrucciones saltar al controlar el flujo
        self.bytes: bytearray = bytearray()

        # Pool de constantes:
        # Almacena números, cadenas y nombres de variables globales
        self.constants: list[ConstantType] = []

    # Escribe un byte al chunk
    def write(self, byte: int):
        self.bytes.append(byte)

    # Agrega una constante al pool y devuelve el índice
    def add_constant(self, value: ConstantType):
        self.constants.append(value)
        return len(self.constants) - 1

    # Desensambla el chunk (secuencia de bytes con distinto significado)
    # para imprimirlo en un formato legible (el nombre de las instrucciones)
    # (es la operación inversa a ensamblar instrucciones assembly a código máquina)
    def dis(self):
        print(f"== COMPILETIME ==")
        i = 0
        while i < len(self.bytes):
            byte = self.bytes[i]
            print(f"{i:04d}|", end=" ")
            match byte:
                case (
                    OpCode.OP_CONSTANT
                    | OpCode.OP_DEFINE_GLOBAL
                    | OpCode.OP_GET_GLOBAL
                    | OpCode.OP_SET_GLOBAL
                ):
                    # Instrucciones con operandos: constantes
                    constant_index = self.bytes[i + 1]
                    constant_value = self.constants[constant_index]
                    if byte == OpCode.OP_CONSTANT and type(constant_value) is str:
                        constant_value = f"'{constant_value}'"
                    print(f"{OpCode(byte).name}<{constant_value}>")
                    i += 2

                case OpCode.OP_GET_LOCAL | OpCode.OP_SET_LOCAL:
                    # Instrucciones con operandos: slots
                    var_index = self.bytes[i + 1]
                    print(f"{OpCode(byte).name}<@{var_index}>")
                    i += 2

                case OpCode.OP_JUMP | OpCode.OP_JUMP_IF_FALSE | OpCode.OP_LOOP:
                    # Instrucciones con operandos: saltos
                    highbyte, lowbyte = self.bytes[i + 1], self.bytes[i + 2]
                    offset = (highbyte << 8) | lowbyte
                    sign = -1 if byte == OpCode.OP_LOOP else 1
                    jump_to = i + 3 + (offset * sign)
                    print(f"{OpCode(byte).name}<{jump_to:04d}>")
                    i += 3

                case _:
                    # Instrucciones sin operandos
                    print(OpCode(byte).name)
                    i += 1

        print(f"CONST {self.constants}")

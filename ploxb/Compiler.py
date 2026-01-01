from enum import IntEnum
from functools import total_ordering
from ploxb.Scanner import Token, TokenType
from ploxb.Chunk import Chunk, OpCode


@total_ordering
class Precedence(IntEnum):
    # Ordenados de menor a mayor precedencia!
    PREC_NONE = 0
    PREC_ASSIGNMENT = 1
    PREC_OR = 2
    PREC_AND = 3
    PREC_EQUALITY = 4
    PREC_COMPARISON = 5
    PREC_TERM = 6
    PREC_FACTOR = 7
    PREC_UNARY = 8
    PREC_CALL = 9
    PREC_PRIMARY = 10

    # Permite hacer comparaciones entre precedencias
    def __lt__(self, other):
        return self.value < other.value

    def __eq__(self, other):
        return self.value == other.value

    # Obtiene la siguiente precedencia (mayor a la actual)
    def next(self):
        members = list(type(self))
        index = members.index(self)
        return members[index + 1] if index + 1 < len(members) else None


# fmt: off
# Es muy flexible! Agregar operadores es una fila nueva, y cambiár la gramática es solamente editar una celda
# TODO: puedo matar las que tienen todo none? para mostrar que esto es solo expresiones?
PRATT: dict[TokenType, tuple[str | None, str | None, Precedence, Precedence]] = {
    # TokenType              (prefix_fn,   infix_fn,   prefix_precedence,     infix_precedence)
    TokenType.LEFT_PAREN:    ("grouping",  None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.RIGHT_PAREN:   (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.LEFT_BRACE:    (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.RIGHT_BRACE:   (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.SEMICOLON:     (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.NUMBER:        ("value",     None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.STRING:        ("value",     None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.NIL:           ("literal",   None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.FALSE:         ("literal",   None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.TRUE:          ("literal",   None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.MINUS:         ("unary",     "binary",   Precedence.PREC_UNARY, Precedence.PREC_TERM),
    TokenType.PLUS:          (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_TERM),
    TokenType.STAR:          (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_FACTOR),
    TokenType.SLASH:         (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_FACTOR),
    TokenType.BANG:          ("unary",     None,       Precedence.PREC_UNARY, Precedence.PREC_NONE),
    TokenType.BANG_EQUAL:    (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_EQUALITY),
    TokenType.EQUAL:         (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.EQUAL_EQUAL:   (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_EQUALITY),
    TokenType.GREATER:       (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.GREATER_EQUAL: (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.LESS:          (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.LESS_EQUAL:    (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.AND:           (None,        "logic_and",Precedence.PREC_NONE,  Precedence.PREC_AND),
    TokenType.OR:            (None,        "logic_or", Precedence.PREC_NONE,  Precedence.PREC_OR),
    TokenType.IF:            (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.ELSE:          (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.WHILE:         (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.FOR:           (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.FUN:           (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.COMMA:         (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.RETURN:        (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.VAR:           (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.IDENTIFIER:    ("variable",  None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.PRINT:         (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.EOF:           (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
}
# fmt: on


class Local:
    def __init__(self, name: str):
        self.name = name
        self.depth = None


class CompilerContext:
    def __init__(self):
        self.locals = []
        self.scope_depth = 0

    def begin_scope(self):
        self.scope_depth += 1

    def end_scope(self, on_pop=lambda: None):
        self.scope_depth -= 1
        while self.locals and self.locals[-1].depth == self.scope_depth:
            on_pop()
            self.locals.pop()

    def define(self, name: str):
        self.locals.append(Local(name))

    def initialize_last(self):
        self.locals[-1].depth = self.scope_depth


class Compiler:
    def __init__(self, tokens: list[Token]):
        # Todos los tokens a compilar
        self.tokens = tokens
        # El índice del token actual
        self.current = 0
        # El chunk resultante de la compilación
        self.chunk = Chunk()
        self.context = CompilerContext()

    # ---------- Core ---------- #

    # Agregar bytes al chunk
    def emit(self, *bytes: int):
        for byte in bytes:
            self.chunk.write(byte)

    # Compila una expresión completa, y emite un return final para tener de centinela
    def compile(self):
        while not self._is_at_end():
            self.statement()
        self.emit(OpCode.OP_RETURN)
        return self.chunk

    # Parsea una expresión de una precedencia mayor o igual a la pasada.
    # Es el core del algoritmo de Pratt Parsing.
    def parse(self, precedence: Precedence):
        # Usando - 5 + 3 de ejemplo

        # Consume: -
        token = self._advance()

        # Si llamamos a `parse` con un token que no es un prefijo,
        # entonces fue mal llamada. Directamente lanzamos un error
        rule = self.get_rule(token.token_type)
        if rule["prefix_fn"] is None:
            raise SyntaxError(f"Unexpected token: {token}")

        prefix_fn_name = PRATT[token.token_type][0]
        can_assign = precedence <= Precedence.PREC_ASSIGNMENT
        if prefix_fn_name == "variable":
            self.variable(can_assign)
        else:
            # Llama a unary, que compila el - y el 5
            rule["prefix_fn"]()

        # Ya compilamos el - 5, nos queda el + 3
        # Ahora, nos fijamos si estamos parados en una expresión infija
        while not self._is_at_end():
            # Lee: +
            next_token = self._lookahead()
            next_rule = self.get_rule(next_token.token_type)

            # Nos aseguramos de no capturar operandos que no pertenecen
            # a este nivel de precedencia
            if precedence > next_rule["infix_precedence"]:
                break

            # Consume: +
            self._advance()
            # Llama a binary que consume el + y el 3
            # Y llega al final de la expresión
            next_rule["infix_fn"]()

            if can_assign and self._match(TokenType.EQUAL):
                raise SyntaxError("Invalid assignment target.")

    # ---------- Parsers de Statements  ---------- #

    def statement(self):
        if self._match(TokenType.VAR):
            self.var_declaration()
        elif self._match(TokenType.PRINT):
            self.print_statement()
        elif self._match(TokenType.IF):
            self.if_statement()
        elif self._match(TokenType.WHILE):
            self.while_statement()
        elif self._match(TokenType.LEFT_BRACE):
            self.context.begin_scope()
            self.block()
            self.context.end_scope(lambda: self.emit(OpCode.OP_POP))
        else:
            self.expression_statement()

    def var_declaration(self):
        if not self._match(TokenType.IDENTIFIER):
            raise SyntaxError(
                f"Expected variable name after 'var', got `{self._lookahead()}` instead"
            )

        var_name = self._previous()

        if self._match(TokenType.EQUAL):
            self.expression()
        else:
            self.emit(OpCode.OP_NIL)

        if not self._match(TokenType.SEMICOLON):
            raise SyntaxError(
                f"Expected ';' after variable declaration, got `{self._lookahead()}` instead"
            )

        if self.context.scope_depth > 0:
            for local in reversed(self.context.locals):
                if local.depth and local.depth < self.context.scope_depth:
                    break
                if local.name == var_name.lexeme:
                    raise SyntaxError(
                        f"Variable with name `{var_name.lexeme}` already declared in this scope"
                    )

            self.context.define(var_name.lexeme)
            self.context.initialize_last()
            return

        self.emit(OpCode.OP_DEFINE_GLOBAL)
        constant_index = self.chunk.add_constant(var_name.lexeme)
        self.emit(constant_index)

    def block(self):
        while (
            not self._is_at_end()
            and not self._lookahead().token_type == TokenType.RIGHT_BRACE
        ):
            self.statement()

        if not self._match(TokenType.RIGHT_BRACE):
            raise SyntaxError(
                f"Expected '}}' after block, got `{self._lookahead()}` instead"
            )

    def if_statement(self):
        if not self._match(TokenType.LEFT_PAREN):
            raise SyntaxError(
                f"Expected '(' after 'if', got `{self._lookahead()}` instead"
            )

        self.expression()

        if not self._match(TokenType.RIGHT_PAREN):
            raise SyntaxError(
                f"Expected ')' after condition, got `{self._lookahead()}` instead"
            )

        self.emit(OpCode.OP_JUMP_IF_FALSE)
        jump_offset = len(self.chunk.bytes)
        self.emit(0xFF)
        self.emit(0xFF)

        self.emit(OpCode.OP_POP)
        self.statement()

        self.emit(OpCode.OP_JUMP)
        else_jump_offset = len(self.chunk.bytes)
        self.emit(0xFF)
        self.emit(0xFF)

        jump_target = len(self.chunk.bytes) - jump_offset - 2
        self.chunk.bytes[jump_offset] = (jump_target >> 8) & 0xFF
        self.chunk.bytes[jump_offset + 1] = jump_target & 0xFF
        self.emit(OpCode.OP_POP)

        if self._match(TokenType.ELSE):
            self.statement()

        else_jump_target = len(self.chunk.bytes) - else_jump_offset - 2
        self.chunk.bytes[else_jump_offset] = (else_jump_target >> 8) & 0xFF
        self.chunk.bytes[else_jump_offset + 1] = else_jump_target & 0xFF

    def while_statement(self):
        loop_start = len(self.chunk.bytes)

        if not self._match(TokenType.LEFT_PAREN):
            raise SyntaxError(
                f"Expected '(' after 'while', got `{self._lookahead()}` instead"
            )

        self.expression()

        if not self._match(TokenType.RIGHT_PAREN):
            raise SyntaxError(
                f"Expected ')' after condition, got `{self._lookahead()}` instead"
            )

        self.emit(OpCode.OP_JUMP_IF_FALSE)
        jump_offset = len(self.chunk.bytes)
        self.emit(0xFF)
        self.emit(0xFF)

        self.emit(OpCode.OP_POP)
        self.statement()

        self.emit(OpCode.OP_LOOP)
        offset = len(self.chunk.bytes) - loop_start
        self.emit((offset >> 8) & 0xFF)
        self.emit(offset & 0xFF)

        jump_target = len(self.chunk.bytes) - jump_offset - 2
        self.chunk.bytes[jump_offset] = (jump_target >> 8) & 0xFF
        self.chunk.bytes[jump_offset + 1] = jump_target & 0xFF

        self.emit(OpCode.OP_POP)

    def print_statement(self):
        self.expression()
        if not self._match(TokenType.SEMICOLON):
            raise SyntaxError(
                f"Expected ';' after value to print, got `{self._lookahead()}` instead"
            )

        self.emit(OpCode.OP_PRINT)

    def expression_statement(self):
        self.expression()
        if not self._match(TokenType.SEMICOLON):
            raise SyntaxError(
                f"Expected ';' after expression, got `{self._lookahead()}` instead"
            )

        self.emit(OpCode.OP_POP)

    # ---------- Parsers de Expresiones ---------- #

    # Parsear una expresión completa es parsear la precedencia más baja
    def expression(self):
        self.parse(Precedence.PREC_ASSIGNMENT)

    def variable(self, valid_target: bool):
        var_name = self._previous()

        is_local = False
        for slot_index, local in enumerate(reversed(self.context.locals)):
            if local.name == var_name.lexeme:
                if not local.depth:
                    raise SyntaxError(
                        "Can't read local variable in its own initializer."
                    )
                is_local = True
                break

        set_op = OpCode.OP_SET_LOCAL if is_local else OpCode.OP_SET_GLOBAL
        get_op = OpCode.OP_GET_LOCAL if is_local else OpCode.OP_GET_GLOBAL

        if valid_target and self._match(TokenType.EQUAL):
            self.expression()
            self.emit(set_op)
        else:
            self.emit(get_op)

        if is_local:
            self.emit(slot_index)
        else:
            constant_index = self.chunk.add_constant(var_name.lexeme)
            self.emit(constant_index)

    # Parsea un número o un string
    def value(self):
        token = self._previous()
        if token.literal is None:
            raise SyntaxError(
                f"Expected a number or string literal, got `{token}` instead"
            )

        # Agrega los bytes correspondientes a una operación de una constante
        constant_index = self.chunk.add_constant(token.literal)
        self.emit(OpCode.OP_CONSTANT)
        self.emit(constant_index)

    def logic_and(self):
        self.emit(OpCode.OP_JUMP_IF_FALSE)
        jump_offset = len(self.chunk.bytes)
        self.emit(0xFF)
        self.emit(0xFF)

        self.emit(OpCode.OP_POP)
        self.parse(Precedence.PREC_AND)

        jump_target = len(self.chunk.bytes) - jump_offset - 2
        self.chunk.bytes[jump_offset] = (jump_target >> 8) & 0xFF
        self.chunk.bytes[jump_offset + 1] = jump_target & 0xFF

    def logic_or(self):
        self.emit(OpCode.OP_JUMP_IF_FALSE)
        else_jump_offset = len(self.chunk.bytes)
        self.emit(0xFF)
        self.emit(0xFF)

        self.emit(OpCode.OP_JUMP)
        end_jump_offset = len(self.chunk.bytes)
        self.emit(0xFF)
        self.emit(0xFF)

        else_jump_target = len(self.chunk.bytes) - else_jump_offset - 2
        self.chunk.bytes[else_jump_offset] = (else_jump_target >> 8) & 0xFF
        self.chunk.bytes[else_jump_offset + 1] = else_jump_target & 0xFF

        self.emit(OpCode.OP_POP)
        self.parse(Precedence.PREC_OR)

        end_jump_target = len(self.chunk.bytes) - end_jump_offset - 2
        self.chunk.bytes[end_jump_offset] = (end_jump_target >> 8) & 0xFF
        self.chunk.bytes[end_jump_offset + 1] = end_jump_target & 0xFF

    # Parsea expresiones unarias
    # Por más que el orden de lectura sea <operador><operando>,
    # emite los bytes correspondientes a <operando><operador>,
    # para que el operador se utilice sobre el tope del stack de la VM
    def unary(self):
        # El operador ya fue consumido
        operator = self._previous()

        # Obtiene la regla asociada al operador y
        # parsea lo que viene después del operador,
        # con la precedencia correspondiente
        rule = self.get_rule(operator.token_type)
        self.parse(rule["prefix_precedence"])

        match operator.token_type:
            case TokenType.BANG:
                self.emit(OpCode.OP_NOT)
            # El menos es una operación de negación
            case TokenType.MINUS:
                self.emit(OpCode.OP_NEGATE)
            case _:
                raise SyntaxError(f"Unexpected unary operator: {operator}")

    # Parsea expresiones binarias
    # La magia es que ahora tenemos todos los operadores binarios en la misma función!
    def binary(self):
        # El operador, y el operando de la izquierda ya fueron consumidos
        operator = self._previous()

        # Obtiene la regla asociada al operador y
        # compila el operando de la derecha con el
        # nivel de precedencia siguiente al de la tabla
        # Esto es porque todos nuestros operadores binarios solo
        # operan con un nivel mayor al propio.
        # En la primera suma de 2 + 3 + 4, queremos que a la derecha
        # se parsee el 3, en vez de capturar el 3 + 4
        rule = self.get_rule(operator.token_type)
        self.parse(rule["infix_precedence"].next())

        match operator.token_type:
            case TokenType.PLUS:
                self.emit(OpCode.OP_ADD)
            case TokenType.MINUS:
                self.emit(OpCode.OP_SUBTRACT)
            case TokenType.STAR:
                self.emit(OpCode.OP_MULTIPLY)
            case TokenType.SLASH:
                self.emit(OpCode.OP_DIVIDE)
            case TokenType.BANG_EQUAL:
                self.emit(OpCode.OP_EQUAL)
                self.emit(OpCode.OP_NOT)
            case TokenType.EQUAL_EQUAL:
                self.emit(OpCode.OP_EQUAL)
            case TokenType.GREATER:
                self.emit(OpCode.OP_GREATER)
            case TokenType.GREATER_EQUAL:
                self.emit(OpCode.OP_LESS)
                self.emit(OpCode.OP_NOT)
            case TokenType.LESS:
                self.emit(OpCode.OP_LESS)
            case TokenType.LESS_EQUAL:
                self.emit(OpCode.OP_GREATER)
                self.emit(OpCode.OP_NOT)
            case _:
                raise SyntaxError(f"Unexpected binary operator: {operator}")

    # El agrupamiento no produce código extra, solamente es un atajo a
    # parsear una expresión de la precedencia más baja
    def grouping(self):
        # El `(` inicial ya fue consumido,
        # solo falta la expresión dentro de los parentesis
        self.expression()

        # Si no me cruzo un `)`, lanzo un error
        if not self._match(TokenType.RIGHT_PAREN):
            raise SyntaxError(
                f"Expected ')' after grouping expression, got `{self._lookahead()}` instead"
            )

    def literal(self):
        token = self._previous()
        match token.token_type:
            case TokenType.NIL:
                self.emit(OpCode.OP_NIL)
            case TokenType.FALSE:
                self.emit(OpCode.OP_FALSE)
            case TokenType.TRUE:
                self.emit(OpCode.OP_TRUE)
            case _:
                raise SyntaxError(f"Unexpected lietral token: {token}")

    # ---------- Helpers ---------- #

    # Dado un tipo de token, devuelve las funciones y precedencias asociadas
    def get_rule(self, token_type: TokenType) -> dict:
        try:
            prefix_fn, infix_fn, prefix_prec, infix_prec = PRATT[token_type]
        except KeyError:
            raise SyntaxError(f"Unexpected Token Type: {token_type}")

        return {
            "prefix_fn": getattr(self, prefix_fn) if prefix_fn else None,
            "infix_fn": getattr(self, infix_fn) if infix_fn else None,
            "prefix_precedence": prefix_prec,
            "infix_precedence": infix_prec,
        }

    def _is_at_end(self) -> bool:
        return self._lookahead().token_type == TokenType.EOF

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    def _lookahead(self) -> Token:
        return self.tokens[self.current]

    def _advance(self) -> Token:
        token = self._lookahead()
        if not self._is_at_end():
            self.current += 1
        return token

    def _match(self, *token_types: TokenType) -> bool:
        for token_type in token_types:
            token = self._lookahead()
            if token.token_type == token_type:
                self._advance()
                return True

        return False

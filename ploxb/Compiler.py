from enum import IntEnum
from functools import total_ordering
from ploxb.Scanner import Token, TokenType
from ploxb.Chunk import Chunk, OpCode
from ploxb.CompilerContext import CompilerContext


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
# Usamos un pratt parser para resolver las ambiguedades de precedencia y asociatividad
# en la gramática de las expresiones.
# Es muy flexible! Agregar operadores es una fila nueva, y cambiár la gramática es solamente editar una celda
PRATT: dict[TokenType, tuple[str | None, str | None, Precedence, Precedence]] = {
    # TokenType              (prefix_fn,   infix_fn,   prefix_precedence,     infix_precedence)
    TokenType.LEFT_PAREN:    ("grouping",  None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.RIGHT_PAREN:   (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.NUMBER:        ("value",     None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.STRING:        ("value",     None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.NIL:           ("literal",   None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.FALSE:         ("literal",   None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.TRUE:          ("literal",   None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.MINUS:         ("unary",     "binary",   Precedence.PREC_UNARY, Precedence.PREC_TERM),
    TokenType.PLUS:          (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_TERM),
    TokenType.STAR:          (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_FACTOR),
    TokenType.SLASH:         (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_FACTOR),
    TokenType.PERCENT:       (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_FACTOR),
    TokenType.BANG:          ("unary",     None,       Precedence.PREC_UNARY, Precedence.PREC_NONE),
    TokenType.BANG_EQUAL:    (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_EQUALITY),
    TokenType.EQUAL_EQUAL:   (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_EQUALITY),
    TokenType.GREATER:       (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.GREATER_EQUAL: (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.LESS:          (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.LESS_EQUAL:    (None,        "binary",   Precedence.PREC_NONE,  Precedence.PREC_COMPARISON),
    TokenType.AND:           (None,        "logic_and",Precedence.PREC_NONE,  Precedence.PREC_AND),
    TokenType.OR:            (None,        "logic_or", Precedence.PREC_NONE,  Precedence.PREC_OR),
    TokenType.IDENTIFIER:    ("variable",  None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
    TokenType.EOF:           (None,        None,       Precedence.PREC_NONE,  Precedence.PREC_NONE),
}
# fmt: on


class Compiler:
    def __init__(self, tokens: list[Token]):
        # Todos los tokens a compilar
        self.tokens = tokens
        # El índice del token actual
        self.current = 0
        # El chunk resultante de la compilación
        self._chunk = Chunk()
        # El contexto del compilador:
        # cuan anidado esta el scope que estamos compilando,
        # y que variables locales contiene
        self.context = CompilerContext()

    # Encapsulamos nuestro chunk para cuando agreguemos funciones
    @property
    def chunk(self):
        return self._chunk

    # ---------- Core ---------- #

    # Compila todos los statements hasta el final,
    # y emite un return final para tener de centinela
    def compile(self) -> Chunk:
        while not self._is_at_end():
            self.statement()
        self.emit(OpCode.OP_RETURN)
        return self.chunk

    # Agregar bytes al chunk
    def emit(self, *bytes: int):
        for byte in bytes:
            self.chunk.write(byte)

    # ---------- Parsers de Statements  ---------- #

    # Parsea un statement
    # como todos estan avisados por su primer token,
    # con chequear ese ya se puede decidir que hacer
    def statement(self):
        if self._match(TokenType.VAR):
            self.var_declaration()
        elif self._match(TokenType.PRINT):
            self.print_statement()
        elif self._match(TokenType.IF):
            self.if_statement()
        elif self._match(TokenType.WHILE):
            self.while_statement()
        elif self._match(TokenType.FOR):
            self.for_statement()
        elif self._match(TokenType.LEFT_BRACE):
            self.block_statement()
        else:
            self.expression_statement()

    # Parsea un expression statement
    # Es solamente resolver una expresión, y descartarla con un pop
    def expression_statement(self):
        self.expression()
        if not self._match(TokenType.SEMICOLON):
            raise SyntaxError(
                f"Expected ';' after expression, got `{self._lookahead()}` instead"
            )

        self.emit(OpCode.OP_POP)

    # Parsea un print statement
    def print_statement(self):
        self.expression()
        if not self._match(TokenType.SEMICOLON):
            raise SyntaxError(
                f"Expected ';' after value to print, got `{self._lookahead()}` instead"
            )

        self.emit(OpCode.OP_PRINT)

    # Parsea un bloque y maneja su scope
    def block_statement(self):
        self.context.begin_scope()
        self.block()
        vars_removed = self.context.end_scope()
        for _ in range(vars_removed):
            self.emit(OpCode.OP_POP)

    # Parsea una declaración de variable
    def var_declaration(self):
        # Si estamos anidados, tenemos que declarar una variable local
        # Si no, una variable global
        is_local = self.context.scope_depth > 0

        if not self._match(TokenType.IDENTIFIER):
            raise SyntaxError("Expected variable name after `var`")

        var_name = self._previous()

        if is_local:
            # En variables locales tenemos que chequear que no estamos
            # re-declarando una variable con el mismo nombre en el mismo scope
            for local in reversed(self.context.locals):
                if local.initialized and local.depth < self.context.scope_depth:
                    break

                if local.name == var_name.lexeme:
                    raise SyntaxError(f"Variable {var_name.lexeme} already exists")

            # Agregamos la variable local al contexto
            self.context.declare(var_name.lexeme)
        else:
            # Si es una variable global, la agregamos a las constantes
            var_index = self.chunk.add_constant(var_name.lexeme)

        # Después de compilar el identificador, tenemos que compilar el valor.
        # Si hay un `=`, entonces compilamos la expresión del valor inicializador
        # Si no (`var x;`), usamos nil como valor
        if self._match(TokenType.EQUAL):
            self.expression()
        else:
            self.emit(OpCode.OP_NIL)

        if not self._match(TokenType.SEMICOLON):
            raise SyntaxError("Expected ';' after var declaration")

        if is_local:
            # En una variable local no queda mas que hacer que
            # marcarla como inicializada, ahora que ya compilamos
            # su valor
            # Ya no se emiten nuevos bytes
            self.context.mark_initialized()
        else:
            # En una variable global tenemos que emitir las instrucciones
            # para que se resuelva el binding en runtime
            self.emit(OpCode.OP_DEFINE_GLOBAL, var_index)

    # Parsea un if
    def if_statement(self):
        if not self._match(TokenType.LEFT_PAREN):
            raise SyntaxError(
                f"Expected '(' after 'if', got `{self._lookahead()}` instead"
            )

        # Compila la condición
        self.expression()

        if not self._match(TokenType.RIGHT_PAREN):
            raise SyntaxError(
                f"Expected ')' after condition, got `{self._lookahead()}` instead"
            )

        # Salta el cuerpo del if si la condición no se cumple
        self.emit(OpCode.OP_JUMP_IF_FALSE)
        then_jump = self.emit_jump_operand()

        # Hay que sacar la condición del stack
        self.emit(OpCode.OP_POP)

        # Compila el cuerpo del if
        self.statement()

        # Si esta dentro del cuerpo del if, cuando termine
        # hay que saltearse todo el cuerpo del else
        self.emit(OpCode.OP_JUMP)
        else_jump = self.emit_jump_operand()

        # Ahora que se cuanto saltar, emparcho el then
        self.patch_jump(then_jump)

        # Hay que sacar la condición del stack
        # (o lo popeamos antes, o lo popeamos ahora)
        self.emit(OpCode.OP_POP)

        # Si tengo un `else`, compilo su cuerpo
        if self._match(TokenType.ELSE):
            self.statement()

        # Ahora que se cuanto saltar, emparcho el else
        self.patch_jump(else_jump)

    # Parsea un while
    def while_statement(self):
        loop_start = len(self.chunk.bytes)

        if not self._match(TokenType.LEFT_PAREN):
            raise SyntaxError(
                f"Expected '(' after 'while', got `{self._lookahead()}` instead"
            )

        # Compila la condición
        self.expression()

        if not self._match(TokenType.RIGHT_PAREN):
            raise SyntaxError(
                f"Expected ')' after condition, got `{self._lookahead()}` instead"
            )

        # Si la condición no se cumple, nos salteamos todo el cuerpo
        self.emit(OpCode.OP_JUMP_IF_FALSE)
        exit_jump = self.emit_jump_operand()

        # Popeamos la condición
        self.emit(OpCode.OP_POP)

        # Compilamos el cuerpo del while
        self.statement()

        # Terminado el cuerpo del while, loopeamos a su comienzo
        self.emit(OpCode.OP_LOOP)
        self.emit_loop_operand(loop_start)

        # Ahora que ya sabemos a donde se salta, lo emparchamos
        self.patch_jump(exit_jump)

        # Popeamos la condición (si no paso en la otra branch, pasa acá)
        self.emit(OpCode.OP_POP)

    def for_statement(self):
        # for (<inicializador> ; <condición> ; <incremento>) <cuerpo>

        # Las variables que se crean en el inicializador viven en su
        # propio scope
        self.context.begin_scope()

        if not self._match(TokenType.LEFT_PAREN):
            raise SyntaxError(
                f"Expected '(' after 'for', got `{self._lookahead()}` instead"
            )

        # <inicializador>
        if self._match(TokenType.SEMICOLON):
            # Si directamente tenemos un ;
            # no hay inicializador
            pass
        elif self._match(TokenType.VAR):
            # Si hay un var, tenemos que declarar la variable
            self.var_declaration()
        else:
            # Si no, directamente es una expresión
            self.expression_statement()

        # Post inicializador, arranca el bucle
        loop_start = len(self.chunk.bytes)

        # <condición>
        exit_jump = None
        if not self._match(TokenType.SEMICOLON):
            self.expression()
            if not self._match(TokenType.SEMICOLON):
                raise SyntaxError(
                    f"Expected ';' after `for` loop condition, got `{self._lookahead()}` instead"
                )

            # Si la condición no se cumple, tenemos que saltearnos el cuerpo
            self.emit(OpCode.OP_JUMP_IF_FALSE)
            exit_jump = self.emit_jump_operand()
            self.emit(OpCode.OP_POP)

        # <incremento>
        # El incremento esta antes del cuerpo, pero se ejecuta después,
        # lo que nos lleva a hacer un par de saltos extraños
        if not self._match(TokenType.RIGHT_PAREN):
            # Si está presente, lo tenemos que saltear, ejecutar el cuerpo,
            # y después con un loop volver al incremento para poder correrlo.
            self.emit(OpCode.OP_JUMP)
            body_jump = self.emit_jump_operand()

            increment_start = len(self.chunk.bytes)

            # El incremento en sí
            self.expression()

            self.emit(OpCode.OP_POP)

            if not self._match(TokenType.RIGHT_PAREN):
                raise SyntaxError(
                    f"Expected ')' after `for` clauses, got `{self._lookahead()}` instead"
                )

            self.emit(OpCode.OP_LOOP)
            self.emit_loop_operand(loop_start)

            loop_start = increment_start
            self.patch_jump(body_jump)

        # <cuerpo>
        self.statement()

        # Loopeamos sobre el cuerpo
        self.emit(OpCode.OP_LOOP)
        self.emit_loop_operand(loop_start)

        if exit_jump is not None:
            self.patch_jump(exit_jump)
            self.emit(OpCode.OP_POP)

        self.context.end_scope()
        # Tenemos que sacar del stack la variable removida
        self.emit(OpCode.OP_POP)

    # ---------- Utils ---------- #

    # Parsea una seguidilla de statements dentro de un bloque
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

    # El corazon de la resolución de variables
    # Retorna el índice de la variable buscada sobre la lista de locales
    # que a su vez coincide con el índice sobre el stack de la VM una vez
    # que estemos en runtime
    def resolve_local(self, var_name):
        # Recorremos de atras para adelante y devolvemos el primer match,
        # para que el shadowing local funcione
        for idx, local in enumerate(reversed(self.context.locals), 1):
            if local.name == var_name.lexeme:
                if not local.initialized:
                    raise SyntaxError(
                        "Can't read local variable in its own initializer."
                    )
                return len(self.context.locals) - idx

        # Si no hubo match, entonces podemos asegurar que la variable no esta
        # declarada localmente, y podemos utilizar esto para asumir que será
        # una variable resuelta en runtime. AKA: una variable global
        return None

    # Para emitir a donde se hace el salto, primero dejamos unos bytes vacios
    # en su lugar y cuando sepamos el valor volvemos a ponerlo
    def emit_jump_operand(self):
        # Necesitamos guardarnos donde esta el salto para
        # después poder volver a emparcharlo
        current = len(self.chunk.bytes)
        self.emit(0xFF, 0xFF)
        return current

    # Ahora si ya podemos emparchar el salto: ponemos la posición
    # actual en su lugar
    def patch_jump(self, jump_instruction: int):
        target = len(self.chunk.bytes) - jump_instruction - 2
        self.chunk.bytes[jump_instruction] = (target >> 8) & 0xFF
        self.chunk.bytes[jump_instruction + 1] = target & 0xFF

    def emit_loop_operand(self, loop_start: int):
        target = len(self.chunk.bytes) - loop_start + 2
        self.emit((target >> 8) & 0xFF, target & 0xFF)

    # ---------- Pratt Parser para expresiones ---------- #

    # Dado un tipo de token, devuelve las funciones y precedencias asociadas
    # Defaultea a None y PREC_NONE si no existe la regla
    # (para, por ejemplo, los tokens que refieren a statements)
    def get_rule(self, token_type: TokenType) -> dict:
        prefix_fn, infix_fn, prefix_prec, infix_prec = PRATT.get(
            token_type, (None, None, None, None)
        )

        return {
            "prefix_fn": getattr(self, prefix_fn) if prefix_fn else None,
            "infix_fn": getattr(self, infix_fn) if infix_fn else None,
            "prefix_precedence": prefix_prec if prefix_prec else Precedence.PREC_NONE,
            "infix_precedence": infix_prec if infix_prec else Precedence.PREC_NONE,
        }

    # Parsea una expresión de una precedencia mayor o igual a la pasada.
    # Es el core del algoritmo de Pratt Parsing.
    def parse(self, precedence: Precedence):
        token = self._advance()

        # Si llamamos a `parse` con un token que no es un prefijo,
        # entonces fue mal llamada. Directamente lanzamos un error
        rule = self.get_rule(token.token_type)
        if rule["prefix_fn"] is None:
            raise SyntaxError(f"Unexpected token: {token}")

        # La asignación tiene una precedencia muy baja:
        # cualquier cosa por encima de eso, no puede ser un target
        # valido de asignación. Por ejemplo `a + b = 2;` debería fallar
        # porque la suma es de mayor precedencia que la asignación.
        # Entonces, le pasamos ese valor a la función de parseo para
        # que la utilice si hace falta lanzar un error
        can_assign = precedence <= Precedence.PREC_ASSIGNMENT
        rule["prefix_fn"](can_assign)

        # Ahora, nos fijamos si estamos parados en una expresión infija
        while not self._is_at_end():
            next_token = self._lookahead()
            next_rule = self.get_rule(next_token.token_type)

            # Nos aseguramos de no capturar operandos que no pertenecen
            # a este nivel de precedencia
            if precedence > next_rule["infix_precedence"]:
                break

            self._advance()
            next_rule["infix_fn"](can_assign)

            # Si estoy en un target válido de asignación, y no consumi el `=`
            # todavía, entonces tengo un error
            if can_assign and self._match(TokenType.EQUAL):
                raise SyntaxError("Invalid assignment target.")

    # ---------- Parsers de Expresiones  ---------- #

    # Parsear una expresión completa es parsear la precedencia más baja
    def expression(self, _=None):
        self.parse(Precedence.PREC_ASSIGNMENT)

    # Parsea un número o un string
    def value(self, _=None):
        token = self._previous()
        if token.literal is None:
            raise SyntaxError(
                f"Expected a number or string literal, got `{token}` instead"
            )

        # Agrega los bytes correspondientes a una operación de una constante
        constant_index = self.chunk.add_constant(token.literal)
        self.emit(OpCode.OP_CONSTANT, constant_index)

    # Parsea un booleano o nil
    def literal(self, _=None):
        token = self._previous()
        match token.token_type:
            case TokenType.NIL:
                self.emit(OpCode.OP_NIL)
            case TokenType.FALSE:
                self.emit(OpCode.OP_FALSE)
            case TokenType.TRUE:
                self.emit(OpCode.OP_TRUE)
            case _:
                raise SyntaxError(f"Unexpected literal token: {token}")

    # El agrupamiento no produce código extra, solamente es un atajo a
    # parsear una expresión de la precedencia más baja
    def grouping(self, _=None):
        # El `(` inicial ya fue consumido,
        # solo falta la expresión dentro de los parentesis
        self.expression()

        # Si no me cruzo un `)`, lanzo un error
        if not self._match(TokenType.RIGHT_PAREN):
            raise SyntaxError(
                f"Expected ')' after grouping expression, got `{self._lookahead()}` instead"
            )

    # Parsea expresiones unarias
    def unary(self, _=None):
        # El operador ya fue consumido
        operator = self._previous()

        # Obtiene la regla asociada al operador y
        # parsea lo que viene después del operador,
        # con la precedencia correspondiente
        # Es decir: compila el operando
        rule = self.get_rule(operator.token_type)
        self.parse(rule["prefix_precedence"])

        # Por más que el orden de lectura sea <operador><operando>,
        # emite los bytes correspondientes a <operando><operador>,
        # para que el operador se utilice sobre el tope del stack de la VM

        match operator.token_type:
            case TokenType.BANG:
                self.emit(OpCode.OP_NOT)
            case TokenType.MINUS:
                self.emit(OpCode.OP_NEGATE)
            case _:
                raise SyntaxError(f"Unexpected unary operator: {operator}")

    # Parsea expresiones binarias
    def binary(self, _=None):
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

        # La magia es que ahora tenemos todos los operadores binarios en la misma función!
        match operator.token_type:
            case TokenType.PLUS:
                self.emit(OpCode.OP_ADD)
            case TokenType.MINUS:
                self.emit(OpCode.OP_SUBTRACT)
            case TokenType.STAR:
                self.emit(OpCode.OP_MULTIPLY)
            case TokenType.SLASH:
                self.emit(OpCode.OP_DIVIDE)
            case TokenType.PERCENT:
                self.emit(OpCode.OP_MODULO)
            case TokenType.BANG_EQUAL:
                self.emit(OpCode.OP_EQUAL, OpCode.OP_NOT)
            case TokenType.EQUAL_EQUAL:
                self.emit(OpCode.OP_EQUAL)
            case TokenType.GREATER:
                self.emit(OpCode.OP_GREATER)
            case TokenType.GREATER_EQUAL:
                self.emit(OpCode.OP_LESS, OpCode.OP_NOT)
            case TokenType.LESS:
                self.emit(OpCode.OP_LESS)
            case TokenType.LESS_EQUAL:
                self.emit(OpCode.OP_GREATER, OpCode.OP_NOT)
            case _:
                raise SyntaxError(f"Unexpected binary operator: {operator}")

    # Parsea un identificador que es el nombre de una variable,
    # para resolver al valor de la variable
    def variable(self, valid_target: bool):
        var_name = self._previous()

        # el operador de la instrucción (`arg`) depende de si
        # la variable es local o global
        # - en una variable local, es el índice sobre el stack de la VM,
        # para poder acceder directamente al valor
        # - en una variable global, es el indice sobre el pool de constantes
        # lo cual me va a referenciar al nombre de la variable, y con eso
        # poder pedirle el valor a la tabla de globales
        arg = self.resolve_local(var_name)
        is_local = arg is not None

        if is_local:
            get_op = OpCode.OP_GET_LOCAL
            set_op = OpCode.OP_SET_LOCAL
        else:
            arg = self.chunk.add_constant(var_name.lexeme)
            get_op = OpCode.OP_GET_GLOBAL
            set_op = OpCode.OP_SET_GLOBAL

        if valid_target and self._match(TokenType.EQUAL):
            # Si me cruzo un igual, estoy en una asignación, por lo que
            # tengo que emitir una instrucción de set, y tengo que
            # compilar el nuevo valor de la variable
            self.expression()
            self.emit(set_op, arg)
        else:
            # Si no, solamente me interesa el valor de la variable
            # y tengo que emitir una instrucción de get
            self.emit(get_op, arg)

    # Parsea un and
    def logic_and(self, _):
        # A esta altura, el operador de la izquierda ya se compiló y
        # esta en el tope del stack
        # Si da falso, el and es falso, y directamente nos salteamos
        # el operador de la derecha
        self.emit(OpCode.OP_JUMP_IF_FALSE)
        shortcircuit = self.emit_jump_operand()

        self.emit(OpCode.OP_POP)
        self.parse(Precedence.PREC_AND)
        self.patch_jump(shortcircuit)

    # Parsea un or
    def logic_or(self, _=None):
        # A esta altura, el operador de la izquierda ya se compiló y
        # esta en el tope del stack
        # Si da verdadero, el or es verdadero, y directamente nos
        # salteamos el operador de la derecha

        # Pero... no tenemos un JUMP_IF_TRUE
        # Entonces, hacemos una jugarreta: si da falso, vamos al
        # operador de la derecha, y si no, hacemos un salto incondicional
        self.emit(OpCode.OP_JUMP_IF_FALSE)
        else_jump = self.emit_jump_operand()

        self.emit(OpCode.OP_JUMP)
        end_jump = self.emit_jump_operand()

        self.patch_jump(else_jump)
        self.emit(OpCode.OP_POP)
        self.parse(Precedence.PREC_OR)
        self.patch_jump(end_jump)

    # ---------- Helpers ---------- #

    # Devuelve si llegamos al token EOF
    def _is_at_end(self) -> bool:
        return self._lookahead().token_type == TokenType.EOF

    # Devuelve el token anterior, ya consumido
    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    # Devuelve el token actual, sin consumirlo
    def _lookahead(self) -> Token:
        return self.tokens[self.current]

    # Consume un token y lo devuelve
    def _advance(self) -> Token:
        token = self._lookahead()
        if not self._is_at_end():
            self.current += 1
        return token

    # Devuelve si el siguiente token es cualquiera de los esperados, y lo consume
    # Es solo una combinación de advance y check
    def _match(self, *token_types: TokenType) -> bool:
        for token_type in token_types:
            token = self._lookahead()
            if token.token_type == token_type:
                self._advance()
                return True

        return False

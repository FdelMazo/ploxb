"""
x86-64 Assembly code generator from compiled bytecode.
Translates bytecode instructions to x86-64 assembly.
"""

from ploxb.Chunk import OpCode
from ploxb.Function import Function


class x86BytecodeTranslator:
    """Translates compiled bytecode to x86-64 assembly"""

    def __init__(self, function: Function):
        self.function = function
        self.code_lines: list[str] = []
        self.label_count = 0
        self.string_literals: dict[str, str] = {}
        self.string_count = 0
        self.float_literals: dict[float, str] = {}
        self.float_count = 0
        self.uses_printf = False  # Track if we need printf

    def translate(self) -> str:
        """Translate bytecode to x86-64 assembly and return as string"""
        # First pass: scan for all jump targets
        self._scan_for_labels(self.function.chunk)

        # Second pass: emit code
        self._emit_header()
        self._translate_chunk(self.function.chunk)
        self._emit_footer()
        result = "\n".join(self.code_lines)
        # Ensure file ends with newline
        if result and not result.endswith("\n"):
            result += "\n"
        return result

    def _scan_for_labels(self, chunk):
        """First pass: identify all jump targets and pre-create labels"""
        self.ip_to_label: dict[int, str] = {}
        self.next_label_id = 0
        ip = 0

        while ip < len(chunk.bytes):
            byte = chunk.bytes[ip]
            ip += 1

            if byte == OpCode.OP_CONSTANT:
                ip += 1
            elif byte in (
                OpCode.OP_GET_LOCAL,
                OpCode.OP_SET_LOCAL,
                OpCode.OP_GET_UPVALUE,
                OpCode.OP_SET_UPVALUE,
                OpCode.OP_CALL,
                OpCode.OP_DEFINE_GLOBAL,
                OpCode.OP_SET_GLOBAL,
                OpCode.OP_GET_GLOBAL,
            ):
                ip += 1
            elif byte in (OpCode.OP_JUMP, OpCode.OP_JUMP_IF_FALSE, OpCode.OP_LOOP):
                high = chunk.bytes[ip]
                ip += 1
                low = chunk.bytes[ip]
                ip += 1
                offset = (high << 8) | low

                # Calculate target
                if byte == OpCode.OP_LOOP:
                    target = ip - offset
                else:
                    target = ip + offset

                # Create label if not exists
                if target not in self.ip_to_label:
                    self.ip_to_label[target] = f"L{self.next_label_id}"
                    self.next_label_id += 1
            elif byte == OpCode.OP_CLOSURE:
                ip += 1  # function index
                if ip < len(chunk.bytes):
                    fun = chunk.constants[chunk.bytes[ip - 1]]
                    # Rough estimate - in reality would need better parsing
                    pass

    # ========== Emission helpers ==========

    def _emit(self, line: str):
        """Emit an assembly line"""
        if line.strip():
            self.code_lines.append(line)

    def _emit_header(self):
        """Emit file header and setup"""
        self._emit(".intel_syntax noprefix")
        self._emit(".text")
        self._emit(".globl main")
        self._emit("main:")
        self._emit("    push rbp")
        self._emit("    mov rbp, rsp")
        self._emit("    sub rsp, 256  # Space for locals/temporaries")

    def _emit_footer(self):
        """Emit file footer and cleanup"""
        self._emit("    xor rax, rax  # Return 0")
        self._emit("    mov rsp, rbp")
        self._emit("    pop rbp")
        self._emit("    ret")

        # Emit string and float literals section
        if self.string_literals or self.float_literals:
            self._emit("")
            self._emit(".data")
            for value, label in self.string_literals.items():
                # Escape the string properly for assembly
                escaped = (
                    value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                )
                self._emit(f'{label}: .string "{escaped}"')
            for float_value, label in self.float_literals.items():
                self._emit(f"{label}: .double {float_value}")

        # Declare printf if we use it
        if self.uses_printf:
            self._emit(".extern printf")

    def _unique_label(self, prefix: str = "L") -> str:
        """Generate a unique label"""
        self.label_count += 1
        return f"{prefix}{self.label_count}"

    def _string_literal_label(self, value: str) -> str:
        """Get or create a label for a string literal"""
        if value not in self.string_literals:
            label = f"str_{self.string_count}"
            self.string_literals[value] = label
            self.string_count += 1
        return self.string_literals[value]

    def _float_literal_label(self, value: float) -> str:
        """Get or create a label for a float literal"""
        if value not in self.float_literals:
            label = f"float_{self.float_count}"
            self.float_literals[value] = label
            self.float_count += 1
        return self.float_literals[value]

    def _get_or_create_format_string(self, fmt: str) -> str:
        """Get or create a label for a format string"""
        return self._string_literal_label(fmt)

    def _get_or_create_label(self, bytecode_ip: int) -> str:
        """Get label for a bytecode IP (assumes already created in scan phase)"""
        return self.ip_to_label.get(bytecode_ip, f"L_unknown_{bytecode_ip}")

    # ========== Bytecode translation ==========

    def _translate_chunk(self, chunk):
        """Translate bytecode instructions from a chunk"""
        ip = 0
        last_constant_was_string = False  # Track if last OP_CONSTANT was a string

        while ip < len(chunk.bytes):
            byte = chunk.bytes[ip]
            ip += 1

            # Helper to read bytes
            def read_byte():
                nonlocal ip
                b = chunk.bytes[ip]
                ip += 1
                return b

            def read_word():
                high = read_byte()
                low = read_byte()
                return (high << 8) | low

            # Check if we need to emit a label for this bytecode IP
            if (ip - 1) in self.ip_to_label:
                self._emit(f"{self.ip_to_label[ip - 1]}:")

            # Translate each instruction
            match byte:
                # Push constants
                case OpCode.OP_CONSTANT:
                    idx = read_byte()
                    value = chunk.constants[idx]
                    last_constant_was_string = isinstance(value, str)

                    if isinstance(value, (int, float)):
                        # Push number
                        if isinstance(value, float) and value != int(value):
                            # Float - load from data section
                            label = self._float_literal_label(value)
                            self._emit(f"    movsd xmm0, [{label}]")
                            self._emit("    sub rsp, 8")
                            self._emit("    movsd [rsp], xmm0")
                        else:
                            # Integer
                            self._emit(f"    mov rax, {int(value)}")
                            self._emit("    push rax")
                    elif isinstance(value, str):
                        # Push string address
                        label = self._string_literal_label(value)
                        self._emit(f"    lea rax, [{label}]")
                        self._emit("    push rax")

                # Literals
                case OpCode.OP_NIL:
                    self._emit("    xor rax, rax")
                    self._emit("    push rax")

                case OpCode.OP_TRUE:
                    self._emit("    mov rax, 1")
                    self._emit("    push rax")

                case OpCode.OP_FALSE:
                    self._emit("    xor rax, rax")
                    self._emit("    push rax")

                # Unary operations
                case OpCode.OP_NOT:
                    self._emit("    pop rax")
                    self._emit("    test rax, rax")
                    self._emit("    setz al")
                    self._emit("    movzx rax, al")
                    self._emit("    push rax")

                case OpCode.OP_NEGATE:
                    self._emit("    pop rax")
                    self._emit("    neg rax")
                    self._emit("    push rax")

                # Binary operations
                case OpCode.OP_ADD:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    add rax, rbx")
                    self._emit("    push rax")

                case OpCode.OP_SUBTRACT:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    sub rax, rbx")
                    self._emit("    push rax")

                case OpCode.OP_MULTIPLY:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    imul rax, rbx")
                    self._emit("    push rax")

                case OpCode.OP_DIVIDE:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    cqo")
                    self._emit("    idiv rbx")
                    self._emit("    push rax")

                case OpCode.OP_MODULO:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    cqo")
                    self._emit("    idiv rbx")
                    self._emit("    mov rax, rdx")  # Remainder
                    self._emit("    push rax")

                case OpCode.OP_EQUAL:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    cmp rax, rbx")
                    self._emit("    sete al")
                    self._emit("    movzx rax, al")
                    self._emit("    push rax")

                case OpCode.OP_GREATER:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    cmp rax, rbx")
                    self._emit("    setg al")
                    self._emit("    movzx rax, al")
                    self._emit("    push rax")

                case OpCode.OP_LESS:
                    self._emit("    pop rbx")
                    self._emit("    pop rax")
                    self._emit("    cmp rax, rbx")
                    self._emit("    setl al")
                    self._emit("    movzx rax, al")
                    self._emit("    push rax")

                # Print (call printf)
                case OpCode.OP_PRINT:
                    self.uses_printf = True
                    # Pop the value to print
                    self._emit("    pop rax")
                    # Use %s for strings (if last constant was string)
                    # and %lld for numbers
                    fmt_label = self._get_or_create_format_string(
                        "%s\n" if last_constant_was_string else "%lld\n"
                    )
                    self._emit(f"    lea rdi, [{fmt_label}]")
                    self._emit("    mov rsi, rax")
                    self._emit("    xor rax, rax  # No vector registers used")
                    self._emit("    call printf")

                # Stack operations
                case OpCode.OP_POP:
                    self._emit("    pop rax")

                # Variable operations (simplified - just stack operations for now)
                case (
                    OpCode.OP_DEFINE_GLOBAL
                    | OpCode.OP_SET_GLOBAL
                    | OpCode.OP_GET_GLOBAL
                ):
                    idx = read_byte()
                    # Simplified: just treat as stack operations
                    match byte:
                        case OpCode.OP_DEFINE_GLOBAL:
                            self._emit("    pop rax  # define global (simplified)")
                        case OpCode.OP_SET_GLOBAL:
                            self._emit("    # set global (simplified)")
                        case OpCode.OP_GET_GLOBAL:
                            self._emit("    xor rax, rax  # get global (simplified)")
                            self._emit("    push rax")

                case OpCode.OP_GET_LOCAL | OpCode.OP_SET_LOCAL:
                    slot = read_byte()
                    match byte:
                        case OpCode.OP_GET_LOCAL:
                            # Load from stack slot
                            offset = slot * 8
                            self._emit(f"    mov rax, [rbp - {offset}]")
                            self._emit("    push rax")
                        case OpCode.OP_SET_LOCAL:
                            # Store to stack slot
                            offset = slot * 8
                            self._emit("    pop rax")
                            self._emit(f"    mov [rbp - {offset}], rax")
                            self._emit("    push rax")  # Assignment returns value

                # Jump operations
                case OpCode.OP_JUMP:
                    offset = read_word()
                    target = ip + offset
                    label = self._get_or_create_label(target)
                    self._emit(f"    jmp {label}")

                case OpCode.OP_JUMP_IF_FALSE:
                    offset = read_word()
                    target = ip + offset
                    label = self._get_or_create_label(target)
                    self._emit("    pop rax")
                    self._emit("    test rax, rax")
                    self._emit(f"    jz {label}")

                case OpCode.OP_LOOP:
                    offset = read_word()
                    target = ip - offset
                    label = self._get_or_create_label(target)
                    self._emit(f"    jmp {label}")

                # Function operations
                case OpCode.OP_CLOSURE:
                    idx = read_byte()
                    # Read upvalue info (simplified)
                    for _ in range(0):  # Skip for now
                        read_byte()
                        read_byte()
                    self._emit("    # closure (simplified)")

                case OpCode.OP_CALL:
                    arg_count = read_byte()
                    self._emit(f"    # call with {arg_count} args (simplified)")

                case OpCode.OP_RETURN:
                    self._emit("    pop rax  # return value")
                    self._emit("    mov rsp, rbp")
                    self._emit("    pop rbp")
                    self._emit("    ret")

                case _:
                    self._emit(f"    # Unknown opcode: {byte}")

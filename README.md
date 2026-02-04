# ploxb

Compilador a Bytecode de [Lox](https://craftinginterpreters.com/) hecho en Python, para enseñar Lenguajes y Compiladores I (FIUBA)

```sh
# Install uv
# https://docs.astral.sh/uv/getting-started/installation/

# Install the project
uv tool install --editable .

# Set up a simple type checking pre-commit hook
cp pre-commit.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# Reload your terminal!!!

# Run a script!
ploxb ./examples/hello.lox

# Run ploxb anywhere!
ploxb
```

En cada branch del repo hay distintas implementaciones de Lox:

- `main` -> Versión sin funciones, con lo visto hasta el capítulo 23 del libro. Al no incluir funciones ni closures, es más facil de comprender.
- `fns-and-closures` -> Lo que hay en `main` más lo visto en el capítulo 24 y 25 del libro, que complejiza un poco el modelo original.
- `to-x86` -> Un experimento para comparar nuestro bytecode contra assembly

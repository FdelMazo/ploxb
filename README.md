# plox

Compilador a Bytecode de Lox (Crafting Interpreters), hecho en Python, para enseñar Lenguajes y Compiladores I (FIUBA)

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

# Skillbot

A bot which uses skills to do work.

## Installation

```bash
pip install skillbot
```

## Quick Start

```python
from skillbot import hello

print(hello())          # "Hello, World!"
print(hello("Alice"))   # "Hello, Alice!"
```

## CLI Usage

After installation, a `skillbot` command is available:

```bash
skillbot
# Output: Hello, World!
```

## API Reference

### `hello(name: str = "World") -> str`

Return a greeting message.

**Parameters:**

| Name   | Type  | Default   | Description             |
| ------ | ----- | --------- | ----------------------- |
| `name` | `str` | `"World"` | The name to greet.      |

**Returns:** A greeting string in the format `"Hello, {name}!"`.

## License

See [LICENSE](../LICENSE) for details.

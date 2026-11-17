from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ModuleSource:
    """Откуда грузится модуль.

    kind:
      - "path":   директория с __init__.py
      - "import": импортируемое имя пакета (обязан быть пакетом)
      - "object": уже готовый модуль/инстанс (для тестов, динамики)

    Модули без __init__.py не поддерживаются (fallback-заглушка, см. loader).
    """
    kind: str
    ref: Any

    def __post_init__(self):
        if self.kind not in {"path", "import", "object"}:
            raise ValueError(f"unknown kind: {self.kind}")

    @classmethod
    def from_path(cls, p): return cls("path", Path(p))

    @classmethod
    def from_import(cls, name): return cls("import", name)

    @classmethod
    def from_object(cls, obj): return cls("object", obj)
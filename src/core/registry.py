import threading
from dataclasses import dataclass
from typing import Any, Callable

from .errors import CapabilityNotFound


@dataclass
class Capability:
    name: str
    callable: Callable
    module: str
    generation: int
    signature: str | None = None
    docstring: str | None = None


class Registry:
    def __init__(self):
        self._lock = threading.RLock()
        self._caps: dict[str, list[Capability]] = {}
        self._gen: dict[str, int] = {}

    def next_generation(self, module: str) -> int:
        with self._lock:
            self._gen[module] = self._gen.get(module, 0) + 1
            return self._gen[module]

    def current_generation(self, module: str) -> int:
        with self._lock:
            return self._gen.get(module, 0)

    def register(self, cap: Capability) -> None:
        with self._lock:
            lst = self._caps.setdefault(cap.name, [])
            lst[:] = [c for c in lst if c.module != cap.module]
            lst.append(cap)

    def unregister_module(self, module: str) -> None:
        with self._lock:
            for name in list(self._caps):
                kept = [c for c in self._caps[name] if c.module != module]
                if kept:
                    self._caps[name] = kept
                else:
                    del self._caps[name]
            self._gen[module] = self._gen.get(module, 0) + 1

    def resolve(self, name: str, module: str | None = None) -> Capability:
        with self._lock:
            entries = list(self._caps.get(name, []))
        if module is not None:
            entries = [c for c in entries if c.module == module]
        if not entries:
            raise CapabilityNotFound(name)
        if len(entries) > 1:
            raise CapabilityNotFound(
                f"ambiguous capability '{name}' from {[c.module for c in entries]}"
            )
        return entries[0]

    def snapshot(self) -> list[Capability]:
        with self._lock:
            return [c for lst in self._caps.values() for c in lst]
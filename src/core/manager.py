import threading
from dataclasses import dataclass, field
from typing import Any

from .discovery import discover
from .errors import ModuleLoadError, ModuleNotFound
from .hooks import Hooks
from .loader import load_from_source, unload_from_sys
from .registry import Capability, Registry
from .source import ModuleSource


@dataclass
class LoadedModule:
    name: str
    version: str
    generation: int
    instance: Any
    source: ModuleSource
    sys_key: str | None = None
    capabilities: list[str] = field(default_factory=list)
    #entry_runtime: Any = None


class ModuleManager:
    def __init__(self, registry: Registry, hooks: Hooks):
        self._registry = registry
        self._hooks = hooks
        self._modules: dict[str, LoadedModule] = {}
        self._lock = threading.RLock()
        self._diagnostics: list[dict] = []

    # --- публичное ---

    def load(self, name, source, *, version="0.0.0", allow_reload=False):
        with self._lock:
            if name in self._modules and not allow_reload:
                raise ModuleLoadError(f"'{name}' already loaded (use allow_reload)")
            return self._load_locked(name, source, version)

    def unload(self, name):
        with self._lock:
            self._unload_locked(name)

    def reload(self, name, source=None):
        with self._lock:
            if name not in self._modules:
                raise ModuleNotFound(name)
            mod = self._modules[name]
            src = source if source is not None else mod.source
            return self._load_locked(name, src, mod.version)

    def apply(self, desired: dict[str, ModuleSource]) -> dict:
        """Минимальная реконсиляция: load отсутствующих, unload лишних.

        Не детектирует смену source у существующего модуля — для этого reload().
        """
        loaded, unloaded = [], []
        with self._lock:
            for name in list(self._modules):
                if name not in desired:
                    self._unload_locked(name)
                    unloaded.append(name)
            for name, src in desired.items():
                if name not in self._modules:
                    self._load_locked(name, src, "0.0.0")
                    loaded.append(name)
        return {"loaded": loaded, "unloaded": unloaded}

    def modules(self) -> list[LoadedModule]:
        with self._lock:
            return list(self._modules.values())

    def diagnostics(self) -> list[dict]:
        with self._lock:
            return list(self._diagnostics)

    # --- внутреннее ---

    def _load_locked(self, name, source, version):
        if name in self._modules:
            self._unload_locked(name)

        self._hooks.emit("before_load", name=name, source=source)

        try:
            instance = load_from_source(name, source)
        except ModuleLoadError as e:
            self._diag(name, "load", e)
            self._hooks.emit("on_error", phase="load", name=name, error=e)
            raise
        except Exception as e:
            self._diag(name, "load", e)
            self._hooks.emit("on_error", phase="load", name=name, error=e)
            raise ModuleLoadError(f"failed to load '{name}': {e}") from e

        sys_key = None
        if source.kind == "path":
            sys_key = name
        elif source.kind == "import":
            sys_key = source.ref

        generation = self._registry.next_generation(name)

        try:
            caps = discover(name, instance)
        except Exception as e:
            self._diag(name, "discover", e)
            self._hooks.emit("on_error", phase="discover", name=name, error=e)
            if sys_key is not None:
                try: unload_from_sys(sys_key)
                except Exception: pass
            raise ModuleLoadError(f"failed to discover '{name}': {e}") from e

        for cap in caps:
            self._registry.register(Capability(
                name=cap["name"], callable=cap["callable"], module=name,
                generation=generation, signature=cap["signature"],
                docstring=cap["docstring"],
            ))
        """
        entry_runtime = None
        entry = getattr(instance, "__entry_point__", None)
        if callable(entry):
            try:
                entry_runtime = entry()
            except Exception as e:
                self._diag(name, "entry_point", e)
                self._hooks.emit("on_error", phase="entry_point", name=name, error=e)
                self._registry.unregister_module(name)
                if sys_key is not None:
                    try: unload_from_sys(sys_key)
                    except Exception: pass
                raise ModuleLoadError(
                    f"__entry_point__ failed for '{name}': {e}"
                ) from e
        """
        loaded = LoadedModule(
            name=name, version=version, generation=generation,
            instance=instance, source=source, sys_key=sys_key,
            capabilities=[c["name"] for c in caps],
            #entry_runtime=entry_runtime,
        )
        self._modules[name] = loaded
        self._hooks.emit("after_load", name=name, module=loaded)
        return loaded

    def _unload_locked(self, name):
        mod = self._modules.pop(name, None)
        if mod is None:
            return
        self._hooks.emit("before_unload", name=name)
        self._registry.unregister_module(name)
        if mod.sys_key is not None:
            try:
                unload_from_sys(mod.sys_key)
            except Exception as e:
                self._diag(name, "unload_sys", e)
        self._hooks.emit("after_unload", name=name)

    def _diag(self, name, phase, error):
        self._diagnostics.append({
            "module": name, "phase": phase,
            "error": f"{type(error).__name__}: {error}",
        })

import contextvars
from contextlib import contextmanager
from pathlib import Path

from .hooks import Hooks
from .invocable import Invocable
from .manager import ModuleManager
from .registry import Capability, Registry
from .source import ModuleSource


class Core:
    def __init__(self):
        self.registry = Registry()
        self.hooks = Hooks()
        self.manager = ModuleManager(self.registry, self.hooks)
        self._scopes = contextvars.ContextVar("core_scope", default=())

    # --- lifecycle ---

    def load(self, name, source, *, version="0.0.0", allow_reload=False):
        return self.manager.load(name, self._coerce(source),
                                 version=version, allow_reload=allow_reload)

    def unload(self, name):
        return self.manager.unload(name)

    def reload(self, name, source=None):
        src = self._coerce(source) if source is not None else None
        return self.manager.reload(name, src)

    def apply(self, desired):
        return self.manager.apply({k: self._coerce(v) for k, v in desired.items()})

    # --- capability surface ---

    def register(self, name, callable_, *, signature=None, docstring=None):
        """Регистрация внешней capability (Overlay/Userspace-клей)."""
        self.registry.register(Capability(
            name=name, callable=callable_, module="__external__",
            generation=0, signature=signature, docstring=docstring,
        ))

    def resolve(self, name, module=None) -> Invocable:
        return Invocable(self.registry, self.registry.resolve(name, module), self.hooks)

    def invoke(self, name, *args, **kwargs):
        return self.resolve(name)(*args, **kwargs)

    # --- introspection ---

    def capabilities(self):
        return [
            {"name": c.name, "module": c.module, "generation": c.generation,
             "signature": c.signature, "docstring": c.docstring}
            for c in self.registry.snapshot()
        ]

    def modules(self):
        return [
            {"name": m.name, "version": m.version, "generation": m.generation,
             "capabilities": list(m.capabilities)}
            for m in self.manager.modules()
        ]

    def diagnostics(self):
        return self.manager.diagnostics()

    # --- scopes ---

    @contextmanager
    def scope(self, **tags):
        token = self._scopes.set(self._scopes.get() + (tags,))
        try:
            yield
        finally:
            self._scopes.reset(token)

    def current_scope(self):
        return self._scopes.get()

    # --- helper ---

    @staticmethod
    def _coerce(source) -> ModuleSource:
        if isinstance(source, ModuleSource):
            return source
        if isinstance(source, Path):
            return ModuleSource.from_path(source)
        if isinstance(source, str):
            p = Path(source)
            if p.is_dir() and (p / "__init__.py").exists():
                return ModuleSource.from_path(p)
            return ModuleSource.from_import(source)
        return ModuleSource.from_object(source)
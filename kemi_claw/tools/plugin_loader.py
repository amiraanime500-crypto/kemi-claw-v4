"""Auto-load extra tools from the plugins/ folder without touching the core."""
import importlib
import pathlib
import pkgutil


def load_plugins(package="plugins"):
    loaded = []
    path = pathlib.Path(package)
    if not path.exists():
        return loaded
    for mod in pkgutil.iter_modules([str(path)]):
        importlib.import_module(f"{package}.{mod.name}")
        loaded.append(mod.name)
    return loaded

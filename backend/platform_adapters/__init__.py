from platform_adapters.base import BaseAdapter
from platform_adapters.standalone import StandaloneAdapter
from platform_adapters.manual import ManualAdapter

try:
    from platform_adapters.jd import JDAdapter
except ImportError:
    JDAdapter = None  # type: ignore


__all__ = [
    "BaseAdapter",
    "StandaloneAdapter",
    "JDAdapter",
    "ManualAdapter",
]

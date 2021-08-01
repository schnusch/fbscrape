import setuptools  # type: ignore
from typing import Any, Dict

info = {}  # type: Dict[str, Any]
with open('fbscrape/__init__.py', 'r', encoding='utf-8') as fp:
    exec(fp.read(), info)

setuptools.setup(version=info['__version__'])

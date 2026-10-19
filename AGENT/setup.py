# Shim so old pip versions (21.x, the default on macOS Python 3.9) can install this package in editable mode.
# All real configuration lives in pyproject.toml.
from setuptools import setup

setup()

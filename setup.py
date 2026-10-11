"""
Gaia build configuration.

Builds the optional Cython extension for the simulation loop.
If Cython is not installed, the build is skipped and Gaia falls back
to the pure-Python simulation loop automatically.

Usage:
    python setup.py build_ext --inplace
"""

import re
from pathlib import Path

from setuptools import setup, find_packages


def _read_version() -> str:
    """Read __version__ from gaia/__init__.py without importing the package."""
    init = Path(__file__).parent / "gaia" / "__init__.py"
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"), re.M)
    if match is None:
        raise RuntimeError("Cannot find __version__ in gaia/__init__.py")
    return match.group(1)


try:
    from Cython.Build import cythonize
    ext_modules = cythonize(
        "gaia/cy/simulation_cy.pyx",
        compiler_directives={
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "language_level": "3",
        },
    )
except ImportError:
    ext_modules = []
    print("Cython not found — building without C extensions.")
    print("The pure-Python simulation loop will be used instead.")

setup(
    name="gaia",
    version=_read_version(),
    description="Gaia — Externality Computation Framework",
    packages=find_packages(),
    ext_modules=ext_modules,
    python_requires=">=3.9",
)

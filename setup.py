"""
Gaia build configuration.

Builds the optional Cython extension for the simulation loop.
If Cython is not installed, the build is skipped and Gaia falls back
to the pure-Python simulation loop automatically.

Usage:
    python setup.py build_ext --inplace
"""

import hashlib
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


_PYX = Path(__file__).parent / "gaia" / "cy" / "simulation_cy.pyx"


def _pyx_sha256(path: Path) -> str:
    """SHA-256 of a source file with normalised line endings.

    Must match gaia.simulation._pyx_sha256, which compares the hash embedded
    in the compiled module against the .pyx at import time.
    """
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


try:
    from Cython.Build import cythonize
    _pyx_hash = _pyx_sha256(_PYX)
    _generated_c = _PYX.with_suffix(".c")
    ext_modules = cythonize(
        "gaia/cy/simulation_cy.pyx",
        compile_time_env={"GAIA_PYX_SHA256": _pyx_hash},
        # Regenerate whenever the existing .c embeds a different hash, even if
        # its mtime looks newer than the .pyx.
        force=not (
            _generated_c.exists()
            and _pyx_hash in _generated_c.read_text(encoding="utf-8", errors="ignore")
        ),
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

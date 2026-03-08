"""
Gaia build configuration.

Builds the optional Cython extension for the simulation loop.
If Cython is not installed, the build is skipped and Gaia falls back
to the pure-Python simulation loop automatically.

Usage:
    python setup.py build_ext --inplace
"""

from setuptools import setup, find_packages

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
    version="0.8.0",
    description="Gaia — Externality Computation Framework",
    packages=find_packages(),
    ext_modules=ext_modules,
    python_requires=">=3.9",
)

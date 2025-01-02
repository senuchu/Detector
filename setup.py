from setuptools import setup
from Cython.Build import cythonize
from setuptools.extension import Extension

# Define the modules you want to compile
extensions = [
    Extension("main", ["main.py"]),
    Extension("models", ["models.py"]),
    Extension("functions", ["functions.py"]),
]

setup(
    ext_modules=cythonize(extensions),
)
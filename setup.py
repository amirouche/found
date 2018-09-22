#!/usr/bin/env python

import os
import sys

from setuptools import setup, find_packages
from found import VERSION


os.chdir(os.path.dirname(sys.argv[0]) or ".")


setup(
    name="asyncio-foundationdb",
    version=VERSION,
    description="asyncio drivers for FoundationDB",
    long_description=open("README.rst", "rt").read(),
    url="https://github.com/amirouche/asyncio-foundationdb/",
    author="Amirouche BOUBEKKI",
    author_email="amirouche.boubekki@gmail.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
    ],
    packages=find_packages(),
    package_data={'found': ['*.h']},
    install_requires=["cffi>=1.0.0", "immutables", "six"],
    setup_requires=["cffi>=1.0.0"],
    cffi_modules=["./found/build_found.py:ffi"],
)

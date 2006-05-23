#!/usr/bin/env python

"""Distutils setup file"""

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup

# Metadata
PACKAGE_NAME = "BytecodeAssembler"
PACKAGE_VERSION = "0.0.1"
PACKAGES = ['peak', 'peak.util']

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,

    description='Generate Python code objects by "assembling" bytecode',
    author="Phillip J. Eby",
    author_email="peak@eby-sarna.com",
    license="PSF or ZPL",

    test_suite = 'peak.util.assembler',

    packages = PACKAGES,
    namespace_packages = PACKAGES,
)


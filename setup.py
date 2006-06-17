#!/usr/bin/env python

"""Distutils setup file"""

import ez_setup
ez_setup.use_setuptools()

from setuptools import setup

# Metadata
PACKAGE_NAME = "BytecodeAssembler"
PACKAGE_VERSION = "0.1"
PACKAGES = ['peak', 'peak.util']

def get_description():
    # Get our long description from the documentation
    f = file('README.txt')
    lines = []
    for line in f:
        if not line.strip():
            break     # skip to first blank line
    for line in f:
        if line.startswith('.. contents::'):
            break     # read to table of contents
        lines.append(line)
    f.close()
    return ''.join(lines)

setup(
    name=PACKAGE_NAME,
    version=PACKAGE_VERSION,
    url = "http://peak.telecommunity.com/DevCenter/BytecodeAssembler",
    description='Generate Python code objects by "assembling" bytecode',
    long_description = get_description(),

    author="Phillip J. Eby",
    author_email="peak@eby-sarna.com",
    license="PSF or ZPL",

    test_suite = 'test_assembler',

    packages = PACKAGES,
    namespace_packages = PACKAGES,
)


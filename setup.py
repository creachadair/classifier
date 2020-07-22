#!/usr/bin/env python
##
## Name:     setup.py
## Purpose:  Install Classifier and associated tools.
##
## Copyright (C) 2008 Michael J. Fromberger, All Rights Reserved.
##
## Standard usage:  python setup.py install
##
from distutils.core import setup
from Classifier import __version__ as lib_version

setup(name='Classifier',
      version=lib_version,
      description='Text classification tools',
      long_description="""
This library and its associated tools implement a framework for
trainable text classification.  It is designed mainly for use in
classifying e-mail, for example to filter out spam, but it can be
used for many other text classification problems.

This code requires Python 2.5 or newer, and the sqlite3 module.""",
      author='M. J. Fromberger',
      author_email="michael.j.fromberger@gmail.com",
      url='http://spinning-yarns.org/michael/sw/',
      classifiers=[
          'Development Status :: 3 - Alpha', 'Intended Audience :: Developers',
          'License :: Freeware', 'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Communications :: Email :: Filters',
          'Topic :: Software Development :: Libraries'
      ],
      packages=['Classifier'],
      package_dir={'Classifier': 'Classifier'},
      scripts=['mailtagger', 'mailtrainer', 'maildumper'])

# Here there be dragons

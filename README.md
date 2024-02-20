# Overview

![Documentation Status](https://readthedocs.org/projects/python-typewriter/badge/?style=flat)
[![GitHub Actions Build Status](https://github.com/danphenderson/python-typewriter/actions/workflows/github-actions.yml/badge.svg)](https://github.com/danphenderson/python-typewriter/actions)
[![Coverage Status](https://coveralls.io/repos/danphenderson/python-typewriter/badge.svg?branch=main&service=github)](https://coveralls.io/r/danphenderson/python-typewriter)
[![Coverage Status](https://codecov.io/gh/danphenderson/python-typewriter/branch/main/graphs/badge.svg?branch=main)](https://codecov.io/github/danphenderson/python-typewriter)
[![PyPI Package latest release](https://img.shields.io/pypi/v/typewriter.svg)](https://pypi.org/project/typewriter)
[![PyPI Wheel](https://img.shields.io/pypi/wheel/typewriter.svg)](https://pypi.org/project/typewriter)
[![Supported versions](https://img.shields.io/pypi/pyversions/typewriter.svg)](https://pypi.org/project/typewriter)
[![Supported implementations](https://img.shields.io/pypi/implementation/typewriter.svg)](https://pypi.org/project/typewriter)
[![Commits since latest release](https://img.shields.io/github/commits-since/danphenderson/python-typewriter/v0.1.0.svg)](https://github.com/danphenderson/python-typewriter/compare/v0.1.0...main)



    pip install typewriter

# Contributing


Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

# Development

To set up `python-typewriter` for local development:

1. Fork [python-typewriter](<https://github.com/danphenderson/python-typewriter>) (look for the "Fork" button).


2. Clone your fork locally and setup you python environment with [Pipenv](https://pipenv.pypa.io/en/latest/):

   `git clone git@github.com:YOURGITHUBNAME/python-typewriter.git`
   `cd python-typewriter && pipenv install .`

3. Create a branch for local development:

    `git checkout -b name-of-your-bugfix-or-feature`

   Now you can make your changes locally.

4. Generate Documentation, commit your changes, and push your branch to GitHub:

    git add .
    pipenv run build docs
    git commit -m "Your detailed description of your changes."
    git push origin name-of-your-bugfix-or-feature

5. Submit a pull request through the GitHub website.

# Modular Application Utilities

`mau` is a modular python library containing utilities for building
front-end applications as part of the Yosys ecosystem. The goal is to avoid
duplicating similar functionality in different front-end tools, by providing a
common high-quality implementation.

This is currently an early work in progress.

## Development Setup

To install the library in development mode, including all dev-dependencies run:

    make dev-install

This invokes `python3 -m pip install -e '.[dev]'` and thus works fine within a
virtual environment. It does require a fairly recent version of `pip`, so if it
complains about a missing `setup.py` run this first:

    python3 -m pip install --upgrade pip

In generall all `make` targets invoke development command line tools using
`python3 -m ...` where `python3` can be overriden with the `PYTHON` make
variable to use a specific python installation.

Currently this library targets Python 3.8 and newer.

## Documentation

Documentation is available online at
https://yosyshq.readthedocs.io/projects/mau/en/latest/.

To build the Sphinx documentation of this library locally, run:

    make docs

The resulting HTML documentation can be found in `docs/build/html`. Note that
this uses Sphinx extensions and requires having run the development setup
first.

## Testing

To run all tests, lints, etc. run:

    make ci

A HTML test coverage report can be found in the `htmlcov` output directory.

It is also possible to run specific tasks individually. To see an overview run:

    make help

## Auto-Formatting and Fixing

When `make ci` or `make formatting` complain about formatting issues, you can
run `make reformat` to automatically fix the formatting.

When `make ci` or `make lint` complain about linting issues, you can run `make
fix` to attempt to automatically fix some of these issues.

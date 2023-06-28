#!/usr/bin/env python
from __future__ import annotations

import os
import traceback
import warnings
from distutils.sysconfig import customize_compiler

import setuptools
import setuptools.command.build
import setuptools.command.build_clib


class NativeBinDistribution(setuptools.Distribution):
    def has_ext_modules(self):
        return True


class build_helpers(setuptools.Command, setuptools.command.build.SubCommand):
    build_lib = None  # type: ignore
    editable_mode = True

    progname = "yosys_mau/helpers/preexec_wrapper"

    def initialize_options(self) -> None:
        self.build_temp = None
        pass

    def finalize_options(self) -> None:
        self.set_undefined_options(
            "build",
            ("build_lib", "build_lib"),
            ("build_temp", "build_temp"),
        )
        pass

    def get_source_files(self) -> list[str]:
        return [f"src/{self.progname}.c"]

    def get_outputs(self) -> list[str]:
        return ["{build_lib}/" + self.progname]

    def run(self):
        try:
            if (
                os.stat(f"src/{self.progname}.c").st_mtime
                < os.stat(os.path.join(self.build_lib, self.progname)).st_mtime
            ):
                print("skipping build_helpers because it is up to date")
                return
        except FileNotFoundError:
            pass

        try:
            from distutils.ccompiler import new_compiler

            self.compiler = new_compiler()
            customize_compiler(self.compiler)
            objects = self.compiler.compile(
                sources=self.get_source_files(),
                output_dir=self.build_temp,
            )
            self.compiler.link_executable(
                objects=objects,
                output_progname=self.progname,
                output_dir=self.build_lib,
            )
        except BaseException:
            traceback.print_exc()
            warnings.warn("Error building optional preexec_wrapper")


class build(setuptools.command.build.build):
    sub_commands = [
        *setuptools.command.build.build.sub_commands,  # type: ignore
        ("build_helpers", lambda self: os.name == "posix"),
    ]


if __name__ == "__main__":
    if int(setuptools.__version__.split(".")[0]) < 61:
        print("Please upgrade setuptools to at least version 61.0.0")
        exit(1)

    setuptools.setup(
        cmdclass={
            "build_helpers": build_helpers,
            "build": build,
        },
        distclass=NativeBinDistribution,
    )

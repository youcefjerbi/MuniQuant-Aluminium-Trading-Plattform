from setuptools import setup
from pybind11.setup_helpers import Pybind11Extension, build_ext

setup(ext_modules=[Pybind11Extension("muniquant_core", ["cpp/core.cpp"], cxx_std=17)],
      cmdclass={"build_ext": build_ext})

"""
Script to compile eval7.pyx
"""
from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext

print "(Note: usage is normally 'python setup.py build_ext --inplace'"  \
    " (run locally)"
print "On Windows, follow:"  \
    " https://github.com/cython/cython/wiki/CythonExtensionsOnWindows"

# Steps on Windows (once set up):
# - Launch Visual Studio for Python 32-bit command prompt (no other command
#   prompt will do!)
# - make sure it's the Python one
# - make sure it's the 32-bit one
# - SET DISTUTILS_USE_SDK=1
# - SET MSSdk=1
# - python.exe setup.py build_ext --inplace --compiler=msvc

setup(
    cmdclass = {'build_ext': build_ext},
    ext_modules = [Extension("eval7", ["./eval7.pyx"])]
)

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

setup(
    cmdclass = {'build_ext': build_ext},
    ext_modules = [Extension("eval7", ["./eval7.pyx"])]
)
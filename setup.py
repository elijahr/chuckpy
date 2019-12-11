import platform

import subprocess

from setuptools import setup, Extension
from setuptools.command.develop import develop
from setuptools.command.install import install
from setuptools.command.build_ext import build_ext


DARWIN_CFLAGS = ['-D__MACOSX_CORE__']
# '-mmacosx-version-min=10.6', '-stdlib=libstdc++', '-std=c++11'


DARWIN_LDFLAGS = [
    '-framework', 'CoreAudio',
    '-framework', 'CoreMIDI',
    '-framework', 'CoreFoundation',
    '-framework', 'IOKit',
    '-framework', 'Carbon',
    '-framework', 'AppKit',
    '-framework', 'Foundation',
    # '-undefined', 'dynamic_lookup',
    # '-stdlib=libc++',
]


# Order is important here, folks
EXTRA_OBJECTS = [
    # This is generated during make by yacc
    'chuck-external/src/core/chuck.tab.o',

    # This is generated during make by lex
    'chuck-external/src/core/chuck.yy.o',

    'chuck-external/src/core/util_math.o',
    'chuck-external/src/core/util_network.o',
    'chuck-external/src/core/util_raw.o',
    'chuck-external/src/core/util_xforms.o',

    'chuck-external/src/core/chuck.o',
    'chuck-external/src/core/chuck_absyn.o',
    'chuck-external/src/core/chuck_parse.o',
    'chuck-external/src/core/chuck_errmsg.o',
    'chuck-external/src/core/chuck_frame.o',
    'chuck-external/src/core/chuck_symbol.o',
    'chuck-external/src/core/chuck_table.o',
    'chuck-external/src/core/chuck_utils.o',
    'chuck-external/src/core/chuck_vm.o',
    'chuck-external/src/core/chuck_instr.o',
    'chuck-external/src/core/chuck_scan.o',
    'chuck-external/src/core/chuck_type.o',
    'chuck-external/src/core/chuck_emit.o',
    'chuck-external/src/core/chuck_compile.o',
    'chuck-external/src/core/chuck_dl.o',
    'chuck-external/src/core/chuck_oo.o',
    'chuck-external/src/core/chuck_lang.o',
    'chuck-external/src/core/chuck_ugen.o',
    'chuck-external/src/core/chuck_otf.o',
    'chuck-external/src/core/chuck_stats.o',
    'chuck-external/src/core/chuck_shell.o',
    'chuck-external/src/core/chuck_io.o',
    'chuck-external/src/core/chuck_carrier.o',
    'chuck-external/src/core/hidio_sdl.o',
    'chuck-external/src/core/midiio_rtmidi.o',
    'chuck-external/src/core/rtmidi.o',
    'chuck-external/src/core/ugen_osc.o',
    'chuck-external/src/core/ugen_filter.o',
    'chuck-external/src/core/ugen_stk.o',
    'chuck-external/src/core/ugen_xxx.o',
    'chuck-external/src/core/ulib_machine.o',
    'chuck-external/src/core/ulib_math.o',
    'chuck-external/src/core/ulib_std.o',
    'chuck-external/src/core/ulib_opsc.o',
    'chuck-external/src/core/ulib_regex.o',
    'chuck-external/src/core/util_buffers.o',
    'chuck-external/src/core/util_console.o',
    'chuck-external/src/core/util_string.o',
    'chuck-external/src/core/util_thread.o',
    'chuck-external/src/core/util_opsc.o',
    'chuck-external/src/core/util_serial.o',
    'chuck-external/src/core/util_hid.o',
    'chuck-external/src/core/uana_xform.o',
    'chuck-external/src/core/uana_extract.o',

    'chuck-external/src/core/lo/address.o',
    'chuck-external/src/core/lo/blob.o',
    'chuck-external/src/core/lo/bundle.o',
    'chuck-external/src/core/lo/message.o',
    'chuck-external/src/core/lo/method.o',
    'chuck-external/src/core/lo/pattern_match.o',
    'chuck-external/src/core/lo/send.o',
    'chuck-external/src/core/lo/server.o',
    'chuck-external/src/core/lo/server_thread.o',
    'chuck-external/src/core/lo/timetag.o',

    'chuck-external/src/core/util_sndfile.o',
]


SOURCES = [
    # _chuckpy.cpp contains the wrapper created by pybindgen
    # It should already exist, but if it doesn't, run generate_chuckpy_cpp.py
    '_chuckpy.cpp'
]


INCLUDE_DIRS = [
    '.',
    'chuck-external/src',
    'chuck-external/src/core',
    'chuck-external/src/core/lo'
]


EXTENSION_CONFIG = dict(
    sources=SOURCES,
    include_dirs=INCLUDE_DIRS,
    extra_objects=EXTRA_OBJECTS,
)


DARWIN_EXTENSION_CONFIG = dict(
    extra_compile_args=DARWIN_CFLAGS,
    extra_link_args=DARWIN_LDFLAGS,
    sources=SOURCES,
    include_dirs=INCLUDE_DIRS,
    extra_objects=EXTRA_OBJECTS,
)


def get_extension_config():
    system = platform.system()
    if system == 'Darwin':
        return DARWIN_EXTENSION_CONFIG
    else:
        return EXTENSION_CONFIG


MAKE_TARGETS = {
    'Darwin': 'osx',
    'Linux': 'linux-alsa',
    'Windows': 'win32',
}


chuckpy_extension = Extension(
    '_chuckpy',
    **get_extension_config()
)


def make():
    """
    Compile Chuck
    """
    cmd = ['make', MAKE_TARGETS[platform.system()]]
    subprocess.check_call(cmd, cwd='chuck-external/src')


class Install(install):
    def run(self, *args, **kwargs):
        make()
        install.run(*args, **kwargs)


class Develop(develop):
    def run(self, *args, **kwargs):
        make()
        develop.run(self, *args, **kwargs)


class BuildExt(build_ext):
    def run(self, *args, **kwargs):
        make()
        build_ext.run(self, *args, **kwargs)


setup(
    name='chuckpy',
    version='1.0.0',
    description='ChucK bindings for Python',
    author='Elijah Shaw-Rutschman',
    author_email='elijahr+chuckpy@gmail.com',
    packages=['chuckpy'],
    ext_modules=[chuckpy_extension],
    cmdclass={
        'install': Install,
        'develop': Develop,
        # 'build_py': BuildPy,
        'build_ext': BuildExt,
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Operating System :: MacOS :: MacOS X',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: MIDI',
        'Topic :: Multimedia :: Sound/Audio :: Sound Synthesis',
    ],
)

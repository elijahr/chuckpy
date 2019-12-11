import sys
from collections import OrderedDict

import pybindgen

from pybindgen import retval, param, Parameter

from pybindgen.typehandlers.base import ForwardWrapperBase


DEFINES = OrderedDict((
    ('t_CKINT', 'long'),
    ('t_CKFLOAT', 'double'),
    ('t_CKBOOL', 'unsigned long'),
    ('SAMPLE', 'float'),  # or double, if built with USE_64_BIT_SAMPLE
))

t_CKINT = 'long'
t_CKFLOAT = 'double'
t_CKBOOL = 'unsigned long'
SAMPLE = 'float'
SAMPLE_PTR = 'float *'

F_CK_Query_Callback_Code = """
class F_CK_Query_Callback_Wrapper {
PyObject * py_callback;
public:
F_CK_Query_Callback_Wrapper(PyObject * py_cb) {
    py_callback = py_cb;
    Py_INCREF(py_callback);
}
~F_CK_Query_Callback_Wrapper() {
    if (py_callback) {
        Py_XDECREF(py_callback);
        py_callback = NULL;
    }
}
static t_CKBOOL call(F_CK_Query_Callback_Wrapper * f_ck_query_callback_wrapper, Chuck_DL_Query QUERY) {
    PyChuck_DL_Query *pychuck_dl_query;
    pychuck_dl_query = PyObject_New(PyChuck_DL_Query, &PyChuck_DL_Query_Type);
    pychuck_dl_query->obj = &QUERY;
    pychuck_dl_query->flags = PYBINDGEN_WRAPPER_FLAG_NONE;

    PyObject *result = PyEval_CallObject(f_ck_query_callback_wrapper->py_callback, (PyObject*) pychuck_dl_query);
    
    Py_XDECREF(pychuck_dl_query);

    // Destroy after a single call
    delete f_ck_query_callback_wrapper;

    return (t_CKBOOL) PyLong_AsLong(result);
}
};
"""


class f_ck_query(Parameter):

    DIRECTIONS = [Parameter.DIRECTION_IN]
    CTYPES = ['f_ck_query']

    def convert_python_to_c(self, wrapper):
        assert isinstance(wrapper, ForwardWrapperBase)

        py_cb = wrapper.declarations.declare_variable("PyObject*", self.name)
        wrapper.parse_params.add_parameter('O', ['&'+py_cb], self.name)
        wrapper.before_call.write_error_check(
            '!PyCallable_Check({py_cb})'.format(py_cb=py_cb),
            'PyErr_SetString(PyExc_TypeError, "f_ck_query parameter must be callable");')

        # wrapper.before_call.write_code('''
        #     Py_XDECREF(my_callback);
        #     my_callback = cb;
        #
        #     // Build up the argument list...
        #     PyObject *arglist = Py_BuildValue("(OO)", *a, *b);
        #
        #     // ...for calling the Python compare function
        #     PyObject *result = PyEval_CallObject(py_compare_func, arglist);
        # ''')

        wrapper.before_call.write_code('''
            F_CK_Query_Callback_Wrapper * f_ck_query_callback_wrapper = new F_CK_Query_Callback_Wrapper({py_cb});
        '''.format(py_cb=py_cb))
        wrapper.call_params.append('''
        std::bind (&F_CK_Query_Callback_Wrapper::call, &f_ck_query_callback_wrapper, std::placeholders::_1)
        ''')
        # wrapper.before_call.write_code("Py_INCREF(%s);" % py_cb)
        # wrapper.before_call.add_cleanup_code("Py_DECREF(%s);" % py_cb)

    def convert_c_to_python(self, wrapper):
        raise NotImplementedError


def generate(f):
    module = pybindgen.Module('_chuckpy')
    # for key, value in DEFINES.items():
    #     module.header.writeln('''
    #     #define %s %s
    #     ''' % (key, value))
    # module.add_include('<functional>')  # for std::bind used by F_CK_Query_Callback_Wrapper
    module.add_include('"core/chuck_oo.h"')
    module.add_include('"core/util_thread.h"')
    module.add_include('"core/chuck_dl.h"')
    module.add_include('"core/util_raw.h"')
    module.add_include('"core/chuck_vm.h"')
    module.add_include('"core/chuck.h"')
    # module.header.writeln(F_CK_Query_Callback_Code)

    # module.body.writeln("""
    # void _wrap_callback(int value)
    # {
    # int arg;
    # PyObject *arglist;
    #
    # arg = value;
    # printf("@@@@ Inside the binding: %d %p\\n", value, my_callback); fflush(NULL);
    #
    # arglist = Py_BuildValue("(i)", arg);
    # PyObject_CallObject(my_callback, arglist);
    # Py_DECREF(arglist);
    # }
    # """)
    module.add_container('std::list<std::string>', 'std::string', 'list')

    Chuck_Object = module.add_struct('Chuck_Object')
    Chuck_Object.add_constructor([])

    Chuck_VM = module.add_struct('Chuck_VM', parent=Chuck_Object)
    Chuck_VM.add_constructor([])

    Chuck_Carrier = module.add_struct('Chuck_Carrier')
    Chuck_Carrier.add_constructor([])

    Chuck_Compiler = module.add_struct('Chuck_Compiler')
    Chuck_Compiler.add_constructor([])

    Chuck_VM_Object = module.add_struct('Chuck_VM_Object')
    Chuck_VM_Object.add_constructor([])

    Chuck_Env = module.add_struct('Chuck_Env', parent=Chuck_VM_Object)
    Chuck_Env.add_constructor([])

    Chuck_DL_Query = module.add_struct('Chuck_DL_Query', no_constructor=True)
    Chuck_DL_Query.add_constructor([
        param('Chuck_Carrier *', 'carrier', transfer_ownership=False)
    ])

    Chuck_DL_Query.add_method(
        'compiler',
        retval('Chuck_Compiler *', caller_owns_return=True),
        []
    )

    Chuck_DL_Query.add_method(
        'vm',
        retval('Chuck_VM *', caller_owns_return=True),
        []
    )

    Chuck_DL_Query.add_method(
        'env',
        retval('Chuck_Env *', caller_owns_return=True),
        []
    )

    ChucK = module.add_class('ChucK')
    ChucK.add_constructor([])
    ChucK.add_method(
        'setParam',
        retval('bool'),
        [
            param('const std::string &', 'name'),
            param(DEFINES['t_CKINT'], 'value')
        ])

    ChucK.add_method(
        'setParamFloat',
        retval('bool'),
        [
            param('const std::string &', 'name'),
            param(DEFINES['t_CKFLOAT'], 'value')
        ])

    ChucK.add_method(
        'setParam',
        retval('bool'),
        [
            param('const std::string &', 'name'),
            param('const std::string &', 'value'),
        ])

    ChucK.add_method(
        'setParam',
        retval('bool'),
        [
            param('const std::string &', 'name'),
            param('const std::list< std::string > &', 'value'),
        ])

    ChucK.add_method(
        'getParamInt',
        retval(DEFINES['t_CKINT']),
        [
            param('const std::string &', 'key'),
        ])

    ChucK.add_method(
        'getParamFloat',
        retval(DEFINES['t_CKFLOAT']),
        [
            param('const std::string &', 'key'),
        ])

    ChucK.add_method(
        'getParamString',
        retval('std::string'),
        [
            param('const std::string &', 'key'),
        ])

    ChucK.add_method(
        'getParamStringList',
        retval('std::list< std::string >'),
        [
            param('const std::string &', 'key'),
        ])

    ChucK.add_method(
        'compileFile',
        retval('bool'),
        [
            param('const std::string &', 'path'),
            param('const std::string &', 'argsTogether'),
            param('int', 'count', 1)
        ]
    )

    ChucK.add_method(
        'compileCode',
        retval('bool'),
        [
            param('const std::string &', 'code'),
            param('const std::string &', 'argsTogether'),
            param('int', 'count', 1)
        ]
    )

    ChucK.add_method(
        'init',
        retval('bool'),
        []
    )

    ChucK.add_method(
        'start',
        retval('bool'),
        []
    )

    ChucK.add_method(
        'run',
        retval('void'),
        [
            param(SAMPLE_PTR, 'input'),
            param(SAMPLE_PTR, 'output'),
            param('int', 'numFrames')
        ]
    )

    ChucK.add_method(
        'running',
        retval('bool'),
        []
    )
    #
    # ChucK.add_method(
    #     'bind',
    #     retval('bool'),
    #     [
    #         param('f_ck_query', 'queryFunc'),
    #         param('const std::string &', 'name'),
    #     ]
    # )

    ChucK.add_method(
        'vm',
        retval('Chuck_VM *', caller_owns_return=True),
        []
    )

    ChucK.add_method(
        'compiler',
        retval('Chuck_Compiler *', caller_owns_return=True),
        []
    )

    ChucK.add_method(
        'running',
        retval('bool'),
        []
    )

    module.generate(f)


if __name__ == '__main__':
    filename = '_chuckpy.cpp'
    with open(filename, 'wt') as f:
        generate(f)
        print('Generated file {}'.format(filename))

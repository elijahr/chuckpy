from methodtools import lru_cache
from pybindgen import Parameter
from pybindgen.typehandlers.base import PointerParameter, TypeConfigurationError, ForwardWrapperBase, NotSupportedError
from pybindgen.typehandlers.doubletype import DoubleParam, DoubleReturn
from pybindgen.typehandlers.floattype import FloatParam, FloatPtrParam
from pybindgen.typehandlers.inttype import LongParam, LongReturn, UnsignedLongParam, UnsignedLongReturn, \
    UnsignedIntParam


@lru_cache()
def configure_chuck_types():
    class UnsignedLongPointerParam(PointerParameter):
        DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT,
                      Parameter.DIRECTION_IN | Parameter.DIRECTION_OUT]
        CTYPES = ['unsigned long*']

        def __init__(self, ctype, name, direction=None, is_const=None, default_value=None, transfer_ownership=None):
            if direction is None:
                if is_const:
                    direction = Parameter.DIRECTION_IN
                else:
                    raise TypeConfigurationError("direction not given")

            super(UnsignedLongPointerParam, self).__init__(ctype, name, direction, is_const, default_value,
                                                           transfer_ownership)

        def convert_c_to_python(self, wrapper):
            if self.direction & self.DIRECTION_IN:
                wrapper.build_params.add_parameter('k', ['*' + self.value])
            if self.direction & self.DIRECTION_OUT:
                wrapper.parse_params.add_parameter("k", [self.value], self.name)

        def convert_python_to_c(self, wrapper):
            name = wrapper.declarations.declare_variable('int8_t', self.name)
            wrapper.call_params.append('&' + name)
            if self.direction & self.DIRECTION_IN:
                wrapper.parse_params.add_parameter('k', ['&' + name], self.name)
            if self.direction & self.DIRECTION_OUT:
                wrapper.build_params.add_parameter("k", [name])

    class param_t_CKINT(LongParam):
        CTYPES = ['t_CKINT']

    class retval_t_CKINT(LongReturn):
        CTYPES = ['t_CKINT']

    class param_t_CKUINT(UnsignedLongParam):
        CTYPES = ['t_CKUINT']

    class retval_t_CKUINT(UnsignedLongReturn):
        CTYPES = ['t_CKUINT']

    class param_t_CKFLOAT(DoubleParam):
        CTYPES = ['t_CKFLOAT']

    class retval_t_CKFLOAT(DoubleReturn):
        CTYPES = ['t_CKFLOAT']

    class param_t_CKBOOL(UnsignedLongParam):
        CTYPES = ['t_CKBOOL']

    class retval_t_CKBOOL(UnsignedLongReturn):
        CTYPES = ['t_CKBOOL']

    class param_t_CKBOOL_PTR(UnsignedLongPointerParam):
        CTYPES = ['t_CKBOOL *']

    class retval_t_CKBOOL_PTR(UnsignedLongReturn):
        CTYPES = ['t_CKBOOL *']

    class param_SAMPLE(FloatParam):
        CTYPES = ['SAMPLE']

    class param_SAMPLE_PTR(FloatPtrParam):
        CTYPES = ['SAMPLE*']

    class param_RtAudioStreamStatus(UnsignedIntParam):
        CTYPES = ['RtAudioStreamStatus']

    class param_f_audio_cb(Parameter):
        CTYPES = ['f_audio_cb']
        DIRECTIONS = [Parameter.DIRECTION_IN, Parameter.DIRECTION_OUT, Parameter.DIRECTION_INOUT]

        def convert_python_to_c(self, wrapper):
            assert isinstance(wrapper, ForwardWrapperBase)
            py_cb = wrapper.declarations.declare_variable("PyObject*", self.name)
            wrapper.parse_params.add_parameter('O', ['&' + py_cb], self.name)
            wrapper.before_call.write_error_check(
                "!PyCallable_Check(%s)" % py_cb,
                """PyErr_SetString(PyExc_TypeError, "f_audio_cb parameter must be callable");""")

            # Increase the ref count for py_cb since it will be (presumably) stored in
            # ChuckAudio::m_cb_user_data.
            # It will never get Py_DECREF'd completely, I guess that's a memory leak
            # but I'm not sure what to do about it right now.
            wrapper.before_call.write_code("Py_XINCREF(%s);" % py_cb)

            # Rather than pass f_audio_cb as the callback parameter,
            # pass _wrap_f_audio_cb, and replace userData with a pointer
            # to the python callback. This means userData can't be used
            # for other purposes. It feels a bit hacky to me, but allows
            # us to wrap f_audio_cb with python object conversions.
            wrapper.call_params.append('_wrap_f_audio_cb')
            wrapper.call_params.append('(void*)' + py_cb)

        def convert_c_to_python(self, wrapper):
            raise NotImplementedError


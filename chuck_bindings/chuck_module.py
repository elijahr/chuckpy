
import pybindgen
from methodtools import lru_cache
from pybindgen import retval, param

from chuck_bindings.chuck_types import configure_chuck_types


class ChuckModule(pybindgen.Module):
    def __init__(self):
        super(ChuckModule, self).__init__('_chuck')
        self.add_include('<stdio.h>')
        self.add_include('<numpy/arrayobject.h>')

        self.add_include('"chuck_def.h"')

        # self.add_include('"util_math.h"')
        # self.add_include('"util_raw.h"')

        self.add_include('"RtAudio.h"')
        self.add_include('"chuck_audio.h"')

        self.add_include('"chuck.h"')
        self.add_include('"chuck_vm.h"')

        # self.add_include('"chuck_oo.h"')
        self.add_include('"chuck_carrier.h"')
        # self.add_include('"chuck_dl.h"')
        # self.add_include('"util_thread.h"')

        self.configure_chuck_types()

        # Necessary for using numpy API
        self.before_init.write_code('import_array();')

        self.add_global_functions()
        self.add_chuck()
        self.add_chuck_audio()

    @lru_cache()
    def configure_chuck_types(self):
        configure_chuck_types()
        self.add_container('std::list<std::string>', 'std::string', 'list')

    @lru_cache()
    def add_global_functions(self):
        self.header.writeln(
            """
            PyObject* samples_to_numpy_array(SAMPLE * samples, t_CKUINT count, t_CKUINT shape);
            SAMPLE* numpy_array_to_samples(PyObject * npy_samples);
            
            // Wrapper for f_audio_cb which calls a Python function
            void _wrap_f_audio_cb(
                SAMPLE * input,
                SAMPLE * output,
                t_CKUINT num_frames,
                t_CKUINT num_in_chans,
                t_CKUINT num_out_chans,
                void * py_cb
            );
            static void log_obj(PyObject * o);
            """
        )
        self.body.writeln(
            """
            PyObject* samples_to_numpy_array(SAMPLE * samples, t_CKUINT num_frames, t_CKUINT num_channels) {
                npy_intp dims[num_frames];
                for (int i=0; i<num_frames; i++) {
                     dims[i] = num_channels;
                }
                PyObject* npy_samples = PyArray_SimpleNewFromData(num_channels, dims, NPY_DOUBLE, samples);
                return npy_samples;
            }
            
            SAMPLE* numpy_array_to_samples(PyObject * npy_samples) {
                SAMPLE * samples = (SAMPLE *)PyArray_DATA(npy_samples);
                //npy_intp * dims = PyArray_DIMS(npy_samples);
                //npy_int num_channels = dims[0];
                //npy_int num_frames = dims[1];                
                return samples;
            }
            
            // Wrapper for f_audio_cb which calls a Python function
            void _wrap_f_audio_cb(
                SAMPLE * input,
                SAMPLE * output,
                t_CKUINT num_frames,
                t_CKUINT num_in_chans,
                t_CKUINT num_out_chans,
                void * py_cb
            )
            {
                // acquire the GIL prior to running the callback
                PyGILState_STATE gil_state = PyGILState_Ensure();
                PyObject* input_numpy_array = samples_to_numpy_array(input, num_frames, num_in_chans);
                PyObject* output_numpy_array = samples_to_numpy_array(output, num_frames, num_out_chans);
                
                //PyArray_UpdateFlags((PyArrayObject *)input_numpy_array, NPY_ARRAY_OWNDATA);
                Py_XINCREF(input_numpy_array);
                //PyArray_UpdateFlags((PyArrayObject *)output_numpy_array, NPY_ARRAY_OWNDATA);
                Py_XINCREF(output_numpy_array);
                
                PyObject *callback = (PyObject*) py_cb;
                //log_obj(callback);
                PyObject *args = Py_BuildValue("(OOkkk)", input_numpy_array, output_numpy_array, num_frames, num_in_chans, num_out_chans);
                
                PyEval_CallObject(callback, args);
                
                Py_XDECREF(input_numpy_array);
                Py_XDECREF(output_numpy_array);
                Py_XDECREF(args);
                PyGILState_Release(gil_state);
            }

            static void log_obj(PyObject * o)
            {
                static PyObject *repr = NULL;
            
                // build msg-string
                repr = PyObject_Repr(o);
            
                const char* string = PyUnicode_AsUTF8(repr);
                EM_log( CK_LOG_CORE, string );
            
                Py_DECREF(repr);
            }

            """
        )
        # self.add_function('set_xthread_priority', retval('void'), [])
        self.add_function(
            'EM_setlog',
            retval('void'),
            [
                param('t_CKUINT', 'level'),
            ],
            custom_name='set_error_message_log_level'
        )
        self.add_function('mtof', retval('double'), [param('double', 'f')])
        self.add_function('ftom', retval('double'), [param('double', 'f')])
        self.add_function('powtodb', retval('double'), [param('double', 'f')])
        self.add_function('rmstodb', retval('double'), [param('double', 'f')])
        self.add_function('dbtopow', retval('double'), [param('double', 'f')])
        self.add_function('dbtorms', retval('double'), [param('double', 'f')])
        self.add_function('nextpow2', retval('unsigned long'), [param('unsigned long', 'i')])
        self.add_function('ensurepow2', retval('unsigned long'), [param('unsigned long', 'i')])

    @lru_cache()
    def add_rt_audio(self):
        RtAudio = self.add_class('RtAudio')
        RtAudio.add_constructor([])
        return RtAudio

    @lru_cache()
    def add_chuck_audio(self):
        self.add_rt_audio()

        # ChuckAudio is a global, shared singleton, not a constructable class, so lets snake-case it
        chuck_audio = self.add_class('ChuckAudio', is_singleton=True, custom_name='chuck_audio')

        chuck_audio.add_static_attribute('m_dac_n', 't_CKUINT')
        chuck_audio.add_static_attribute('m_adc_n', 't_CKUINT')
        chuck_audio.add_method(
            'initialize',
            retval('t_CKBOOL'),
            [
                param('t_CKUINT', 'num_dac_channels'),
                param('t_CKUINT', 'num_adc_channels'),
                param('t_CKUINT', 'sample_rate'),
                param('t_CKUINT', 'buffer_size'),
                param('t_CKUINT', 'num_buffers'),
                param('f_audio_cb', 'callback'),
                # Note that we omit the data argument; it is not supported because
                # we use it to pass the python callback via _wrap_f_audio_cb,
                # This should be fine, because presumably you have access in your
                # python callback to whatever data you want to use
                # in the callback.
                # param('PyObject*', 'data', transfer_ownership=True),
                param('t_CKBOOL', 'force_srate'),
            ],
            is_static=True,
            custom_name='initialize'
        )

        chuck_audio.add_method('shutdown', retval('void'),[], is_static=True)
        chuck_audio.add_method('start', retval('t_CKBOOL'),[], is_static=True)
        chuck_audio.add_method('stop', retval('t_CKBOOL'),[], is_static=True)
        chuck_audio.add_method('watchdog_start', retval('t_CKBOOL'),[], is_static=True)
        chuck_audio.add_method('watchdog_stop', retval('t_CKBOOL'),[], is_static=True)
        chuck_audio.add_method('probe', retval('void'),[], is_static=True)

        chuck_audio.add_method('srate', retval('t_CKUINT'),[], is_static=True, custom_name='get_sample_rate')
        chuck_audio.add_method('num_channels_out', retval('t_CKUINT'),[], is_static=True, custom_name='get_num_channels_out')
        chuck_audio.add_method('num_channels_in', retval('t_CKUINT'),[], is_static=True, custom_name='get_num_channels_in')
        chuck_audio.add_method('dac_num', retval('t_CKUINT'),[], is_static=True, custom_name='get_dac_num')
        chuck_audio.add_method('adc_num', retval('t_CKUINT'),[], is_static=True, custom_name='get_adc_num')
        # This method appears to be unused and ChuckAudio::m_bps never gets initialized so its an undefined symbol
        # chuck_audio.add_method('bps', retval('t_CKUINT'),[], is_static=True, custom_name='get_bps')
        chuck_audio.add_method('buffer_size', retval('t_CKUINT'),[], is_static=True, custom_name='get_buffer_size')
        chuck_audio.add_method('num_buffers', retval('t_CKUINT'),[], is_static=True, custom_name='get_num_buffers')

        chuck_audio.add_method('audio', retval('RtAudio *', caller_owns_return=True), [], is_static=True, custom_name='get_rt_audio')

        # for things like audicle
        chuck_audio.add_method(
            'set_extern',
            retval('void'),
            [
                param('SAMPLE *', 'in'),
                param('SAMPLE *', 'out'),
            ],
            is_static=True,
            custom_name='set_extern'
        )

        chuck_audio.add_method(
            'cb',
            retval('int'),
            [
                param('SAMPLE *', 'output_buffer'),
                param('SAMPLE *', 'input_buffer'),
                param('unsigned int', 'buffer_size'),
                param('double', 'streamTime'),
                param('RtAudioStreamStatus', 'status'),
                param('PyObject*', 'user_data', transfer_ownership=False),
            ],
            is_static=True,
            custom_name='cb'
        )
        return chuck_audio

    @lru_cache()
    def add_chuck_object(self):
        ChuckObject = self.add_struct('Chuck_Object', custom_name='ChuckObject')
        ChuckObject.add_constructor([])
        return ChuckObject

    @lru_cache()
    def add_chuck_carrier(self):
        ChuckCarrier = self.add_struct('Chuck_Carrier', custom_name='ChuckCarrier')
        ChuckCarrier.add_constructor([])
        return ChuckCarrier

    @lru_cache()
    def add_chuck_vm(self):
        # Depends on:
        self.add_chuck_carrier()
        ChuckObject = self.add_chuck_object()

        ChuckVM = self.add_struct('Chuck_VM', parent=ChuckObject, custom_name='ChuckVM')
        ChuckVM.add_constructor([])
        ChuckVM.add_method(
            'initialize',
            retval('t_CKBOOL'),
            [
                param('t_CKUINT', 'srate'),
                param('t_CKUINT', 'doc_chan'),
                param('t_CKUINT', 'adc_chan'),
                param('t_CKUINT', 'adaptive'),
                param('t_CKBOOL', 'halt'),
            ]
        )
        ChuckVM.add_method(
            'initialize_synthesis',
            retval('t_CKBOOL'),
            []
        )
        ChuckVM.add_method(
            'setCarrier',
            retval('t_CKBOOL'),
            [
                param('Chuck_Carrier *', 'c', transfer_ownership=False),
            ],
            custom_name='set_carrier'
        )
        ChuckVM.add_method(
            'shutdown',
            retval('t_CKBOOL'),
            []
        )
        ChuckVM.add_method(
            'has_init',
            retval('t_CKBOOL'),
            []
        )
        ChuckVM.add_method(
            'start',
            retval('t_CKBOOL'),
            []
        )
        ChuckVM.add_method(
            'stop',
            retval('t_CKBOOL'),
            []
        )
        return ChuckVM

    @lru_cache()
    def add_chuck(self):
        # Depends on:
        self.add_chuck_vm()

        Chuck = self.add_class('ChucK', custom_name='Chuck')
        Chuck.add_constructor([])
        Chuck.add_method(
            'setParam',
            retval('bool'),
            [
                param('const std::string &', 'name'),
                param('t_CKINT', 'value')
            ],
            custom_name='set_param'
        )

        Chuck.add_method(
            'setParamFloat',
            retval('bool'),
            [
                param('const std::string &', 'name'),
                param('t_CKFLOAT', 'value')
            ],
            custom_name='set_param_float'
        )

        Chuck.add_method(
            'setParam',
            retval('bool'),
            [
                param('const std::string &', 'name'),
                param('const std::string &', 'value'),
            ],
            custom_name='set_param'
        )

        Chuck.add_method(
            'setParam',
            retval('bool'),
            [
                param('const std::string &', 'name'),
                param('const std::list< std::string > &', 'value'),
            ],
            custom_name='set_param'
        )

        Chuck.add_method(
            'getParamInt',
            retval('t_CKINT'),
            [
                param('const std::string &', 'key'),
            ],
            custom_name='get_param_int'
        )

        Chuck.add_method(
            'getParamFloat',
            retval('t_CKFLOAT'),
            [
                param('const std::string &', 'key'),
            ],
            custom_name='get_param_float'
        )

        Chuck.add_method(
            'getParamString',
            retval('std::string'),
            [
                param('const std::string &', 'key'),
            ],
            custom_name='get_param_string'
        )

        Chuck.add_method(
            'getParamStringList',
            retval('std::list< std::string >'),
            [
                param('const std::string &', 'key'),
            ],
            custom_name='get_param_string_list'
        )

        Chuck.add_method(
            'compileFile',
            retval('bool'),
            [
                param('const std::string &', 'path'),
                param('const std::string &', 'argsTogether'),
                param('int', 'count', 1)
            ],
            custom_name='compile_file'
        )

        Chuck.add_method(
            'compileCode',
            retval('bool'),
            [
                param('const std::string &', 'code'),
                param('const std::string &', 'argsTogether'),
                param('int', 'count', 1)
            ],
            custom_name='compile_code'
        )

        Chuck.add_method(
            'init',
            retval('bool'),
            []
        )

        Chuck.add_method(
            'start',
            retval('bool'),
            []
        )


        chuck_run_body = '''
        PyObject * _wrap_PyChucK_run__inner(
            PyChucK *self,
            PyObject *args,
            PyObject *kwargs,
            PyObject **return_exception
        )
        {
            PyObject* input_numpy_array;
            PyObject* output_numpy_array;
            int numFrames;
            const char *keywords[] = {"input", "output", "numFrames", NULL};
            if (!PyArg_ParseTupleAndKeywords(args, kwargs, (char *) "OOi", (char **) keywords, &input_numpy_array, &output_numpy_array, &numFrames)) {
                PyObject *exc_type, *traceback;
                PyErr_Fetch(&exc_type, return_exception, &traceback);
                Py_XDECREF(exc_type);
                Py_XDECREF(traceback);
                return NULL;
            }
            SAMPLE * input = numpy_array_to_samples(input_numpy_array);
            SAMPLE * output = numpy_array_to_samples(output_numpy_array);
        
            Py_XINCREF(input_numpy_array);
            Py_XINCREF(output_numpy_array);

            //PyArray_UpdateFlags((PyArrayObject *)input_numpy_array, NPY_ARRAY_OWNDATA);
            //PyArray_UpdateFlags((PyArrayObject *)output_numpy_array, NPY_ARRAY_OWNDATA);
            
            self->obj->run(input, output, numFrames);
            
            Py_INCREF(Py_None);
            return Py_None;
        }
        '''
        Chuck.add_custom_method_wrapper('run', '_wrap_PyChucK_run__inner', chuck_run_body, flags=["METH_VARARGS", "METH_KEYWORDS"],)
        # Chuck.add_method(
        #     'run',
        #     retval('void'),
        #     [
        #         param('SAMPLE *', 'input'),
        #         param('SAMPLE *', 'output'),
        #         param('int', 'numFrames')
        #     ]
        # )

        Chuck.add_method(
            'running',
            retval('bool'),
            []
        )

        Chuck.add_method(
            'vm',
            retval('Chuck_VM *', caller_owns_return=True),
            []
        )

        Chuck.add_method(
            'setLogLevel',
            retval('void'),
            [
                param('t_CKINT', 'level')
            ],
            custom_name='set_log_level'
        )

        # Chuck.add_method(
        #     'compiler',
        #     retval('Chuck_Compiler *', caller_owns_return=True),
        #     []
        # )

        Chuck.add_method(
            'running',
            retval('bool'),
            []
        )
        return Chuck
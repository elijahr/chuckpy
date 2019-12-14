import logging
import platform
import signal
import sys
from time import sleep

import numpy
from _chuck import Chuck, chuck_audio, ensurepow2, nextpow2, set_error_message_log_level

logger = logging.getLogger('chuckpy')

CHUCK_PARAM_SAMPLE_RATE = "SAMPLE_RATE"
CHUCK_PARAM_LOG_LEVEL = "LOG_LEVEL"
CHUCK_PARAM_DUMP_INSTRUCTIONS = "DUMP_INSTRUCTIONS"
CHUCK_PARAM_DEPRECATE_LEVEL = "DEPRECATE_LEVEL"
CHUCK_PARAM_WORKING_DIRECTORY = "WORKING_DIRECTORY"

CHUCK_PARAM_SAMPLE_RATE = "SAMPLE_RATE"
CHUCK_PARAM_INPUT_CHANNELS = "INPUT_CHANNELS"
CHUCK_PARAM_OUTPUT_CHANNELS = "OUTPUT_CHANNELS"
CHUCK_PARAM_VM_ADAPTIVE = "VM_ADAPTIVE"
CHUCK_PARAM_VM_HALT = "VM_HALT"
CHUCK_PARAM_OTF_ENABLE = "OTF_ENABLE"
CHUCK_PARAM_OTF_PORT = "OTF_PORT"
CHUCK_PARAM_DUMP_INSTRUCTIONS = "DUMP_INSTRUCTIONS"
CHUCK_PARAM_AUTO_DEPEND = "AUTO_DEPEND"
CHUCK_PARAM_DEPRECATE_LEVEL = "DEPRECATE_LEVEL"
CHUCK_PARAM_WORKING_DIRECTORY = "WORKING_DIRECTORY"
CHUCK_PARAM_CHUGIN_ENABLE = "CHUGIN_ENABLE"
CHUCK_PARAM_CHUGIN_DIRECTORY = "CHUGIN_DIRECTORY"
CHUCK_PARAM_USER_CHUGINS = "USER_CHUGINS"
CHUCK_PARAM_USER_CHUGIN_DIRECTORIES = "USER_CHUGIN_DIRECTORIES"
CHUCK_PARAM_HINT_IS_REALTIME_AUDIO = "HINT_IS_REALTIME_AUDIO"

NUM_CHANNELS_DEFAULT = 2
NUM_BUFFERS_DEFAULT = 8
DEVICE_NUM_OUT_DEFAULT = 0
DEVICE_NUM_IN_DEFAULT = 0

HOST_NAME_DEFAULT = '0.0.0.0'
PORT_DEFAULT = 8888

CK_LOG_CRAZY = 10  # use this to log everything
CK_LOG_FINEST = 9
CK_LOG_FINER = 8
CK_LOG_FINE = 7
CK_LOG_CONFIG = 6
CK_LOG_INFO = 5
CK_LOG_WARNING = 4
CK_LOG_SEVERE = 3
CK_LOG_SYSTEM = 2
CK_LOG_CORE = 1
CK_LOG_NONE = 0  # use this to log nothing


RTAUDIO_INPUT_OVERFLOW = 0x1  # Input data was discarded because of an overflow condition at the driver.
RTAUDIO_OUTPUT_UNDERFLOW = 0x2  # The output buffer ran low, likely causing a gap in the output sound.

system = platform.system()

if system == 'Linux':
  SAMPLE_RATE_DEFAULT = 48000
  BUFFER_SIZE_DEFAULT = 256
elif system == 'Darwin':
  SAMPLE_RATE_DEFAULT = 44100
  BUFFER_SIZE_DEFAULT = 256
else:
  SAMPLE_RATE_DEFAULT = 44100
  BUFFER_SIZE_DEFAULT = 512


BUFFER_SIZE_DEFAULT = 16


class ChuckError(Exception):
    pass


chuck_sources = [
    '''
// run each stooge, or run three stooges concurrently
// %> chuck moe++ larry++ curly++

// impulse to filter to dac
SndBuf i => BiQuad f => Gain g => JCRev r => dac;
// second formant
i => BiQuad f2 => g;
// third formant
i => BiQuad f3 => g;

// set the filter's pole radius
0.800 => f.prad; .995 => f2.prad; .995 => f3.prad;
// set equal gain zeroes
1 => f.eqzs; 1 => f2.eqzs; 1 => f3.eqzs;
// initialize float variable
0.0 => float v => float v2;
// set filter gain
.1 => f.gain; .1 => f2.gain; .01 => f3.gain;
0.05 => r.mix;
// load glottal pop
"special:glot_pop" => i.read;
// play
1.0 => i.rate;
  
// infinite time-loop   
while( true )
{
    // set the current sample/impulse
    0 => i.pos;
    // sweep the filter resonant frequency
    250.0 + Math.sin(v*100.0)*20.0 => v2 => f.pfreq;
    2290.0 + Math.sin(v*200.0)*50.0 => f2.pfreq;
    3010.0 + Math.sin(v*300.0)*80.0 => f3.pfreq;
    // increment v
    v + .05 => v;
    // gain
    0.2 + Math.sin(v)*.1 => g.gain;
    // advance time
    (1000.0 + Math.random2f(-100.0, 100.0))::ms => now;
}
''',
'''
// run each stooge, or run three stooges concurrently
// %> chuck moe++ larry++ curly++

// impulse to filter to dac
SndBuf i => NRev r => dac;

// load glottal ooo
"special:glot_ooo" => i.read;
// play 
//5.0 => i.rate;
.1 => r.mix;

0.0 => float v;
  
// infinite time-loop   
while( true )
{
    // set the current sample/impulse
    0 => i.pos;
    // control gain
    Math.cos(v) => i.gain;
    // increment v
    .05 +=> v;
    // advance time
    81.0::ms => now;
}
''',
'''
// run each stooge, or run three stooges concurrently
// %> chuck moe larry curly

// impulse to filter to dac
Impulse i => BiQuad f => dac;
// set the filter's pole radius
.99 => f.prad; 
// set equal gain zeros
1 => f.eqzs;
// initialize float variable
0.0 => float v;
// set filter gain
.5 => f.gain;
  
// infinite time-loop   
while( true )
{
    // set the current sample/impulse
    1.0 => i.next;
    // sweep the filter resonant frequency
    Std.fabs(Math.sin(v)) * 4000.0 => f.pfreq;
    // increment v
    v + .1 => v;
    // advance time
    100::ms => now;
}
'''
]

def go(
    sample_rate=SAMPLE_RATE_DEFAULT,
    dac_chans=NUM_CHANNELS_DEFAULT,
    adc_chans=NUM_CHANNELS_DEFAULT,
    # host_name=HOST_NAME_DEFAULT,
    dac=0,
    adc=0,
    port=PORT_DEFAULT,
    dump=True,
    chugins=None,
    chugin_paths=None,
    use_realtime_audio=True,
    num_buffers=NUM_BUFFERS_DEFAULT,
    buffer_size=BUFFER_SIZE_DEFAULT,
    log_level=CK_LOG_CORE
):
    if chugins is None:
        chugins = []
    if chugin_paths is None:
        chugin_paths = []

    if not ensurepow2(buffer_size):
        buffer_size = nextpow2(buffer_size)

    chuck = Chuck()
    chuck.set_param(CHUCK_PARAM_SAMPLE_RATE, sample_rate)
    chuck.set_param(CHUCK_PARAM_INPUT_CHANNELS, dac_chans)
    chuck.set_param(CHUCK_PARAM_OUTPUT_CHANNELS, adc_chans)
    chuck.set_param(CHUCK_PARAM_VM_HALT, False)
    chuck.set_param(CHUCK_PARAM_OTF_PORT, port)
    chuck.set_param(CHUCK_PARAM_OTF_ENABLE, True)
    chuck.set_param(CHUCK_PARAM_DUMP_INSTRUCTIONS, dump)
    chuck.set_param(CHUCK_PARAM_AUTO_DEPEND, False)
    chuck.set_param(CHUCK_PARAM_DEPRECATE_LEVEL, 1)  # warn only
    chuck.set_param(CHUCK_PARAM_USER_CHUGINS, chugins)
    chuck.set_param(CHUCK_PARAM_USER_CHUGIN_DIRECTORIES, chugin_paths)

    # set hint, so internally can advise things like async data writes etc.
    chuck.set_param(CHUCK_PARAM_HINT_IS_REALTIME_AUDIO, use_realtime_audio)

    set_error_message_log_level(log_level)
    chuck.set_log_level(log_level)

    if not chuck.init():
        raise ChuckError('Failed to initialize Chuck')

    def callback(sample_in, sample_out, num_frames, num_in_chans, num_out_chans):
        # print('in callback', sample_in, sample_out)
        # print('here', sample_in, sample_out, num_frames, num_in_chans, num_out_chans)
        chuck.run(sample_in, sample_out, num_frames)

    logger.info('Initializing Audio IO')
    logger.info('Probing \'%s\' audio subsystem...' % ('real-time' if use_realtime_audio else 'fake-time'))
    if use_realtime_audio:
        chuck_audio.m_adc_n = adc
        chuck_audio.m_dac_n = dac
        force_srate = sample_rate != SAMPLE_RATE_DEFAULT
        initialized = chuck_audio.initialize(
            dac_chans,
            adc_chans,
            sample_rate,
            buffer_size,
            num_buffers,
            callback,
            force_srate
        )
        if not initialized:
            raise ChuckError('Cannot initialize Audio IO')
    for code in chuck_sources:
        chuck.compile_code(code, '', 1)

    chuck.start()
    if not chuck_audio.start():
        raise ChuckError('Could not start chuck audio')

    # RtAudio uses an interleaved data format, so we use the shape
    # (buffer_size, dac_chans) rather than (dac_chans, buffer_size)
    samples_in = numpy.zeros((buffer_size, dac_chans), numpy.single)
    samples_out = numpy.zeros((buffer_size, adc_chans), numpy.single)
    while chuck.running():
        sleep(100)


def signalint_handler(sig, frame):
    print('You pressed Ctrl+C!')
    sys.exit(0)


signal.signal(signal.SIGINT, signalint_handler)
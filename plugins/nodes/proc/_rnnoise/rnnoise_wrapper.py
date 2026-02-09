"""
RNNoise C Wrapper
Provides a Python interface to the RNNoise library for noise suppression.
Requires the RNNoise library to be installed and accessible as a shared library.
Installation:
  git clone https://github.com/xiph/rnnoise.git
  cd rnnoise && \
    ./autogen.sh && \
    ./configure && make && sudo make install
"""

import ctypes
from pathlib import Path
import numpy as np


class RNNoiseWrapper:
    """
    RNNoise C Wrapper

    Attributes
    ----------
    SAMPLE_RATE : int
        Sample rate (fixed at 48000 Hz)
    FRAME_SIZE : int
        Frame size in samples (fixed at 480 = 10ms @ 48kHz)

    """

    SAMPLE_RATE = 48000
    FRAME_SIZE = 480

    def __init__(self, lib_path: str = None):
        """
        Load the RNNoise library
        Parameters

        ----------
        lib_path : str, optional
            Custom path to the library. If None, searches in standard paths.
        """
        self.lib = self._load_library(lib_path)
        self._setup_functions()
        self.state = self.lib.rnnoise_create(None)

    def _load_library(self, lib_path: str = None):
        if lib_path and Path(lib_path).exists():
            return ctypes.CDLL(lib_path)

        search_paths = [
            '/usr/local/lib/librnnoise.so',
            '/usr/lib/librnnoise.so',
            'librnnoise.so',
            './librnnoise.so',
        ]

        for path in search_paths:
            try:
                return ctypes.CDLL(path)
            except OSError:
                continue

        raise RuntimeError(
            'librnnoise.so not found. Install RNNoise: ./instal_rnnoise.sh'
        )

    def _setup_functions(self):
        # DenoiseState* rnnoise_create(RNNModel *model)
        self.lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_create.restype = ctypes.c_void_p

        # void rnnoise_destroy(DenoiseState *st)
        self.lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        self.lib.rnnoise_destroy.restype = None

        # float rnnoise_process_frame(DenoiseState *st, float *out, const float *in)  # noqa: E501
        self.lib.rnnoise_process_frame.argtypes = [
            ctypes.c_void_p,  # DenoiseState pointer
            ctypes.POINTER(ctypes.c_float),  # float *out
            ctypes.POINTER(ctypes.c_float),  # const float *in
        ]
        self.lib.rnnoise_process_frame.restype = (
            ctypes.c_float
        )  # vad probability

    def process_frame(
        self,
        audio_frame: np.ndarray,
    ) -> tuple[np.ndarray, float]:
        """
        Process a single audio frame

        Parameters
        ----------
        audio_frame : np.ndarray
            Audio frame of 480 samples (10ms @ 48kHz), float32
        resample : bool, optional
            Whether to resample input audio to 48kHz if it's not already.
        keep_original_sr : bool, optional
            Whether to keep the original sample rate in the output payload
             (only relevant if resampling is applied).

        Returns
        -------
        tuple[np.ndarray, float]
            - Audio denoised (480 samples, float32)
            - VAD probability (0.0-1.0)

        Raises
        ------
        ValueError
            If the input frame is not 480 samples long

        """
        if len(audio_frame) != RNNoiseWrapper.FRAME_SIZE:
            raise ValueError(
                f'Frame must be {RNNoiseWrapper.FRAME_SIZE} samples,'
                f' received {len(audio_frame)}'
            )

        frame = audio_frame.astype(np.float32, copy=False)
        output = np.zeros(RNNoiseWrapper.FRAME_SIZE, dtype=np.float32)

        frame_ptr = frame.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        output_ptr = output.ctypes.data_as(ctypes.POINTER(ctypes.c_float))

        vad_prob = self.lib.rnnoise_process_frame(
            self.state, output_ptr, frame_ptr
        )

        return output, vad_prob

    def __del__(self):
        """Cleanup"""
        if hasattr(self, 'state') and self.state:
            self.lib.rnnoise_destroy(self.state)

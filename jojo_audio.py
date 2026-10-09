"""Bounded microphone capture and sample-count based speech segmentation."""
from collections import deque
import math
import queue
import threading
import time
import numpy as np

class SpeechSegmenter:
    def __init__(self, sample_rate=16000, block_size=800, max_seconds=30, pause_seconds=1.1):
        self.sample_rate, self.block_size = sample_rate, block_size
        self.max_samples = int(max_seconds * sample_rate)
        self.pause_samples = int(pause_seconds * sample_rate)
        self.noise = 60.0
        self.pre = deque(maxlen=max(1, int(.4 * sample_rate / block_size)))
        self.reset()

    def reset(self):
        self.pre.clear()
        self.blocks = []
        self.samples = self.silence = self.onset = self.voiced = 0
        self.active = False

    def feed(self, block):
        block = np.asarray(block, dtype=np.int16)
        rms = float(np.sqrt(np.mean(block.astype(np.float32) ** 2)))
        voiced = rms >= max(180, self.noise * (2.2 if self.active else 3.0))
        if not self.active:
            self.pre.append(block)
            if not voiced:
                self.noise = .98 * self.noise + .02 * rms
            self.onset = self.onset + len(block) if voiced else 0
            if self.onset < self.sample_rate * .1:
                return None
            self.active = True
            self.blocks = list(self.pre)
            self.samples = sum(len(item) for item in self.blocks)
            self.voiced = self.onset
        else:
            self.blocks.append(block)
            self.samples += len(block)
            self.voiced += len(block) if voiced else 0
            self.silence = 0 if voiced else self.silence + len(block)
        if self.silence >= self.pause_samples or self.samples >= self.max_samples:
            audio = np.concatenate(self.blocks) if self.voiced >= self.sample_rate * .25 else None
            self.reset()
            return audio
        return None

class MicrophoneListener:
    def __init__(self, sample_rate=16000, block_size=800, device=None,
                 suppressed=lambda: False, on_error=lambda message: None, language='hi-IN'):
        import speech_recognition as sr
        self.recognizer = sr.Recognizer()
        self.recognizer.operation_timeout = 6
        self.sample_rate, self.block_size, self.device = sample_rate, block_size, device
        self.suppressed, self.on_error, self.language = suppressed, on_error, language
        self.q = queue.Queue(maxsize=64)
        self.stream = None
        self._running = False
        self._next_start = 0
        self.lock = threading.RLock()

    def _callback(self, indata, frames, time_info, status):
        # Drop speech playback immediately; do not accumulate minutes of stale commands.
        if self.suppressed():
            self.flush()
            return
        item = (time.monotonic(), indata[:, 0].copy())
        try:
            self.q.put_nowait(item)
        except queue.Full:
            try:
                self.q.get_nowait()
            except queue.Empty:
                pass
            try:
                self.q.put_nowait(item)
            except queue.Full:
                pass

    def flush(self):
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                return

    def close(self):
        with self.lock:
            self._running = False
            if self.stream is not None:
                try:
                    self.stream.stop()
                    self.stream.close()
                finally:
                    self.stream = None
            self.flush()

    def start(self):
        import sounddevice as sd
        if time.monotonic() < self._next_start:
            return
        with self.lock:
            self.close()
            errors = []
            for device in dict.fromkeys((self.device, None)):
                try:
                    info = sd.query_devices(device, 'input')
                    native_rate = int(info['default_samplerate'])
                    self.capture_rate = native_rate
                    block_size = max(1, native_rate // 20)
                    self.segmenter = SpeechSegmenter(native_rate, block_size)
                    self.stream = sd.InputStream(samplerate=native_rate, blocksize=block_size,
                        channels=1, dtype='int16', device=device, callback=self._callback)
                    self.stream.start()
                    self._running = True
                    self.on_error('' if device == self.device else 'Selected microphone unavailable; using Windows default.')
                    return
                except Exception as exc:
                    errors.append(type(exc).__name__)
                    self.close()
            self._next_start = time.monotonic() + 3
            self.on_error('Microphone unavailable (' + ', '.join(errors) + '). Select an input device or use text.')

    def listen(self, timeout=3.0, max_speech_duration=30):
        if not self._running or not getattr(self.stream, 'active', False):
            self.start()
            if not self._running:
                time.sleep(.15)
                return '', None
        self.segmenter.max_samples = int(max_speech_duration * self.capture_rate)
        self.segmenter.reset()
        deadline = time.monotonic() + timeout
        last_block = time.monotonic()
        while True:
            if self.suppressed():
                self.flush()
                time.sleep(.08)
                return '', None
            try:
                timestamp, block = self.q.get(timeout=.1)
            except queue.Empty:
                if time.monotonic() - last_block > 2:
                    self.close()
                    self.on_error('Microphone stream stalled; reconnecting…')
                    return '', None
                if not self.segmenter.active and time.monotonic() >= deadline:
                    return '', None
                continue
            last_block = time.monotonic()
            if last_block - timestamp > 2.5:
                continue
            audio = self.segmenter.feed(block)
            if audio is not None:
                break
            if not self.segmenter.active and time.monotonic() >= deadline:
                return '', None
        if self.capture_rate != self.sample_rate:
            from scipy.signal import resample_poly
            divisor = math.gcd(self.sample_rate, self.capture_rate)
            audio = np.clip(resample_poly(audio.astype(float), self.sample_rate // divisor,
                            self.capture_rate // divisor), -32768, 32767).astype(np.int16)
        return self.transcribe(audio), audio

    def transcribe(self, audio):
        import speech_recognition as sr
        data = sr.AudioData(audio.tobytes(), self.sample_rate, 2)
        languages = [self.language, 'en-IN' if self.language == 'hi-IN' else 'hi-IN']
        for language in languages:
            try:
                result = self.recognizer.recognize_google(data, language=language)
                self.on_error('')
                return result.strip()
            except sr.UnknownValueError:
                continue
            except (sr.RequestError, TimeoutError, OSError) as exc:
                self.on_error('Speech service unavailable (' + type(exc).__name__ + '). Text commands still work.')
                return ''
        self.on_error('Awaaz clear nahi samajh aayi. Dobara boliye ya command type kijiye.')
        return ''

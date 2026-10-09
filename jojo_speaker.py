"""Local neural speaker embeddings; explicit enrollment, never auto-adaptation."""
import hashlib
import json
from pathlib import Path
import sys
import threading
import numpy as np
from jojo_config import ROOT, DATA_DIR

MODEL = ROOT / 'models/wespeaker_en_voxceleb_resnet34_LM.onnx'
MODEL_SHA256 = 'e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012'

class SpeakerVerifier:
    def __init__(self, directory=DATA_DIR):
        self.path = Path(directory) / 'jojo_owner_voice.npz'
        self.lock = threading.RLock()
        self.extractor = None
        self.profile = None
        self.error = ''
        self.model_hash = ''
        try:
            self.model_hash = hashlib.sha256(MODEL.read_bytes()).hexdigest() if MODEL.is_file() else ''
            if self.path.exists():
                with np.load(self.path, allow_pickle=False) as saved:
                    profile = np.asarray(saved['profile'], dtype=np.float32)
                    if str(saved['model_hash']) != self.model_hash or not np.all(np.isfinite(profile)):
                        raise ValueError('Model changed or invalid voice profile. Re-enroll your voice.')
                    self.profile = self.normalize(profile)
        except Exception as exc:
            self.error = str(exc)

    @staticmethod
    def normalize(vector):
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm < 1e-6:
            raise ValueError('Invalid speaker embedding')
        return vector / norm

    def load_model(self):
        if self.extractor is not None:
            return
        if not MODEL.is_file():
            raise RuntimeError('Install the local model using jojo_setup_voice.py first.')
        if self.model_hash != MODEL_SHA256:
            raise RuntimeError('Speaker model checksum mismatch. Reinstall the verified model.')
        local = str(ROOT / '.jojo-deps/python')
        if local not in sys.path:
            sys.path.insert(0, local)
        import sherpa_onnx
        config = sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(MODEL), num_threads=2, provider='cpu')
        if not config.validate():
            raise RuntimeError('Speaker model configuration is invalid.')
        self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(config)

    def embedding(self, audio):
        samples = np.asarray(audio, dtype=np.float32).flatten()
        if len(samples) < 8000 or not np.all(np.isfinite(samples)):
            raise ValueError('Speak a clear phrase of at least half a second.')
        if float(np.sqrt(np.mean(samples*samples))) < 100:
            raise ValueError('Voice recording is too quiet.')
        samples = np.ascontiguousarray(samples/32768)
        with self.lock:
            self.load_model()
            stream = self.extractor.create_stream()
            stream.accept_waveform(sample_rate=16000, waveform=samples)
            stream.input_finished()
            if not self.extractor.is_ready(stream):
                raise ValueError('Not enough speech to verify the speaker.')
            return self.normalize(np.asarray(self.extractor.compute(stream), dtype=np.float32))

    def enroll(self, audio):
        if len(audio) < 6*16000:
            raise ValueError('Enrollment requires at least six seconds of speech.')
        with self.lock:
            embeddings = [self.embedding(chunk) for chunk in np.array_split(audio, 3)]
            consistency = min(float(np.dot(a,b)) for i,a in enumerate(embeddings) for b in embeddings[i+1:])
            if consistency < .55:
                raise ValueError('Enrollment samples are inconsistent. Use one speaker, less noise, and speak throughout the recording.')
            profile = self.normalize(np.mean(embeddings, axis=0))
            temporary = self.path.with_suffix('.tmp')
            with temporary.open('wb') as out:
                np.savez(out, profile=profile, model_hash=self.model_hash, samples=3, consistency=consistency)
            temporary.replace(self.path)
            self.profile = profile
            self.error = ''
            return profile

    def verify(self, audio, threshold=.65):
        if self.profile is None:
            return False, 0.0
        try:
            with self.lock:
                vector = self.embedding(audio)
                score = float(np.dot(vector,self.profile))
            return score >= max(.6, min(.95, threshold)), score
        except Exception as exc:
            self.error = str(exc)
            return False, 0.0

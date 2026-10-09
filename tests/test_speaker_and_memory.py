"""No real microphone use; speaker decisions use controlled embeddings."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from jojo_speaker import SpeakerVerifier
import jojo_journal as journal

class SpeakerTests(unittest.TestCase):
    def test_missing_profile_is_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            verifier=SpeakerVerifier(folder)
            self.assertEqual(verifier.verify(np.ones(16000)),(False,0.0))

    def test_owner_and_other_speaker_embeddings(self):
        with tempfile.TemporaryDirectory() as folder:
            verifier=SpeakerVerifier(folder);verifier.profile=np.array([1.,0.])
            with patch.object(verifier,'embedding',return_value=np.array([1.,0.])):
                self.assertTrue(verifier.verify(np.ones(16000))[0])
            with patch.object(verifier,'embedding',return_value=np.array([0.,1.])):
                self.assertFalse(verifier.verify(np.ones(16000))[0])

    def test_three_consistent_enrollment_samples_survive_reload(self):
        with tempfile.TemporaryDirectory() as folder:
            verifier=SpeakerVerifier(folder)
            with patch.object(verifier,'embedding',return_value=np.array([1.,0.])) as embed:
                verifier.enroll(np.ones(9*16000))
                self.assertEqual(embed.call_count,3)
            restored=SpeakerVerifier(folder)
            np.testing.assert_array_equal(restored.profile,[1.,0.])

    def test_inconsistent_enrollment_never_overwrites_profile(self):
        with tempfile.TemporaryDirectory() as folder:
            verifier=SpeakerVerifier(folder)
            with patch.object(verifier,'embedding',side_effect=[np.array([1.,0.]),np.array([0.,1.]),np.array([1.,0.])]):
                with self.assertRaises(ValueError):verifier.enroll(np.ones(9*16000))
            self.assertFalse(verifier.path.exists())

    def test_silence_and_short_audio_rejected_before_model(self):
        with tempfile.TemporaryDirectory() as folder:
            verifier=SpeakerVerifier(folder)
            for audio in [np.zeros(16000),np.ones(100),np.full(16000,np.nan)]:
                with self.assertRaises(ValueError):verifier.embedding(audio)

class DurableRecallTests(unittest.TestCase):
    def test_old_memory_recalled_beyond_last_300(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(journal,'DATA_DIR',Path(folder)):
            with journal.connect() as db:
                db.executemany('INSERT INTO turns VALUES (?,?,?,?,?,?,?)',[(str(i),i,'laptop','favorite fruit guava' if i==0 else 'unrelated chat', 'saved','completed','[]') for i in range(350)])
            self.assertIn('guava',journal.recall('guava'))

    def test_restart_marks_unfinished_without_replay(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(journal,'DATA_DIR',Path(folder)):
            journal.record({'id':'q','source':'laptop','message':'a task','reply':'','status':'queued'})
            journal.recover_interrupted()
            self.assertEqual(journal.history()[0]['status'],'incomplete')
            self.assertIn('No actions were replayed',journal.history()[0]['reply'])

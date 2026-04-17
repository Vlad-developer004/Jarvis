import wave
class Responder:
    def __init__(self, pa, wav_path: str):
        self.pa = pa
        self._bytes, self._fmt_width, self._ch, self._rate = self._load_wav(wav_path)
    @staticmethod
    def _load_wav(path: str):
        wf = wave.open(path, 'rb')
        w = wf.getsampwidth()
        ch = wf.getnchannels()
        r = wf.getframerate()
        parts = []
        blk = 4096
        d = wf.readframes(blk)
        while d:
            parts.append(d)
            d = wf.readframes(blk)
        wf.close()
        import numpy as np
        data = b''.join(parts)
        if w == 2:
            arr = np.frombuffer(data, dtype=np.int16).astype(np.float32)
            arr = (arr * 1.3).clip(-32768, 32767).astype(np.int16)
            data = arr.tobytes()
        return (data, w, ch, r)
    def play(self):
        try:
            out = self.pa.open(format=self.pa.get_format_from_width(self._fmt_width), channels=self._ch, rate=self._rate, output=True)
        except Exception as e:
            return
        pos = 0
        blk = 4096
        data = self._bytes
        ln = len(data)
        try:
            while pos < ln:
                out.write(data[pos:pos + blk])
                pos += blk
        except OSError as e:
            pass
        except Exception as e:
            pass
        finally:
            import time
            time.sleep(0.2)
            try:
                out.stop_stream()
            except Exception:
                pass
            try:
                out.close()
            except Exception:
                pass
    def close(self):
        self._bytes = None
        self.pa = None

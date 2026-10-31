"""Musik latar buatan sendiri (sintesis lewat kode) - bebas hak cipta, aman untuk monetisasi.

Tiga gaya dipilih acak: ceria, santai, energik. Tanpa library tambahan (hanya Python + ffmpeg).
"""
import math
import os
import random
import subprocess
import tempfile
import wave
from array import array

SR = 32000

GAYA = {
    # bpm, progresi (bass, akor), kick, clap, arp per ketukan, volume pad
    "ceria": dict(bpm=112, kick=[0, 1, 2, 3], clap=[1, 3], hat=True, bass8=False, pad=0.05,
                  prog=[(36, [60, 64, 67]), (43, [59, 62, 67]), (45, [60, 64, 69]), (41, [60, 65, 69])]),
    "santai": dict(bpm=84, kick=[0, 2], clap=[], hat=True, bass8=False, pad=0.08,
                   prog=[(45, [57, 60, 64]), (41, [57, 60, 65]), (36, [55, 60, 64]), (43, [55, 59, 62])]),
    "energik": dict(bpm=124, kick=[0, 1, 2, 3], clap=[1, 3], hat=True, bass8=True, pad=0.04,
                    prog=[(33, [57, 60, 64]), (41, [60, 65, 69]), (36, [60, 64, 67]), (43, [59, 62, 67])]),
}


def _hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def _add(buf, start, samples, gain=1.0):
    n = len(buf)
    for i, v in enumerate(samples):
        j = start + i
        if j >= n:
            break
        buf[j] += v * gain


def _pluck(m, dur, amp):
    f = _hz(m)
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, t / 0.004) * math.exp(-5.5 * t)
        out.append(env * amp * (math.sin(2 * math.pi * f * t) + 0.35 * math.sin(4 * math.pi * f * t)
                                + 0.15 * math.sin(6 * math.pi * f * t)))
    return out


def _tone(m, dur, amp, attack=0.25, release=0.3, detune=0.0):
    f = _hz(m)
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env = min(1.0, t / attack) * min(1.0, max(0.0, (dur - t) / release))
        out.append(env * amp * (math.sin(2 * math.pi * f * t) + math.sin(2 * math.pi * (f + detune) * t)) * 0.5)
    return out


def _bass(m, dur, amp):
    f = _hz(m)
    n = int(SR * dur)
    return [min(1.0, (i / SR) / 0.005) * math.exp(-3.2 * (i / SR)) * amp * math.sin(2 * math.pi * f * (i / SR))
            for i in range(n)]


def _kick(amp):
    n = int(SR * 0.22)
    out, ph = [], 0.0
    for i in range(n):
        t = i / SR
        ph += 2 * math.pi * (45 + 90 * math.exp(-28 * t)) / SR
        out.append(amp * math.exp(-11 * t) * math.sin(ph))
    return out


def _noise(dur, amp, decay, rnd):
    n = int(SR * dur)
    return [amp * math.exp(-decay * (i / SR)) * (rnd.random() * 2 - 1) for i in range(n)]


def buat_musik(out_mp3, dur, gaya=None, seed=None):
    rnd = random.Random(seed)
    nama = gaya or rnd.choice(list(GAYA))
    g = GAYA[nama]
    total = int(SR * (dur + 1.0))
    buf = [0.0] * total
    beat = 60.0 / g["bpm"]
    bar = beat * 4
    n_bar = int((dur + 1.0) / bar) + 2
    for b in range(n_bar):
        bassnote, chord = g["prog"][b % 4]
        t0 = b * bar
        s0 = int(t0 * SR)
        if s0 >= total:
            break
        _add(buf, s0, _tone(chord[0], bar, g["pad"], detune=0.6), 1.0)
        _add(buf, s0, _tone(chord[1], bar, g["pad"], detune=-0.5), 1.0)
        _add(buf, s0, _tone(chord[2], bar, g["pad"], detune=0.4), 1.0)
        seq = [chord[0], chord[1], chord[2], chord[1] + 12, chord[2], chord[1], chord[0] + 12, chord[1]]
        for k, m in enumerate(seq):
            tk = t0 + k * beat / 2
            _add(buf, int(tk * SR), _pluck(m, beat * 1.4, 0.16), 1.0)
        for k in ([0, 2] if not g["bass8"] else range(8)):
            tk = t0 + (k * beat if not g["bass8"] else k * beat / 2)
            _add(buf, int(tk * SR), _bass(bassnote, beat * 1.2, 0.34), 1.0)
        for k in g["kick"]:
            _add(buf, int((t0 + k * beat) * SR), _kick(0.55), 1.0)
        for k in g["clap"]:
            _add(buf, int((t0 + k * beat) * SR), _noise(0.14, 0.17, 24, rnd), 1.0)
        if g["hat"]:
            for k in range(4):
                _add(buf, int((t0 + k * beat + beat / 2) * SR), _noise(0.05, 0.07, 70, rnd), 1.0)
    peak = max(1e-6, max(abs(v) for v in buf))
    scale = 0.85 / peak
    fade = int(SR * 1.2)
    for i in range(fade):
        buf[total - 1 - i] *= i / fade
    pcm = array("h", (int(max(-1.0, min(1.0, v * scale)) * 32767) for v in buf))
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "m.wav")
        with wave.open(wav, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ac", "2", "-ar", "44100",
                        "-b:a", "160k", str(out_mp3)], check=True)
    return nama


if __name__ == "__main__":
    import sys
    print(buat_musik(sys.argv[1], float(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else None, 1))

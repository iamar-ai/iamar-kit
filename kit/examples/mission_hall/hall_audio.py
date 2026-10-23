"""Synthesises the Mission Hall's sounds (no recordings needed) into <package>/audio/.

    python3 kit/examples/mission_hall/hall_audio.py worlds/mission_hall

  hall_ambience.ogg  a big stone room: low air, a distant murmur of voices, a faint chord (loops)
  brazier.ogg        a fire crackling in a brazier (loops, for positional sounds)
Needs numpy and ffmpeg (libvorbis).
"""
import os
import subprocess
import sys
import wave

import numpy as np

RATE = 44100
out_dir = os.path.join(sys.argv[1] if len(sys.argv) > 1 else "worlds/mission_hall", "audio")
os.makedirs(out_dir, exist_ok=True)
rng = np.random.default_rng(11)


def lowpass(x, a):
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):
        acc += (x[i] - acc) * a
        y[i] = acc
    return y


def fast_lowpass(x, a, passes=1):
    # a one-pole filter applied in blocks via cumulative recursion (lfilter-free)
    for _ in range(passes):
        y = np.empty_like(x)
        acc = 0.0
        blk = 4096
        for s in range(0, len(x), blk):
            seg = x[s:s + blk]
            out = np.empty_like(seg)
            for i, v in enumerate(seg):
                acc += (v - acc) * a
                out[i] = acc
            y[s:s + blk] = out
        x = y
    return x


def loop_fade(x, seconds=1.5):
    """Crossfade the end into the start so the file loops seamlessly."""
    n = int(seconds * RATE)
    head, tail = x[:n].copy(), x[-n:].copy()
    t = np.linspace(0, 1, n)
    x = x[:-n].copy()
    x[:n] = head * t + tail * (1 - t)
    return x


def reverb(x, mix=0.35):
    y = x.copy()
    for d, g in ((0.061, 0.5), (0.089, 0.45), (0.131, 0.4), (0.173, 0.35), (0.233, 0.3), (0.311, 0.25)):
        k = int(d * RATE)
        z = np.zeros_like(x)
        z[k:] = x[:-k] * g
        for _ in range(3):
            z[k:] += z[:-k] * g * 0.5
        y += z * mix
    return y


def save(name, x, q=3):
    x = x / (np.max(np.abs(x)) + 1e-9) * 0.9
    wav = os.path.join(out_dir, name + ".wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((x * 32000).astype(np.int16).tobytes())
    ogg = os.path.join(out_dir, name + ".ogg")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libvorbis", "-q:a", str(q), ogg], check=True)
    os.remove(wav)
    print("AUDIO", ogg, os.path.getsize(ogg))


# --- the hall: 24 s
n = 24 * RATE
t = np.arange(n) / RATE
air = fast_lowpass(rng.standard_normal(n) * 0.5, 0.004, 2) * 6.0
murmur_src = rng.standard_normal(n)
murmur = fast_lowpass(murmur_src, 0.05) - fast_lowpass(murmur_src, 0.012)
syll = 0.5 + 0.5 * np.sin(2 * np.pi * (3.1 * t + 0.6 * np.sin(2 * np.pi * 0.21 * t)))
swell = 0.55 + 0.45 * np.sin(2 * np.pi * t / 24.0 * 3) * np.sin(2 * np.pi * t / 24.0 * 2 + 1.0)
murmur *= syll * swell * 1.6
chord = sum(np.sin(2 * np.pi * f * t) * g for f, g in ((65.4, 0.05), (98.0, 0.035), (130.8, 0.025), (196.0, 0.012)))
chord *= 0.6 + 0.4 * np.sin(2 * np.pi * t / 24.0)
hall = reverb(air + murmur * 0.5 + chord, 0.4)
save("hall_ambience", loop_fade(hall))

# --- a brazier: 10 s
n = 10 * RATE
hiss_src = rng.standard_normal(n)
hiss = (hiss_src - fast_lowpass(hiss_src, 0.08)) * 0.08 + fast_lowpass(rng.standard_normal(n), 0.01) * 0.6
roar = fast_lowpass(rng.standard_normal(n), 0.003, 2) * 5.0
crack = np.zeros(n)
for _ in range(150):
    p = rng.integers(0, n - 2000)
    ln = rng.integers(80, 900)
    amp = rng.uniform(0.2, 1.0) ** 2
    crack[p:p + ln] += rng.standard_normal(ln) * np.exp(-np.arange(ln) / (ln * 0.25)) * amp
crack = crack - fast_lowpass(crack, 0.2)
fire = hiss + roar + crack * 0.9
save("brazier", loop_fade(fire, 0.8))

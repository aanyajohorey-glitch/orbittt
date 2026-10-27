# Calm background sounds made with numpy (sine waves and noise), saved as WAV.
# No music files are needed.

import io
import wave

import numpy as np
import streamlit as st

RATE = 16000


def to_wav(samples):
    samples = np.clip(samples, -1, 1)
    pcm = (samples * 32767 * 0.9).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(RATE)
        f.writeframes(pcm.tobytes())
    return buffer.getvalue()


def smooth(signal, width):
    return np.convolve(signal, np.ones(width) / width, mode="same")


def chord(freqs, seconds, wobble=0.12):
    t = np.arange(int(seconds * RATE)) / RATE
    out = np.zeros_like(t)
    for i, f in enumerate(freqs):
        swell = 0.6 + 0.4 * np.sin(2 * np.pi * (wobble + i * 0.03) * t + i)
        out += swell * (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * 2 * f * t))
    return out


@st.cache_data(show_spinner=False)
def soundscape(kind, seconds=24):
    rng = np.random.default_rng(7)
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    if kind == "rain":
        hiss = smooth(rng.normal(0, 1, n), 6)
        drops = np.zeros(n)
        for start in rng.integers(0, n - 400, 260):
            k = np.arange(400)
            drops[start:start + 400] += rng.uniform(0.3, 1) * np.exp(-k / 50) * np.sin(2 * np.pi * rng.uniform(1800, 3200) * k / RATE)
        sound = 0.55 * hiss + 0.25 * drops
    elif kind == "waves":
        swell = (0.5 + 0.5 * np.sin(2 * np.pi * t / 8)) ** 2
        sound = smooth(rng.normal(0, 1, n), 30) * (0.15 + swell)
    elif kind == "dream":
        sound = chord([220.0, 261.6, 329.6, 392.0, 493.9], seconds)
    elif kind == "sunset":
        sound = chord([196.0, 246.9, 293.7, 370.0], seconds, wobble=0.08)
    elif kind == "focus":
        sound = chord([110.0, 164.8], seconds, wobble=0.05) + smooth(rng.normal(0, 1, n), 60) * 0.6
    else:  # night
        crickets = np.zeros(n)
        for start in range(0, n - 3000, int(0.9 * RATE)):
            burst = np.arange(3000) / RATE
            chirp = np.sin(2 * np.pi * 4200 * burst) * (np.sin(2 * np.pi * 30 * burst) > 0)
            crickets[start:start + 3000] += chirp * np.hanning(3000) * rng.uniform(0.2, 0.5)
        sound = 0.25 * crickets + chord([146.8, 220.0], seconds, wobble=0.04) * 0.5

    sound = sound / (np.max(np.abs(sound)) + 1e-9) * 0.6
    # fade the end into the start so the loop doesn't click
    fade = int(1.5 * RATE)
    ramp = np.linspace(0, 1, fade)
    looped = sound[:-fade].copy()
    looped[:fade] = looped[:fade] * ramp + sound[-fade:] * (1 - ramp)
    return to_wav(looped)

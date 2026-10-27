# Creator Mode logic.
# An idea is turned into a "vibe vector" (mood, energy, light, warmth, era, texture, boldness).
# Everything else (palette, fonts, moodboard, aesthetics, music, creators, concept)
# is made from that same vector, so it all fits together.

import colorsys
import copy
import hashlib
import io
import json
import math
import random
import re
import textwrap
from pathlib import Path
from urllib.parse import quote, quote_plus

import pandas as pd
import streamlit as st

import ai

DATA = Path(__file__).parent / "data"


def clamp(x, low=-1.0, high=1.0):
    return max(low, min(high, x))


def seeded_random(*parts):
    text = "|".join(str(p) for p in parts)
    return random.Random(int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16))


# ---------------- word tables ----------------

# word: (valence, arousal, warm, bold, vintage)
VIBE_WORDS = {
    "rain": (-0.2, -0.4, -0.5, -0.3, 0.1), "rainy": (-0.2, -0.4, -0.5, -0.3, 0.1), "monsoon": (0.1, -0.2, -0.4, -0.2, 0.1),
    "sunday": (0.2, -0.4, 0.1, -0.3, 0.1), "lazy": (0.1, -0.6, 0.1, -0.4, 0.0), "cafe": (0.3, -0.2, 0.5, -0.1, 0.3),
    "coffee": (0.2, 0.0, 0.6, 0.0, 0.3), "chai": (0.4, -0.1, 0.7, -0.1, 0.3), "tea": (0.3, -0.3, 0.3, -0.3, 0.3),
    "nostalgic": (0.0, -0.3, 0.3, -0.2, 0.8), "nostalgia": (0.0, -0.3, 0.3, -0.2, 0.8), "vintage": (0.1, -0.1, 0.3, 0.0, 1.0),
    "retro": (0.3, 0.3, 0.4, 0.3, 0.9), "old": (0.0, -0.2, 0.2, -0.1, 0.7), "film": (0.0, -0.1, 0.2, 0.0, 0.6),
    "modern": (0.2, 0.2, -0.1, 0.2, -1.0), "minimal": (0.1, -0.3, -0.1, -0.4, -0.8), "clean": (0.3, -0.1, -0.2, -0.2, -0.7),
    "neon": (0.3, 0.8, -0.2, 0.9, -0.8), "cyber": (0.0, 0.7, -0.6, 0.8, -1.0), "city": (0.1, 0.4, -0.2, 0.3, -0.4),
    "night": (-0.1, -0.2, -0.6, 0.2, 0.0), "midnight": (-0.1, -0.1, -0.7, 0.3, 0.0), "moon": (0.1, -0.4, -0.5, -0.2, 0.2),
    "stars": (0.3, -0.2, -0.4, 0.0, 0.1), "sunset": (0.5, 0.1, 0.9, 0.2, 0.2), "sunrise": (0.6, 0.2, 0.7, 0.0, 0.0),
    "golden": (0.6, 0.2, 0.9, 0.2, 0.3), "summer": (0.7, 0.6, 0.7, 0.5, 0.0), "spring": (0.7, 0.3, 0.2, -0.2, 0.0),
    "autumn": (0.2, -0.2, 0.8, 0.1, 0.5), "winter": (0.0, -0.4, -0.8, -0.1, 0.1), "snow": (0.2, -0.4, -0.9, -0.4, 0.0),
    "beach": (0.7, 0.4, 0.3, 0.2, 0.0), "ocean": (0.3, 0.0, -0.7, 0.1, 0.0), "sea": (0.3, -0.1, -0.7, 0.0, 0.0),
    "forest": (0.3, -0.3, -0.1, 0.0, 0.2), "garden": (0.6, -0.1, 0.1, -0.3, 0.2), "mountain": (0.3, 0.0, -0.4, 0.2, 0.0),
    "desert": (0.2, 0.0, 0.9, 0.1, 0.3), "cosy": (0.6, -0.5, 0.7, -0.4, 0.3), "cozy": (0.6, -0.5, 0.7, -0.4, 0.3),
    "calm": (0.4, -0.7, 0.0, -0.4, 0.0), "chill": (0.4, -0.5, -0.2, -0.3, 0.0), "peaceful": (0.5, -0.7, 0.0, -0.4, 0.1),
    "dreamy": (0.5, -0.4, 0.1, -0.6, 0.2), "soft": (0.4, -0.4, 0.1, -0.8, 0.1), "pastel": (0.6, -0.2, 0.1, -0.9, 0.0),
    "bold": (0.2, 0.5, 0.1, 1.0, -0.2), "bright": (0.6, 0.5, 0.3, 0.6, -0.1), "dark": (-0.3, 0.1, -0.3, 0.6, 0.0),
    "moody": (-0.3, 0.0, -0.3, 0.4, 0.2), "gloomy": (-0.6, -0.3, -0.5, 0.0, 0.1), "sad": (-0.7, -0.4, -0.4, -0.1, 0.0),
    "happy": (0.8, 0.5, 0.4, 0.2, 0.0), "energetic": (0.5, 0.9, 0.2, 0.6, -0.2), "party": (0.7, 0.9, 0.3, 0.8, -0.2),
    "festival": (0.8, 0.8, 0.8, 0.7, 0.1), "diwali": (0.8, 0.6, 0.9, 0.6, 0.3), "holi": (0.9, 0.9, 0.5, 0.9, 0.0),
    "study": (0.1, -0.2, -0.2, -0.2, 0.0), "focus": (0.1, 0.0, -0.3, 0.0, -0.3), "library": (0.1, -0.4, 0.3, 0.0, 0.6),
    "romantic": (0.7, 0.2, 0.6, 0.0, 0.3), "love": (0.8, 0.3, 0.6, 0.1, 0.1), "angry": (-0.6, 0.8, 0.6, 0.9, 0.0),
    "storm": (-0.2, 0.7, -0.5, 0.8, 0.0), "fire": (0.2, 0.8, 1.0, 0.9, 0.0), "y2k": (0.5, 0.6, -0.2, 0.7, -0.6),
}
ERA_WORDS = {"ancient": -1.0, "myth": -0.9, "mythology": -0.9, "mughal": -0.9, "medieval": -0.9, "victorian": -0.8,
             "vintage": -0.7, "old": -0.5, "retro": -0.4, "70s": -0.5, "80s": -0.3, "90s": -0.2, "y2k": 0.0,
             "classic": -0.5, "folk": -0.6, "traditional": -0.7, "heritage": -0.7, "nostalgic": -0.5, "today": 0.2,
             "modern": 0.5, "minimal": 0.4, "digital": 0.6, "tech": 0.7, "future": 1.0, "futuristic": 1.0,
             "space": 0.8, "cyber": 0.9, "robot": 0.9, "ai": 0.8, "neon": 0.6, "sci-fi": 1.0}
BRIGHT_WORDS = {"night": -0.7, "midnight": -0.8, "dark": -0.8, "shadow": -0.6, "moody": -0.5, "storm": -0.5,
                "fog": -0.3, "rain": -0.3, "rainy": -0.3, "moon": -0.4, "stars": -0.5, "neon": -0.3, "noir": -0.9,
                "bright": 0.8, "sunny": 0.8, "sun": 0.7, "summer": 0.7, "beach": 0.6, "morning": 0.6,
                "sunrise": 0.6, "pastel": 0.6, "white": 0.6, "light": 0.5, "golden": 0.4, "festival": 0.6, "holi": 0.9}
TEXTURE_WORDS = {"grain": 0.7, "grainy": 0.7, "film": 0.5, "paper": 0.6, "handmade": 0.8, "hand-made": 0.8,
                 "rough": 0.8, "raw": 0.8, "zine": 0.8, "collage": 0.7, "clay": 0.8, "craft": 0.7, "folk": 0.5,
                 "rustic": 0.7, "grunge": 0.9, "wood": 0.5, "embroidery": 0.7, "glossy": -0.8, "chrome": -0.9,
                 "glass": -0.6, "clean": -0.7, "minimal": -0.7, "sleek": -0.8, "smooth": -0.7, "digital": -0.4,
                 "corporate": -0.8, "neon": -0.3}
FEEL_WORDS = {
    "grandmother": {"warmth": 0.7, "era": -0.6, "texture": 0.5}, "nani": {"warmth": 0.7, "era": -0.6, "texture": 0.5},
    "dadi": {"warmth": 0.7, "era": -0.6, "texture": 0.5}, "kitchen": {"warmth": 0.6, "texture": 0.4},
    "home": {"warmth": 0.6, "texture": 0.3}, "family": {"warmth": 0.6}, "village": {"warmth": 0.4, "era": -0.5, "texture": 0.6},
    "poems": {"era": -0.3, "texture": 0.3}, "poem": {"era": -0.3, "texture": 0.3}, "poetry": {"era": -0.3, "texture": 0.3},
    "letters": {"era": -0.5, "texture": 0.5, "warmth": 0.3}, "memory": {"era": -0.4}, "childhood": {"era": -0.4, "warmth": 0.4},
    "school": {"brightness": 0.3}, "exams": {"brightness": 0.0}, "candle": {"brightness": -0.4, "warmth": 0.7},
    "bubble": {"brightness": 0.5, "texture": -0.5}, "wedding": {"warmth": 0.8, "brightness": 0.4},
}
THEME_WORDS = {"rain", "monsoon", "city", "night", "love", "friendship", "home", "family", "journey", "travel",
               "school", "exams", "space", "ocean", "sea", "forest", "garden", "desert", "mountain", "festival",
               "food", "tea", "chai", "coffee", "music", "dance", "memory", "dream", "dreams", "childhood",
               "loneliness", "hope", "freedom", "identity", "time", "nature", "animals", "cat", "train", "letters",
               "books", "library", "cinema", "film", "fashion", "streets", "village", "kitchen", "grandmother",
               "india", "mumbai", "delhi", "kerala", "rajasthan", "bengal", "punjab", "wedding", "climate",
               "technology", "robot", "magic", "myth", "mythology", "folk", "poetry", "stars", "moon", "poems",
               "nani", "dadi"}
MEDIUMS = ["Film", "Book", "Brand", "Poster", "Music video", "App"]
MEDIUM_HINTS = {"film": "Film", "movie": "Film", "documentary": "Film", "book": "Book", "story": "Book",
                "novel": "Book", "poems": "Book", "comic": "Book", "brand": "Brand", "logo": "Brand",
                "shop": "Brand", "poster": "Poster", "posters": "Poster", "video": "Music video",
                "song": "Music video", "app": "App", "website": "App", "game": "App"}
# for the "which feeling" questions: (valence, arousal, emotion label, heavy?)
FEELINGS = {
    "Joy": (0.8, 0.6, "joy", False), "Calm": (0.5, -0.6, "relief", False), "Wonder": (0.4, 0.5, "curiosity", False),
    "Hope": (0.6, 0.3, "optimism", False), "Love": (0.8, 0.3, "love", False),
    "Nostalgia": (0.1, -0.3, "realization", False), "Thrill": (0.3, 0.9, "excitement", False),
    "Playfulness": (0.7, 0.6, "amusement", False), "Melancholy": (-0.6, -0.4, "sadness", True),
    "Loneliness": (-0.5, -0.3, "sadness", True), "Anger": (-0.6, 0.8, "anger", True),
    "Fear": (-0.6, 0.6, "fear", True), "Grief": (-0.8, -0.3, "grief", True),
}
ERAS = {"Ancient and mythic": -1.0, "Vintage (before 1980)": -0.7, "Retro (1980s-2000s)": -0.3,
        "Today": 0.2, "The future": 0.9}


def words_in(text):
    return re.findall(r"[a-zA-Z][a-zA-Z0-9\-']*", text.lower())


def build_vector(text, emotions, medium=None, audience=None, match_text=None):
    """The vibe vector for an idea. match_text = English translation for Hinglish ideas."""
    ev, ea = ai.valence_arousal(emotions)
    found = {"valence": [], "arousal": [], "warmth": [], "bold": [], "era": [], "brightness": [], "texture": []}
    themes = []
    for w in words_in(match_text or text):
        hit = False
        if w in VIBE_WORDS:
            v, a, warm, bold, vintage = VIBE_WORDS[w]
            found["valence"].append(v)
            found["arousal"].append(a)
            found["warmth"].append(warm)
            found["bold"].append(bold)
            found["era"].append(-vintage)
            hit = True
        if w in ERA_WORDS:
            found["era"].append(ERA_WORDS[w])
            hit = True
        if w in BRIGHT_WORDS:
            found["brightness"].append(BRIGHT_WORDS[w])
            hit = True
        if w in TEXTURE_WORDS:
            found["texture"].append(TEXTURE_WORDS[w])
            hit = True
        for key, value in FEEL_WORDS.get(w, {}).items():
            found[key].append(value)
            hit = True
        if (hit or w in THEME_WORDS) and w not in themes:
            themes.append(w)

    def avg(key, default):
        values = found[key]
        if not values:
            return default
        return sum(values) / len(values)

    # words describe a vibe more directly than emotions, so they count 60%
    valence = clamp(0.4 * ev + 0.6 * avg("valence", ev))
    arousal = clamp(0.4 * ea + 0.6 * avg("arousal", ea))
    return {
        "text": text, "medium": medium, "audience": audience,
        "emotions": [(label, round(float(s), 3)) for label, s in emotions[:8]],
        "valence": round(valence, 3), "arousal": round(arousal, 3),
        "brightness": round(clamp(avg("brightness", 0.4 * valence)), 3),
        "warmth": round(clamp(avg("warmth", 0.3 * valence)), 3),
        "era": round(clamp(avg("era", 0.0)), 3),
        "texture": round(clamp(avg("texture", 0.0)), 3),
        "bold": round(clamp(avg("bold", 0.4 * arousal)), 3),
        "themes": themes or [label for label, _ in emotions[:2]],
        "tweaks": {},
    }


CHIPS = {"Muted": "softer, greyer colours", "Warmer": "warmer colours and mood",
         "Dreamier": "calmer, softer, a little hazy", "Less corporate": "more hand-made and personal",
         "Bolder": "stronger colour and contrast", "More vintage": "further back in time"}


def refine(vector, chip):
    v = copy.deepcopy(vector)
    t = v.setdefault("tweaks", {})
    if chip == "Muted":
        t["muted"] = round(t.get("muted", 1.0) * 0.8, 3)
        v["bold"] = clamp(v["bold"] - 0.2)
    elif chip == "Warmer":
        v["warmth"] = clamp(v["warmth"] + 0.35)
    elif chip == "Dreamier":
        v["arousal"] = clamp(v["arousal"] - 0.25)
        v["texture"] = clamp(v["texture"] - 0.2)
        v["brightness"] = clamp(v["brightness"] + 0.15)
        if "dreamy" not in v["themes"]:
            v["themes"].append("dreamy")
    elif chip == "Less corporate":
        v["texture"] = clamp(v["texture"] + 0.35)
        v["era"] = clamp(v["era"] - 0.15)
        if "hand-made" not in v["themes"]:
            v["themes"].append("hand-made")
    elif chip == "Bolder":
        v["bold"] = clamp(v["bold"] + 0.35)
        v["arousal"] = clamp(v["arousal"] + 0.15)
        t["contrast"] = min(3.0, t.get("contrast", 0.0) + 1.0)
    elif chip == "More vintage":
        v["era"] = clamp(v["era"] - 0.35)
    return v


def apply_sliders(vector, warm_cool, calm_energy, soft_bold, vintage_modern, dark_bright):
    v = copy.deepcopy(vector)
    v["warmth"] = clamp(v["warmth"] - warm_cool)
    v["arousal"] = clamp(v["arousal"] + 0.6 * calm_energy)
    v["bold"] = clamp(v["bold"] + soft_bold)
    v["era"] = clamp(v["era"] + vintage_modern)
    v["brightness"] = clamp(v["brightness"] + dark_bright)
    return v


def directions(vector):
    """Safe = as it is, Bold = louder, Weird = flipped."""
    base = {k: v for k, v in vector.items() if k not in ("direction", "discovery", "harmony")}
    safe = copy.deepcopy(base)
    safe.update(direction="Safe", discovery=0.2, harmony="analogous")
    bold = copy.deepcopy(base)
    bold.update(direction="Bold", discovery=0.6, harmony="complementary", arousal=clamp(base["arousal"] + 0.35),
                bold=clamp(base["bold"] + 0.5), brightness=clamp(base["brightness"] + 0.2))
    weird = copy.deepcopy(base)
    warmth = -0.7 * base["warmth"] if abs(base["warmth"]) > 0.15 else 0.7
    era = base["era"] + 0.9 if base["era"] <= 0 else base["era"] - 0.9
    texture = base["texture"] + 0.5 if base["texture"] < 0.3 else base["texture"] - 0.8
    weird.update(direction="Weird", discovery=1.0, harmony="triadic", warmth=clamp(warmth), era=clamp(era),
                 texture=clamp(texture))
    return {"Safe": safe, "Bold": bold, "Weird": weird}


def describe(vector):
    def word(x, low, high, middle):
        if x > 0.2:
            return high
        if x < -0.2:
            return low
        return middle
    return {
        "Mood": word(vector["valence"], "heavy", "joyful", "in-between"),
        "Energy": word(vector["arousal"], "calm", "energetic", "steady"),
        "Light": word(vector["brightness"], "dark", "bright", "soft light"),
        "Temperature": word(vector["warmth"], "cool", "warm", "neutral"),
        "Era": word(vector["era"], "vintage", "futuristic", "present day"),
        "Texture": word(vector["texture"], "smooth", "hand-made", "mixed"),
        "Boldness": word(vector["bold"], "soft", "bold", "medium"),
    }


# ---------------- palette ----------------

def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, clamp(l, 0, 1), clamp(s, 0, 1))
    return "#{:02X}{:02X}{:02X}".format(round(r * 255), round(g * 255), round(b * 255))


def hex_to_rgb(colour):
    colour = colour.lstrip("#")
    return tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))


def luminance(colour):
    values = []
    for c in hex_to_rgb(colour):
        c = c / 255
        values.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


# angle on the mood circle -> hue. 0 = pleasant, 90 = energetic, 180 = unpleasant, 270 = calm
HUE_POINTS = [(0, 45), (45, 20), (90, 330), (135, 350), (180, 220), (225, 240), (270, 270), (315, 140), (360, 45)]


def feeling_hue(valence, arousal):
    if math.hypot(valence, arousal) < 0.05:
        return 270.0  # neutral = lavender
    angle = math.degrees(math.atan2(arousal, valence)) % 360
    for (a0, h0), (a1, h1) in zip(HUE_POINTS, HUE_POINTS[1:]):
        if a0 <= angle <= a1:
            t = (angle - a0) / (a1 - a0)
            step = (h1 - h0 + 180) % 360 - 180  # short way round
            return (h0 + step * t) % 360
    return 270.0


def shift_hue(hue, warm):
    target = 30 if warm > 0 else 215
    diff = (target - hue + 180) % 360 - 180
    return (hue + max(-45, min(45, diff)) * min(1.0, abs(warm))) % 360


HARMONY = {"analogous": (-30, 30), "complementary": (180, 150), "triadic": (120, 240)}
HUE_NAMES = [(15, "Rose"), (30, "Coral"), (45, "Apricot"), (60, "Honey"), (90, "Lime"), (150, "Sage"),
             (190, "Mint"), (220, "Sky"), (250, "Periwinkle"), (290, "Lavender"), (320, "Orchid"), (345, "Berry"),
             (360, "Rose")]


def colour_name(colour):
    r, g, b = (c / 255 for c in hex_to_rgb(colour))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    base = "Rose"
    for limit, name in HUE_NAMES:
        if h * 360 < limit:
            base = name
            break
    if s < 0.12:
        base = "Stone" if l > 0.35 else "Ink"
    if l > 0.9:
        adj = "Whisper"
    elif l > 0.75:
        adj = "Pale"
    elif l < 0.22:
        adj = "Midnight"
    elif l < 0.38:
        adj = "Deep"
    elif s < 0.3:
        adj = "Dusty"
    elif s > 0.65:
        adj = "Vivid"
    else:
        adj = "Soft"
    return f"{adj} {base}"


def make_palette(valence, arousal, warm=0.0, energy=0.0, bold=0.0, vintage=0.0, tweaks=None, harmony=None,
                 brightness=0.0):
    tweaks = tweaks or {}
    arousal = clamp(arousal + 0.6 * energy)
    hue = shift_hue(feeling_hue(valence, arousal), clamp(warm + tweaks.get("warmth", 0.0)))
    strength = min(1.0, math.hypot(valence, arousal))
    sat = 0.24 + 0.18 * strength + 0.16 * (arousal + 1) / 2 + 0.18 * bold - 0.14 * max(0.0, vintage)
    sat = sat * tweaks.get("muted", 1.0)
    if tweaks.get("playful"):
        sat += 0.1
    sat = clamp(sat, 0.08, 0.85)
    light = clamp(0.66 + 0.06 * valence + 0.08 * brightness - 0.08 * bold - 0.05 * tweaks.get("contrast", 0), 0.35, 0.82)

    if not harmony:
        if tweaks.get("playful") or arousal > 0.45:
            harmony = "triadic"
        elif arousal < -0.1:
            harmony = "analogous"
        else:
            harmony = "complementary"
    first, second = HARMONY[harmony]

    primary = hsl_to_hex(hue, sat, light)
    harmony_a = hsl_to_hex(hue + first, sat * 0.9, clamp(light + 0.08, 0, 1))
    harmony_b = hsl_to_hex(hue + second, sat * (0.75 if harmony == "complementary" else 0.9),
                           clamp(light - 0.1 + (0.04 if tweaks.get("playful") else 0), 0, 1))
    bg_hue = hue + (20 * vintage if vintage > 0 else 0)
    background = hsl_to_hex(bg_hue, clamp(0.25 * sat + 0.12 * max(0, vintage), 0, 1),
                            clamp(0.955 - 0.02 * max(0, vintage) + 0.02 * tweaks.get("contrast", 0), 0.88, 0.985))
    ink_light = 0.2 - 0.04 * tweaks.get("contrast", 0) - (0.03 * abs(vintage) if vintage < 0 else 0)
    ink = hsl_to_hex(hue, 0.22, ink_light)
    # make the text colour dark enough to pass WCAG AA
    while (contrast(ink, background) < 4.5 or contrast(ink, primary) < 3.0) and ink_light > 0.02:
        ink_light -= 0.02
        ink = hsl_to_hex(hue, 0.22, ink_light)
    while contrast(ink, primary) < 3.0 and light < 0.95:
        light += 0.02
        primary = hsl_to_hex(hue, sat, light)

    colours = [("Primary", primary), ("Harmony A", harmony_a), ("Harmony B", harmony_b),
               ("Background", background), ("Ink (text)", ink)]
    checks = []
    for name, a, b, needed in [("Ink on Background", ink, background, 4.5), ("Ink on Primary", ink, primary, 3.0),
                               ("Ink on Harmony A", ink, harmony_a, 3.0),
                               ("Primary on Background (large text)", primary, background, 3.0)]:
        ratio = contrast(a, b)
        checks.append({"pair": name, "ratio": round(ratio, 2), "needed": needed, "passes": ratio >= needed})
    return {"colours": [{"role": role, "hex": h, "name": colour_name(h)} for role, h in colours],
            "rule": harmony, "hue": round(hue), "saturation": round(sat, 2), "lightness": round(light, 2),
            "valence": round(valence, 2), "arousal": round(arousal, 2), "checks": checks}


def refine_tweaks(tweaks, action):
    tweaks = dict(tweaks or {})
    if action == "muted":
        tweaks["muted"] = round(tweaks.get("muted", 1.0) * 0.8, 3)
    elif action == "warmer":
        tweaks["warmth"] = min(1.0, tweaks.get("warmth", 0.0) + 0.35)
    elif action == "cooler":
        tweaks["warmth"] = max(-1.0, tweaks.get("warmth", 0.0) - 0.35)
    elif action == "contrast":
        tweaks["contrast"] = min(3.0, tweaks.get("contrast", 0.0) + 1.0)
    elif action == "playful":
        tweaks["playful"] = True
        tweaks["muted"] = round(min(1.4, tweaks.get("muted", 1.0) * 1.15), 3)
    return tweaks


def vibe_profile(text):
    """for the quick palette: (valence, arousal, warm, bold, vintage, words found)"""
    found = [w.strip(".,!?;:'\"").lower() for w in text.split()]
    found = [w for w in found if w in VIBE_WORDS]
    if not found:
        return 0.0, 0.0, 0.0, 0.0, 0.0, []
    sums = [sum(VIBE_WORDS[w][i] for w in found) / len(found) for i in range(5)]
    return sums[0], sums[1], sums[2], sums[3], sums[4], found


def textures(arousal, vintage):
    picks = ["halftone dots", "bold stripes"] if arousal > 0.3 else ["soft grain", "linen"]
    picks.append("film grain" if vintage > 0.15 else "frosted glass")
    return picks


def palette_css(palette):
    lines = [":root {"]
    for c in palette["colours"]:
        name = c["role"].lower().replace(" (text)", "").replace(" ", "-")
        lines.append(f"  --orbit-{name}: {c['hex']};   /* {c['name']} */")
    lines.append("}")
    return "\n".join(lines)


def palette_json(palette, fonts, extra=None):
    data = {"palette": palette["colours"], "harmony_rule": palette["rule"], "valence": palette["valence"],
            "arousal": palette["arousal"], "fonts": fonts, "contrast_checks": palette["checks"]}
    data.update(extra or {})
    return json.dumps(data, indent=2, ensure_ascii=False)


def moodboard_png(palette, fonts, keywords):
    from PIL import Image, ImageDraw, ImageFont
    colours = [c["hex"] for c in palette["colours"]]
    image = Image.new("RGB", (1200, 800), colours[3])
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.load_default(size=20)
    except TypeError:
        font = ImageFont.load_default()
    a, b = hex_to_rgb(colours[0]), hex_to_rgb(colours[1])
    for x in range(40, 720):
        t = (x - 40) / 680
        draw.line([(x, 40), (x, 460)], fill=tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    draw.rectangle([760, 40, 1160, 460], fill=colours[1])
    for row in range(14):
        for col in range(13):
            cx, cy = 775 + col * 30 + (row % 2) * 15, 55 + row * 30
            draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill=colours[2])
    for i, c in enumerate(palette["colours"]):
        x = 40 + i * 226
        draw.rounded_rectangle([x, 500, x + 206, 650], radius=18, fill=c["hex"], outline=colours[4], width=2)
        draw.text((x, 662), c["name"], fill=colours[4], font=font)
        draw.text((x, 690), c["hex"], fill=colours[4], font=font)
    draw.text((40, 730), f"{fonts['heading']} + {fonts['body']}  |  {palette['rule']} harmony  |  "
              + ", ".join(keywords[:4]), fill=colours[4], font=font)
    draw.text((40, 762), "Made with ORBIT", fill=colours[4], font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


# ---------------- fonts ----------------

@st.cache_data
def load_fonts():
    table = pd.read_csv(DATA / "fonts.csv")
    table["tag_list"] = table["tags"].str.split("|")
    return table


def pick_fonts(vintage, bold, energy, warmth=0.0, hindi=False):
    """Heading = font closest to the vibe. Body = calm, readable, from a different category."""
    table = load_fonts()

    def distance(row, vt, bd, en, wm):
        return (row["vintage"] - vt) ** 2 + (row["bold"] - bd) ** 2 + (row["energy"] - en) ** 2 + 0.5 * (row["warmth"] - wm) ** 2

    best_heading, best_d = None, 999
    for row in table.to_dict("records"):
        if row["use"] not in ("heading", "both"):
            continue
        d = distance(row, vintage, bold, energy, warmth)
        if "devanagari" in row["tag_list"]:
            d += -0.6 if hindi else 0.6
        if d < best_d:
            best_heading, best_d = row, d

    best_body, best_d = None, 999
    for row in table.to_dict("records"):
        if row["use"] not in ("body", "both") or row["family"] == best_heading["family"]:
            continue
        d = distance(row, vintage * 0.5, min(bold, 0.0), energy * 0.3, warmth)
        if row["category"] == best_heading["category"]:
            d += 0.5
        if "readable" in row["tag_list"]:
            d -= 0.1
        if row["category"] in ("mono", "script"):
            d += 0.6
        if hindi and "devanagari" in row["tag_list"]:
            d -= 0.6
        if d < best_d:
            best_body, best_d = row, d

    why = (f"{best_heading['family']} ({best_heading['category']}) is the heading font closest to your vibe; "
           f"{best_body['family']} ({best_body['category']}) is a calm, readable partner.")
    return {"heading": best_heading["family"], "body": best_body["family"],
            "feel": " and ".join(best_heading["tag_list"][:2]), "why": why}


def google_fonts(*families):
    query = "&".join("family=" + f.replace(" ", "+") for f in dict.fromkeys(families))
    return f"<style>@import url('https://fonts.googleapis.com/css2?{query}&display=swap');</style>"


# ---------------- ranking ----------------

def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    size = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / size if size else 0.0


def overlap(a, b):
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def mmr(candidates, similarity, size, discovery, unique=None):
    """Pick items one by one: relevant, but not too similar to what is already picked."""
    trade_off = 0.8 - 0.45 * discovery
    pool = sorted(candidates, key=lambda c: -c["relevance"])
    chosen = []
    while pool and len(chosen) < size:
        best, best_score = None, -999
        for item in pool:
            repeat = max([similarity(item, other) for other in chosen], default=0.0)
            score = trade_off * item["relevance"] - (1 - trade_off) * repeat
            if score > best_score:
                best, best_score = item, score
        pool.remove(best)
        if unique and any(best[unique] == other[unique] for other in chosen):
            continue
        chosen.append(best)
    return chosen


DIMENSIONS = ["mood", "energy", "light", "warmth", "era", "texture"]


def closest(target, item, names=DIMENSIONS):
    gaps = sorted(range(len(target)), key=lambda i: abs(target[i] - item[i]))
    return [names[i] for i in gaps[:2]]


@st.cache_data
def load_aesthetics():
    table = pd.read_csv(DATA / "aesthetics.csv")
    table["tag_list"] = table["tags"].str.split("|")
    table["cue_list"] = table["cues"].str.split(";")
    return table


@st.cache_data
def load_creators():
    table = pd.read_csv(DATA / "creators.csv").fillna({"language": ""})
    table["tag_list"] = table["tags"].str.split("|")
    return table


def rank_aesthetics(vector, discovery):
    target = [vector["valence"], vector["arousal"], vector["brightness"], vector["warmth"], vector["era"], vector["texture"]]
    rows = []
    for row in load_aesthetics().to_dict("records"):
        item = [row["valence"], row["arousal"], row["brightness"] * 2 - 1, row["warmth"], row["era"], row["texture"]]
        row["relevance"] = 0.75 * cosine([1] + target, [1] + item) + 0.25 * overlap(vector["themes"], row["tag_list"])
        row["close"] = closest(target, item)
        rows.append(row)

    def similar(a, b):
        return 0.5 * (a["origin"] == b["origin"]) + 0.5 * bool(set(a["tag_list"]) & set(b["tag_list"]))

    rows = sorted(rows, key=lambda r: -r["relevance"])[:25]
    chosen = mmr(rows, similar, 3, discovery)
    for row in chosen:
        row["why"] = f"Close to your vibe on {' and '.join(row['close'])}. Look for: {', '.join(row['cue_list'][:3])}."
    return chosen


def rank_creators(vector, discovery):
    names = ["mood", "energy", "warmth", "era", "texture"]
    target = [vector["valence"], vector["arousal"], vector["warmth"], vector["era"], vector["texture"]]
    rows = []
    for row in load_creators().to_dict("records"):
        item = [row["valence"], row["arousal"], row["warmth"], row["era"], row["texture"]]
        popularity = (row["mainstream_level"] - 1) / 4
        row["relevance"] = (0.7 * cosine([1] + target, [1] + item) + 0.3 * overlap(vector["themes"], row["tag_list"])
                            + 0.15 * (1 - 2 * discovery) * popularity)
        row["shared"] = [t for t in row["tag_list"] if t in vector["themes"]]
        row["close"] = closest(target, item, names)
        rows.append(row)

    def similar(a, b):
        return (0.4 * (a["field"] == b["field"]) + 0.3 * (("India" in a["region"]) == ("India" in b["region"]))
                + 0.3 * (a["language"] == b["language"] and a["language"] != ""))

    pool = sorted(rows, key=lambda r: -r["relevance"])[:40]
    chosen = mmr(pool, similar, 6, discovery, unique="name")
    if not any("India" in c["region"] for c in chosen):  # always include someone from India
        for r in pool:
            if "India" in r["region"]:
                chosen[-1] = r
                break
    for row in chosen:
        if row["shared"]:
            reason = f"shares your {' and '.join(row['shared'][:2])} themes"
        else:
            reason = f"close to your vibe on {' and '.join(row['close'])}"
        rare = " A lesser-known name worth finding." if row["mainstream_level"] <= 2 else ""
        row["why"] = f"Known for {row['known_for']}. Why it fits: {reason}.{rare}"
    return chosen


# ---------------- music ----------------

INTENT_TAGS = {
    "Sadness": {"match": ["bittersweet", "longing", "cathartic", "acoustic", "calm"], "lift": ["comfort", "hopeful", "warm", "calm"]},
    "Fear": {"match": ["cathartic", "night", "longing", "dreamy"], "lift": ["calm", "comfort", "instrumental", "hopeful"]},
    "Anger": {"match": ["release", "energetic", "cathartic", "empowering"], "lift": ["calm", "chill", "comfort", "hopeful"]},
    "Joy": {"match": ["uplifting", "celebration", "dance", "playful"], "lift": ["uplifting", "celebration", "energetic", "playful"]},
    "Warmth": {"match": ["love", "warm", "friendship", "comfort"], "lift": ["love", "warm", "uplifting", "friendship"]},
    "Wonder": {"match": ["dreamy", "journey", "story", "playful"], "lift": ["hopeful", "journey", "uplifting", "dreamy"]},
    "Neutral": {"match": ["chill", "calm", "focus"], "lift": ["uplifting", "hopeful", "warm"]},
}
ENERGY_WORDS = {1: "very calm", 2: "gentle", 3: "steady", 4: "upbeat", 5: "high-energy"}
MOOD_WORDS = {1: "heavy-hearted", 2: "bittersweet", 3: "in-between", 4: "warm", 5: "bright"}
THEME_TO_MUSIC = {"rain": "rain", "rainy": "rain", "monsoon": "rain", "night": "night", "midnight": "night",
                  "nostalgic": "nostalgic", "nostalgia": "nostalgic", "cafe": "chill", "coffee": "chill",
                  "chai": "warm", "tea": "calm", "love": "love", "romantic": "love", "friendship": "friendship",
                  "journey": "journey", "travel": "journey", "dream": "dreamy", "dreams": "dreamy",
                  "dreamy": "dreamy", "festival": "celebration", "wedding": "celebration", "dance": "dance",
                  "party": "dance", "folk": "folk", "home": "comfort", "family": "warm", "hope": "hopeful",
                  "summer": "summer", "morning": "morning", "space": "dreamy", "study": "focus", "exams": "focus",
                  "nature": "nature", "forest": "nature", "ocean": "calm", "sea": "calm", "hand-made": "acoustic",
                  "memory": "nostalgic", "childhood": "nostalgic", "poetry": "poetry", "loneliness": "longing"}


@st.cache_data
def load_music():
    table = pd.read_csv(DATA / "music_catalog.csv")
    table["tag_list"] = table["tags"].str.split("|")
    return table


def music_target(emotions, intent):
    """(mood 1-5, energy 1-5, family, tags). 'lift' moves a gentle step brighter, not a jump."""
    valence, arousal = ai.valence_arousal(emotions)
    family = ai.FAMILY_OF[max(emotions, key=lambda p: p[1])[0]]
    mood, energy = 3 + 2 * valence, 3 + 2 * arousal
    if intent == "lift":
        mood = min(5.0, mood + (1.5 if valence < 0 else 0.5))
        energy = energy + 0.4 * (3.2 - energy)
    return mood, energy, family, INTENT_TAGS[family][intent]


def recommend_music(mood, energy, tags, intent="match", discovery=0.5, size=10):
    table = load_music()
    vocab = sorted({t for tags_ in table["tag_list"] for t in tags_})

    def vec(m, e, tag_list):
        return [1.0, (m - 3) / 2, (e - 3) / 2] + [0.6 if t in tag_list else 0.0 for t in vocab]

    goal = vec(mood, energy, tags)
    tracks = []
    for track in table.to_dict("records"):
        popularity = (track["mainstream_level"] - 1) / 4
        track["relevance"] = cosine(goal, vec(track["valence"], track["energy"], track["tag_list"])) + 0.15 * (1 - 2 * discovery) * popularity
        tracks.append(track)
    tracks = sorted(tracks, key=lambda t: -t["relevance"])[:60]

    def similar(a, b):
        return 0.45 * (a["artist"] == b["artist"]) + 0.3 * (a["genre"] == b["genre"]) + 0.25 * (a["language"] == b["language"])

    chosen = mmr(tracks, similar, size, discovery, unique="artist")
    start = {"match": "Matches how you feel", "lift": "A gentle step up"}.get(intent, "Fits your project's vibe")
    for t in chosen:
        reason = f"{start}: {ENERGY_WORDS[int(t['energy'])]} and {MOOD_WORDS[int(t['valence'])]}"
        shared = [x for x in t["tag_list"] if x in tags]
        if shared:
            reason += f" ({', '.join(shared[:2])})"
        if t["mainstream_level"] <= 2:
            reason += ". A lesser-known find"
        elif t["language"] not in ("English", "Hindi", "Instrumental"):
            reason += f". Something in {t['language']}"
        t["reason"] = reason + "."
        query = f"{t['title']} {t['artist']}"
        t["spotify"] = f"https://open.spotify.com/search/{quote(query)}"
        t["youtube"] = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    return chosen


def music_tags(vector):
    tags = [THEME_TO_MUSIC[t] for t in vector["themes"] if t in THEME_TO_MUSIC]
    if vector["era"] < -0.3:
        tags.append("nostalgic")
    if vector["arousal"] < -0.2:
        tags.append("calm")
    elif vector["arousal"] > 0.4:
        tags.append("energetic")
    if vector["texture"] > 0.3:
        tags.append("acoustic")
    if len(tags) < 2 and vector["emotions"]:
        tags += INTENT_TAGS[ai.FAMILY_OF[vector["emotions"][0][0]]]["match"]
    return list(dict.fromkeys(tags))[:5]


# ---------------- concept ----------------

MEDIUM_PHRASE = {"Film": "a short film", "Book": "a book", "Brand": "a brand", "Poster": "a poster series",
                 "Music video": "a music video", "App": "an app"}
NOUNS = {"rain": "Rain", "monsoon": "Monsoon", "city": "City", "night": "Night", "love": "Hearts", "home": "Home",
         "family": "Family", "journey": "Road", "travel": "Road", "school": "Corridors", "exams": "Exam Season",
         "space": "Orbit", "ocean": "Tide", "sea": "Tide", "forest": "Forest", "garden": "Garden",
         "desert": "Dunes", "mountain": "Peaks", "festival": "Festival", "food": "Kitchen", "tea": "Chai",
         "chai": "Chai", "coffee": "Coffee", "music": "Rhythm", "dance": "Dance", "memory": "Memory",
         "dream": "Dreams", "dreams": "Dreams", "childhood": "Summer Holidays", "time": "Clocks", "train": "Trains",
         "books": "Pages", "library": "Pages", "cinema": "Reels", "film": "Reels", "moon": "Moon", "stars": "Stars",
         "cafe": "Cafe", "sunset": "Sunset", "beach": "Shore", "village": "Village", "kitchen": "Kitchen",
         "grandmother": "Nani's House", "freedom": "Open Skies", "hope": "Small Lights", "friendship": "Friends",
         "loneliness": "Empty Rooms", "magic": "Small Magic", "myth": "Old Gods", "folk": "Folk Songs",
         "rainy": "Rain", "sunday": "Sundays", "mumbai": "Mumbai", "delhi": "Delhi", "kerala": "Backwaters",
         "rajasthan": "Desert Winds", "wedding": "Wedding Lights", "streets": "Streets", "cat": "Cats",
         "letters": "Letters", "animals": "Wild Things", "nature": "Wild Places", "nostalgic": "Old Photographs"}
MEDIUM_WORDS = {"film", "cinema", "book", "books", "poster", "app", "music", "brand"}
NAMES_MEDIUM = MEDIUM_WORDS | {"story", "video", "song", "series", "comic", "zine", "game", "poems", "poem",
                               "novel", "album", "logo", "website"}


def lighting(vector):
    if vector["era"] > 0.5 and vector["brightness"] < 0.2:
        return "neon glow and screen light"
    warm = vector["warmth"] >= 0
    if vector["brightness"] >= 0.3:
        return "golden-hour sunlight" if warm else "clear daylight"
    if vector["brightness"] >= -0.3:
        return "soft lamp light" if warm else "overcast window light"
    return "candlelight and warm shadows" if warm else "moonlight and neon"


def mood_adjective(v):
    if v["brightness"] < -0.4:
        return "Midnight"
    if v["era"] < -0.5:
        return "Old-world"
    if v["era"] > 0.6:
        return "Neon"
    if v["valence"] >= 0.2:
        return "Bright" if v["arousal"] > 0.2 else "Gentle"
    if v["valence"] <= -0.2:
        return "Restless" if v["arousal"] > 0.2 else "Quiet"
    return "Soft"


def make_concept(vector, colours, aesthetics, fonts):
    rng = seeded_random(vector["text"], vector.get("direction", ""))
    content = [t for t in vector["themes"] if t in NOUNS and t not in MEDIUM_WORDS]
    if content:
        noun = NOUNS[content[0]]
    else:
        any_noun = [NOUNS[t] for t in vector["themes"] if t in NOUNS]
        noun = any_noun[0] if any_noun else rng.choice(["Small Hours", "Weather", "Signals", "Lanterns", "Echoes"])
    colour_word = colours[0]["name"].split()[-1]
    titles = [f"{noun} in {colour_word}", f"Notes from {noun}"]
    if "'" not in noun:
        titles += [f"{mood_adjective(vector)} {noun}", f"After the {noun}"]
        if " " not in noun:
            titles.append(f"The {noun} Hour")
    title = rng.choice(titles)

    words = describe(vector)
    medium = MEDIUM_PHRASE.get(vector.get("medium"), "a creative project")
    idea = vector["text"].strip().rstrip(".")
    says_medium = any(w in NAMES_MEDIUM for w in words_in(idea)[:5])
    if idea and len(idea) <= 140 and says_medium:
        opening = idea[0].upper() + idea[1:]
    elif idea and len(idea) <= 140:
        opening = f"{medium[0].upper() + medium[1:]} about {idea[0].lower() + idea[1:]}"
    else:
        opening = f"{medium[0].upper() + medium[1:]} built from your idea"
    borrows = aesthetics[0]["name"]
    if len(aesthetics) > 1:
        borrows += " and " + aesthetics[1]["name"]
    vision = (f"{opening}. It feels {words['Mood']} and {words['Energy']}, lit by {lighting(vector)}, with "
              f"{words['Texture']} textures and a {words['Era']} edge. Its colours move from "
              f"{colours[0]['name'].lower()} to {colours[1]['name'].lower()}, the type pairs {fonts['heading']} with "
              f"{fonts['body']}, and it borrows from {borrows}.")
    if vector.get("audience"):
        vision += f" Made for {vector['audience'].lower()}."
    return {"title": title, "vision": vision, "polished": False}


def make_universe(vector, discovery=0.5, locks=(), old=None):
    """Make every part from the vector. Locked parts keep the old version."""
    old = old or {}
    u = {}

    def keep(part):
        return part in locks and part in old

    hindi = ai.has_hindi(vector["text"])
    u["palette"] = old["palette"] if keep("palette") else make_palette(
        vector["valence"], vector["arousal"], warm=vector["warmth"], bold=vector["bold"], vintage=-vector["era"],
        tweaks=vector.get("tweaks"), harmony=vector.get("harmony"), brightness=vector["brightness"])
    u["fonts"] = old["fonts"] if keep("fonts") else pick_fonts(-vector["era"], vector["bold"], vector["arousal"],
                                                               vector["warmth"], hindi)
    u["aesthetics"] = old["aesthetics"] if keep("aesthetics") else rank_aesthetics(vector, discovery)
    if keep("moodboard"):
        u["moodboard"] = old["moodboard"]
    else:
        cues = [cue for a in u["aesthetics"][:2] for cue in a["cue_list"][:2]]
        u["moodboard"] = {"textures": textures(vector["arousal"], -vector["era"]), "lighting": lighting(vector),
                          "keywords": list(dict.fromkeys(vector["themes"][:4] + cues))[:8]}
    u["music"] = old["music"] if keep("music") else recommend_music(
        3 + 2 * vector["valence"], 3 + 2 * vector["arousal"], music_tags(vector), "project", discovery, 8)
    u["creators"] = old["creators"] if keep("creators") else rank_creators(vector, discovery)
    u["concept"] = old["concept"] if keep("concept") else make_concept(vector, u["palette"]["colours"],
                                                                       u["aesthetics"], u["fonts"])
    u["vector"] = copy.deepcopy(vector)
    u["discovery"] = discovery
    return u


# ---------------- creative blocks (Create -> Feel bridge) ----------------

BLOCKS = {
    "Perfectionism": {
        "words": ["perfect", "not good enough", "flawless", "mistake", "mistakes", "never good", "ruin", "ruined",
                  "redo", "start over again"],
        "game": "mandala",
        "exercise": ("Make it badly, on purpose. Set a 5-minute timer and make the WORST version you can: wrong "
                     "colours, wobbly lines, silly words. When the timer ends, circle one thing in it you actually "
                     "like. That's your way back in.")},
    "Fear of judgment": {
        "words": ["judge", "judged", "what will people think", "laugh at", "embarrass", "embarrassing", "cringe",
                  "criticise", "criticize", "nobody will like", "they'll hate", "people will hate"],
        "game": "pop_worry",
        "exercise": ("An audience of one. For 5 minutes, make something only for yourself that nobody will ever "
                     "see. Then write down the one person whose opinion you actually care about, and what they would "
                     "most likely say. It's usually kinder than the crowd in your head.")},
    "Burnout": {
        "words": ["tired", "exhausted", "burnt out", "burned out", "burnout", "drained", "no energy",
                  "can't anymore", "cant anymore", "too much work", "overworked", "so much work"],
        "game": "zen_sand",
        "exercise": ("Fill the well. For 5 minutes, don't make anything. Look at one thing you love (a song, a "
                     "painting, a view) and just notice it. Then write one sentence about why it works.")},
    "Comparison": {
        "words": ["everyone else", "better than me", "compare", "comparing", "instagram", "not as good as",
                  "others are", "jealous", "they're so good", "their work"],
        "game": "constellation",
        "exercise": ("Learn like a student. List three things you admire in their work. Then spend 5 minutes "
                     "trying ONE of them your way, mixed with something only you know about: your street, your "
                     "family, your language.")},
    "No direction": {
        "words": ["stuck", "don't know what", "dont know what", "no idea", "no ideas", "blank page", "mind is blank",
                  "feel lost", "feeling lost", "i'm lost", "im lost", "where to start", "can't start", "cant start",
                  "writer's block", "creative block", "blocked"],
        "game": "tiny_wins",
        "exercise": ("Three-object spark. Pick three random things near you. In 5 minutes, make something tiny "
                     "that uses all three: a sketch, three lines of a poem, a colour swatch.")},
}
STRESS_WORDS = ["stress", "stressed", "stressing", "deadline", "pressure", "anxious", "panic", "panicking",
                "overwhelmed", "freaking out", "worried", "nervous"]


def has_phrase(text, phrase):
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


def break_offer(text):
    """None, or {block, game} if the text shows stress or a creative block."""
    text = (text or "").lower().replace("’", "'")
    best, best_count = None, 0
    for name, info in BLOCKS.items():
        count = sum(has_phrase(text, w) for w in info["words"])
        if count > best_count:
            best, best_count = name, count
    stressed = any(has_phrase(text, w) for w in STRESS_WORDS)
    if not best and not stressed:
        return None
    return {"block": best, "game": BLOCKS[best]["game"] if best else "orb_flow"}


# ---------------- spark ("I don't have an idea yet") ----------------

SPARK_PARTS = ["medium", "setting", "contrast", "texture", "structure"]
SPARK_MEDIUM = {"Film": "a short film", "Book": "a short story", "Brand": "a brand identity",
                "Poster": "a poster series", "Music video": "a music video", "App": "an app"}
# which answered parts each direction may change
FREE = {"Safe": set(), "Bold": {"texture", "structure"}, "Weird": {"setting", "structure"}}


@st.cache_data
def load_seeds():
    return pd.read_csv(DATA / "idea_seeds.csv").fillna({"tile": ""})


def seeds(kind):
    table = load_seeds()
    return table[table["kind"] == kind].to_dict("records")


def spark_target(answers):
    chosen = [FEELINGS[e] for e in answers.get("emotions") or [] if e in FEELINGS]
    if not chosen:
        return 0.3, 0.1
    return sum(e[0] for e in chosen) / len(chosen), sum(e[1] for e in chosen) / len(chosen)


def heavy_answers(answers):
    for e in answers.get("emotions") or []:
        if e in FEELINGS and FEELINGS[e][3]:
            return True
    return answers.get("feeling_now") in ("Low", "Very low")


def pick_seed(kind, answers, direction, rng, exclude=()):
    valence, arousal = spark_target(answers)
    if direction == "Bold":
        arousal = min(1.0, arousal + 0.5)
    options = [s for s in seeds(kind) if s["text"] not in exclude]
    options.sort(key=lambda s: -cosine([1, valence, arousal], [1, s["valence"], s["arousal"]]))
    if direction == "Weird":
        pool = options[len(options) // 2:]  # the less obvious half
    elif direction == "Bold":
        pool = options[:6]
    else:
        pool = options[:4]
    return rng.choice(pool)["text"]


def describe_idea(idea, answers, taken=()):
    a, b = [w.strip() for w in idea["contrast"].split("+")]
    place = idea["setting"]
    for article in ("a ", "an ", "the "):
        if place.lower().startswith(article):
            place = place[len(article):]
    rng = seeded_random(idea["setting"], idea["contrast"], idea["texture"], idea["structure"], idea["medium"])
    options = [f"{a.title()} and {b.title()}", f"Notes from the {place}",
               f"The {idea['texture'].split()[0].title()} Hour", f"{b.title()}, Somehow"]
    rng.shuffle(options)
    title = options[0]
    for t in options:
        if t not in taken:
            title = t
            break
    era_part = {"Ancient and mythic": " in a mythic past", "Vintage (before 1980)": " in another decade",
                "Retro (1980s-2000s)": " in the not-so-distant past", "The future": " in the future"}.get(answers.get("era"), "")
    medium = SPARK_MEDIUM[idea["medium"]]
    logline = (f"{medium[0].upper() + medium[1:]} told as {idea['structure']}, around {idea['setting']}{era_part}, "
               f"where {a} meets {b}, in {idea['texture']}.")
    quoted = []
    for key, label in (("medium", "medium"), ("setting", "place"), ("contrast", "contrast"), ("texture", "texture")):
        if answers.get(key) == idea[key]:
            quoted.append(f"your {label} \"{idea[key]}\"")
    if answers.get("emotions"):
        quoted.append(f"the feeling \"{' and '.join(e.lower() for e in answers['emotions'])}\"")
    if answers.get("word"):
        quoted.append(f"your word \"{answers['word']}\"")
    if quoted:
        why = "Built from " + ", ".join(quoted) + "."
    else:
        why = "You skipped the questions, so ORBIT chose parts that fit together."
    if idea["direction"] == "Bold":
        why += " The Bold version turns the energy up."
    elif idea["direction"] == "Weird":
        why += " The Weird version picks the less obvious options on purpose."
    idea.update(title=title, logline=logline, why=why)
    return idea


def three_ideas(answers, seed=0):
    ideas = []
    for direction in ("Safe", "Bold", "Weird"):
        rng = seeded_random(direction, seed, sorted(answers.items(), key=str))
        idea = {"direction": direction}
        idea["medium"] = answers.get("medium") or rng.choice(
            {"Safe": ["Film", "Poster", "Book"], "Bold": ["Music video", "Poster", "Brand"],
             "Weird": ["App", "Brand", "Book"]}[direction])
        for kind in ("setting", "contrast", "texture", "structure"):
            answered = answers.get(kind)
            if answered and kind not in FREE[direction]:
                idea[kind] = answered
            else:
                used = {answered} | {i[kind] for i in ideas}
                idea[kind] = pick_seed(kind, answers, direction, rng, used)
        if answers.get("word"):
            idea["word"] = answers["word"]
        ideas.append(describe_idea(idea, answers, [i["title"] for i in ideas]))
    return ideas


def remix_idea(idea, part, answers, seed, keep_only=False):
    """remix = change only this part. keep_only = keep this part and change all the others."""
    rng = seeded_random("remix" if not keep_only else "lock", part, seed, idea["title"])
    new = copy.deepcopy(idea)
    parts = [p for p in SPARK_PARTS if p != part] if keep_only else [part]
    for p in parts:
        if p == "medium":
            new["medium"] = rng.choice([m for m in MEDIUMS if m != idea["medium"]])
        else:
            new[p] = pick_seed(p, answers, idea["direction"], rng, {idea[p]})
    return describe_idea(new, answers)


def idea_to_vector(idea, answers):
    table = load_seeds()
    rows = [table[(table["kind"] == k) & (table["text"] == idea[k])].iloc[0] for k in ("setting", "contrast", "texture", "structure")]
    chosen = [FEELINGS[e] for e in answers.get("emotions") or [] if e in FEELINGS]
    emotions = [(e[2], 1.0 / len(chosen)) for e in chosen] or [("neutral", 1.0)]
    vector = build_vector(f"{idea['logline']} {idea.get('word', '')}".strip(), emotions, medium=idea["medium"])

    def mean(col):
        return sum(float(r[col]) for r in rows) / len(rows)

    if chosen:
        valence, arousal = spark_target(answers)
    else:
        valence, arousal = mean("valence"), mean("arousal")
    vector.update(valence=round(valence, 3), arousal=round(arousal, 3), warmth=round(mean("warmth"), 3),
                  era=round(ERAS.get(answers.get("era"), mean("era")), 3), brightness=round(mean("brightness"), 3),
                  texture=round(mean("texture"), 3),
                  bold=round(clamp(0.4 * arousal + (0.3 if idea["direction"] == "Bold" else 0)), 3))
    tags = [t for r in rows for t in str(r["tags"]).split("|")]
    vector["themes"] = list(dict.fromkeys(vector["themes"] + tags))[:10]
    return vector


# ---------------- PDF brief ----------------

def brief_pdf(u):
    from PIL import Image, ImageDraw, ImageFont
    width, height, margin = 1240, 1754, 90  # A4 at 150 dpi
    ink, muted = (52, 49, 59), (110, 104, 118)
    page = Image.new("RGB", (width, height), (250, 248, 244))
    draw = ImageDraw.Draw(page)

    def font(size):
        for name in ("Nirmala.ttc", "DejaVuSans.ttf", "arial.ttf", "Arial.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                pass
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    h1, body, small = font(52), font(22), font(18)
    y = 70

    def write(text, f, width_chars, colour=ink, gap=8):
        nonlocal y
        for line in textwrap.wrap(text, width_chars):
            draw.text((margin, y), line, fill=colour, font=f)
            y += f.size + gap

    colours = u["palette"]["colours"]
    draw.rectangle([0, 0, width, 26], fill=colours[0]["hex"])
    write("CREATIVE BRIEF - ORBIT CREATOR MODE", small, 90, muted)
    y += 20
    write(u["concept"]["title"], h1, 34)
    y += 10
    write(u["concept"]["vision"], body, 88)
    y += 30
    write("PALETTE", small, 90, muted)
    size = (width - 2 * margin - 80) // 5
    for i, c in enumerate(colours):
        x = margin + i * (size + 20)
        draw.rounded_rectangle([x, y, x + size, y + 130], radius=16, fill=c["hex"], outline=(220, 216, 226))
        draw.text((x, y + 142), c["name"], fill=ink, font=small)
        draw.text((x, y + 166), f"{c['hex']} {c['role']}", fill=muted, font=small)
    y += 230
    sections = [
        ("Typography", [f"{u['fonts']['heading']} for headings, {u['fonts']['body']} for text (Google Fonts)."]),
        ("Moodboard", [f"Lighting: {u['moodboard']['lighting']}. Textures: {', '.join(u['moodboard']['textures'])}.",
                       "Keywords: " + ", ".join(u["moodboard"]["keywords"])]),
        ("Aesthetics", [f"{a['name']} ({a['era_label']}): {a['why']}" for a in u["aesthetics"]]),
        ("Music to work to", ["; ".join(f"{t['title']} by {t['artist']}" for t in u["music"][:6])]),
        ("Creators to look up", [f"{c['name']}, {c['field']}: {c['known_for']}" for c in u["creators"][:5]]),
    ]
    for title, lines in sections:
        write(title.upper(), small, 90, muted)
        for line in lines:
            write(line, body, 90, gap=6)
        y += 22
    draw.text((margin, height - 70), "Made with ORBIT Creator Mode. Music and creators are suggestions to look up.",
              fill=muted, font=small)
    buffer = io.BytesIO()
    page.save(buffer, format="PDF", resolution=150)
    return buffer.getvalue()

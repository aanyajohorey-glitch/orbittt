# The AI part of ORBIT.
# 1. Hinglish / Hindi words are translated to English with a small dictionary
# 2. A pre-trained RoBERTa model (GoEmotions) gives a score for 28 emotions
# 3. My own small classifier (softmax regression, trained in numpy) picks the
#    emotion family and how sure it is
# 4. The closest "world" from worlds.csv is matched
# 5. The safety check runs on every message

import json
import re
import zlib
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import database
import safety

DATA = Path(__file__).parent / "data"
MODEL_FILE = DATA / "model" / "orbit_head.npz"
OFFLINE_MODEL_FILE = DATA / "model" / "orbit_head_T.npz"
UNSURE_BELOW = 0.5

LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring", "confusion", "curiosity",
    "desire", "disappointment", "disapproval", "disgust", "embarrassment", "excitement", "fear",
    "gratitude", "grief", "joy", "love", "nervousness", "optimism", "pride", "realization", "relief",
    "remorse", "sadness", "surprise", "neutral",
]

FAMILY_EMOTIONS = {
    "Joy": ["joy", "amusement", "excitement", "pride", "optimism", "relief", "approval"],
    "Warmth": ["love", "caring", "gratitude", "admiration", "desire"],
    "Sadness": ["sadness", "grief", "disappointment", "remorse"],
    "Fear": ["fear", "nervousness", "embarrassment"],
    "Anger": ["anger", "annoyance", "disgust", "disapproval"],
    "Wonder": ["curiosity", "confusion", "surprise", "realization"],
    "Neutral": ["neutral"],
}
FAMILIES = list(FAMILY_EMOTIONS)
FAMILY_OF = {}
for fam, emotion_list in FAMILY_EMOTIONS.items():
    for emotion in emotion_list:
        FAMILY_OF[emotion] = fam

FAMILY_COLOURS = {"Joy": "#CDAA78", "Warmth": "#C695AA", "Sadness": "#7F93BF", "Fear": "#A895D2",
                  "Anger": "#6E5A8A", "Wonder": "#98AA8C", "Neutral": "#B3AB9C"}
FAMILY_HELP = {"Joy": "happy, excited, proud, relieved", "Warmth": "love, care, gratitude",
               "Sadness": "sad, lonely, disappointed", "Fear": "worried, nervous, scared, embarrassed",
               "Anger": "annoyed, angry, frustrated", "Wonder": "curious, confused, surprised",
               "Neutral": "no strong feeling"}
# used when the classifier picks a family but RoBERTa gave it tiny scores
REPRESENTATIVE = {"Joy": "joy", "Warmth": "caring", "Sadness": "sadness", "Fear": "nervousness",
                  "Anger": "annoyance", "Wonder": "curiosity", "Neutral": "neutral"}

FEELING_WORDS = {
    "admiration": "admiration", "amusement": "amused", "anger": "angry", "annoyance": "annoyed",
    "approval": "okay with how things are", "caring": "caring", "confusion": "confused",
    "curiosity": "curious", "desire": "a kind of longing", "disappointment": "disappointed",
    "disapproval": "unhappy with how things went", "disgust": "put off", "embarrassment": "embarrassed",
    "excitement": "excited", "fear": "scared", "gratitude": "grateful", "grief": "grief",
    "joy": "happy", "love": "love", "nervousness": "nervous", "optimism": "hopeful", "pride": "proud",
    "realization": "like something just clicked", "relief": "relieved", "remorse": "regretful",
    "sadness": "sad", "surprise": "surprised", "neutral": "fairly steady",
}

# valence (sad -1 to happy +1), arousal (calm -1 to energetic +1) for each emotion
EMOTION_VA = {
    "admiration": (0.6, 0.3), "amusement": (0.7, 0.5), "anger": (-0.6, 0.8), "annoyance": (-0.4, 0.5),
    "approval": (0.5, 0.1), "caring": (0.6, 0.1), "confusion": (-0.2, 0.3), "curiosity": (0.3, 0.5),
    "desire": (0.4, 0.6), "disappointment": (-0.6, -0.2), "disapproval": (-0.4, 0.3), "disgust": (-0.7, 0.4),
    "embarrassment": (-0.4, 0.4), "excitement": (0.7, 0.8), "fear": (-0.7, 0.7), "gratitude": (0.7, 0.1),
    "grief": (-0.8, -0.3), "joy": (0.8, 0.6), "love": (0.8, 0.4), "nervousness": (-0.5, 0.6),
    "optimism": (0.6, 0.4), "pride": (0.6, 0.5), "realization": (0.1, 0.3), "relief": (0.5, -0.3),
    "remorse": (-0.6, -0.1), "sadness": (-0.7, -0.4), "surprise": (0.2, 0.7), "neutral": (0.0, 0.0),
}


# ---------------- Hinglish / Hindi dictionary ----------------

PHRASES = {
    "dil toot gaya": "my heart is broken", "dil toot": "heartbroken", "mann nahi": "i don't feel like it",
    "man nahi": "i don't feel like it", "samajh nahi": "i don't understand",
    "kuch samajh nahi": "i don't understand anything", "darr lag raha": "i am scared",
    "dar lag raha": "i am scared", "dar lagta": "i get scared", "yaad aa raha": "i miss",
    "yaad aa rahi": "i miss", "yaad aata": "i miss", "ro raha": "crying", "ro rahi": "crying",
    "lag raha hai": "feels", "lag rahi hai": "feels", "ho gaya": "happened", "ho gayi": "happened",
    "koi nahi": "nobody", "bilkul nahi": "not at all", "gussa aa raha": "i am angry",
    "gussa aa rahi": "i am angry", "gussa aata": "i get angry", "rona aa raha": "i want to cry",
    "rona aa rahi": "i want to cry", "neend nahi": "i can't sleep", "mood off": "upset",
    "mood kharab": "in a bad mood", "bore ho": "bored", "maza aa raha": "i am having fun",
    "maza aa gaya": "that was so much fun",
    "समझ नहीं": "i don't understand", "डर लग रहा": "i am scared", "गुस्सा आ रहा": "i am angry",
    "याद आ रही": "i miss", "याद आ रहा": "i miss",
}

WORDS = {
    "khush": "happy", "khushi": "happiness", "mast": "great", "maza": "fun", "mazaa": "fun",
    "udaas": "sad", "udas": "sad", "udaasi": "sadness", "dukhi": "unhappy", "dukh": "sorrow",
    "rona": "crying", "roya": "cried", "royi": "cried",
    "gussa": "angry", "gusse": "angry", "naraz": "upset", "naraaz": "upset", "chidh": "irritated",
    "pareshan": "worried", "pareshaan": "worried", "chinta": "worry", "tension": "stress",
    "dar": "fear", "darr": "fear", "darta": "afraid", "darti": "afraid", "ghabrahat": "anxiety",
    "ghabra": "anxious", "ghabrayi": "anxious", "ghabraya": "anxious",
    "akela": "alone", "akeli": "alone", "akelapan": "loneliness",
    "thaka": "tired", "thaki": "tired", "thakaan": "exhaustion", "thak": "tired",
    "pyaar": "love", "pyar": "love", "yaad": "miss", "shukriya": "thank you", "dhanyavad": "thank you",
    "garv": "proud", "umeed": "hope", "sharm": "embarrassed", "sharam": "embarrassed",
    "sharminda": "ashamed", "hairaan": "surprised", "hairan": "surprised",
    "bekar": "useless", "bekaar": "useless", "nafrat": "hate", "jalan": "jealousy",
    "sukoon": "peace", "sukun": "peace", "shaant": "calm", "shant": "calm",
    "accha": "good", "acha": "good", "achha": "good", "bura": "bad", "bure": "bad", "kharab": "bad",
    "pagal": "crazy", "boring": "boring",
    "bahut": "very", "bohot": "very", "bohut": "very", "zyada": "too much", "jyada": "too much",
    "bilkul": "completely", "thoda": "a little", "kam": "less", "sach": "really",
    "nahi": "not", "nahin": "not", "nhi": "not", "mat": "don't",
    "hai": "", "hain": "", "hu": "am", "hoon": "am", "hun": "am", "tha": "was", "thi": "was",
    "aa": "", "gaya": "", "gayi": "",
    "mujhe": "i", "mujhko": "me", "mai": "i", "mera": "my", "meri": "my", "mere": "my",
    "aaj": "today", "kal": "yesterday", "yaar": "friend", "dost": "friend", "ghar": "home",
    "padhai": "studies", "sab": "everything", "kuch": "something", "koi": "someone",
    "kyun": "why", "kya": "what", "chahiye": "need", "chahta": "want", "chahti": "want",
    "lag": "feel", "lagta": "feel", "lagti": "feel", "raha": "", "rahi": "", "rahe": "",
    "ko": "", "ki": "", "ka": "", "ke": "", "se": "", "toh": "", "to": "to", "bhi": "also",
    "खुश": "happy", "खुशी": "happiness", "दुखी": "sad", "उदास": "sad", "गुस्सा": "angry",
    "डर": "fear", "अकेला": "alone", "अकेली": "alone", "थका": "tired", "थकी": "tired",
    "बहुत": "very", "अच्छा": "good", "बुरा": "bad", "प्यार": "love", "याद": "miss",
    "परेशान": "worried", "चिंता": "worry", "तनाव": "stress", "शर्म": "embarrassed",
    "रोना": "crying", "मैं": "i", "मुझे": "i", "मेरा": "my", "मेरी": "my", "आज": "today",
    "नहीं": "not", "है": "", "हूँ": "am", "हूं": "am", "था": "was", "थी": "was",
    "माँ": "mother", "मां": "mother", "पापा": "father", "दोस्त": "friend", "परीक्षा": "exam",
    "कल": "tomorrow", "स्कूल": "school", "अपनी": "my", "से": "", "को": "", "कुछ": "anything",
}

# if 2 or more of these words appear, the text is probably Hinglish
MARKERS = {
    "hai", "hain", "nahi", "nahin", "nhi", "bahut", "bohot", "mujhe", "mera", "meri", "yaar",
    "kya", "kyun", "aaj", "raha", "rahi", "hoon", "hu", "tha", "thi", "kuch", "sab", "accha",
    "acha", "khush", "udaas", "gussa", "pareshan", "akela", "thaka", "pyaar", "lag", "lagta",
    "shukriya", "tum", "hamesha", "bhai", "kaise", "yeh", "jaana", "karun", "khaya", "dosto",
}


def has_hindi(text):
    return re.search(r"[ऀ-ॿ]", text or "") is not None


def looks_hinglish(text):
    if has_hindi(text):
        return True
    words = re.findall(r"[a-z]+", text.lower())
    count = 0
    for word in words:
        if word in MARKERS:
            count += 1
    return count >= 2


def to_english(text):
    """Returns (english text, was it translated?)"""
    if not looks_hinglish(text):
        return text, False
    result = text.lower()
    # longer phrases first
    for phrase in sorted(PHRASES, key=len, reverse=True):
        result = re.sub(rf"(?<!\w){re.escape(phrase)}(?!\w)", PHRASES[phrase], result)
    words = re.findall(r"[^\s.,!?।]+|[.,!?]", result)
    new_words = []
    for word in words:
        word = WORDS.get(word, word)
        if word:
            new_words.append(word)
    english = re.sub(r"\s+([.,!?])", r"\1", " ".join(new_words))
    return english, True


# ---------------- RoBERTa emotion model ----------------

@st.cache_resource(show_spinner="Loading the emotion model (first time takes a minute)...")
def load_roberta():
    import onnxruntime
    from huggingface_hub import hf_hub_download
    from tokenizers import Tokenizer

    repo = "SamLowe/roberta-base-go_emotions-onnx"
    model_path = hf_hub_download(repo, "onnx/model_quantized.onnx")
    tokenizer_path = hf_hub_download(repo, "onnx/tokenizer.json")
    session = onnxruntime.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    tokenizer = Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_truncation(max_length=512)
    return session, tokenizer


def detect_emotions(text):
    """All 28 emotions with a score from 0 to 1, highest first."""
    session, tokenizer = load_roberta()
    encoding = tokenizer.encode(text)
    inputs = {"input_ids": np.array([encoding.ids], dtype=np.int64),
              "attention_mask": np.array([encoding.attention_mask], dtype=np.int64)}
    logits = session.run(None, inputs)[0][0]
    scores = 1 / (1 + np.exp(-logits))  # sigmoid
    results = [(label, float(score)) for label, score in zip(LABELS, scores)]
    results.sort(key=lambda pair: pair[1], reverse=True)
    return results


def mood_score(emotions):
    """-1 (very low) to +1 (very bright), used for the journal charts."""
    positive, negative, total = 0, 0, 0
    for label, score in emotions:
        total += score
        if FAMILY_OF[label] in ("Joy", "Warmth"):
            positive += score
        elif FAMILY_OF[label] in ("Sadness", "Fear", "Anger"):
            negative += score
    return (positive - negative) / max(total, 1e-6)


def valence_arousal(emotions):
    total = sum(score for _, score in emotions) or 1
    valence = sum(EMOTION_VA[label][0] * score for label, score in emotions) / total
    arousal = sum(EMOTION_VA[label][1] * score for label, score in emotions) / total
    return valence, arousal


def intensity_word(score, emotion):
    if emotion == "neutral":
        return "Low"
    if score >= 0.6:
        return "Strong"
    if score >= 0.3:
        return "Moderate"
    return "Gentle"


# ---------------- ORBIT's own classifier ----------------
# features = 28 RoBERTa scores + 7 family totals (+ the same for the translated text)
#            + hashed words / word pairs + hashed character 3-5 grams

def bucket(prefix, piece):
    return zlib.crc32(f"{prefix}:{piece}".encode("utf-8")) % 1024


def text_features(text):
    words = re.findall(r"[^\s.,!?।\"'()]+", text.lower())
    word_vec = np.zeros(1024, dtype=np.float32)
    pairs = [f"{a} {b}" for a, b in zip(words, words[1:])]
    for piece in words + pairs:
        word_vec[bucket("w", piece)] = 1.0
    char_vec = np.zeros(1024, dtype=np.float32)
    padded = f" {' '.join(words)} "
    for n in (3, 4, 5):
        for i in range(len(padded) - n + 1):
            char_vec[bucket("c", padded[i:i + n])] += 1.0
    for vec in (word_vec, char_vec):
        size = np.linalg.norm(vec)
        if size:
            vec /= size
    return np.concatenate([word_vec, char_vec])


def score_features(scores):
    base = [scores[label] for label in LABELS]
    totals = [sum(scores[label] for label in FAMILY_EMOTIONS[f]) for f in FAMILIES]
    return np.array(base + totals, dtype=np.float32)


def features(text, raw_scores, dict_scores=None):
    parts = [score_features(raw_scores)]
    if dict_scores is not None:
        parts.append(score_features(dict_scores))
    parts.append(text_features(text))
    return np.concatenate(parts)


def softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def load_head(path):
    data = np.load(path)
    return data["W"], data["b"], json.loads(str(data["meta"]))


@st.cache_resource
def cached_head(path, modified):
    return load_head(path)


def current_head():
    # the personal model (after Teach ORBIT) or the shared one
    path = database.personal_model_path()
    if not path.exists():
        path = MODEL_FILE
    return cached_head(str(path), path.stat().st_mtime)


def predict(head, X):
    W, b, meta = head
    return softmax((X @ W + b) / meta.get("temperature", 1.0))


def train_model(X, y, weights, l2=1e-5, steps=800, lr=0.5):
    """Softmax regression with gradient descent (Adam)."""
    rng = np.random.default_rng(0)
    n, d = X.shape
    k = len(FAMILIES)
    Y = np.eye(k, dtype=np.float32)[y]
    w = weights / weights.mean()
    W = rng.normal(0, 0.01, (d, k)).astype(np.float32)
    b = np.zeros(k, dtype=np.float32)
    mW, vW = np.zeros_like(W), np.zeros_like(W)
    mb, vb = np.zeros_like(b), np.zeros_like(b)
    for step in range(1, steps + 1):
        P = softmax(X @ W + b)
        G = (P - Y) * w[:, None] / n
        gW = X.T @ G + l2 * W
        gb = G.sum(axis=0)
        mW = 0.9 * mW + 0.1 * gW
        vW = 0.999 * vW + 0.001 * gW * gW
        mb = 0.9 * mb + 0.1 * gb
        vb = 0.999 * vb + 0.001 * gb * gb
        W -= lr * (mW / (1 - 0.9 ** step)) / (np.sqrt(vW / (1 - 0.999 ** step)) + 1e-8)
        b -= lr * (mb / (1 - 0.9 ** step)) / (np.sqrt(vb / (1 - 0.999 ** step)) + 1e-8)
    return W, b


@st.cache_data
def saved_scores():
    # RoBERTa scores for the training and test sentences, saved earlier (so the AI Lab is fast)
    with open(DATA / "model" / "base_scores.json", encoding="utf-8") as f:
        return json.load(f)


def scores_for(text, kind):
    """kind = 'raw' (text as written) or 'dict' (after the Hinglish dictionary)"""
    key = f"{kind}::{text}"
    cache = saved_scores()
    if key in cache:
        return cache[key]
    if kind == "dict":
        text = to_english(text)[0]
    return dict(detect_emotions(text))


def retrain_with_corrections():
    train = pd.read_csv(DATA / "train_augment.csv")
    W, b, meta = load_head(MODEL_FILE)
    rows = []
    for _, row in train.iterrows():
        rows.append((row["text"], row["emotion_family"], scores_for(row["text"], "raw"),
                     scores_for(row["text"], "dict"), 1.0))
    corrections = database.get_corrections()
    for c in corrections:
        # a person took the time to correct ORBIT, so it counts double
        rows.append((c["text"], c["corrected"], c["raw_scores"]["raw"], c["raw_scores"]["dict"], 2.0))
    X = np.stack([features(text, raw, d) for text, _, raw, d, _ in rows])
    y = np.array([FAMILIES.index(fam) for _, fam, _, _, _ in rows])
    counts = np.bincount(y, minlength=len(FAMILIES))
    weights = np.array([len(y) / (len(FAMILIES) * counts[label]) * extra for label, (*_, extra) in zip(y, rows)],
                       dtype=np.float32)
    W, b = train_model(X, y, weights, l2=meta["l2"])
    meta["corrections"] = len(corrections)
    path = database.personal_model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, W=W, b=b, meta=json.dumps(meta))
    return len(corrections)


# ---------------- worlds ----------------

@st.cache_data
def load_worlds():
    worlds = []
    for row in pd.read_csv(DATA / "worlds.csv").to_dict("records"):
        row["palette"] = row["palette"].split("|")
        row["elements"] = row["elements"].split("|")
        row["emotions"] = row["emotions"].split("|")
        worlds.append(row)
    return worlds


def get_world(name):
    for world in load_worlds():
        if world["name"] == name:
            return world
    return None


def prompt_for(world, intent):
    return world["prompt_" + intent.lower().replace(" ", "_")]


def match_world(emotions, family):
    scores = dict(emotions)
    allowed = set(FAMILY_EMOTIONS[family])
    options = [w for w in load_worlds() if allowed & set(w["emotions"])] or load_worlds()
    best, best_total = None, -1
    for world in options:
        total = sum(scores.get(e, 0) for e in world["emotions"])
        if total > best_total:
            best, best_total = world, total
    matched = sorted(best["emotions"], key=lambda e: scores.get(e, 0), reverse=True)
    in_family = [e for e in matched if e in allowed]
    matched = in_family + [e for e in matched if e not in allowed]
    strong = [e for e in matched if scores.get(e, 0) >= 0.05]
    return best["name"], strong or matched[:1]


# ---------------- the whole pipeline ----------------

VAGUE = re.compile(r"\b(idk|i don'?t know|dunno|weird|meh|whatever|okay|ok|fine|it is what it is|not sure|"
                   r"mixed feelings|kuch nahi|pata nahi|aise hi)\b", re.IGNORECASE)


def is_vague(text):
    words = re.findall(r"[^\s.,!?।]+", text)
    return len(words) <= 3 or bool(VAGUE.search(text))


def set_family(result, family, source):
    scores = dict(result["emotions"])
    best = max(FAMILY_EMOTIONS[family], key=lambda e: scores.get(e, 0))
    if scores.get(best, 0) < 0.02:
        best = REPRESENTATIVE[family]
    result["family"] = family
    result["emotion"] = best
    result["source"] = source
    result["world"], result["matched"] = match_world(result["emotions"], family)
    return result


def offline_mode():
    return database.get_setting("demo_mode", "0") == "1" or st.session_state.get("model_failed", False)


def interpret(text):
    model_text, translated = to_english(text)
    if offline_mode():
        # no RoBERTa: a smaller classifier that only looks at the words
        head = load_head(OFFLINE_MODEL_FILE)
        probs = predict(head, text_features(text)[None, :])[0]
        emotions = []
        for i, fam in enumerate(FAMILIES):
            for label in FAMILY_EMOTIONS[fam]:
                emotions.append((label, float(probs[i]) / len(FAMILY_EMOTIONS[fam])))
        emotions.sort(key=lambda pair: pair[1], reverse=True)
        raw = dict(emotions)
        source = "Offline estimate (no emotion model)"
    else:
        emotions = detect_emotions(model_text)
        raw = dict(detect_emotions(text)) if translated else dict(emotions)
        head = current_head()
        probs = predict(head, features(text, raw, dict(emotions))[None, :])[0]
        source = "ORBIT classifier" + (" (personal)" if head[2].get("corrections") else "")

    order = np.argsort(probs)[::-1]
    alternatives = [(FAMILIES[i], float(probs[i])) for i in order[:3]]
    family, confidence = alternatives[0]
    result = {
        "text": text, "model_text": model_text, "translated": translated,
        "emotions": emotions, "raw_scores": raw,
        "confidence": confidence, "alternatives": alternatives,
        "vague": is_vague(text), "unsure": confidence < UNSURE_BELOW or is_vague(text),
        "safety": safety.check(text) or safety.check(model_text, emotions),
    }
    return set_family(result, family, source)


def analyse(text):
    """Runs the pipeline and shows a message if something is wrong. Returns a result or None."""
    if not text:
        st.warning("Write a few words about how you feel first.")
        return None
    if not any(ch.isalpha() for ch in text):
        st.warning("ORBIT reads words. Try describing how you feel in a sentence.")
        return None
    if not offline_mode():
        try:
            load_roberta()
        except Exception:
            st.session_state.model_failed = True
            st.warning("The emotion model could not be loaded (it needs internet the first time). "
                       "ORBIT switched to offline mode.")
    try:
        with st.spinner("Reading your words..."):
            return interpret(text)
    except Exception:
        st.error("Something went wrong while reading that. Please try again.")
        return None


def teach(result, family, source):
    """Teach ORBIT: save the correction and update the result."""
    if result["safety"] == "crisis":
        return
    database.add_correction(result["text"], result["family"], family,
                            {"raw": result["raw_scores"], "dict": dict(result["emotions"])}, source)
    result["unsure"] = False
    result["confidence"] = 1.0
    set_family(result, family, "your correction")


# ---------------- explainable AI ----------------
# remove one word at a time and see how much the emotion score drops

@st.cache_data(max_entries=100, show_spinner=False)
def word_importance(text, emotion):
    words = re.findall(r"\S+", text)[:40]
    if len(words) < 2:
        return [(w, 0.0) for w in words]
    base = dict(detect_emotions(" ".join(words)))[emotion]
    result = []
    for i in range(len(words)):
        without = " ".join(words[:i] + words[i + 1:])
        result.append((words[i], base - dict(detect_emotions(without))[emotion]))
    return result


def show_why(result):
    if offline_mode():
        st.caption("Word explanations need the emotion model, which is off in offline mode.")
        return
    try:
        importance = word_importance(result["model_text"], result["emotion"])
    except Exception:
        return
    best = max([v for _, v in importance] + [1e-6])
    shown = []
    for word, value in importance:
        if value / best >= 0.3:
            shown.append(f"**:violet[{word}]**")
        else:
            shown.append(word)
    st.markdown(" ".join(shown))
    top = sorted([p for p in importance if p[1] > 0.01], key=lambda p: -p[1])[:3]
    if top:
        st.caption(f"The highlighted words pushed the model most towards **{result['emotion']}**: "
                   + ", ".join(w for w, _ in top))
    else:
        st.caption("No single word stood out. The whole sentence carries the feeling.")

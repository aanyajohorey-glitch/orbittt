# Small things used on many pages.

import html
import time
from datetime import datetime, timedelta
from uuid import uuid4

import streamlit as st

import ai
import database
from sounds import soundscape

PAGES = {
    "Create": ["Creative universe", "Quick palette & music"],
    "Feel": ["Check-in", "Talk to ORBIT", "Calm Room", "Stress busters", "Reach Out", "Letters",
             "Safety plan", "Mood Lab", "Soundspace", "Arcade"],
    "My Galaxy": ["Journal", "Patterns", "Saved worlds"],
    "About": ["About ORBIT", "AI Lab", "Care & privacy", "Settings"],
}

MOOD_SCALE = {1: "Very low", 2: "Low", 3: "Okay", 4: "Good", 5: "Great"}
INTENTS = ["Explore", "Digital Art", "Poster", "Presentation", "Scrapbook"]
CONSTRAINTS = ["Use only three colours from the palette.", "Leave at least half of the space empty.",
               "Include one handwritten element.", "Finish a first draft in twenty minutes.",
               "Use one texture you can find at home.", "Keep all of the text in lowercase."]

SOUNDSPACES = [
    {"name": "Dream Pop Haze", "genres": "Dream pop, Shoegaze", "moods": ["Calm", "Reflective"],
     "tempo": "Slow to mid", "best_for": "Drawing, daydreaming", "pairs_with": "Lavender Haze", "sound": "dream"},
    {"name": "Neo-classical Rain", "genres": "Modern piano, Strings", "moods": ["Reflective", "Calm"],
     "tempo": "Slow", "best_for": "Journaling, reading", "pairs_with": "Blue Hour Tide", "sound": "rain"},
    {"name": "Indie Folk Morning", "genres": "Indie folk, Acoustic", "moods": ["Hopeful", "Calm"],
     "tempo": "Mid", "best_for": "Morning routines, sketching outside", "pairs_with": "Sage Morning", "sound": "sunset"},
    {"name": "City Pop Sunset", "genres": "City pop, Vintage soul", "moods": ["Nostalgic", "Hopeful"],
     "tempo": "Mid to upbeat", "best_for": "Scrapbooking, editing photos", "pairs_with": "Blush Static", "sound": "sunset"},
    {"name": "Late-night Jazz", "genres": "Jazz, Lo-fi hip hop", "moods": ["Focused", "Calm"],
     "tempo": "Slow to mid", "best_for": "Studying, writing", "pairs_with": "Midnight Library", "sound": "night"},
    {"name": "Cinematic Electronica", "genres": "Ambient electronica, Film score", "moods": ["Restless", "Focused"],
     "tempo": "Building", "best_for": "Bold artwork, big feelings", "pairs_with": "Velvet Thunder", "sound": "focus"},
    {"name": "Soft Ambient", "genres": "Ambient, Drone", "moods": ["Calm", "Reflective", "Nostalgic"],
     "tempo": "Very slow", "best_for": "Winding down, resting", "pairs_with": "Paper Moon", "sound": "waves"},
]


def go(page):
    for section, pages in PAGES.items():
        if page in pages:
            st.session_state.section = section
            st.session_state.page = page
            if section in ("Create", "Feel"):
                database.set_setting("last_mode", section)


def flash(message):
    st.session_state.flash.append(message)


def earn_token(reason):
    st.session_state.tokens += 1
    flash(f"+1 arcade token, {reason}")


def safe(text):
    """escape text before putting it inside html"""
    return html.escape(str(text))


def plain(text):
    """stop markdown from treating * _ etc in user text as formatting"""
    for ch in "\\`*_[]#<>|~$":
        text = str(text).replace(ch, "\\" + ch)
    return text


def swatches(colours, size=40, labels=True):
    boxes = ""
    for colour in colours:
        caption = f"<br><small>{colour}</small>" if labels else ""
        boxes += (f'<div style="display:inline-block;text-align:center;margin:0 6px 6px 0">'
                  f'<div style="width:{size}px;height:{size}px;background:{colour};border-radius:6px;'
                  f'border:1px solid #ccc"></div>{caption}</div>')
    st.markdown(boxes, unsafe_allow_html=True)


# ---------------- ratings ----------------

def save_rating(kind, target, key, add=0):
    saved = st.session_state.setdefault("rating_ids", {})
    if key in saved:  # changed their mind, remove old rating
        database.delete_rating(saved.pop(key))
    value = st.session_state.get(key)
    if value is not None:
        saved[key] = database.add_rating(kind, target, int(value) + add)


def thumbs(kind, target, key, label="Was this helpful?"):
    st.caption(label)
    st.feedback("thumbs", key=key, on_change=save_rating, args=(kind, target, key))


def stars(kind, target, key, label):
    # st.feedback stars gives 0-4, we save 1-5
    st.caption(label)
    st.feedback("stars", key=key, on_change=save_rating, args=(kind, target, key, 1))


def save_count(kind, target, key):
    saved = st.session_state.setdefault("rating_ids", {})
    if key in saved:
        database.delete_rating(saved.pop(key))
    saved[key] = database.add_rating(kind, target, len(st.session_state.get(key) or []))


# ---------------- saved worlds ----------------

def save_world(name, source, intent, prompt, note="", constraint=""):
    for item in st.session_state.collection:
        if item["world"] == name and item["prompt"] == prompt:
            flash(f"{name} is already in your collection.")
            return
    item = {"id": uuid4().hex[:8], "world": name, "source": source, "intent": intent, "prompt": prompt,
            "constraint": constraint, "note": note, "saved_at": datetime.now().strftime("%d %b, %H:%M")}
    database.add_world(item)
    st.session_state.collection.append(item)
    flash(f"Saved {name} to your collection.")


def remove_world(item_id):
    database.remove_world(item_id)
    st.session_state.collection = [i for i in st.session_state.collection if i["id"] != item_id]
    flash("Removed from your collection.")


def show_world(world, prompt=None, intent="Explore"):
    st.subheader(world["name"])
    st.caption(world["mood"])
    st.write(world["description"])
    swatches(world["palette"])
    st.write("**Visual elements:** " + ", ".join(world["elements"]))
    st.write("**Typography:** " + world["typography"])
    st.write("**Sound vibe:** " + world["sound"])
    st.info(f"**Prompt ({intent}):** {prompt or world['prompt_explore']}")


# ---------------- world theme ----------------

def set_world(result):
    if result and result["safety"] != "crisis":
        st.session_state.world = result["world"]
    else:
        st.session_state.world = None


def world_bar():
    name = st.session_state.get("world")
    if not name:
        return
    if name.startswith("vibe:"):
        colours = st.session_state.get("vibe_colours", [])
        label = name[5:]
        sound = "dream"
    else:
        world = ai.get_world(name)
        colours = world["palette"][:3]
        label = f"{name} ({world['mood']})"
        sound = "sunset"
        for space in SOUNDSPACES:
            if space["pairs_with"] == name:
                sound = space["sound"]
    left, mid, right = st.columns([4, 1.4, 1])
    with left:
        st.markdown(f"🪐 You are in **{label}**")
        swatches(colours, size=18, labels=False)
    mid.button("Back to normal", key="world_reset", on_click=lambda: st.session_state.update(world=None))
    right.toggle("Sound", key="sound_on")
    if st.session_state.get("sound_on"):
        st.audio(soundscape(sound), format="audio/wav", loop=True, autoplay=True)


# ---------------- nudges ----------------

def low_mood_count(days=7):
    since = (datetime.now() - timedelta(days=days)).isoformat()
    count = 0
    for entry in database.get_entries():
        if not entry["demo"] and entry["created_at"] >= since:
            if ai.FAMILY_OF.get(entry["primary_emotion"]) in ("Sadness", "Fear", "Anger"):
                count += 1
    return count


def nudge(result=None):
    """ORBIT should support people, not replace them."""
    if result and result["safety"] == "crisis":
        return
    if low_mood_count() >= 3:
        reason = "low_mood"
        text = ("You've had a few heavy days this week. You don't have to carry that alone. Talking to someone "
                "you trust (a parent, a teacher, a school counsellor or a friend) can really help. Tele-MANAS "
                "(14416) is also free and confidential, any time.")
    elif time.time() - st.session_state.started > 30 * 60 or len(st.session_state.chat) >= 16:
        reason = "long_session"
        text = ("We've been talking for a while. ORBIT is happy to listen, but people can support you in ways an "
                "app can't. Maybe message a friend, step outside, or tell someone at home how you're doing.")
    else:
        return
    if reason in st.session_state.dismissed:
        return
    st.info(text)
    st.button("Okay, thank you", key=f"nudge_{reason}", on_click=st.session_state.dismissed.add, args=(reason,))


# ---------------- result widgets used on check-in, chat and mood lab ----------------

def confidence_text(result):
    if result["source"] == "your correction":
        return "You told ORBIT this"
    if result["vague"]:
        return "Short or vague message, so ORBIT is asking"
    if result["unsure"]:
        return f"ORBIT isn't sure ({result['confidence']:.0%})"
    return f"ORBIT is {result['confidence']:.0%} sure"


def clarify(result, key, after=None):
    """When ORBIT is unsure it asks instead of guessing."""
    if result["safety"] == "crisis" or not result["unsure"]:
        return
    first, second = result["alternatives"][0][0], result["alternatives"][1][0]
    st.write("**Which feels closer?**")
    a, b = st.columns(2)
    for col, fam, n in ((a, first, 1), (b, second, 2)):
        col.button(f"{fam} ({ai.FAMILY_HELP[fam].split(',')[0]})", key=f"{key}_c{n}",
                   on_click=apply_teach, args=(result, fam, "clarification", after))


def apply_teach(result, family, source, after):
    ai.teach(result, family, source)
    if after:
        after(result)
    flash(f"Thank you! ORBIT noted that this felt like {family}. Your answer stays on this device.")


def teach_box(result, key, after=None):
    if result["safety"] == "crisis":
        return
    with st.expander("Not quite right? Teach ORBIT"):
        st.write(f"ORBIT read this as **{result['family']}**. Which feeling fits better?")
        options = [f for f in ai.FAMILIES if f != result["family"]]
        choice = st.radio("A better fit", options, key=f"{key}_pick", index=None,
                          format_func=lambda f: f"{f} ({ai.FAMILY_HELP[f]})")
        st.button("Teach ORBIT", key=f"{key}_teach", disabled=choice is None,
                  on_click=apply_teach, args=(result, choice, "teach", after))


def record_checkin(result, source):
    if result["safety"] == "crisis":
        return  # never saved
    if database.journal_on():
        database.add_entry(source, result["text"], result["emotions"], result["world"], result["emotion"])
    earn_token("thanks for checking in")

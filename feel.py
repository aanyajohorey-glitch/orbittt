# Feel tab: all the wellbeing pages.

import json
import random
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import ai
import database
import replies
import safety
from helpers import (INTENTS, CONSTRAINTS, MOOD_SCALE, SOUNDSPACES, clarify, confidence_text, earn_token, flash,
                     go, low_mood_count, nudge, plain, record_checkin, save_world, set_world, show_world, swatches,
                     teach_box, thumbs)
from sounds import soundscape

GAMES_FOLDER = Path(__file__).parent / "games"
GAMES = {  # key: (title, good for, file, minutes)
    "pop_worry": ("Pop the Worry", "Anxious thoughts", "pop_the_worry.html", "2-3"),
    "orb_flow": ("Orb Flow", "Feeling anxious or overwhelmed", "orb_flow.html", "3-5"),
    "zen_sand": ("Zen Sand Garden", "Feeling sad or tired", "zen_sand.html", "2-5"),
    "constellation": ("Constellation Connect", "Feeling restless", "constellation_connect.html", "2-4"),
    "planet_builder": ("Planet Builder", "Feeling sad or low", "planet_builder.html", "2-4"),
    "tiny_wins": ("Tiny Wins Quest", "Low energy", "tiny_wins.html", "2-5"),
    "crack_glass": ("Crack the Glass", "Feeling angry", "crack_the_glass.html", "2-3"),
    "mandala": ("Mandala Colouring", "Feeling stressed", "mandala.html", "3-5"),
    "rhythm": ("Rhythm Pulse", "Feeling tense", "rhythm_pulse.html", "2-3"),
}
GAMES_FOR = {"nervousness": ["pop_worry", "orb_flow", "rhythm"], "fear": ["orb_flow", "pop_worry", "constellation"],
             "sadness": ["zen_sand", "planet_builder", "tiny_wins"],
             "disappointment": ["planet_builder", "tiny_wins", "mandala"],
             "anger": ["crack_glass", "rhythm"], "annoyance": ["crack_glass", "rhythm", "mandala"]}
TOOLS = ["Breathing", "Grounding", "Thought Reframe", "Gratitude Jar"]


def mood_slider(label, key, default=3):
    return st.select_slider(label, options=list(MOOD_SCALE), value=st.session_state.get(key, default),
                            format_func=MOOD_SCALE.get, key=key)


def name():
    return database.get_setting("name", "")


def keep_talking(result):
    st.session_state.chat = [{"role": "user", "content": result["text"], "result": result},
                             {"role": "assistant", "content": result["reply"], "style": result["style"], "result": result}]
    st.session_state.chat_token = True
    go("Talk to ORBIT")


def emotion_summary(result):
    score = dict(result["emotions"]).get(result["emotion"], 0)
    a, b, c = st.columns(3)
    a.metric("Main feeling", result["emotion"].capitalize(), result["family"], delta_color="off")
    b.metric("Confidence", "You" if result["source"] == "your correction" else f"{result['confidence']:.0%}")
    c.metric("Intensity", ai.intensity_word(score, result["emotion"]))
    st.caption(confidence_text(result) + f" · {result['source']}")
    if result["translated"]:
        st.caption(f"ORBIT translated your Hinglish/Hindi and understood it as: \"{plain(result['model_text'])}\"")


def emotion_chart(emotions, count=5):
    table = pd.DataFrame(emotions[:count], columns=["emotion", "score"]).set_index("emotion")
    st.bar_chart(table, horizontal=True, height=200)


# ---------------- 1. check-in ----------------

def new_checkin():
    st.session_state.home_result = None
    st.session_state.today_done = False
    st.session_state.game_playing = None
    st.session_state.home_text = ""


def finish_checkin(tool):
    before = st.session_state.get("today_before", 3)
    after = st.session_state.get("today_after", 3)
    database.add_wellbeing(f"Check-in: {tool}", before, after)
    if after != before:
        flash(f"Mood {MOOD_SCALE[before]} -> {MOOD_SCALE[after]}.")
    earn_token("for finishing today's check-in")
    st.session_state.today_done = True


def refresh_reply(result):
    result["reply"], result["style"] = replies.reply(result, name=name())
    set_world(result)


def feeling_to_create(result):
    import create
    import creative
    st.session_state.create_break = None
    st.session_state.create_offer = None
    vector = creative.build_vector("a creative piece inspired by today's feeling", result["emotions"],
                                   match_text=result["model_text"])
    create.generate(vector, 0.5, "From your check-in")
    go("Creative universe")


def checkin_page():
    hour = datetime.now().hour
    part = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
    who = name()
    st.title("ORBIT")
    st.caption("Every feeling has a universe.")
    result = st.session_state.home_result
    step = 1 if not result else 6 if st.session_state.today_done else 3
    st.progress(step / 6, text=f"Step {step} of 6")

    st.header(f"Good {part}{', ' + who if who else ''}. What does your world feel like today?")
    st.write("Describe a feeling, a moment or a whole day, in English, Hinglish or Hindi.")
    if not who:
        st.text_input("What should ORBIT call you? (optional)", key="home_name", max_chars=30,
                      on_change=lambda: database.set_setting("name", st.session_state.home_name.strip()))
    st.text_area("Your feelings", key="home_text", height=120,
                 placeholder="e.g. Exams finished today. I feel relieved but strangely empty...")
    a, b = st.columns(2)
    with a:
        mood_slider("How are you, right now?", "today_before")
    with b:
        st.pills("Creative intent (optional)", INTENTS, key="home_intent")

    if st.button("Find my orbit", type="primary"):
        result = ai.analyse(st.session_state.home_text.strip())
        if result:
            result["intent"] = st.session_state.home_intent or "Explore"
            result["reply"], result["style"] = replies.reply(result, name=who)
            record_checkin(result, "Check-in")
            st.session_state.home_result = result
            st.session_state.today_done = False
            set_world(result)
            st.rerun()

    if not result:
        st.caption("ORBIT is an AI, not a therapist. If you are ever in danger, call Tele-MANAS on 14416 or 112.")
        return

    if result["safety"] == "crisis":
        safety.show_safety_card("crisis")
        st.info(result["reply"])
        st.button("Talk to ORBIT", on_click=keep_talking, args=(result,))
        st.button("Start a new check-in", on_click=new_checkin)
        return

    st.divider()
    st.subheader("2. What ORBIT noticed")
    emotion_summary(result)
    emotion_chart(result["emotions"])
    with st.expander("Why ORBIT decided this"):
        ai.show_why(result)
    clarify(result, "home_clarify", refresh_reply)
    teach_box(result, "home_teach", refresh_reply)
    st.button("See the full analysis in the Mood Lab", on_click=open_in_lab, args=(result,))
    if result["safety"] == "concern":
        safety.show_safety_card("concern")

    st.subheader("3. ORBIT's reply")
    with st.chat_message("assistant"):
        st.write(result["reply"])
        st.caption(f"Reply style: {result['style']}")
    st.button("Keep talking", on_click=keep_talking, args=(result,))
    thumbs("reply", result["style"], key="fb_today_reply")
    nudge(result)
    maybe_offer_game(result)
    game_box(result)
    reach_out_offer(result)

    tool, line = replies.suggestion(result)
    st.subheader(f"4. One small thing to try: {tool}")
    st.write(line)
    with st.container(border=True):
        show_tool(tool)
    st.button("Choose a different tool", on_click=open_calm_room, args=(tool,))

    st.subheader("5. How do you feel now?")
    mood_slider("Right now I feel...", "today_after", st.session_state.get("today_before", 3))
    if not st.session_state.today_done:
        st.button("Finish check-in", type="primary", on_click=finish_checkin, args=(tool,))
        return
    thumbs("tool", tool, key=f"fb_today_tool_{tool}")

    st.subheader("6. Your new planet joined your galaxy")
    world = ai.get_world(result["world"])
    prompt = ai.prompt_for(world, result["intent"])
    show_world(world, prompt, result["intent"])
    st.write("**Matched on:** " + ", ".join(result["matched"]))
    a, b, c, d = st.columns(4)
    a.button("Save world", type="primary", on_click=save_world,
             args=(world["name"], "Check-in", result["intent"], prompt, result["text"][:160]))
    b.button("See my galaxy", on_click=go, args=("Journal",))
    c.button("Turn this feeling into something", on_click=feeling_to_create, args=(result,))
    d.button("New check-in", on_click=new_checkin)
    st.caption("You earned an arcade token for looking after yourself. Spend it in Feel -> Arcade.")


def open_in_lab(result):
    st.session_state.lab_text = result["text"]
    st.session_state.lab_result = result
    go("Mood Lab")


def open_calm_room(tool):
    st.session_state.calm_tool = tool
    go("Calm Room")


# ---------------- stress-buster games ----------------

def game_reason(result):
    """None if a game may be offered, otherwise why not."""
    if result["safety"]:
        return "safety"
    if result["emotion"] not in GAMES_FOR:
        return "not distress"
    if result["unsure"]:
        return "unsure"
    if low_mood_count() >= 3:
        return "repeated low mood"  # suggest a person instead
    if database.get_setting("games_opt_out", "0") == "1":
        return "opted out"
    if st.session_state.get("game_offered"):
        return "already offered"
    return None


@st.dialog("A stress buster for you")
def game_dialog(key):
    title, helps, _, minutes = GAMES[key]
    st.write("We found a stress buster game for you. Would you like to play?")
    st.write(f"**{title}**: {helps}, about {minutes} minutes, no scores.")
    a, b, c = st.columns(3)
    if a.button("Play", type="primary"):
        st.session_state.game_playing = key
        st.rerun()
    if b.button("Not now"):
        st.rerun()
    if c.button("Don't suggest games"):
        database.set_setting("games_opt_out", "1")
        flash("Okay, ORBIT won't suggest games. You can turn them back on in Settings.")
        st.rerun()


def maybe_offer_game(result):
    if game_reason(result) is None:
        st.session_state.game_offered = True
        game_dialog(random.choice(GAMES_FOR[result["emotion"]]))


def play_game(key, height=620):
    title, _, filename, _ = GAMES[key]
    world = ai.get_world(st.session_state.world) if st.session_state.get("world", "") and not st.session_state.world.startswith("vibe:") else None
    colours = world["palette"][:3] if world else ["#C9B9E8", "#B9C8EA", "#EBCBD7"]
    ink = world["planet_dark"] if world else "#A895D2"
    css = (GAMES_FOLDER / "_shared.css").read_text(encoding="utf-8")
    body = (GAMES_FOLDER / filename).read_text(encoding="utf-8")
    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>:root {{ --a: {colours[0]}; --b: {colours[1]}; --c: {colours[2]}; --ink: {ink}; }}\n{css}</style>"
            f"<script>const PALETTE = {json.dumps(colours)}; const INK = {json.dumps(ink)}; "
            f"const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;</script>"
            f"</head><body>{body}</body></html>")
    st.iframe(page, height=height)


def game_box(result):
    key = st.session_state.get("game_playing")
    if not key:
        return
    with st.container(border=True):
        st.subheader(f"Stress buster: {GAMES[key][0]}")
        play_game(key)
        thumbs("tool", f"Game: {GAMES[key][0]}", key=f"fb_game_{key}", label="Did this game help?")
        st.button("I'm done", on_click=lambda: st.session_state.update(game_playing=None))


def games_page():
    st.header("Small games for big feelings")
    st.write("Nine gentle games, 2-5 minutes each. No scores, no streaks, no pressure.")
    choice = st.selectbox("Choose a game", list(GAMES), format_func=lambda k: GAMES[k][0])
    title, helps, _, minutes = GAMES[choice]
    st.write(f"Good for: **{helps}**, about {minutes} minutes")
    play_game(choice)
    thumbs("tool", f"Game: {title}", key=f"fb_gamelib_{choice}", label="Did this game help?")
    st.caption("Games are for everyday stress. If you're struggling a lot, please talk to someone you trust or call "
               "Tele-MANAS on 14416.")


# ---------------- 2. chat ----------------

STARTERS = ["Exams are next week and I can't stop worrying.", "Today was actually really good!",
            "I had a fight with my best friend.", "aaj mood thoda off hai yaar"]


def handle_message(text):
    result = ai.analyse(text.strip())
    if not result:
        return
    set_world(result)
    chat = st.session_state.chat
    chat.append({"role": "user", "content": text.strip(), "result": result})
    answer, style = replies.reply(result, chat, name())
    chat.append({"role": "assistant", "content": answer, "style": style, "result": result})
    if result["safety"] != "crisis":
        if database.journal_on():
            database.add_entry("Chat", result["text"], result["emotions"], result["world"], result["emotion"])
        if not st.session_state.chat_token:
            st.session_state.chat_token = True
            earn_token("thanks for talking")


def refresh_chat(result):
    for m in st.session_state.chat:
        if m["role"] == "assistant" and m["result"] is result:
            m["content"], m["style"] = replies.reply(result, (), name())


def chat_page():
    st.header("Someone to talk to")
    st.write("Tell ORBIT what's on your mind. It listens for the feelings in your words and helps you take a small "
             "next step.")
    st.caption(f"ORBIT is an AI, not a person. Replies: {replies.mode_label()}. If you are ever in danger, call "
               "Tele-MANAS on 14416 or 112.")
    nudge()
    typed = st.chat_input("Tell ORBIT how you're feeling...")
    pending = st.session_state.pop("chat_pending", None)
    if typed or pending:
        handle_message(typed or pending)

    chat = st.session_state.chat
    with st.chat_message("assistant"):
        hello = f"Hi {name()}. " if name() else "Hi. "
        st.write(hello + "I'm ORBIT, an AI companion. I'm not a person, but I'm here to listen. How are you feeling?")
    for i, m in enumerate(chat):
        with st.chat_message(m["role"]):
            st.markdown(plain(m["content"]))
            r = m["result"]
            if m["role"] == "user":
                tops = ", ".join(f"{l} {s:.0%}" for l, s in r["emotions"][:3] if s >= 0.05)
                st.caption(f"{confidence_text(r)} · {r['family']} ({r['emotion']}) · {tops}")
            else:
                if r["safety"]:
                    safety.show_safety_card(r["safety"])
                st.caption(f"Reply style: {m['style']}")
                if r["safety"] != "crisis":
                    thumbs("reply", m["style"], key=f"fb_chat_{i}")

    if not chat:
        st.write("**Not sure how to start? Try one:**")
        for col, starter in zip(st.columns(4), STARTERS):
            col.button(starter, on_click=lambda s=starter: st.session_state.update(chat_pending=s))
        return

    last = chat[-1]["result"]
    clarify(last, f"chat_{len(chat)}", refresh_chat)
    teach_box(last, f"chat_{len(chat)}", refresh_chat)
    a, b = st.columns(2)
    if last["safety"] != "crisis":
        tool, line = replies.suggestion(last)
        st.write(line)
        a.button(f"Open {tool}", type="primary", on_click=open_calm_room, args=(tool,))
    b.button("New conversation", on_click=lambda: st.session_state.update(chat=[], chat_token=False))


# ---------------- 3. calm room ----------------

BREATHING = {"Calm 4-6": [("Breathe in", 4), ("Breathe out", 6)],
             "Box 4-4-4-4": [("Breathe in", 4), ("Hold", 4), ("Breathe out", 4), ("Hold", 4)],
             "Relax 4-7-8": [("Breathe in", 4), ("Hold", 7), ("Breathe out", 8)]}
THINKING_TRAPS = {
    "All-or-nothing thinking": (["always", "never", "completely", "totally", "nothing", "everything", "perfect"],
                                "Seeing things as all good or all bad, with nothing in between."),
    "Overgeneralising": (["everyone", "nobody", "no one", "everybody", "every time"],
                         "Turning one event into a rule about everything."),
    "Catastrophising": (["worst", "ruined", "disaster", "terrible", "end of the world", "fail everything"],
                        "Jumping to the worst possible outcome."),
    "Should statements": (["should", "must", "have to", "supposed to"],
                          "Holding yourself to rigid rules that create guilt or pressure."),
    "Mind reading": (["they think", "everyone thinks", "they must think", "judging me", "hates me"],
                     "Assuming you know what others are thinking."),
    "Labelling": (["i'm stupid", "i am stupid", "i'm a failure", "i am a failure", "i'm useless", "loser",
                   "i'm not good enough", "i am not good enough"],
                  "Putting a harsh label on yourself instead of describing what happened."),
}
NEGATIVE = ["sadness", "fear", "nervousness", "anger", "annoyance", "disappointment", "grief", "remorse",
            "embarrassment", "disgust", "disapproval"]


def show_tool(tool):
    if tool == "Grounding":
        grounding()
    elif tool == "Thought Reframe":
        reframe()
    elif tool == "Gratitude Jar":
        gratitude()
    else:
        breathing()


def breathing():
    pattern = st.radio("Pattern", list(BREATHING), horizontal=True, key="breath_pattern")
    total = sum(sec for _, sec in BREATHING[pattern])
    st.write(f"One full breath takes {total} seconds. Press start and follow along for five breaths.")
    if st.button("Start breathing", key="breath_start"):
        box = st.empty()
        bar = st.progress(0.0)
        for n in range(5):
            for label, seconds in BREATHING[pattern]:
                for left in range(seconds, 0, -1):
                    box.subheader(f"Breath {n + 1} of 5: {label}... {left}")
                    time.sleep(1)
            bar.progress((n + 1) / 5)
        box.success("Well done. Notice how you feel now.")


def grounding():
    senses = [("5", "things you can see"), ("4", "things you can touch"), ("3", "things you can hear"),
              ("2", "things you can smell"), ("1", "thing you can taste")]
    done = 0
    for number, label in senses:
        if st.text_input(f"{number} {label}", key=f"ground_{number}").strip():
            done += 1
    st.progress(done / 5, text=f"{done} of 5 senses")
    if done == 5:
        st.success("You're here, in this moment. Notice your feet on the floor and take one slow breath.")


def find_traps(thought):
    text = " " + thought.lower().replace("’", "'") + " "
    found = []
    for trap, (words, meaning) in THINKING_TRAPS.items():
        hits = [w for w in words if re.search(rf"(?<!\w){re.escape(w)}(?!\w)", text)]
        if hits:
            found.append((trap, meaning, hits))
    return found


def reframe():
    st.text_area("What happened?", key="reframe_situation", height=70, placeholder="e.g. I got a low mark in my maths test.")
    thought = st.text_area("What thought went through your mind?", key="reframe_thought", height=70,
                           placeholder="e.g. I always fail. I'm never going to be good at this.")
    if thought.strip():
        traps = find_traps(thought)
        if traps:
            st.write("**Possible thinking traps:**")
            for trap, meaning, hits in traps:
                st.write(f"- **{trap}** ({', '.join(hits)}): {meaning}")
        else:
            st.write("No common thinking traps spotted. That thought may simply be honest.")
    st.text_area("Evidence that the thought might NOT be completely true", key="reframe_evidence", height=70)
    balanced = st.text_area("A kinder, more balanced thought", key="reframe_balanced", height=70,
                            placeholder="e.g. This test went badly, but I can ask for help and improve.")
    if thought.strip() and balanced.strip():
        if ai.offline_mode():
            st.caption("In offline mode ORBIT cannot compare the two thoughts. Your balanced thought still counts!")
        elif st.button("See how the feeling changes", key="reframe_compare"):
            before = dict(ai.detect_emotions(ai.to_english(thought)[0]))
            label = max(NEGATIVE, key=lambda e: before[e])
            after = dict(ai.detect_emotions(ai.to_english(balanced)[0]))
            a, b = st.columns(2)
            a.metric("Original thought", f"{before[label]:.0%}", label, delta_color="off")
            b.metric("Balanced thought", f"{after[label]:.0%}", f"{(after[label] - before[label]) * 100:+.0f} points",
                     delta_color="inverse")


def gratitude():
    filled = 0
    for i in (1, 2, 3):
        if st.text_input(f"Good thing {i}", key=f"grat_{i}", placeholder="Something small counts too...").strip():
            filled += 1
    st.write("🫙 " + "⭐" * filled + f"  ({filled} of 3 in your jar)")


def save_calm_session(tool):
    before = st.session_state.get("calm_before", 3)
    after = st.session_state.get("calm_after", 3)
    database.add_wellbeing(tool, before, after)
    if after != before:
        flash(f"{tool} saved. Your mood moved from {MOOD_SCALE[before]} to {MOOD_SCALE[after]}.")
    else:
        flash(f"{tool} saved. You stayed at {MOOD_SCALE[after]}. Showing up still counts.")
    earn_token("for looking after yourself")


def calm_room_page():
    st.header("A quiet place to breathe")
    st.write("Small, evidence-based exercises for big feelings. Notice how you feel before and after.")
    if st.session_state.get("calm_tool") not in TOOLS:
        st.session_state.calm_tool = "Breathing"
    tool = st.radio("Choose an exercise", TOOLS, horizontal=True, key="calm_tool")
    info = {"Breathing": "Slow, paced breathing calms the body's stress response.",
            "Grounding": "Naming what your senses notice brings you back to the present moment.",
            "Thought Reframe": "A thought record from CBT: catch a thought, test it, and find a kinder one.",
            "Gratitude Jar": "Noticing good things, even small ones, gently lifts mood over time."}
    st.caption(info[tool])
    mood_slider("How do you feel right now?", "calm_before")
    with st.container(border=True):
        show_tool(tool)
    thumbs("tool", tool, key=f"fb_calm_{tool}", label="Was this exercise helpful?")
    mood_slider("And how do you feel now?", "calm_after")
    st.button("Save this session", type="primary", on_click=save_calm_session, args=(tool,))


# ---------------- 4. reach out ----------------

WHO = {"friend": "A friend", "parent": "A parent or family member", "teacher": "A teacher or counsellor"}
LEVELS = {"hard": "Just \"I'm having a hard time\"", "little": "A little detail (how I feel)",
          "more": "More detail (what it's about)"}
LANGUAGES = ["English", "Hinglish", "Hindi"]
FEELING_TEXT = {
    "English": {"Sadness": "really low", "Fear": "really anxious and stressed", "Anger": "really angry and frustrated", None: "a bit off"},
    "Hinglish": {"Sadness": "bahut low", "Fear": "bahut anxious aur stressed", "Anger": "bahut gussa aur frustrated", None: "theek nahi"},
    "Hindi": {"Sadness": "मेरा मन बहुत उदास है", "Fear": "मुझे बहुत घबराहट और तनाव हो रहा है",
              "Anger": "मुझे बहुत गुस्सा और चिढ़ हो रही है", None: "मेरा मन ठीक नहीं है"},
}
SOMETHING = {"English": "a few things", "Hinglish": "kuch cheezon", "Hindi": "कुछ बातों"}
# {f} = the feeling, {c} = what it's about
TEMPLATES = {
    "English": {
        "friend": {
            "hard": ["Hey, I'm having a hard time right now. Could we talk sometime today?",
                     "Hi, I'm not doing great lately. Are you free to chat or hang out for a bit?",
                     "Hey, can I talk to you? Things feel like a lot right now."],
            "little": ["Hey, I've been feeling {f} lately. Could we talk sometime today?",
                       "Hi, honestly I've been feeling {f}. Would you be free for a call?",
                       "Hey, I'm feeling {f} and could use a friend. Can we talk?"],
            "more": ["Hey, I've been feeling {f}, mostly because of {c}. Could we talk about it?",
                     "Hi, can I share something? I've been feeling {f} about {c}, and it's been hard.",
                     "Hey, I keep thinking about {c} and I'm feeling {f}. Do you have some time to talk?"]},
        "parent": {
            "hard": ["Hi, I'm having a hard time lately. Can we talk tonight?",
                     "I wanted to tell you that I'm not doing very well. Can we sit together for a bit?",
                     "Can I talk to you about something? I've been finding things hard."],
            "little": ["Hi, I've been feeling {f} lately and I wanted you to know. Can we talk?",
                       "I've been feeling {f} for a while. Can we talk tonight?",
                       "I don't really know how to say this, but I've been feeling {f}. Can we talk?"],
            "more": ["I've been feeling {f}, mostly because of {c}. Can we talk about it tonight?",
                     "Can we talk? I've been worried about {c} and I'm feeling {f}.",
                     "I wanted to tell you that I'm feeling {f} about {c}. I'd like your help."]},
        "teacher": {
            "hard": ["Hello, I've been finding things hard lately. Could I speak to you for a few minutes?",
                     "Good morning. I'm having a difficult time at the moment. Could we talk sometime this week?",
                     "Hello, may I talk to you privately for a few minutes? I'm not doing very well."],
            "little": ["Hello, I've been feeling {f} lately. Could I speak to you for a few minutes?",
                       "Good morning. I've been feeling {f} and I'd like some advice. When would be a good time?",
                       "Hello, I've been feeling {f}. Would it be possible to talk this week?"],
            "more": ["Hello, I've been feeling {f}, mostly because of {c}. Could I speak to you about it?",
                     "Good morning. I've been struggling with {c} and I'm feeling {f}. Could we talk?",
                     "Hello, I'd like some help with {c}. I've been feeling {f}. When could we talk?"]},
    },
    "Hinglish": {
        "friend": {
            "hard": ["Hey, abhi thoda tough time chal raha hai. Aaj baat kar sakte hain?",
                     "Yaar, main theek nahi hoon aajkal. Thodi der baat karein?",
                     "Hey, kya main tujhse baat kar sakta/sakti hoon? Sab bahut zyada lag raha hai."],
            "little": ["Hey, aajkal main {f} feel kar raha/rahi hoon. Aaj baat karein?",
                       "Yaar, sach bolun toh main {f} feel kar raha/rahi hoon. Call kar sakte hain?",
                       "Hey, main {f} hoon aur ek dost ki zaroorat hai. Baat karein?"],
            "more": ["Hey, {c} ki wajah se main {f} feel kar raha/rahi hoon. Iske baare mein baat karein?",
                     "Yaar, ek baat share karni hai. {c} ko leke main {f} hoon, mushkil ho raha hai.",
                     "Hey, {c} ko leke bahut soch raha/rahi hoon aur main {f} hoon. Thoda time hai baat karne ka?"]},
        "parent": {
            "hard": ["Mumma/Papa, aajkal mera time thoda mushkil chal raha hai. Aaj raat baat kar sakte hain?",
                     "Mujhe aapko batana tha ki main theek nahi hoon. Thodi der saath baith sakte hain?",
                     "Kya main aapse kuch baat kar sakta/sakti hoon? Sab thoda mushkil lag raha hai."],
            "little": ["Mumma/Papa, aajkal main {f} feel kar raha/rahi hoon. Baat kar sakte hain?",
                       "Kuch dino se main {f} feel kar raha/rahi hoon. Aaj raat baat karein?",
                       "Samajh nahi aa raha kaise bolun, par main {f} feel kar raha/rahi hoon. Baat karein?"],
            "more": ["{c} ki wajah se main {f} feel kar raha/rahi hoon. Aaj raat iske baare mein baat karein?",
                     "Baat kar sakte hain? {c} ki tension hai aur main {f} feel kar raha/rahi hoon.",
                     "Aapko batana tha ki {c} ko leke main {f} hoon. Mujhe aapki help chahiye."]},
        "teacher": {
            "hard": ["Good morning Ma'am/Sir, aajkal mujhe thoda mushkil lag raha hai. Kya main aapse thodi der baat kar sakta/sakti hoon?",
                     "Ma'am/Sir, mera time abhi thoda difficult chal raha hai. Is hafte baat ho sakti hai?",
                     "Ma'am/Sir, kya main aapse akele mein thodi der baat kar sakta/sakti hoon?"],
            "little": ["Good morning Ma'am/Sir, aajkal main {f} feel kar raha/rahi hoon. Kya thodi der baat ho sakti hai?",
                       "Ma'am/Sir, main {f} feel kar raha/rahi hoon aur aapki advice chahiye. Kab baat ho sakti hai?",
                       "Ma'am/Sir, main {f} hoon. Is hafte baat karna possible hai?"],
            "more": ["Ma'am/Sir, {c} ki wajah se main {f} feel kar raha/rahi hoon. Kya iske baare mein baat ho sakti hai?",
                     "Good morning Ma'am/Sir, {c} ko leke mujhe mushkil ho rahi hai aur main {f} hoon. Baat kar sakte hain?",
                     "Ma'am/Sir, mujhe {c} mein help chahiye. Main {f} feel kar raha/rahi hoon. Kab baat ho sakti hai?"]},
    },
    "Hindi": {
        "friend": {
            "hard": ["अरे, अभी मेरा समय थोड़ा मुश्किल चल रहा है। क्या आज बात कर सकते हैं?",
                     "यार, आजकल मन ठीक नहीं है। थोड़ी देर बात करें?",
                     "क्या मैं तुमसे बात कर सकता/सकती हूँ? सब कुछ बहुत भारी लग रहा है।"],
            "little": ["अरे, आजकल {f}। क्या आज बात कर सकते हैं?", "सच कहूँ तो {f}। क्या फ़ोन पर बात हो सकती है?",
                       "{f}, और मुझे एक दोस्त की ज़रूरत है। बात करें?"],
            "more": ["{c} की वजह से {f}। क्या इसके बारे में बात कर सकते हैं?",
                     "एक बात बतानी है। {c} को लेकर {f}, और यह मुश्किल हो रहा है।",
                     "{c} के बारे में सोचकर {f}। क्या तुम्हारे पास बात करने का थोड़ा समय है?"]},
        "parent": {
            "hard": ["मम्मी/पापा, आजकल मेरा समय थोड़ा मुश्किल चल रहा है। क्या आज रात बात कर सकते हैं?",
                     "मुझे आपको बताना था कि मैं ठीक महसूस नहीं कर रहा/रही। क्या थोड़ी देर साथ बैठ सकते हैं?",
                     "क्या मैं आपसे कुछ बात कर सकता/सकती हूँ? सब थोड़ा मुश्किल लग रहा है।"],
            "little": ["मम्मी/पापा, आजकल {f}। मैं चाहता/चाहती हूँ कि आपको पता हो। क्या बात कर सकते हैं?",
                       "कुछ दिनों से {f}। क्या आज रात बात करें?", "समझ नहीं आ रहा कैसे कहूँ, पर {f}। क्या हम बात कर सकते हैं?"],
            "more": ["{c} की वजह से {f}। क्या आज रात इसके बारे में बात कर सकते हैं?",
                     "क्या हम बात कर सकते हैं? {c} की चिंता है और {f}।", "आपको बताना था कि {c} को लेकर {f}। मुझे आपकी मदद चाहिए।"]},
        "teacher": {
            "hard": ["नमस्ते मैम/सर, आजकल मुझे चीज़ें मुश्किल लग रही हैं। क्या मैं आपसे कुछ मिनट बात कर सकता/सकती हूँ?",
                     "मैम/सर, अभी मेरा समय थोड़ा कठिन चल रहा है। क्या इस हफ़्ते बात हो सकती है?",
                     "मैम/सर, क्या मैं आपसे अकेले में कुछ मिनट बात कर सकता/सकती हूँ?"],
            "little": ["नमस्ते मैम/सर, आजकल {f}। क्या कुछ मिनट बात हो सकती है?",
                       "मैम/सर, {f} और मुझे आपकी सलाह चाहिए। कब बात करना ठीक रहेगा?", "मैम/सर, {f}। क्या इस हफ़्ते बात करना संभव है?"],
            "more": ["मैम/सर, {c} की वजह से {f}। क्या इसके बारे में बात हो सकती है?",
                     "नमस्ते मैम/सर, {c} को लेकर मुझे मुश्किल हो रही है और {f}। क्या हम बात कर सकते हैं?",
                     "मैम/सर, मुझे {c} में मदद चाहिए। {f}। कब बात हो सकती है?"]},
    },
}


def detect_language(text):
    if ai.has_hindi(text):
        return "Hindi"
    if ai.to_english(text)[1]:
        return "Hinglish"
    return "English"


def needs_extra_care(result):
    return (result is not None and result["safety"] == "concern") or low_mood_count() >= 3


def reach_out_offer(result):
    if result["safety"] == "crisis" or result["family"] not in ("Sadness", "Fear", "Anger"):
        return
    with st.container(border=True):
        st.write("**Reach Out Helper:** finding it hard to tell someone how you feel? ORBIT can help you write a short "
                 "message. You decide if and when to send it.")
        st.button("Help me write it", on_click=open_reach_out, args=(result,))
        if needs_extra_care(result):
            st.write("If it feels like too much, please also talk to a trusted adult, or call **Tele-MANAS 14416**.")


def open_reach_out(result):
    st.session_state.ro_family = result["family"]
    st.session_state.ro_lang = detect_language(result["text"])
    go("Reach Out")


def save_draft(who, key):
    text = st.session_state.get(key, "").strip()
    if text and safety.check(text) != "crisis":
        database.add_note("reach_out", WHO[who], text)
        flash("Saved on this device only.")


def reach_out_page():
    st.header("Say it to a real person")
    st.write("Pick who you'd like to talk to and how much to share. ORBIT drafts a few short messages. You edit, "
             "copy and send it yourself. ORBIT never sends anything.")
    last = st.session_state.get("home_result")
    if last and last["safety"] == "crisis":
        safety.show_safety_card("crisis")
        return
    if needs_extra_care(last):
        st.info("A message to a friend is a great step, and it's okay to ask for more help too. Please talk to a "
                "trusted adult, or call a free helpline:")
        safety.show_helplines()
    who = st.radio("Who would you like to write to?", list(WHO), format_func=WHO.get, horizontal=True)
    level = st.radio("How much do you want to share?", list(LEVELS), format_func=LEVELS.get, horizontal=True)
    language = st.selectbox("Language", LANGUAGES, key="ro_lang")
    context = ""
    if level == "more":
        context = st.text_input("What's it about? (a few words, optional)", max_chars=60, placeholder="e.g. my board exams")
        if context and safety.check(context) == "crisis":
            safety.show_safety_card("crisis")
            return
    family = st.session_state.get("ro_family")
    if family in ("Sadness", "Fear", "Anger"):
        st.caption(f"Using the feeling from your last check-in: {family}")
    else:
        family = None
    feeling = FEELING_TEXT[language][family]
    about = context.strip().rstrip(".") or SOMETHING[language]
    for i, template in enumerate(TEMPLATES[language][who][level]):
        draft = template.format(f=feeling, c=about)
        draft = draft[0].upper() + draft[1:]
        with st.container(border=True):
            key = f"ro_{who}_{level}_{language}_{about}_{i}"
            edited = st.text_area(f"Version {i + 1}", value=draft, key=key, height=80)
            st.code(edited, language=None, wrap_lines=True)
            st.button("Save on this device", key=f"save_{key}", on_click=save_draft, args=(who, key))
    st.caption("To send it: copy a version (icon at the top right of the grey box) and paste it into WhatsApp, SMS "
               "or email yourself.")
    thumbs("reach_out", WHO[who], key="fb_reach_out", label="Were these drafts helpful?")
    saved = database.get_notes("reach_out")
    if saved:
        with st.expander(f"Saved drafts ({len(saved)})"):
            for item in saved:
                left, right = st.columns([5, 1])
                left.write(f"**{item['title']}** ({item['created_at'][:10]}): {plain(item['text'])}")
                right.button("Delete", key=f"ro_del_{item['id']}", on_click=database.delete_note, args=(item["id"],))


# ---------------- 5. letters ----------------

LETTER_FEELINGS = ["Hopeful", "Calm", "Happy", "Proud", "Worried", "Stressed", "Sad", "Lonely", "Angry", "Mixed"]


def let_go(kind):
    text = st.session_state.get("unsent_text", "").strip()
    if not text:
        st.session_state.letter_message = "Write something first. Even one line is enough."
        return
    st.session_state.unsent_text = ""
    if safety.check(text) == "crisis":
        st.session_state.letter_crisis = True
        return
    if st.session_state.get("unsent_keep"):
        database.add_note("unsent_letter", st.session_state.get("unsent_to", "") or "Unsent letter", text)
    st.session_state.letter_done = kind


def seal_letter():
    text = st.session_state.get("future_text", "").strip()
    if not text:
        st.session_state.letter_message = "Write something to your future self first."
        return
    st.session_state.future_text = ""
    if safety.check(text) == "crisis":
        st.session_state.letter_crisis = True
        return
    feeling = st.session_state.get("future_feeling")
    last = st.session_state.get("home_result")
    if not feeling and last and last["safety"] != "crisis":
        feeling = f"{last['family']} (from your check-in)"
    opens = (date.today() + timedelta(days=30)).isoformat()
    database.add_note("future_letter", opens, json.dumps({"letter": text, "feeling": feeling or "not recorded"}))
    flash(f"Sealed until {opens}. It's saved only on this device.")


def letters_page():
    st.header("Words that need somewhere to go")
    st.write("Writing things down can make feelings a little lighter.")
    if st.session_state.pop("letter_crisis", False):
        safety.show_safety_card("crisis")
        return
    part = st.radio("Letter", ["A letter you'll never send", "A letter to future me"], horizontal=True,
                    label_visibility="collapsed")
    message = st.session_state.pop("letter_message", None)
    if message:
        st.info(message)

    if part == "A letter you'll never send":
        done = st.session_state.pop("letter_done", None)
        if done:
            if done == "burn":
                st.success("🔥 Let it burn. It doesn't have to stay with you.")
            else:
                st.success("🎈 Let it float away. You can breathe out now.")
            thumbs("tool", "Unsent letter", key="fb_unsent", label="Did that help a little?")
            st.button("Write another")
            return
        st.text_input("Who is it to? (optional, only you will see it)", key="unsent_to", max_chars=40)
        st.text_area("Write everything you wish you could say", key="unsent_text", height=180, placeholder="Dear ...")
        st.checkbox("Keep it, privately, on this device", key="unsent_keep")
        a, b = st.columns(2)
        a.button("Burn it", type="primary", on_click=let_go, args=("burn",))
        b.button("Let it float away", on_click=let_go, args=("float",))
        kept = database.get_notes("unsent_letter")
        if kept:
            with st.expander(f"Letters you kept ({len(kept)})"):
                for item in kept:
                    left, right = st.columns([5, 1])
                    left.write(f"**{item['title']}** ({item['created_at'][:10]}): {plain(item['text'])}")
                    right.button("Delete", key=f"del_unsent_{item['id']}", on_click=database.delete_note, args=(item["id"],))
    else:
        st.text_area("Dear future me...", key="future_text", height=160,
                     placeholder="What are you hoping for? What do you want to remember about right now?")
        st.pills("How are you feeling as you write? (optional)", LETTER_FEELINGS, key="future_feeling")
        st.button("Seal it for 30 days", type="primary", on_click=seal_letter)
        today = date.today().isoformat()
        for item in database.get_notes("future_letter"):
            if today >= item["title"]:
                data = json.loads(item["text"])
                with st.container(border=True):
                    st.caption(f"Opened. Written {item['created_at'][:10]}")
                    st.write(plain(data["letter"]))
                    st.write(f"When you wrote this, you were feeling: **{data['feeling']}**. How does it feel to read it now?")
                    st.button("Delete", key=f"del_future_{item['id']}", on_click=database.delete_note, args=(item["id"],))
            else:
                st.write(f"✉️ A sealed letter opens on {item['title']}")
    st.caption("Letters stay on this device, are included in Download my data, and are deleted by Panic wipe.")


# ---------------- 6. safety plan ----------------

PLAN = [("warning_signs", "My warning signs", "e.g. I stop replying to friends, I can't sleep"),
        ("coping", "Things I can do on my own", "e.g. go for a walk, 4-6 breathing, my calm playlist"),
        ("places", "People and places that take my mind off things", "e.g. my cousin's house, the park"),
        ("people", "People I can ask for help", "e.g. Mum: 98xxxxxx, school counsellor: room 12"),
        ("reasons", "Things that matter to me", "e.g. my little sister, finishing my comic")]


def load_plan():
    try:
        return json.loads(database.get_setting("safety_plan", "{}"))
    except ValueError:
        return {}


def save_plan():
    plan = {key: st.session_state.get(f"plan_{key}", "").strip() for key, _, _ in PLAN}
    database.set_setting("safety_plan", json.dumps(plan, ensure_ascii=False))
    st.session_state.plan_editing = False
    flash("Your safety plan is saved on this device.")


def safety_plan_page():
    st.header("A plan for hard moments")
    st.write("Fill this in while you feel okay, so it's ready when things feel hard. It's private and stays on this device.")
    plan = load_plan()
    if st.session_state.get("plan_editing") or not any(plan.values()):
        for key, title, example in PLAN:
            st.text_area(title, value=plan.get(key, ""), key=f"plan_{key}", height=80, placeholder=example)
        st.button("Save my plan", type="primary", on_click=save_plan)
    else:
        for i, (key, title, _) in enumerate(PLAN, 1):
            st.write(f"**{i}. {title}**")
            st.write(plain(plan.get(key) or "Not filled in yet"))
        st.write("**6. If I need help now**")
        safety.show_helplines()
        text = "MY SAFETY PLAN (from ORBIT)\n\n"
        for key, title, _ in PLAN:
            text += title.upper() + "\n" + (plan.get(key) or "-") + "\n\n"
        text += "HELPLINES\n" + "\n".join(f"{n}: {num}" for n, num, _ in safety.HELPLINES)
        a, b = st.columns(2)
        a.button("Edit my plan", on_click=lambda: st.session_state.update(plan_editing=True))
        b.download_button("Download as text", text, "my_safety_plan.txt", "text/plain")
    st.caption("A safety plan is a tool, not a treatment. Sharing it with a trusted adult can make it stronger. "
               "In an emergency, call 112.")


# ---------------- 7. mood lab ----------------

def mood_lab_page():
    st.header("Put a feeling into words")
    st.write("A deeper look: all the strongest feelings, the words that caused them, and the world that matches best.")
    with st.expander("How the lab works"):
        st.write("1. **Describe** how you feel.  \n2. **Translate** Hinglish and Hindi words into English.  \n"
                 "3. **Detect** 28 emotions with a pre-trained RoBERTa model (GoEmotions).  \n"
                 "4. **Decide** the main feeling with ORBIT's own classifier.  \n"
                 "5. **Explain** which words mattered most.  \n6. **Match** the closest world from worlds.csv.")
    st.text_area("Mood description", key="lab_text", height=140,
                 placeholder="e.g. I'm excited about the trip but nervous about meeting new people...")
    if st.button("Analyse my mood", type="primary"):
        result = ai.analyse(st.session_state.lab_text.strip())
        if result:
            set_world(result)
            record_checkin(result, "Mood Lab")
        st.session_state.lab_result = result
    result = st.session_state.get("lab_result")
    if not result:
        return
    if result["safety"]:
        safety.show_safety_card(result["safety"])
    if result["safety"] == "crisis":
        return
    st.write("**What the lab received:** " + plain(result["text"][:280]))
    emotion_summary(result)
    st.write("**The base model's five strongest scores**")
    emotion_chart(result["emotions"])
    st.caption("The bars are RoBERTa's own scores (each 0-100%, so they don't add up to 100). ORBIT's classifier "
               "then decides the main feeling, which can differ: a racing heart before a presentation scores high "
               "on excitement, but usually means nerves.")
    clarify(result, "lab_clarify")
    teach_box(result, "lab_teach")
    st.subheader(f"Why does ORBIT think this is {result['emotion']}?")
    if st.toggle("Explain this result (takes a few seconds)", key="lab_why"):
        ai.show_why(result)
    st.subheader("Suggested world")
    world = ai.get_world(result["world"])
    show_world(world)
    st.write("**Matched on:** " + ", ".join(result["matched"]))
    st.button("Save to collection", type="primary", on_click=save_world,
              args=(world["name"], "Mood Lab", "Explore", world["prompt_explore"], result["text"][:160]))


# ---------------- 8. soundspace ----------------

def soundspace_page():
    st.header("Music for the world you're in")
    st.write("Listening vibes that match each world. Press play to hear a calm soundscape that ORBIT makes itself "
             "with maths (sine waves and filtered noise), so it works offline.")
    playing = st.session_state.get("now_playing")
    if playing:
        space = next(s for s in SOUNDSPACES if s["name"] == playing)
        st.success(f"Now playing: {playing}. Close your eyes and breathe slowly.")
        st.audio(soundscape(space["sound"]), format="audio/wav", loop=True, autoplay=True)
        st.button("Stop", on_click=lambda: st.session_state.update(now_playing=None))
    mood = st.pills("Filter by mood", ["Calm", "Reflective", "Hopeful", "Nostalgic", "Focused", "Restless"])
    spaces = [s for s in SOUNDSPACES if mood is None or mood in s["moods"]]
    cols = st.columns(3)
    for i, space in enumerate(spaces):
        with cols[i % 3]:
            with st.container(border=True):
                st.subheader(space["name"])
                st.caption(space["genres"])
                st.write(f"**Moods:** {', '.join(space['moods'])}  \n**Tempo:** {space['tempo']}  \n"
                         f"**Pairs with:** {space['pairs_with']}  \n**Best for:** {space['best_for']}")
                st.button("Playing" if playing == space["name"] else "Play soundscape", key=f"play_{i}",
                          on_click=lambda n=space["name"]: st.session_state.update(now_playing=n))


# ---------------- 9. arcade (aesthetic vending machine) ----------------

CODES = ["A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3"]


def arcade_say(text):
    st.session_state.vm_message = text


def insert_token():
    s = st.session_state
    if s.vm_credit:
        return arcade_say("Credit already in.")
    if s.tokens <= 0:
        return arcade_say("No tokens left.")
    s.tokens -= 1
    s.vm_credit = True
    s.vm_pack = None
    arcade_say("Token in. Choose a capsule.")


def return_token():
    s = st.session_state
    if s.vm_credit:
        s.tokens += 1
        s.vm_credit = False
        arcade_say("Token returned.")


def vend():
    s = st.session_state
    code = s.get("vm_code")
    if not s.vm_credit:
        return arcade_say("Insert a token first.")
    if code in s.vm_sold:
        return arcade_say(f"{code} is sold out.")
    worlds = ai.load_worlds()
    world = random.choice(worlds)
    while s.vm_pack and world["name"] == s.vm_pack["world"]:
        world = random.choice(worlds)
    s.vm_pack = {"world": world["name"], "intent": random.choice(INTENTS), "constraint": random.choice(CONSTRAINTS),
                 "slot": code}
    s.vm_sold.append(code)
    s.vm_credit = False
    arcade_say(f"Capsule {code} dropped!")


def arcade_page():
    s = st.session_state
    st.header("Insert a token. Pick a capsule. Catch a world.")
    st.write("Every capsule hides a world, a creative prompt and a small challenge. Tokens are earned by looking "
             "after yourself: each check-in or Calm Room session adds one.")
    a, b, c = st.columns(3)
    a.metric("Your tokens", s.tokens)
    b.metric("Credit", "1" if s.vm_credit else "0")
    c.metric("Sold out", f"{len(s.vm_sold)} of 9")
    if s.vm_message:
        st.info(s.vm_message)
        s.vm_message = None
    a, b = st.columns(2)
    a.button("Insert token", type="primary", on_click=insert_token)
    b.button("Return token", on_click=return_token)
    available = [code for code in CODES if code not in s.vm_sold]
    if available:
        st.radio("Choose a capsule", available, horizontal=True, key="vm_code")
        st.button("Vend", on_click=vend)
    else:
        st.write("Everything is sold out.")
    st.button("Call the restocker", on_click=lambda: s.update(vm_sold=[], vm_message="Restocked!"))
    if s.tokens <= 0 and not s.vm_credit:
        st.caption("Out of tokens? Check in, talk to ORBIT or try a Calm Room exercise to earn more.")
    pack = s.vm_pack
    if pack:
        world = ai.get_world(pack["world"])
        prompt = ai.prompt_for(world, pack["intent"])
        with st.container(border=True):
            st.caption(f"Capsule {pack['slot']}: creative pack")
            show_world(world, prompt, pack["intent"])
            st.write(f"**Constraint:** {pack['constraint']}")
            st.button("Save to collection", on_click=save_world,
                      args=(world["name"], "Arcade", pack["intent"], prompt, "", pack["constraint"]))

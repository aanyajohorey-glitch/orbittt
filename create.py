# Create tab: Creative universe (Creator Mode + Spark) and Quick palette & music.
# Crisis words typed here -> only the safety card is shown and nothing is made or kept.

import colorsys
import copy
import random
import zlib
from datetime import date, datetime
from urllib.parse import quote_plus

import streamlit as st

import ai
import creative
import database
import replies
import safety
from feel import play_game, GAMES
from helpers import flash, safe, stars, save_count, swatches, thumbs

AUDIENCES = ["Friends", "Teenagers", "Kids", "Everyone", "A client"]
START_FROM = ["A feeling", "A colour", "A song", "A word"]
PARTS = {"concept": "Concept", "palette": "Palette", "fonts": "Typography", "moodboard": "Moodboard",
         "aesthetics": "Aesthetics", "music": "Music", "creators": "Creators"}


def is_crisis(*texts):
    for t in texts:
        if t and safety.check(t) == "crisis":
            return True
    return False


def block():
    st.session_state.create_blocked = True
    for key in ("create_text", "create_song", "create_word", "spark_word", "cu_feel"):
        st.session_state.pop(key, None)
    st.session_state.creative = None
    st.session_state.world = None


def read_emotions(text):
    try:
        return ai.interpret(text)
    except Exception:
        st.session_state.model_failed = True
        return ai.interpret(text)


def colour_to_vibe(hex_colour):
    r, g, b = (int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    hue = h * 360
    if hue < 70 or hue > 330:
        warmth = 1.0
    elif 170 < hue < 260:
        warmth = -1.0
    else:
        warmth = 0.2
    return {"warmth": round(warmth * s, 3), "brightness": round(creative.clamp((l - 0.5) * 2), 3),
            "bold": round(creative.clamp((s - 0.4) * 2), 3)}


# ---------------- versions ----------------

def generate(vector, discovery=0.5, label="New idea"):
    current = st.session_state.get("creative")
    locks = st.session_state.get("locks", set())
    old = current["universe"] if current else None
    universe = creative.make_universe(vector, discovery, locks, old)
    history = []
    if current:
        history = [{"label": current["label"], "time": current["time"], "universe": current["universe"]}]
        history = (history + current["history"])[:10]
    st.session_state.creative = {"universe": universe, "label": label, "history": history,
                                 "time": datetime.now().strftime("%H:%M:%S")}
    set_vibe_world(universe)


def set_vibe_world(universe):
    st.session_state.world = "vibe:" + universe["concept"]["title"]
    st.session_state.vibe_colours = [c["hex"] for c in universe["palette"]["colours"][:3]]


def restore(index):
    current = st.session_state.creative
    old = current["history"][index]
    history = [{"label": current["label"], "time": current["time"], "universe": current["universe"]}]
    history += [h for i, h in enumerate(current["history"]) if i != index]
    st.session_state.creative = {"universe": old["universe"], "label": "Restored: " + old["label"],
                                 "history": history[:10], "time": datetime.now().strftime("%H:%M:%S")}
    set_vibe_world(old["universe"])


def use_chip(chip):
    u = st.session_state.creative["universe"]
    generate(creative.refine(u["vector"], chip), u["discovery"], chip)


def use_direction(name):
    u = st.session_state.creative["universe"]
    chosen = creative.directions(u["vector"])[name]
    generate(chosen, chosen["discovery"], f"{name} direction")


def use_sliders():
    u = st.session_state.creative["universe"]
    s = st.session_state
    vector = creative.apply_sliders(u["vector"], s.cs_warm, s.cs_energy, s.cs_bold, s.cs_era, s.cs_bright)
    generate(vector, s.cs_discovery, "Fine-tuned")


def new_idea():
    st.session_state.creative = None
    st.session_state.create_pending = None
    st.session_state.locks = set()


def polish():
    u = copy.deepcopy(st.session_state.creative["universe"])
    better = replies.polish(u["concept"]["vision"])
    if better:
        u["concept"]["vision"] = better
        u["concept"]["polished"] = True
        st.session_state.creative["universe"] = u
    else:
        flash("The AI wasn't available, so the template version stays.")


# ---------------- 1. entry ----------------

def build_from_input():
    s = st.session_state
    text = s.get("create_text", "").strip()
    start = s.get("create_start")
    song, word = s.get("create_song", ""), s.get("create_word", "")
    if is_crisis(text, song, word):
        block()
        return
    full = " ".join(x for x in (text, song, word) if x).strip()
    if not full and not (start == "A feeling" and s.get("create_feeling")) and start != "A colour":
        s.create_message = "Write a few words about your idea first, or try \"I don't have an idea yet\"."
        return
    result = read_emotions(full or "a new creative idea")
    emotions = result["emotions"]
    if start == "A feeling" and s.get("create_feeling"):
        chosen = [creative.FEELINGS[f] for f in s.create_feeling[:2]]
        emotions = [(e[2], 1.0 / len(chosen)) for e in chosen] + [(l, sc * 0.3) for l, sc in emotions[:3]]
    vector = creative.build_vector(full or "a new creative idea", emotions, s.get("create_medium"),
                                   s.get("create_audience"), result["model_text"])
    if start == "A colour" and s.get("create_colour"):
        vector.update(colour_to_vibe(s.create_colour))
    vector["result"] = {"text": result["text"], "model_text": result["model_text"], "emotion": result["emotion"]}
    vector["concern"] = result["safety"] == "concern"
    s.create_offer = creative.break_offer(full)
    words = creative.words_in(result["model_text"] or full)
    if not vector["medium"]:
        for w in words:
            if w in creative.MEDIUM_HINTS:
                vector["medium"] = creative.MEDIUM_HINTS[w]
                break

    questions = []
    if not vector["medium"]:
        questions.append("medium")
    if result["unsure"] or emotions[0][0] == "neutral":
        questions.append("feeling")
    if not any(w in creative.ERA_WORDS for w in words):
        questions.append("era")
    s.create_pending = {"vector": vector, "questions": questions}
    if not questions:
        finish_questions(skip=True)


def entry_screen():
    st.header("What are you making, or what's on your mind?")
    st.write("Type an idea in English, Hinglish or Hindi. ORBIT turns it into a whole creative universe: concept, "
             "palette, fonts, moodboard, aesthetics, music and creators to discover.")
    st.text_area("Your idea", key="create_text", height=130,
                 placeholder="e.g. a short film about a rainy Sunday cafe in Mumbai, nostalgic and warm")
    st.pills("Medium (optional)", creative.MEDIUMS, key="create_medium")
    st.pills("Audience (optional)", AUDIENCES, key="create_audience")
    start = st.pills("Start from (optional)", START_FROM, key="create_start")
    if start == "A feeling":
        st.pills("Which feeling? (up to 2)", list(creative.FEELINGS), selection_mode="multi", key="create_feeling")
    elif start == "A colour":
        st.color_picker("Pick a colour", "#C9B9E8", key="create_colour")
    elif start == "A song":
        st.text_input("A song title (just the name)", key="create_song", max_chars=80)
    elif start == "A word":
        st.text_input("One word", key="create_word", max_chars=30)
    a, b = st.columns(2)
    a.button("Build my universe", type="primary", on_click=build_from_input, width="stretch")
    b.button("I don't have an idea yet", on_click=start_spark, width="stretch")
    message = st.session_state.pop("create_message", None)
    if message:
        st.warning(message)
    st.caption("Nothing you type here is saved unless you download it.")


# ---------------- 2. quick questions ----------------

def finish_questions(skip=False):
    s = st.session_state
    vector = s.create_pending["vector"]
    if not skip:
        if s.get("cq_medium"):
            vector["medium"] = s.cq_medium
        if s.get("cq_feeling"):
            chosen = [creative.FEELINGS[f] for f in s.cq_feeling[:2]]
            vector["valence"] = round(sum(e[0] for e in chosen) / len(chosen), 3)
            vector["arousal"] = round(sum(e[1] for e in chosen) / len(chosen), 3)
            vector["emotions"] = [(e[2], 1.0 / len(chosen)) for e in chosen] + vector["emotions"][:3]
        if s.get("cq_era"):
            vector["era"] = creative.ERAS[s.cq_era]
    s.create_pending = None
    generate(vector, 0.5, "First version")


def questions_screen():
    pending = st.session_state.create_pending
    st.header("A couple of quick taps")
    st.write("Optional: they help ORBIT get the vibe right.")
    if "medium" in pending["questions"]:
        st.pills("What is it?", creative.MEDIUMS, key="cq_medium")
    if "feeling" in pending["questions"]:
        st.pills("Which feeling should it have? (up to 2)", list(creative.FEELINGS), selection_mode="multi", key="cq_feeling")
    if "era" in pending["questions"]:
        st.pills("When does it live?", list(creative.ERAS), key="cq_era")
    a, b = st.columns(2)
    a.button("Continue", type="primary", on_click=finish_questions, width="stretch")
    b.button("Skip", on_click=finish_questions, args=(True,), width="stretch")


# ---------------- short break (Create -> Feel) ----------------

def take_break(kind, game=None, block_name=None):
    st.session_state.create_break = {"kind": kind, "game": game, "block": block_name}
    st.session_state.create_offer = None


def project_check_in():
    text = st.session_state.get("cu_feel", "").strip()
    if not text:
        return
    if is_crisis(text):
        block()
        return
    st.session_state.cu_feel = ""
    offer = creative.break_offer(text)
    if offer:
        st.session_state.create_offer = offer
    else:
        flash("Sounds like it's going okay. Keep going!")


def offer_box(offer):
    with st.container(border=True):
        what = f"a bit of **{offer['block'].lower()}**" if offer["block"] else "some stress"
        st.write(f"**A short break?** It sounds like there might be {what} in the way. That's normal in creative "
                 "work. Your project will be right here when you come back.")
        cols = st.columns(4 if offer["block"] else 3)
        cols[0].button("2-minute breather", on_click=take_break, args=("game", "orb_flow"))
        cols[1].button(f"Play {GAMES[offer['game']][0]}", on_click=take_break, args=("game", offer["game"]))
        if offer["block"]:
            cols[2].button(f"{offer['block']} exercise", on_click=take_break, args=("exercise", None, offer["block"]))
        cols[-1].button("No thanks", on_click=lambda: st.session_state.update(create_offer=None))


def break_screen(pause):
    if pause["kind"] == "game":
        title = GAMES[pause["game"]][0]
        st.header(f"A short break: {title}")
        play_game(pause["game"])
    else:
        title = f"{pause['block']}: a 5-minute exercise"
        st.header(title)
        st.info(creative.BLOCKS[pause["block"]]["exercise"])
        st.write("No need to show anyone. When the five minutes are up, come back.")
    thumbs("tool", f"Create break: {title}", key=f"fb_break_{title}", label="Did the break help?")
    st.button("Back to my project", type="primary", on_click=lambda: st.session_state.update(create_break=None))


# ---------------- 3. the universe ----------------

def lock(part):
    locks = st.session_state.setdefault("locks", set())
    key = f"lock_{part}"

    def flip():
        if st.session_state[key]:
            locks.add(part)
        else:
            locks.discard(part)

    st.toggle(f"Lock {PARTS[part].lower()}", key=key, value=part in locks, on_change=flip,
              help="A locked part stays the same when you refine.")


def universe_screen():
    data = st.session_state.creative
    u = data["universe"]
    v, concept, fonts = u["vector"], u["concept"], u["fonts"]
    st.markdown(creative.google_fonts(fonts["heading"], fonts["body"]), unsafe_allow_html=True)

    st.caption(f"Your creative universe · {data['label']}" + (f" · {v['direction']}" if v.get("direction") else ""))
    st.markdown(f"<h1 style=\"font-family:'{fonts['heading']}',serif\">{safe(concept['title'])}</h1>",
                unsafe_allow_html=True)
    st.markdown(f"<p style=\"font-family:'{fonts['body']}',sans-serif;font-size:1.1rem\">{safe(concept['vision'])}</p>",
                unsafe_allow_html=True)
    if concept.get("polished"):
        st.caption("Polished with AI (checked)")
    a, b, c = st.columns(3)
    with a:
        lock("concept")
    b.button("New idea", on_click=new_idea)
    if replies.cloud_allowed() and not concept.get("polished"):
        c.button("Polish the vision with AI", on_click=polish)

    if st.session_state.get("create_offer"):
        offer_box(st.session_state.create_offer)
    a, b, c = st.columns([3, 1, 1], vertical_alignment="bottom")
    a.text_input("How's the project going?", key="cu_feel", max_chars=200,
                 placeholder="e.g. it has to be perfect and I can't start")
    b.button("Tell ORBIT", on_click=project_check_in)
    c.button("I'm stuck", on_click=lambda: st.session_state.update(create_offer=creative.break_offer("I'm stuck")))
    if v.get("concern"):
        st.info("Some of what you wrote sounds heavy. Making things can help, and so can talking: the Feel tab is "
                "here whenever you want it, and Tele-MANAS (14416) is free, any time.")

    st.subheader("Refine the vibe")
    chips = list(creative.CHIPS.items())
    for row in (chips[:3], chips[3:]):
        for col, (chip, tip) in zip(st.columns(3), row):
            col.button(chip, key=f"chip_{chip}", on_click=use_chip, args=(chip,), help=tip, width="stretch")
    with st.expander("Sliders and discovery dial"):
        left, right = st.columns(2)
        left.slider("Warm <-> Cool", -1.0, 1.0, 0.0, 0.1, key="cs_warm")
        right.slider("Calm <-> Energetic", -1.0, 1.0, 0.0, 0.1, key="cs_energy")
        left.slider("Soft <-> Bold", -1.0, 1.0, 0.0, 0.1, key="cs_bold")
        right.slider("Vintage <-> Modern", -1.0, 1.0, 0.0, 0.1, key="cs_era")
        left.slider("Dark <-> Bright", -1.0, 1.0, 0.0, 0.1, key="cs_bright")
        right.slider("Comfort zone <-> Unfamiliar", 0.0, 1.0, float(u["discovery"]), 0.1, key="cs_discovery")
        st.button("Apply", type="primary", on_click=use_sliders)

    st.subheader("Three directions")
    hints = {"Safe": "your vibe, familiar picks", "Bold": "louder, stronger, braver", "Weird": "flipped and unexpected"}
    for col, (name, option) in zip(st.columns(3), creative.directions(v).items()):
        preview = creative.make_palette(option["valence"], option["arousal"], warm=option["warmth"], bold=option["bold"],
                                        vintage=-option["era"], harmony=option["harmony"], brightness=option["brightness"])
        with col:
            with st.container(border=True):
                st.write(f"**{name}**: {hints[name]}")
                swatches([c["hex"] for c in preview["colours"]], size=24, labels=False)
                st.button(f"Use {name}", key=f"dir_{name}", on_click=use_direction, args=(name,))

    with st.container(border=True):
        st.subheader("Palette and moodboard")
        lock("palette")
        show_palette(u["palette"])
        mood = u["moodboard"]
        st.write(f"**Lighting:** {mood['lighting']}  \n**Textures:** {', '.join(mood['textures'])}  \n"
                 f"**Keywords:** {', '.join(mood['keywords'])}")
        lock("moodboard")

    with st.container(border=True):
        st.subheader("Typography")
        lock("fonts")
        st.markdown(f"<div style=\"font-family:'{fonts['heading']}',serif;font-size:2rem\">{safe(concept['title'])}</div>"
                    f"<p style=\"font-family:'{fonts['body']}',sans-serif\">{fonts['heading']} for headings and "
                    f"{fonts['body']} for text: {fonts['feel']}. Both are free Google Fonts.</p>", unsafe_allow_html=True)

    with st.container(border=True):
        st.subheader("Aesthetics to explore")
        lock("aesthetics")
        for a in u["aesthetics"]:
            st.write(f"**{a['name']}** ({a['era_label']}, {a['origin']}): {a['why']}")

    with st.container(border=True):
        st.subheader("Music to work to")
        lock("music")
        show_tracks(u["music"])

    with st.container(border=True):
        st.subheader("Creators and artists to discover")
        lock("creators")
        for c in u["creators"]:
            link = "https://www.google.com/search?q=" + quote_plus(c["name"] + " " + c["field"])
            st.write(f"**{c['name']}** ({c['field']}, {c['region']}): {c['why']} [Look them up]({link})")

    with st.expander("How this was made"):
        st.write("Every part is made from these numbers (the vibe vector):")
        keys = ["valence", "arousal", "brightness", "warmth", "era", "texture", "bold"]
        rows = [{"Part": k, "Value": round(v[key], 2), "Means": word}
                for (k, word), key in zip(creative.describe(v).items(), keys)]
        st.table(rows)
        st.write("Words ORBIT understood: " + (", ".join(v["themes"]) or "none"))
        st.write("Emotions: " + ", ".join(f"{l} {s:.0%}" for l, s in v["emotions"][:4]))
        p = u["palette"]
        st.write(f"**Palette:** the feeling's angle on the mood circle gives hue {p['hue']}°, energy gives "
                 f"saturation {p['saturation']}, light gives lightness {p['lightness']}. Harmony rule: {p['rule']}. "
                 "The text colour is darkened until it passes WCAG AA.")
        st.write(f"**Typography:** {fonts['why']}")
        st.write(f"**Aesthetics, music and creators:** cosine similarity with the vibe vector plus shared tags, then "
                 f"Maximal Marginal Relevance so the list stays varied. Discovery dial: {u['discovery']:.1f}.")
        if v.get("result") and not ai.offline_mode():
            st.write("**Which words drove the emotion reading:**")
            ai.show_why(v["result"])

    rate_universe(u)

    st.subheader("Export")
    name = f"orbit_brief_{date.today()}"
    a, b, c, d = st.columns(4)
    a.download_button("Brief (PDF)", creative.brief_pdf(u), f"{name}.pdf", "application/pdf")
    b.download_button("Moodboard (PNG)", creative.moodboard_png(u["palette"], fonts, u["moodboard"]["keywords"]),
                      f"{name}.png", "image/png")
    c.download_button("Palette (CSS)", creative.palette_css(u["palette"]), f"{name}.css", "text/css")
    d.download_button("Palette (JSON)", creative.palette_json(u["palette"], fonts, {"title": concept["title"]}),
                      f"{name}.json", "application/json")

    if data["history"]:
        with st.expander(f"Version history ({len(data['history'])})"):
            for i, item in enumerate(data["history"]):
                left, right = st.columns([4, 1])
                left.write(f"**{item['universe']['concept']['title']}** ({item['label']}, {item['time']})")
                right.button("Restore", key=f"restore_{i}", on_click=restore, args=(i,))


def rate_universe(u):
    sig = (u["concept"]["title"] + st.session_state.creative["time"]).replace(" ", "_")
    target = u["vector"].get("direction", "Default")
    st.subheader("Rate this universe")
    a, b, c = st.columns(3)
    with a:
        stars("creative_palette", target, f"fb_pal_{sig}", "Does the palette fit your idea?")
    with b:
        stars("creative_cohesion", target, f"fb_coh_{sig}", "Does it all feel like one world?")
    with c:
        stars("creative_music", target, f"fb_mus_{sig}", "Does the music fit the project?")
    titles = [t["title"] for t in u["music"]]
    st.pills("Tracks that fit your project", titles, selection_mode="multi", key=f"fb_p8_{sig}",
             on_change=save_count, args=("music_p_at_k", str(len(titles)), f"fb_p8_{sig}"))
    st.pills("Tracks that are new to you", titles, selection_mode="multi", key=f"fb_n8_{sig}",
             on_change=save_count, args=("music_novel_k", str(len(titles)), f"fb_n8_{sig}"))
    names = [c["name"] for c in u["creators"]]
    st.pills("Creators worth looking up", names, selection_mode="multi", key=f"fb_c6_{sig}",
             on_change=save_count, args=("creators_p_at_k", str(len(names)), f"fb_c6_{sig}"))


def show_palette(palette):
    swatches([c["hex"] for c in palette["colours"]], size=60)
    st.write(" · ".join(f"**{c['role']}**: {c['name']}" for c in palette["colours"]))
    rows = []
    for c in palette["checks"]:
        rows.append({"Pair": c["pair"], "Contrast": f"{c['ratio']} : 1", "Needs": c["needed"],
                     "Result": "Pass" if c["passes"] else "Decoration only"})
    st.table(rows)


def show_tracks(tracks):
    for i, t in enumerate(tracks, 1):
        st.write(f"{i}. **{t['title']}** by {t['artist']} ({t['language']}, {t['genre']})  \n"
                 f"{t['reason']} [Spotify]({t['spotify']}) · [YouTube]({t['youtube']})")


# ---------------- spark ----------------

SPARK_STEPS = ["Medium", "Feeling", "Setting", "Era", "Contrast", "Texture", "One word"]
SPARK_KEYS = ["medium", "emotions", "setting", "era", "contrast", "texture", None]
SPARK_QUESTIONS = ["What are you making?", "Which feeling should it have? (up to 2)", "Where does it happen?",
                   "When is it set?", "Pick a contrast", "What texture does it have?", "Anything else? (optional)"]


def start_spark():
    st.session_state.spark_step = 1
    st.session_state.spark_answers = {}
    st.session_state.spark_ideas = None


def spark_options(step):
    if step == 1:
        return creative.MEDIUMS
    if step == 2:
        return list(creative.FEELINGS)
    if step == 4:
        return list(creative.ERAS)
    kind = {3: "setting", 5: "contrast", 6: "texture"}[step]
    return [s["text"] for s in creative.seeds(kind)]


def spark_answer(step, value):
    st.session_state.spark_answers[SPARK_KEYS[step - 1]] = value
    st.session_state.spark_step = step + 1


def spark_pick(step):
    value = st.session_state.get(f"spark_pick_{step}")
    if value:
        spark_answer(step, list(value)[:2] if step == 2 else value)


def spark_surprise(step):
    choice = random.choice(spark_options(step))
    spark_answer(step, [choice] if step == 2 else choice)


def spark_skip(step):
    st.session_state.spark_answers.pop(SPARK_KEYS[step - 1], None)
    st.session_state.spark_step = step + 1


def spark_finish():
    word = st.session_state.get("spark_word", "").strip()
    if is_crisis(word):
        block()
        st.session_state.spark_step = None
        return
    answers = st.session_state.spark_answers
    if word:
        answers["word"] = word
    if st.session_state.get("spark_now"):
        answers["feeling_now"] = st.session_state.spark_now
    st.session_state.spark_seed = 0
    st.session_state.spark_ideas = creative.three_ideas(answers)
    st.session_state.spark_step = 8


def spark_change(index, keep_only):
    idea = st.session_state.spark_ideas[index]
    part = st.session_state.get(f"spark_part_{index}", "setting")
    st.session_state.spark_seed += 1
    st.session_state.spark_ideas[index] = creative.remix_idea(idea, part, st.session_state.spark_answers,
                                                              st.session_state.spark_seed, keep_only)


def spark_use(index):
    idea = st.session_state.spark_ideas[index]
    st.session_state.spark_step = None
    discovery = {"Safe": 0.3, "Bold": 0.6, "Weird": 0.9}[idea["direction"]]
    generate(creative.idea_to_vector(idea, st.session_state.spark_answers), discovery,
             f"Spark idea: {idea['direction']}")


def spark_screen():
    step = st.session_state.spark_step
    if step >= 8 and st.session_state.get("spark_ideas"):
        st.header("Three ideas for you")
        st.write("Use one, remix one part, or keep one part and change the rest.")
        if creative.heavy_answers(st.session_state.spark_answers):
            st.info("Some of what you picked sounds heavy. That can make powerful work. If it's also how you feel "
                    "right now, the Feel tab is here for you too.")
        for i, idea in enumerate(st.session_state.spark_ideas):
            with st.container(border=True):
                st.caption(f"{idea['direction']} · {idea['medium']}")
                st.subheader(idea["title"])
                st.write(idea["logline"])
                st.write(f"*Why this idea:* {idea['why']}")
                a, b, c, d = st.columns(4, vertical_alignment="bottom")
                a.button("Use this idea", key=f"spark_use_{i}", type="primary", on_click=spark_use, args=(i,))
                b.selectbox("Part", creative.SPARK_PARTS, index=1, key=f"spark_part_{i}")
                c.button("Remix", key=f"spark_remix_{i}", on_click=spark_change, args=(i, False),
                         help="Change only this part")
                d.button("Keep only this", key=f"spark_lock_{i}", on_click=spark_change, args=(i, True),
                         help="Keep this part and change the rest")
                left, right = st.columns(2)
                with left:
                    stars("idea_make", idea["direction"], f"fb_make_{i}_{idea['title']}", "Would you actually make this?")
                with right:
                    stars("idea_match", idea["direction"], f"fb_match_{i}_{idea['title']}", "Does it match your answers?")
        a, b = st.columns(2)
        a.button("Answer again", on_click=start_spark)
        b.button("Back to Create", on_click=lambda: st.session_state.update(spark_step=None))
        return

    step = min(step, 7)
    st.header("Let's find a spark")
    st.progress(step / 7, text=f"Step {step} of 7: {SPARK_STEPS[step - 1]}")
    st.subheader(SPARK_QUESTIONS[step - 1])
    if step == 7:
        st.text_input("One word on your mind (optional)", key="spark_word", max_chars=30)
        st.pills("How are you feeling right now? (optional)", ["Great", "Good", "Okay", "Low", "Very low"], key="spark_now")
        st.button("Show me three ideas", type="primary", on_click=spark_finish)
    elif step == 2:
        st.pills("Feelings", spark_options(2), selection_mode="multi", key="spark_pick_2", label_visibility="collapsed")
        st.button("Next", type="primary", on_click=spark_pick, args=(2,))
    else:
        st.radio("Options", spark_options(step), index=None, key=f"spark_pick_{step}", label_visibility="collapsed",
                 on_change=spark_pick, args=(step,))
    if step != 7:
        a, b, c = st.columns(3)
        a.button("Surprise me", on_click=spark_surprise, args=(step,))
        b.button("Skip", on_click=spark_skip, args=(step,))
        if step > 1:
            c.button("Back", on_click=lambda: st.session_state.update(spark_step=step - 1))
    st.button("Back to Create", key="spark_leave", on_click=lambda: st.session_state.update(spark_step=None))


def create_page():
    if st.session_state.get("create_blocked"):
        safety.show_safety_card("crisis")
        if st.button("I'm okay, go back to Create"):
            st.session_state.create_blocked = False
            st.rerun()
        return
    if st.session_state.get("create_break"):
        break_screen(st.session_state.create_break)
    elif st.session_state.get("spark_step"):
        spark_screen()
    elif st.session_state.get("create_pending"):
        questions_screen()
    elif st.session_state.get("creative"):
        universe_screen()
    else:
        entry_screen()


# ---------------- quick palette & music (Mood Studio) ----------------

def studio_page():
    st.header("Your feeling, in colour and sound")
    st.write("Turn a check-in or a vibe into a palette, or find music that fits. Nothing you type here is saved.")
    last = st.session_state.get("home_result")
    if last and last["safety"] == "crisis":
        safety.show_safety_card("crisis")
        return
    part = st.radio("Studio", ["Palettes & moodboards", "Music discovery"], horizontal=True, label_visibility="collapsed")
    if part == "Music discovery":
        music_section(last)
    else:
        palette_section(last)
    st.caption("Mood Studio is for creativity and comfort. It isn't a treatment and doesn't diagnose anything.")


def palette_section(last):
    has_checkin = last is not None
    source = st.radio("Start from", ["My last check-in", "A vibe I describe"], horizontal=True,
                      index=0 if has_checkin else 1)
    vibe = ""
    if source == "A vibe I describe" or not has_checkin:
        vibe = st.text_input("Describe a vibe in a few words", max_chars=80, placeholder="e.g. rainy Sunday cafe, nostalgic")
        if vibe and safety.check(vibe) == "crisis":
            safety.show_safety_card("crisis")
            return
    a, b = st.columns(2)
    warm_cool = a.slider("Warm <-> Cool", -1.0, 1.0, 0.0, 0.1)
    calm_energy = b.slider("Calm <-> Energetic", -1.0, 1.0, 0.0, 0.1)
    soft_bold = a.slider("Soft <-> Bold", -1.0, 1.0, 0.0, 0.1)
    vintage_modern = b.slider("Vintage <-> Modern", -1.0, 1.0, 0.0, 0.1)
    harmony = st.selectbox("Colour harmony", ["Auto", "analogous", "complementary", "triadic"])

    if source == "My last check-in" and has_checkin:
        valence, arousal = ai.valence_arousal(last["emotions"])
        warm = bold = vintage = 0.0
        keywords = [label for label, _ in last["emotions"][:3]]
        target = last["emotion"]
        origin = f"your last check-in ({', '.join(keywords)})"
    elif vibe.strip():
        valence, arousal, warm, bold, vintage, found = creative.vibe_profile(vibe)
        keywords = found or ["your vibe"]
        target = "vibe"
        origin = f"the vibe words {', '.join(found)}" if found else "your vibe (no known words, so a neutral start)"
    else:
        st.info("Do a check-in, or describe a vibe above, to make a palette.")
        return

    warm, bold, vintage = warm - warm_cool, bold + soft_bold, vintage - vintage_modern
    signature = f"{source}|{vibe}|{target}"
    if st.session_state.get("studio_sig") != signature:
        st.session_state.studio_sig = signature
        st.session_state.studio_tweaks = {}
    tweaks = st.session_state.studio_tweaks
    palette = creative.make_palette(valence, arousal, warm, calm_energy, bold, vintage, tweaks,
                                    None if harmony == "Auto" else harmony)
    fonts = creative.pick_fonts(vintage, bold, palette["arousal"])
    tiles = creative.textures(palette["arousal"], vintage)
    keywords = list(dict.fromkeys(keywords + tiles))

    with st.container(border=True):
        show_palette(palette)
        st.markdown(creative.google_fonts(fonts["heading"], fonts["body"])
                    + f"<div style=\"font-family:'{fonts['heading']}',serif;font-size:1.8rem\">Every feeling has a universe</div>"
                    f"<p style=\"font-family:'{fonts['body']}',sans-serif\">{fonts['heading']} for headings, "
                    f"{fonts['body']} for text: {fonts['feel']}.</p>", unsafe_allow_html=True)
        st.write("**Textures:** " + ", ".join(tiles) + "  \n**Keywords:** " + ", ".join(keywords))

    def tweak(action):
        if action == "reset":
            st.session_state.studio_tweaks = {}
        else:
            st.session_state.studio_tweaks = creative.refine_tweaks(st.session_state.studio_tweaks, action)

    buttons = [("More muted", "muted"), ("Warmer", "warmer"), ("Cooler", "cooler"), ("More contrast", "contrast"),
               ("More playful", "playful"), ("Reset", "reset")]
    for col, (label, action) in zip(st.columns(6), buttons):
        col.button(label, key=f"refine_{action}", on_click=tweak, args=(action,))

    with st.expander("How this was made"):
        st.write(f"Started from {origin}.")
        st.write(f"1. Feeling to numbers: valence {palette['valence']:+.2f}, energy {palette['arousal']:+.2f}.")
        st.write(f"2. Numbers to colour: hue {palette['hue']}°, saturation {palette['saturation']}, "
                 f"lightness {palette['lightness']}.")
        st.write(f"3. Harmony rule: {palette['rule']}.")
        st.write("4. The text colour is darkened until it passes WCAG AA (4.5 : 1).")
        st.write(f"5. Fonts and textures are the closest match to the vibe. Refinements: {tweaks or 'none'}.")

    name = f"orbit_palette_{date.today()}"
    a, b, c = st.columns(3)
    a.download_button("Download PNG", creative.moodboard_png(palette, fonts, keywords), f"{name}.png", "image/png")
    b.download_button("CSS variables", creative.palette_css(palette), f"{name}.css", "text/css")
    c.download_button("JSON", creative.palette_json(palette, fonts, {"keywords": keywords}), f"{name}.json", "application/json")
    stars("palette_fit", target, f"fb_palette_{zlib.crc32(signature.encode())}", "Does this palette fit the vibe?")


MUSIC_FEELINGS = ["joy", "love", "gratitude", "curiosity", "neutral", "sadness", "disappointment", "nervousness",
                  "fear", "anger", "annoyance"]


def music_section(last):
    if last:
        emotions = last["emotions"][:6]
        label = last["emotion"]
        st.write(f"Using your last check-in: **{label}**")
    else:
        label = st.selectbox("How are you feeling?", MUSIC_FEELINGS, index=MUSIC_FEELINGS.index("neutral"))
        emotions = [(label, 1.0)]
    intent = st.radio("What would help?", ["match", "lift"], horizontal=True,
                      format_func={"match": "Match my mood", "lift": "Gently lift me"}.get)
    if ai.FAMILY_OF[label] in ("Sadness", "Fear", "Anger"):
        st.caption("Both are okay. Music that matches a heavy feeling can feel understood; music that lifts you a "
                   "little can help it shift.")
    discovery = st.slider("Comfort zone <-> Explore", 0.0, 1.0, 0.5, 0.1)
    mood, energy, family, tags = creative.music_target(emotions, intent)
    playlist = creative.recommend_music(mood, energy, tags, intent, discovery)
    languages = len({t["language"] for t in playlist})
    genres = len({t["genre"] for t in playlist})
    st.subheader(f"Your playlist: {len(playlist)} tracks, {languages} languages, {genres} genres")
    show_tracks(playlist)
    with st.expander("How this playlist was made"):
        st.write(f"1. Target: mood {mood:.1f}/5 and energy {energy:.1f}/5, plus the tags {', '.join(tags)}.")
        st.write("2. Every track is a vector of mood, energy and tags. Cosine similarity measures how close it is.")
        st.write(f"3. Discovery ({discovery:.1f}): towards Explore, lesser-known tracks get a small boost.")
        st.write("4. Diversity (MMR): tracks are picked one by one, avoiding the same artist, genre or language.")
    sig = zlib.crc32(f"{label}|{intent}|{discovery}".encode())
    a, b = st.columns(2)
    with a:
        stars("music_fit", label, f"fb_music_fit_{sig}", "Did this fit your mood?")
    with b:
        key = f"fb_music_new_{sig}"
        st.radio("New to you?", ["Yes", "No"], index=None, horizontal=True, key=key,
                 on_change=save_new, args=(label, key))
    st.caption("The catalogue is small (about 270 songs) and hand-labelled, so the labels are opinions. Links open "
               "a search on Spotify or YouTube.")


def save_new(target, key):
    saved = st.session_state.setdefault("rating_ids", {})
    if key in saved:
        database.delete_rating(saved.pop(key))
    answer = st.session_state.get(key)
    if answer:
        saved[key] = database.add_rating("music_new", target, 1 if answer == "Yes" else 0)

# About tab: About ORBIT, AI Lab (how well the AI works), Care & privacy, Settings.

import re
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

import ai
import database
import replies
import safety
from helpers import flash, go


def about_page():
    st.header("About ORBIT")
    st.write("ORBIT is a companion for creative people: it helps you feel okay and helps you make things. "
             "**Create** turns an idea into a creative universe. **Feel** supports wellbeing with safe check-ins, "
             "coping tools and stress-buster games. A Class 12 CBSE Artificial Intelligence project.")
    st.subheader("SDGs")
    st.write("- **SDG 3, Good Health and Well-being:** check-ins, coping tools and a safety net that points to real help.\n"
             "- **SDG 4, Quality Education:** made for students and exam stress; builds emotional vocabulary.\n"
             "- **SDG 8, Decent Work:** free creative briefs for young creators and small brands.\n"
             "- **SDG 10, Reduced Inequalities:** free, private, and understands Hinglish and Hindi.")
    st.subheader("How a check-in works")
    steps = [("Check in", "Write how you feel, in English, Hinglish or Hindi."),
             ("Detect", "RoBERTa scores 28 emotions; ORBIT's own classifier picks the main feeling and how sure it is."),
             ("Protect", "Fixed safety rules check every message first. Crisis messages get helplines only."),
             ("Reply", "The companion reflects and validates, and asks when it isn't sure."),
             ("Act", "One small exercise: breathing, grounding, a thought reframe or gratitude."),
             ("Grow", "Your check-in joins your galaxy; patterns appear over time.")]
    for i, (title, text) in enumerate(steps, 1):
        st.write(f"**{i}. {title}:** {text}")
    st.info("**What ORBIT is not:** a therapist, a doctor or a crisis service. It does not diagnose. It only reads "
            "what you type inside ORBIT.")


# ---------------- AI Lab ----------------

LANGUAGE_NAMES = {"en": "English", "english": "English", "hinglish": "Hinglish", "hindi": "Hindi"}
BODY_WORDS = re.compile(r"\b(heart\w*|chest|stomach\w*|tummy|breath\w*|shak\w*|trembl\w*|sweat\w*|hands?|legs?|"
                        r"dizzy|nause\w*|throat|fists?|head\w*|ache\w*|pulse|tense|tight|numb|butterflies|"
                        r"pounding|racing|sleep|slept|exhausted|dil|dhadak\w*|dhadkan|pasina|haath|pet|kaanp\w*)\b|"
                        r"(सांस|दिल|धड़क|पसीना|हाथ|पेट|काँप|कांप)", re.IGNORECASE)
SLANG = re.compile(r"\b(lol|lmao|ugh|omg|bro|tbh|idk|ngl|fr|yaar|bhai|bruh)\b", re.IGNORECASE)


def writing_style(text):
    if BODY_WORDS.search(text):
        return "Body-based"
    if len(text.split()) <= 4:
        return "Very short"
    if SLANG.search(text):
        return "Informal / slang"
    return "Standard"


def load_test_set(name):
    if name == "Development set":
        table = pd.read_csv(ai.DATA / "eval_set.csv").rename(columns={"expected": "family"})
    else:
        table = pd.read_csv(ai.DATA / "eval_body.csv").rename(columns={"emotion_family": "family"})
    table["language"] = table["language"].str.strip().str.lower().map(LANGUAGE_NAMES)
    table["family"] = table["family"].str.strip().str.capitalize()
    table["style"] = table["text"].map(writing_style)
    return table


@st.cache_data(show_spinner="Testing the model...")
def run_tests(name, model_time):
    table = load_test_set(name)
    head = ai.current_head()
    roberta, dictionary, live, confidence = [], [], [], []
    for text in table["text"]:
        raw = ai.scores_for(text, "raw")
        translated = ai.scores_for(text, "dict")
        roberta.append(ai.FAMILY_OF[max(raw, key=raw.get)])
        dictionary.append(ai.FAMILY_OF[max(translated, key=translated.get)])
        probs = ai.predict(head, ai.features(text, raw, translated)[None, :])[0]
        live.append(ai.FAMILIES[int(np.argmax(probs))])
        confidence.append(float(probs.max()))
    table["RoBERTa only"] = roberta
    table["RoBERTa + dictionary"] = dictionary
    table["ORBIT classifier"] = live
    table["confidence"] = confidence
    return table


def scores(truth, predicted):
    truth, predicted = list(truth), list(predicted)
    rows = []
    for fam in ai.FAMILIES:
        tp = sum(t == fam and p == fam for t, p in zip(truth, predicted))
        fp = sum(t != fam and p == fam for t, p in zip(truth, predicted))
        fn = sum(t == fam and p != fam for t, p in zip(truth, predicted))
        if tp + fn == 0:
            continue
        precision = tp / (tp + fp) if tp + fp else 0
        recall = tp / (tp + fn)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        rows.append({"Family": fam, "Sentences": tp + fn, "Precision": round(precision, 2),
                     "Recall": round(recall, 2), "F1": round(f1, 2)})
    table = pd.DataFrame(rows)
    accuracy = sum(t == p for t, p in zip(truth, predicted)) / max(1, len(truth))
    return accuracy, table["F1"].mean() if len(table) else 0, table


def model_time():
    path = database.personal_model_path()
    if not path.exists():
        path = ai.MODEL_FILE
    return path.stat().st_mtime


def ai_lab_page():
    st.header("AI Lab")
    st.write("How ORBIT's AI works, how well it works, where it fails, and whether it helps. "
             "Every number here is worked out live from the files in the data folder.")

    st.subheader("1. The data")
    train = pd.read_csv(ai.DATA / "train_augment.csv")
    a, b, c, d = st.columns(4)
    a.metric("Training sentences", len(train))
    b.metric("Development test", len(pd.read_csv(ai.DATA / "eval_set.csv")))
    c.metric("Body-feelings test", len(pd.read_csv(ai.DATA / "eval_body.csv")))
    d.metric("Safety tests", len(pd.read_csv(ai.DATA / "safety_tests.csv")))
    st.caption("All sentences were written by me. The development set results are a bit optimistic, because the "
               "dictionary was written while looking at it.")

    st.subheader("2. Three ways to read a feeling")
    name = st.radio("Test set", ["Development set", "Body-feelings set"], horizontal=True)
    table = run_tests(name, model_time())
    methods = ["RoBERTa only", "RoBERTa + dictionary", "ORBIT classifier"]
    rows = []
    for m in methods:
        acc, f1, _ = scores(table["family"], table[m])
        rows.append({"Method": m, "Accuracy": round(acc, 2), "Macro-F1": round(f1, 2)})
    st.table(rows)
    method = st.selectbox("Look closer at", methods, index=2)
    left, right = st.columns(2)
    with left:
        st.write("**Confusion matrix** (rows = correct answer, columns = ORBIT's guess)")
        grid = pd.crosstab(table["family"], table[method]).reindex(index=ai.FAMILIES, columns=ai.FAMILIES, fill_value=0)
        st.dataframe(grid)
    with right:
        st.write("**Precision, recall and F1 per family**")
        st.dataframe(scores(table["family"], table[method])[2], hide_index=True)
    wrong = table[table["family"] != table[method]]
    with st.expander(f"Sentences this method got wrong ({len(wrong)})"):
        st.dataframe(wrong[["text", "language", "family", method]], hide_index=True)

    st.subheader("3. Fairness: does it work equally well for everyone?")
    for column in ("language", "style"):
        rows = []
        for value, part in table.groupby(column):
            acc, f1, _ = scores(part["family"], part["ORBIT classifier"])
            rows.append({column.capitalize(): value, "Sentences": len(part), "Accuracy": round(acc, 2),
                         "Macro-F1": round(f1, 2)})
        st.table(rows)

    st.subheader("4. Knowing when to ask")
    sure = table[table["confidence"] >= ai.UNSURE_BELOW]
    unsure = table[table["confidence"] < ai.UNSURE_BELOW]
    a, b = st.columns(2)
    if len(sure):
        a.metric(f"Sure ({len(sure)} sentences)", f"{(sure['family'] == sure['ORBIT classifier']).mean():.0%} correct")
    if len(unsure):
        b.metric(f"Unsure ({len(unsure)} sentences)", f"{(unsure['family'] == unsure['ORBIT classifier']).mean():.0%} correct")
    st.caption(f"Below {ai.UNSURE_BELOW:.0%} confidence (or for very short or vague messages) ORBIT asks which feeling "
               "is closer instead of guessing.")

    st.subheader("5. Testing the safety net")
    tests = pd.read_csv(ai.DATA / "safety_tests.csv")
    tests["detected"] = [safety.check(t) or "none" for t in tests["text"]]
    rows = []
    for split, part in tests.groupby("split"):
        crisis = part[part["expected"] == "crisis"]
        rows.append({"Split": split, "Sentences": len(part),
                     "Crisis caught": f"{(crisis['detected'] == 'crisis').mean():.0%}" if len(crisis) else "-",
                     "All correct": f"{(part['detected'] == part['expected']).mean():.0%}"})
    st.table(rows)
    misses = tests[tests["detected"] != tests["expected"]]
    with st.expander(f"Known misses ({len(misses)})"):
        st.dataframe(misses[["text", "language", "expected", "detected", "split"]], hide_index=True)
    st.caption("The safety rules were written using only the 'dev' rows. The 'holdout' rows show how well they "
               "work on sentences they were not written for.")

    st.subheader("6. Teach ORBIT (human in the loop)")
    corrections = database.get_corrections()
    st.write(f"You have taught ORBIT **{len(corrections)}** correction(s). They stay on this device.")
    if corrections:
        with st.expander("Your corrections"):
            st.dataframe(pd.DataFrame(corrections)[["created_at", "text", "predicted", "corrected", "source"]],
                         hide_index=True)
    a, b = st.columns(2)
    if a.button("Retrain ORBIT with my corrections", type="primary", disabled=not corrections):
        with st.spinner("Training..."):
            count = ai.retrain_with_corrections()
        flash(f"ORBIT retrained with your {count} correction(s). This personal model stays on this device.")
        st.rerun()
    personal = database.personal_model_path().exists()
    if b.button("Use the shared model", disabled=not personal):
        database.personal_model_path().unlink()
        st.rerun()

    st.subheader("7. Impact study")
    sessions = database.get_wellbeing()
    if sessions:
        data = pd.DataFrame(sessions)
        data["change"] = data["after"] - data["before"]
        a, b, c = st.columns(3)
        a.metric("Sessions", len(data))
        b.metric("Average mood change", f"{data['change'].mean():+.2f}")
        c.metric("Felt better", f"{(data['change'] > 0).mean():.0%}")
        st.bar_chart(data.groupby("tool")["change"].mean(), height=220)
        st.caption("An early signal, not proof: small numbers, no control group, and people rate themselves.")
    else:
        st.info("No sessions yet. Use the Calm Room or finish a check-in to start the impact study.")
    with st.form("feedback"):
        rating = st.select_slider("How helpful is ORBIT?", options=[1, 2, 3, 4, 5], value=4,
                                  format_func={1: "Not at all", 2: "A little", 3: "Somewhat", 4: "Helpful",
                                               5: "Very helpful"}.get)
        comment = st.text_area("Anything to add? (optional, no names please)", max_chars=300)
        if st.form_submit_button("Send feedback"):
            database.add_feedback(rating, "" if safety.check(comment) == "crisis" else comment.strip())
            st.success("Thank you! Saved on this device.")
    feedback = database.get_feedback()
    if feedback:
        st.caption(f"{len(feedback)} feedback responses, average {np.mean([f['rating'] for f in feedback]):.1f} out of 5.")

    st.subheader("8. Satisfaction ratings")
    ratings = pd.DataFrame(database.get_ratings())
    if ratings.empty:
        st.info("No ratings yet. Every reply, tool and creative result has rating buttons.")
    else:
        thumbs = ratings[ratings["kind"].isin(["reply", "tool", "reach_out"])]
        if not thumbs.empty:
            st.write("**Thumbs up share**")
            summary = thumbs.groupby(["kind", "target"])["value"].agg(["mean", "count"]).reset_index()
            summary.columns = ["Kind", "What", "Thumbs up", "Ratings"]
            summary["Thumbs up"] = (summary["Thumbs up"] * 100).round().astype(int).astype(str) + "%"
            st.dataframe(summary, hide_index=True)
        star_kinds = ["palette_fit", "music_fit", "creative_palette", "creative_cohesion", "creative_music",
                      "idea_make", "idea_match"]
        rated = ratings[ratings["kind"].isin(star_kinds)]
        if not rated.empty:
            st.write("**Star ratings (1-5)**")
            summary = rated.groupby("kind")["value"].agg(["mean", "count"]).reset_index()
            summary.columns = ["Question", "Average", "Ratings"]
            summary["Average"] = summary["Average"].round(2)
            st.dataframe(summary, hide_index=True)

    st.subheader("9. Model card")
    W, b, meta = ai.current_head()
    st.write(f"- **Base model:** SamLowe/roberta-base-go_emotions-onnx (28 emotions, runs on the CPU)\n"
             f"- **ORBIT classifier:** softmax regression in numpy, {W.shape[0]} features, 7 families\n"
             f"- **Trained on:** {meta.get('train_sentences')} sentences, {meta.get('corrections', 0)} corrections\n"
             f"- **Cross-validation:** accuracy {meta.get('cv_accuracy', 0):.2f}, macro-F1 {meta.get('cv_macro_f1', 0):.2f}\n"
             f"- **Temperature scaling:** {meta.get('temperature', 1):.2f} (makes confidence more honest)\n"
             f"- **Limits:** sarcasm, very short messages, rare Hinglish spellings, and a small hand-made dataset.")


# ---------------- Care & privacy ----------------

PRINCIPLES = [
    ("Safety first", "If someone writes about suicide or self-harm, ORBIT stops and shows free helplines before "
                     "anything else. These messages are never sent to an AI model and never saved."),
    ("Always honest", "ORBIT never pretends to be a person. Every reply shows how it was written."),
    ("Private by design", "Your journal and saved worlds stay on this device. You can delete it all below."),
    ("Fair and measured", "The AI Lab shows how accurate the model is, including where it struggles."),
    ("Not a therapist", "ORBIT can help you name feelings and try coping exercises. For anything serious, please "
                        "talk to a trusted adult, a counsellor or a doctor."),
]


def delete_all():
    database.delete_everything()
    st.session_state.collection = []
    st.session_state.chat = []
    flash("All ORBIT data on this device has been deleted.")


def care_page():
    st.header("How ORBIT looks after you")
    for title, text in PRINCIPLES:
        st.write(f"**{title}:** {text}")
    st.button("Open my safety plan", on_click=go, args=("Safety plan",))
    st.subheader("Real people who can help, any time")
    safety.show_helplines()
    st.subheader("Your data")
    st.text_input("What should ORBIT call you? (optional)", value=database.get_setting("name", ""), key="care_name",
                  max_chars=30, on_change=lambda: database.set_setting("name", st.session_state.care_name.strip()))
    st.toggle("Keep a private journal of my check-ins", value=database.journal_on(), key="care_journal",
              on_change=lambda: database.set_setting("journal_on", "1" if st.session_state.care_journal else "0"))
    st.write(f"Stored on this device: {len(database.get_entries())} journal entries, "
             f"{len(database.get_worlds())} saved worlds, {len(database.get_wellbeing())} calm sessions, "
             f"{len(database.get_corrections())} corrections, {len(database.get_ratings())} ratings. "
             "Crisis messages are never stored.")
    st.button("Delete my Teach ORBIT corrections", on_click=database.delete_corrections)
    sure = st.checkbox("I understand this permanently deletes all of my ORBIT data")
    st.button("Delete all my data", disabled=not sure, on_click=delete_all)
    st.caption("To download or import your data, see Settings. ORBIT is a student project, not a medical device.")


# ---------------- Settings ----------------

def panic():
    database.delete_everything()
    if database.on_cloud() and database.db_path().exists():
        database.db_path().unlink()
    st.session_state.clear()
    st.session_state.wiped = True


def do_import():
    upload = st.session_state.get("import_file")
    if upload is None:
        return
    try:
        count = database.import_data(upload.getvalue())
        st.session_state.collection = database.get_worlds()
        flash(f"Imported {count} saved items.")
    except Exception as error:
        flash(f"That file couldn't be imported: {error}")


def save_toggle(setting, key):
    database.set_setting(setting, "1" if st.session_state[key] else "0")


def settings_page():
    st.header("Settings")
    st.subheader("Accessibility")
    st.toggle("Larger text", value=database.get_setting("large_text", "0") == "1", key="set_large",
              on_change=save_toggle, args=("large_text", "set_large"))
    st.caption("For a dark theme, use the menu at the top right -> Settings -> Theme.")

    st.subheader("Companion replies")
    modes = {"auto": "Automatic (best available)", "templates": "ORBIT templates only (nothing leaves the device)"}
    current = database.get_setting("reply_mode", "auto")
    st.radio("Who writes ORBIT's replies?", list(modes), format_func=modes.get, key="set_mode",
             index=list(modes).index(current) if current in modes else 0,
             on_change=lambda: database.set_setting("reply_mode", st.session_state.set_mode))
    if replies.api_key():
        st.toggle("I agree that my messages are sent to Anthropic's Claude to write replies", key="set_cloud",
                  value=database.get_setting("cloud_ai_consent", "0") == "1",
                  on_change=save_toggle, args=("cloud_ai_consent", "set_cloud"))
    else:
        st.caption("Cloud AI is not set up (no API key in Streamlit secrets).")
    st.write(f"Right now: **{replies.mode_label()}**")
    st.caption("Crisis messages are never sent to any AI. AI replies are checked before they're shown.")

    st.subheader("Stress-buster games")
    st.toggle("Suggest a game when I'm stressed, anxious, sad or angry", key="set_games",
              value=database.get_setting("games_opt_out", "0") != "1",
              on_change=lambda: database.set_setting("games_opt_out", "0" if st.session_state.set_games else "1"))

    st.subheader("Offline mode")
    st.toggle("Use offline mode (no emotion model needed)", key="set_demo",
              value=database.get_setting("demo_mode", "0") == "1", on_change=save_toggle, args=("demo_mode", "set_demo"))
    st.caption("For presentations without internet. It uses a smaller, less accurate model that only looks at words. "
               "ORBIT also switches to this by itself if the emotion model can't load.")

    st.subheader("Your data")
    if database.on_cloud():
        st.write("ORBIT is running online, so data is kept only for **this browser session** and deleted within 24 "
                 "hours. Download it to keep your journal, and import it next time.")
    else:
        st.write("Data is saved **only on this computer** (data/orbit.db).")
    st.download_button("Download my data (.json)", database.export_data(), f"orbit_data_{date.today()}.json",
                       "application/json")
    st.file_uploader("Import a file you downloaded before (replaces what's here now)", type=["json"], key="import_file")
    st.button("Import", on_click=do_import)
    st.button("Panic wipe: delete everything now", type="primary", key="settings_panic", on_click=panic)

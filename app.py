# ORBIT - Every feeling has a universe.
# Class 12 CBSE AI project. Run with:  streamlit run app.py

import time

import streamlit as st

import about
import create
import database
import feel
import galaxy
import safety
from helpers import PAGES, go, world_bar

st.set_page_config(page_title="ORBIT", page_icon="🪐", layout="wide")
database.setup()

defaults = {"home_result": None, "today_done": False, "lab_result": None, "chat": [], "chat_token": False,
            "tokens": 3, "flash": [], "creative": None, "create_pending": None, "create_offer": None,
            "create_break": None, "world": None, "vm_credit": False, "vm_sold": [], "vm_pack": None,
            "vm_message": None, "studio_tweaks": {}, "spark_seed": 0, "started": time.time()}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value
if "dismissed" not in st.session_state:
    st.session_state.dismissed = set()
if "collection" not in st.session_state:
    st.session_state.collection = database.get_worlds()

if database.get_setting("large_text", "0") == "1":
    st.markdown("<style>html, body, p, li, label { font-size: 1.15rem !important; }</style>", unsafe_allow_html=True)

if st.session_state.pop("wiped", False):
    st.toast("Everything was deleted from this device.")


def start():
    database.set_setting("onboarded", "1")
    if st.session_state.get("onb_name", "").strip():
        database.set_setting("name", st.session_state.onb_name.strip())
    if st.session_state.get("onb_cloud"):
        database.set_setting("cloud_ai_consent", "1")


# first visit: what ORBIT is and isn't
if database.get_setting("onboarded", "0") != "1":
    st.title("🪐 ORBIT")
    st.caption("Every feeling has a universe.")
    st.subheader("A few honest things before we begin")
    st.write("- **ORBIT is an AI, not a therapist.** It can help you name a feeling and try a small exercise. "
             "It can't diagnose anything and it is not for emergencies.")
    if database.on_cloud():
        st.write("- **What is stored:** ORBIT is online, so your data is kept only for this browser session and "
                 "deleted within 24 hours. Use Settings -> Download my data to keep it.")
    else:
        st.write("- **What is stored:** your check-ins and settings are saved only on this computer.")
    st.write("- **No personal details needed.** No account, no email. A name is optional.\n"
             "- **Under 18?** It's a good idea to let a parent, guardian or teacher know you're using ORBIT.")
    st.write("**If you ever need help right now:**")
    safety.show_helplines()
    st.text_input("What should ORBIT call you? (optional)", key="onb_name", max_chars=30)
    import replies
    if replies.api_key():
        st.checkbox("Let ORBIT send my messages to Anthropic's Claude to write warmer replies (optional)", key="onb_cloud")
    agreed = st.checkbox("I understand that ORBIT is an AI and not a replacement for real help")
    st.button("Start ORBIT", type="primary", disabled=not agreed, on_click=start)
    st.stop()

if "section" not in st.session_state:
    go("Creative universe" if database.get_setting("last_mode") == "Create" else "Check-in")

with st.sidebar:
    st.title("🪐 ORBIT")
    st.radio("Section", list(PAGES), key="section",
             on_change=lambda: st.session_state.update(page=PAGES[st.session_state.section][0]))
    st.radio("Page", PAGES[st.session_state.section], key="page")
    st.divider()
    st.write(f"Arcade tokens: **{st.session_state.tokens}**")
    st.write(f"Saved worlds: **{len(st.session_state.collection)}**")
    with st.popover("Panic wipe"):
        st.write("Deletes your journal, saved worlds, ratings and settings from this device **immediately**.")
        st.button("Delete everything now", type="primary", key="side_panic", on_click=about.panic)
    st.caption("Need help now? Tele-MANAS 14416 (free, 24/7) or 112.")

world_bar()

page_functions = {
    "Creative universe": create.create_page, "Quick palette & music": create.studio_page,
    "Check-in": feel.checkin_page, "Talk to ORBIT": feel.chat_page, "Calm Room": feel.calm_room_page,
    "Stress busters": feel.games_page, "Reach Out": feel.reach_out_page, "Letters": feel.letters_page,
    "Safety plan": feel.safety_plan_page, "Mood Lab": feel.mood_lab_page, "Soundspace": feel.soundspace_page,
    "Arcade": feel.arcade_page, "Journal": galaxy.journal_page, "Patterns": galaxy.patterns_page,
    "Saved worlds": galaxy.saved_worlds_page, "About ORBIT": about.about_page, "AI Lab": about.ai_lab_page,
    "Care & privacy": about.care_page, "Settings": about.settings_page,
}
page_functions[st.session_state.page]()

st.divider()
st.caption("ORBIT · Every feeling has a universe · Class 12 CBSE AI project · Python + Streamlit")

for message in st.session_state.flash:
    st.toast(message)
st.session_state.flash = []

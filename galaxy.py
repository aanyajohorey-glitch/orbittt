# My Galaxy tab: journal, patterns and saved worlds.
# Patterns only describe, they never diagnose.

import json
import random
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import ai
import database
from helpers import flash, go, plain, remove_world, save_world, show_world, swatches, thumbs

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
FAMILY_SCALE = alt.Scale(domain=ai.FAMILIES, range=[ai.FAMILY_COLOURS[f] for f in ai.FAMILIES])

DEMO_STORY = [
    "Pre-boards start next week and I can't stop worrying about maths.",
    "Couldn't sleep properly, my mind keeps racing about the exams.",
    "Had a fight with my brother and I'm so annoyed with everyone today.",
    "Studied for six hours, I'm exhausted but a bit proud of myself.",
    "I miss my old friends from my previous school so much.",
    "Got my chemistry practical done! Such a relief.",
    "Feeling nervous again, the physics paper is tomorrow.",
    "The physics paper went better than I expected, I'm so happy!",
    "My best friend surprised me with my favourite snacks, I love her.",
    "Kind of a normal day, nothing special happened.",
    "I wonder what I actually want to study in college.",
    "Thank you to my mom for staying up with me while I revised.",
    "Went for a walk in the evening and felt calm for the first time in weeks.",
    "Feeling hopeful about the results, whatever happens I tried my best.",
]
DEMO_SESSIONS = [("Breathing", 2, 4), ("Grounding", 2, 3), ("Thought Reframe", 1, 3), ("Breathing", 3, 4),
                 ("Gratitude Jar", 3, 5), ("Breathing", 2, 3)]


def entries_table():
    rows = []
    for e in database.get_entries():
        when = datetime.fromisoformat(e["created_at"])
        rows.append({"id": e["id"], "when": when, "date": when.date(), "weekday": WEEKDAYS[when.weekday()],
                     "source": e["source"], "text": e["text"], "primary": e["primary_emotion"],
                     "score": e["primary_score"], "family": ai.FAMILY_OF[e["primary_emotion"]],
                     "mood": ai.mood_score(e["emotions"]), "world": e["world"], "demo": e["demo"]})
    return pd.DataFrame(rows)


def load_demo():
    rng = random.Random(14)
    start = datetime.now().replace(minute=0, second=0, microsecond=0) - timedelta(days=len(DEMO_STORY) - 1)
    with st.spinner("Making a demo journal..."):
        for day, text in enumerate(DEMO_STORY):
            when = (start + timedelta(days=day)).replace(hour=rng.randint(17, 22))
            r = ai.interpret(text)
            database.add_entry("Demo", text, r["emotions"], r["world"], r["emotion"], when.isoformat(timespec="seconds"), True)
    for i, (tool, before, after) in enumerate(DEMO_SESSIONS):
        when = start + timedelta(days=i * 2 + 1, hours=20)
        database.add_wellbeing(tool, before, after, when.isoformat(timespec="seconds"), True)
    database.add_note("future_letter", (datetime.now() - timedelta(days=1)).date().isoformat(),
                      json.dumps({"letter": "Hi future me. Pre-boards are next week and I'm scared about maths. I hope "
                                  "you're proud that you kept going, whatever the marks were.",
                                  "feeling": "Worried", "demo": True}),
                      (datetime.now() - timedelta(days=31)).isoformat(timespec="seconds"))
    flash("Loaded a 14-day demo journal (marked as demo).")


def clear_demo():
    for item in database.get_notes("future_letter"):
        if '"demo": true' in item["text"]:
            database.delete_note(item["id"])
    database.run("DELETE FROM entries WHERE demo = 1")
    database.run("DELETE FROM wellbeing WHERE demo = 1")
    flash("Demo data removed.")


def insights(table, sessions):
    lines = []
    top = table["family"].value_counts()
    lines.append(f"Your most common feeling family is **{top.index[0]}** ({top.iloc[0] / len(table):.0%} of check-ins).")
    by_day = table.groupby("weekday")["mood"].mean()
    if len(by_day) >= 3:
        lines.append(f"**{by_day.idxmax()}** tends to be your brightest day and **{by_day.idxmin()}** your toughest.")
    now = datetime.now()
    recent = table[table["when"] >= now - timedelta(days=7)]["mood"]
    earlier = table[(table["when"] < now - timedelta(days=7)) & (table["when"] >= now - timedelta(days=14))]["mood"]
    if len(recent) and len(earlier):
        change = recent.mean() - earlier.mean()
        word = "brighter" if change > 0.05 else "lower" if change < -0.05 else "about the same"
        lines.append(f"This week your mood has been **{word}** than the week before ({change:+.2f}).")
    if sessions:
        gains = pd.DataFrame(sessions)
        gains["change"] = gains["after"] - gains["before"]
        best = gains.groupby("tool")["change"].mean()
        lines.append(f"Calm Room sessions lifted your mood by **{gains['change'].mean():+.1f}** points on average; "
                     f"**{best.idxmax()}** helped most.")
    streak, expected = 0, now.date()
    for day in sorted(set(table["date"]), reverse=True):
        if day == expected or (streak == 0 and day == expected - timedelta(days=1)):
            streak += 1
            expected = day - timedelta(days=1)
        else:
            break
    if streak >= 2:
        lines.append(f"You're on a **{streak}-day** check-in streak. That's real self-care.")
    return lines


def journal_page():
    st.header("Your emotional weather")
    st.write("Every check-in becomes a planet in your galaxy. Over time, patterns appear.")
    if not database.journal_on():
        st.info("Journaling is switched off, so new check-ins aren't saved. Turn it on in Care & privacy.")
    table = entries_table()
    sessions = database.get_wellbeing()
    if table.empty:
        st.info("Your galaxy is waiting. Check in, use the Mood Lab or talk to ORBIT and your planets will appear here.")
        st.button("Load a 14-day demo journal", on_click=load_demo)
        return
    has_demo = bool(table["demo"].any())
    if has_demo:
        st.caption("This journal includes demo entries for presentations.")
    a, b, c, d, e = st.columns(5)
    a.metric("Check-ins", len(table))
    b.metric("Days", table["date"].nunique())
    c.metric("Most common", table["family"].mode()[0])
    d.metric("Average mood", f"{table['mood'].mean():+.2f}")
    e.metric("Calm sessions", len(sessions))

    st.subheader("Your galaxy")
    st.caption("Each dot is a check-in. Colour = main feeling, size = how strong.")
    galaxy = alt.Chart(table.tail(42)).mark_circle(opacity=0.85).encode(
        x=alt.X("when:T", title=None), y=alt.Y("mood:Q", title="Mood", scale=alt.Scale(domain=[-1, 1])),
        size=alt.Size("score:Q", legend=None, scale=alt.Scale(range=[80, 600])),
        color=alt.Color("family:N", scale=FAMILY_SCALE, title=None), tooltip=["when", "primary", "world"])
    st.altair_chart(galaxy, width="stretch")

    st.subheader("Insights")
    for line in insights(table, sessions):
        st.write("- " + line)

    left, right = st.columns(2)
    with left:
        st.write("**Emotional weather**")
        daily = table.groupby("date", as_index=False)["mood"].mean()
        daily["date"] = pd.to_datetime(daily["date"])
        st.line_chart(daily, x="date", y="mood", height=240)
    with right:
        st.write("**Feeling families by day**")
        counts = table.groupby(["date", "family"], as_index=False).size()
        chart = alt.Chart(counts).mark_bar().encode(x=alt.X("date:T", title=None), y=alt.Y("size:Q", title="Check-ins"),
                                                    color=alt.Color("family:N", scale=FAMILY_SCALE, title=None))
        st.altair_chart(chart.properties(height=240), width="stretch")
    st.write("**By day of the week**")
    by_day = table.groupby("weekday")["mood"].mean().reindex(WEEKDAYS).dropna()
    st.bar_chart(by_day, height=200)

    with st.expander(f"All entries ({len(table)})"):
        for _, row in table.iloc[::-1].iterrows():
            left, right = st.columns([6, 1])
            left.write(f"**{row['when']:%d %b %Y, %H:%M}** · {row['source']} · {row['primary']} {row['score']:.0%} "
                       f"-> {row['world']}  \n{plain(row['text'])}")
            right.button("Delete", key=f"del_entry_{row['id']}", on_click=database.delete_entry, args=(int(row["id"]),))
    csv = table.drop(columns=["id", "demo"]).to_csv(index=False).encode("utf-8")
    a, b = st.columns(2)
    a.download_button("Download journal (CSV)", csv, "orbit_journal.csv", "text/csv")
    if has_demo:
        b.button("Remove demo data", on_click=clear_demo)
    else:
        b.button("Add demo data", on_click=load_demo)


# ---------------- patterns ----------------
# these numbers are rules of thumb I chose, not medical thresholds

RANGES = {"7 days": 7, "14 days": 14, "30 days": 30, "1 year": 365}
MIN_DAYS = {7: 3, 14: 5, 30: 7, 365: 14}


def part_of_day(hour):
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def patterns_page():
    st.header("What your check-ins show")
    st.write("Patterns we noticed in your own check-ins. They describe, they don't diagnose.")
    label = st.radio("Period", list(RANGES), index=1, horizontal=True)
    days = RANGES[label]
    table = entries_table()
    if not table.empty:
        table = table[table["when"] >= datetime.now() - timedelta(days=days)]
    have = 0 if table.empty else table["date"].nunique()
    if have < MIN_DAYS[days]:
        st.info(f"Not enough data yet. Patterns over {label} need check-ins on at least {MIN_DAYS[days]} different "
                f"days (so far: {have}). Keep checking in, or load the demo journal in My Galaxy -> Journal.")
        return
    if table["demo"].any():
        st.caption("This period includes demo entries, so the patterns are partly made up.")

    daily = table.groupby("date").agg(mood=("mood", "mean"), checkins=("mood", "size")).reset_index()
    daily["kind"] = daily["mood"].apply(lambda m: "low" if m < -0.2 else "bright" if m > 0.2 else "in-between")
    kinds = daily["kind"].value_counts()
    a, b, c, d, e = st.columns(5)
    a.metric("Check-ins", len(table))
    b.metric("Days", len(daily))
    c.metric("Bright days", kinds.get("bright", 0))
    d.metric("In-between", kinds.get("in-between", 0))
    e.metric("Low days", kinds.get("low", 0))

    left, right = st.columns(2)
    with left:
        st.write("**How often each feeling appeared**")
        st.bar_chart(table["family"].value_counts(), horizontal=True, height=240)
    with right:
        st.write("**Mood over time**")
        line = daily.copy()
        line["date"] = pd.to_datetime(line["date"])
        st.line_chart(line, x="date", y="mood", height=240)

    st.write("**Calendar** (gold = brighter, blue = lower, grey = no check-in)")
    start = datetime.now().date() - timedelta(days=days - 1)
    moods = dict(zip(daily["date"], daily["mood"]))
    cells = []
    for i in range(days):
        day = start + timedelta(days=i)
        cells.append({"date": pd.Timestamp(day), "week": (day - start + timedelta(days=start.weekday())).days // 7,
                      "weekday": WEEKDAYS[day.weekday()], "mood": moods.get(day)})
    calendar = alt.Chart(pd.DataFrame(cells)).mark_rect(stroke="white").encode(
        x=alt.X("week:O", axis=None), y=alt.Y("weekday:N", sort=WEEKDAYS, title=None),
        color=alt.condition("datum.mood === null", alt.value("#ECE7F2"),
                            alt.Color("mood:Q", scale=alt.Scale(domain=[-1, 0, 1], range=["#7F93BF", "#F1EDE6", "#CDAA78"]))),
        tooltip=["date:T", "mood:Q"])
    st.altair_chart(calendar.properties(height=180), width="stretch")

    st.subheader("A pattern we noticed")
    low = table[table["mood"] < -0.2]
    if low.empty:
        st.write("No low-mood check-ins in this period.")
    else:
        day, count = low["weekday"].value_counts().index[0], low["weekday"].value_counts().iloc[0]
        parts = low["when"].apply(lambda w: part_of_day(w.hour)).value_counts()
        st.write(f"Lower moods showed up most on **{day}** ({count} check-ins) and most often in the "
                 f"**{parts.index[0]}** ({parts.iloc[0]}). Is there something about that time that could be a little easier?")
    best = daily.sort_values("mood").iloc[-1]
    st.write(f"Your brightest day was **{best['date']:%a %d %b}**.")

    # layered suggestions when low days are frequent
    low_days = daily[daily["kind"] == "low"]
    if len(low_days) >= 3 and len(low_days) / len(daily) >= 0.4:
        st.subheader("Some things that might help")
        st.write("Low days have come up quite often in this period. That happens to everyone sometimes.")
        a, b, c = st.columns(3)
        a.button("1. A calming tool", on_click=go, args=("Calm Room",))
        b.button("1. A stress-buster game", on_click=go, args=("Stress busters",))
        c.button("2. Tell someone (Reach Out)", on_click=go, args=("Reach Out",))
        today = datetime.now().date()
        this_week = sum(1 for d in low_days["date"] if (today - d).days < 7)
        last_week = sum(1 for d in low_days["date"] if 7 <= (today - d).days < 14)
        if this_week >= 2 and last_week >= 2:
            st.warning("**3.** Because this has lasted about two weeks, it could really help to talk to a trusted "
                       "adult or a school counsellor. You can also call **Tele-MANAS on 14416** (free, any time).")
    thumbs("tool", "Pattern Insights", key=f"fb_patterns_{days}", label="Was this page useful?")
    st.caption("These patterns use ORBIT's emotion model on your own words, so they can be wrong.")


# ---------------- saved worlds ----------------

def saved_worlds_page():
    st.header("Your saved worlds")
    st.write("Every world you save from a check-in, the Mood Lab or the Arcade is kept here, on this device.")
    items = st.session_state.collection
    if not items:
        st.info("Nothing saved yet.")
        a, b = st.columns(2)
        a.button("Find my orbit", type="primary", on_click=go, args=("Check-in",))
        b.button("Open a capsule", on_click=go, args=("Arcade",))
    for item in reversed(items):
        world = ai.get_world(item["world"])
        with st.container(border=True):
            left, right = st.columns([5, 1])
            with left:
                st.write(f"**{world['name']}** · {item['source']} · {item['intent']} · {item['saved_at']}")
                swatches(world["palette"], size=24, labels=False)
            right.button("Remove", key=f"remove_{item['id']}", on_click=remove_world, args=(item["id"],))
            with st.expander("Open world"):
                show_world(world, item["prompt"], item["intent"])
                if item["constraint"]:
                    st.write(f"**Constraint:** {item['constraint']}")
                if item["note"]:
                    st.write(f"**Your words:** \"{plain(item['note'])}\"")

    st.subheader("Discover worlds")
    cols = st.columns(4)
    for i, world in enumerate(ai.load_worlds()[:4]):
        with cols[i]:
            with st.container(border=True):
                st.write(f"**{world['name']}**")
                st.caption(world["mood"])
                st.write(world["description"])
                swatches(world["palette"], size=22, labels=False)
                st.button("Save world", key=f"save_example_{i}", on_click=save_world,
                          args=(world["name"], "Example worlds", "Explore", world["prompt_explore"]))

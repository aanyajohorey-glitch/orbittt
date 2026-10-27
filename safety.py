# Safety check for ORBIT.
# "crisis"  = words about suicide or self harm -> show helplines only, save nothing
# "concern" = hopeless or very heavy words     -> keep going but remind about help
# It uses fixed word lists (no AI) so it always gives the same answer.

import re
import streamlit as st

CRISIS_PHRASES = [
    "kill myself", "killing myself", "want to die", "wanna die", "wish i was dead", "wish i were dead",
    "end my life", "ending my life", "take my life", "suicide", "suicidal", "self harm", "self-harm",
    "hurt myself", "harm myself", "cut myself", "cutting myself", "don't want to live", "dont want to live",
    "do not want to live", "no reason to live", "better off without me", "better off dead", "end it all",
    "ending it all", "kill me now", "hang myself", "overdose", "not worth living", "can't go on living",
    "cant go on living",
    "marna chahta", "marna chahti", "mar jana chahta", "mar jana chahti", "mar jaana chahta",
    "mar jaana chahti", "khudkushi", "aatmahatya", "jeena nahi chahta", "jeena nahi chahti",
    "zinda nahi rehna", "mar jaun",
    "आत्महत्या", "खुदकुशी", "मरना चाहता", "मरना चाहती", "जीना नहीं चाहता", "जीना नहीं चाहती",
]

CRISIS_PATTERNS = [
    r"\b(don'?t|do not|no longer|never)\s+want\s+to\s+(live|be alive|exist|be here)\b",
    r"\b(want|wanna|wish|going|planning|plan|thinking about|thinking of)\s+(to\s+)?(die|be dead)\b(?!\s+(of|from|laughing|for))",
    r"\b(kill|hurt|harm|cut|injure)\w*\s+myself\b",
    r"\b(end|ending|take|taking)\s+my\s+(own\s+)?life\b",
    r"\b(never|not|don'?t want to)\s+wake\s+up\b",
    r"\bbetter off\s+(without me|dead|if i\s+(was|were)n'?t\s+(here|around|alive))",
    r"\bif i\s+(was|were)n'?t\s+(here|around|alive)\b",
    r"\bwon'?t be\s+(around|here|alive)\b",
    r"\b(disappear|vanish)\s+(forever|and never come back)\b",
    r"\bgiving away my\s+(things|stuff|belongings)\b",
    r"\bgoodbye\s+(letter|note|message)s?\b",
    r"\bsuicide\s+note\b",
    r"\bno\s+(reason|point)\s+(for me\s+)?(to|in)\s+(keep going|go on|live|living|be alive)\b",
    r"\bpoint\s+(in|of)\s+living\b",
    r"\b(take|swallow|took|taking)\s+(all\s+)?(of\s+)?(my\s+|the\s+|these\s+|those\s+)?(sleeping\s+)?(pills|tablets)\b",
    r"\bjump(ing)?\s+(off|from)\s+(the\s+|a\s+)?(building|bridge|roof|terrace)\b",
    r"\b(ways|how)\s+to\s+(die|kill myself|end it)\b",
    r"\b(decided|going|planning|plan|want|wanna)\s+to\s+end\s+(things|it|everything)\b(?!\s+with)",
    r"\bcan'?t\s+do\s+(this\s+)?life\b",
    r"\bdone\s+for\s+good\b",
    r"\b(happier|better|fine)\s+without\s+me\b",
    r"\bstop(ped)?\s+existing\b",
    r"\b(pills|tablets)\b.{0,40}\bswallow|\bswallow\w*\s+(them\s+)?all\b",
    r"\b(this is|it'?s)\s+my\s+last\s+(message|goodbye|text)\b",
    r"\blife\s+(isn'?t|is not)\s+worth\b",
    r"\bi\s+want\s+out\b(?!\s+of)",
    r"\bthrow\s+myself\s+(in front of|off|under)\b",
    r"\bjeena\s+nahi\b",
    r"\bkhud\s+ko\s+(khatam|maar)",
    r"\bkhatam\s+kar\s+(dena|dunga|dungi|lunga|lungi|du|doon)\b",
    r"\bmarne\s+ka\s+(mann|man|dil)\b",
    r"\bmar\s+jaa?na\b",
    r"\bnahi\s+jee\s+(sakta|sakti|paunga|paungi)\b",
    r"\bnahi\s+rah(unga|ungi)\b",
    r"\bsabko\s+alvida\b",
    r"\bjaan\s+de\s*(dunga|dungi|doon|du|denge)\b",
    r"\bjeene\s+ka\s+(koi\s+)?matlab\s+nahi\b",
    r"मर\s*जाना",
    r"जीना\s*नहीं",
    r"जान\s*दे",
    r"जीने\s*का\s*(कोई\s*)?मतलब\s*नहीं",
    r"खुद\s*को\s*खत्म",
    r"(ज़िंदा|जिंदा)\s*नहीं",
]

# things like a film name or a school topic, not about the user
NOT_ABOUT_ME = [r"suicide\s+squad", r"suicide\s+(prevention|awareness)"]

CONCERN_PHRASES = [
    "hopeless", "worthless", "no point", "pointless", "can't do this anymore", "cant do this anymore",
    "can't take it anymore", "cant take it anymore", "nobody cares", "no one cares", "give up on everything",
    "empty inside", "hate myself", "i'm a burden", "im a burden", "trapped", "nobody would notice",
    "disappear forever", "no way out", "koi nahi samajhta", "main bekaar hoon", "sab khatam", "bojh",
    "kuch accha nahi hoga",
]

CONCERN_PATTERNS = [
    r"\bwhat'?s the point\b",
    r"\b(i'?m|i am|feel like)\s+(such\s+)?a\s+burden\b",
    r"\bnothing\s+(will|is going to)\s+ever\s+get\s+better\b",
    r"\b(feel|feeling)\s+(so\s+|completely\s+)?empty\b",
    r"\bhate\s+(everything about\s+)?my\s+life\b",
    r"\bnothing\s+matters\b",
    r"\btired\s+of\s+trying\b",
    r"\b(i'?m|i am|feel like)\s+(such\s+)?a\s+failure\b",
    r"\bkoi\s+farak\s+nahi\s+padta\b",
    r"\b(nobody|no one)\s+would\s+(even\s+)?(miss|notice|care)\b",
    r"\bcan'?t\s+get\s+out\b",
    r"\bkuch\s+(bhi\s+)?accha\s+nahi\s+lagta\b",
]

HELPLINES = [
    ("Tele-MANAS (Govt. of India)", "14416", "Free, confidential, 24/7, in many Indian languages"),
    ("Tele-MANAS toll-free", "1-800-891-4416", "Same service, another number"),
    ("Emergency", "112", "If you or someone else is in danger right now"),
]


def clean_text(text):
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"\s+", " ", text)
    for pattern in NOT_ABOUT_ME:
        text = re.sub(pattern, " ", text)
    return text


def check(text, emotions=None):
    text = clean_text(text)
    for phrase in CRISIS_PHRASES:
        if phrase in text:
            return "crisis"
    for pattern in CRISIS_PATTERNS:
        if re.search(pattern, text):
            return "crisis"
    for phrase in CONCERN_PHRASES:
        if phrase in text:
            return "concern"
    for pattern in CONCERN_PATTERNS:
        if re.search(pattern, text):
            return "concern"
    # very strong grief also counts as concern
    if emotions and dict(emotions).get("grief", 0) >= 0.4:
        return "concern"
    return None


def show_helplines():
    for name, number, detail in HELPLINES:
        st.markdown(f"**{name}:** [{number}](tel:{number.replace('-', '')}) — {detail}")


def show_safety_card(level):
    if level == "crisis":
        st.error("**You don't have to carry this alone.**\n\n"
                 "It sounds like you are going through something really painful. "
                 "Please reach out to a real person today. You can call for free, any time:")
        show_helplines()
        st.write("Please also tell a parent, teacher or friend you trust. ORBIT is an app, not a counsellor. "
                 "What you wrote here has **not** been saved.")
    else:
        st.warning("That sounds really heavy. If feelings like this keep coming back, talking to someone can help "
                   "a lot. **Tele-MANAS (14416)** is free, confidential and open 24/7, and a trusted adult can "
                   "help too.")

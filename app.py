# === CONFIG START =============================================================
import streamlit as st

st.set_page_config(page_title="Better-Ball Caddie", page_icon="⛳", layout="centered")

# Course / handicap config
HOLE_HANDICAP = [15, 9, 7, 17, 1, 13, 5, 11, 3, 16, 10, 2, 18, 8, 14, 4, 6, 12]
PAR =            [ 4, 4, 4,  3, 4,  4,  4,  3, 5,  3,  4,  4,  3, 5,  4,  4,  5,  4]

# Letter-grade scoring (more intuitive + cleaner UI)
GRADE_TO_SCORE = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
SCORE_TO_GRADE = {v: k for k, v in GRADE_TO_SCORE.items()}
GRADE_HELP = {
    "A": "Best / Perfect",
    "B": "Good / Green light",
    "C": "Playable / Average",
    "D": "Trouble / Recovery likely",
    "F": "Penalty / Unplayable",
}

SAFE_SCORE = 4   # >= B is “safe”
BAD_SCORE  = 2   # <= D is “trouble”
BAD_STREAK_THRESHOLD = 3  # 3 bad shots in a row triggers damage-control recommendations

def strokes_for(hcp: int, hole_index: int) -> int:
    """Standard stroke allocation.
    - 1 stroke on holes whose handicap rating <= hcp (1..18)
    - Extra strokes beyond 18 start again at HCP 1, then 2, etc.
    """
    rating = HOLE_HANDICAP[hole_index]  # 1..18, 1 is hardest
    strokes = 1 if hcp >= rating else 0
    extras = max(0, hcp - 18)
    if extras > 0 and rating <= extras:
        strokes += 1
    return strokes

def last(vals):
    return vals[-1] if vals else None

def bad_streak(grades: list[int]) -> int:
    """How many bad shots (<= D) in a row at the end of the sequence?"""
    s = 0
    for v in reversed(grades):
        if v <= BAD_SCORE:
            s += 1
        else:
            break
    return s
# === CONFIG END ===============================================================


# === UI START ================================================================
st.title("On-Course Better-Ball Caddie")
st.caption("Give each shot a letter grade (A/B/C/D/F). The app returns live, handicap-aware tactics for Matt and Mike.")

with st.sidebar:
    st.subheader("Round Controls")
    # Big Prev/Next controls
    cprev, cnext = st.columns([1,1])
    if "hole" not in st.session_state:
        st.session_state["hole"] = 1
    if cprev.button("◀ Prev", use_container_width=True):
        st.session_state["hole"] = max(1, st.session_state["hole"] - 1)
    if cnext.button("Next ▶", use_container_width=True):
        st.session_state["hole"] = min(18, st.session_state["hole"] + 1)

    hole = st.slider("Hole", 1, 18, st.session_state["hole"])
    st.session_state["hole"] = hole

    matt_hcp = st.number_input("Matt handicap", min_value=0, max_value=54, value=19)
    mike_hcp = st.number_input("Mike handicap", min_value=0, max_value=54, value=13)

    st.write("Grades: A=Best, B=Good, C=Playable, D=Trouble, F=Penalty")

    if st.button(f"Reset Hole {hole}", key=f"reset_{hole}", use_container_width=True):
        st.session_state[f"matt_{hole}"] = []
        st.session_state[f"mike_{hole}"] = []

# Per-hole state
if f"matt_{hole}" not in st.session_state: st.session_state[f"matt_{hole}"] = []
if f"mike_{hole}" not in st.session_state: st.session_state[f"mike_{hole}"] = []

matt_shots = st.session_state[f"matt_{hole}"]
mike_shots = st.session_state[f"mike_{hole}"]

hole_idx = hole - 1
matt_strokes = strokes_for(matt_hcp, hole_idx)
mike_strokes = strokes_for(mike_hcp, hole_idx)

# Gentle CSS to make buttons bigger and spaced
st.markdown("""
<style>
.bigbtn > div > button {padding: 18px 10px; font-size: 18px;}
.grade-grid {display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px;}
</style>
""", unsafe_allow_html=True)

# Shot entry UI: letter grades with tooltips
c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("### Matt — grade this shot")
    st.markdown('<div class="grade-grid">', unsafe_allow_html=True)
    for i, g in enumerate(["A","B","C","D","F"]):
        if st.button(g, key=f"matt_{hole}_{g}", help=GRADE_HELP[g], use_container_width=True):
            matt_shots.append(GRADE_TO_SCORE[g])
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("Matt shots:", " ".join(SCORE_TO_GRADE[s] for s in matt_shots) or "—")

with c2:
    st.markdown("### Mike — grade this shot")
    st.markdown('<div class="grade-grid">', unsafe_allow_html=True)
    for i, g in enumerate(["A","B","C","D","F"]):
        if st.button(g, key=f"mike_{hole}_{g}", help=GRADE_HELP[g], use_container_width=True):
            mike_shots.append(GRADE_TO_SCORE[g])
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("Mike shots:", " ".join(SCORE_TO_GRADE[s] for s in mike_shots) or "—")
# === UI END ==================================================================


# === LOGIC START =============================================================
def role_advice_and_rules():
    """Return (recommendation: str, rules_fired: list[str]) with explainability."""
    rules = []
    m1 = last(matt_shots)  # last score
    k1 = last(mike_shots)

    matt_bad_run = bad_streak(matt_shots)
    mike_bad_run = bad_streak(mike_shots)
    if matt_bad_run >= BAD_STREAK_THRESHOLD:
        rules.append(f"Matt bad streak: {matt_bad_run} (≥{BAD_STREAK_THRESHOLD}) → Matt should NOT attack.")
    if mike_bad_run >= BAD_STREAK_THRESHOLD:
        rules.append(f"Mike bad streak: {mike_bad_run} (≥{BAD_STREAK_THRESHOLD}) → Mike should NOT attack.")

    # No tee shots yet
    if len(matt_shots) == 0 and len(mike_shots) == 0:
        who_first = "Matt" if (mike_strokes == 0 and matt_strokes >= 1) else "Mike"
        rules.append(f"Tee order rule: strokes on hole → {who_first} tees first.")
        return (f"{who_first} tees first. First player: put a ball in play. Partner adjusts based on result.",
                rules)

    # Only one tee shot taken
    if len(matt_shots) + len(mike_shots) == 1:
        first_who = "Matt" if len(matt_shots) else "Mike"
        first_rating = m1 if len(matt_shots) else k1
        other_who = "Mike" if first_who == "Matt" else "Matt"

        if first_rating >= SAFE_SCORE:
            rules.append(f"{first_who} safe (≥B).")
            if (other_who == "Matt" and matt_bad_run >= BAD_STREAK_THRESHOLD) or \
               (other_who == "Mike" and mike_bad_run >= BAD_STREAK_THRESHOLD):
                rules.append(f"{other_who} bad streak → no attack; play controlled aggressive.")
                return (f"{first_who} is safe. {other_who}: **controlled** attack (no hero shots).",
                        rules)
            return (f"{first_who} is safe. {other_who}: ATTACK for a birdie look.",
                    rules)

        if first_rating <= BAD_SCORE:
            rules.append(f"{first_who} in trouble (≤D).")
            return (f"{first_who} is in trouble. {other_who}: ANCHOR (fairway finder; middle of green).",
                    rules)

        rules.append(f"{first_who} average (C).")
        return (f"{first_who} is average. {other_who}: medium risk; favor fairway/center green.",
                rules)

    # Both tee shots hit
    if len(matt_shots) == 1 and len(mike_shots) == 1:
        safe_balls = sum(1 for r in [m1, k1] if r is not None and r >= SAFE_SCORE)
        if safe_balls >= 1:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            partner = "Mike" if better_who == "Matt" else "Matt"
            rules.append("At least one safe tee ball.")
            if (better_who == "Matt" and matt_bad_run >= BAD_STREAK_THRESHOLD) or \
               (better_who == "Mike" and mike_bad_run >= BAD_STREAK_THRESHOLD):
                rules.append(f"{better_who} bad streak → downgrade aggression.")
                return (f"Team has a safe ball. {better_who}: **controlled** attack. {partner}: secure easy two-putt.",
                        rules)
            return (f"Team has a safe ball. {better_who}: ATTACK. {partner}: play for easy two-putt.",
                    rules)

        if (m1 or 0) <= BAD_SCORE and (k1 or 0) <= BAD_SCORE:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            rules.append("Both tee balls in trouble.")
            return (f"Both in trouble. Play from {better_who}'s better lie. Advance safely; **protect bogey** "
                    f"(often net par for Matt on stroke holes).",
                    rules)

        better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
        rules.append("Mixed tee outcomes.")
        return (f"Mixed results off tee. Favor {better_who}'s lie. Attacker aims for putt inside 15 ft.",
                rules)

    # Approaches and beyond
    matt_safe = (m1 or 0) >= SAFE_SCORE
    mike_safe = (k1 or 0) >= SAFE_SCORE

    if matt_safe and not mike_safe:
        rules.append("Matt safe; Mike not safe.")
        if mike_bad_run >= BAD_STREAK_THRESHOLD:
            rules.append("Mike bad streak → no green light.")
            return ("Matt is safe. Mike: smart, center-green target. Matt: avoid short-siding.",
                    rules)
        return ("Matt is safe. Mike: ATTACK pin if angle allows. Matt: avoid short-siding.",
                rules)

    if mike_safe and not matt_safe:
        rules.append("Mike safe; Matt not safe.")
        if matt_bad_run >= BAD_STREAK_THRESHOLD:
            rules.append("Matt bad streak → damage control.")
            return ("Mike is safe. Matt: **stop chasing par**; advance to comfy yardage; avoid hazard.",
                    rules)
        return ("Mike is safe. Matt: ATTACK with freedom. Mike: play to easy two-putt for par.",
                rules)

    if mike_safe and matt_safe:
        rules.append("Both safe.")
        return ("Both are safe. Choose the best birdie look; one goes flag-hunting, other locks in par.",
                rules)

    rules.append("No one safe yet → damage control bias.")
    return ("Neither is safe yet. Advance to comfortable yardage; prioritize bogey (often net par for Matt on stroke holes).",
            rules)


def net_targets_text() -> str:
    par = PAR[hole_idx]
    return f"Par {par}. Strokes here — Matt: {matt_strokes}, Mike: {mike_strokes}. Matt bogey often equals net {par}."

rec, rules = role_advice_and_rules()
# === LOGIC END ===============================================================


# === OUTPUT START ============================================================
st.markdown("### Live Recommendation")
st.write(rec)
st.caption(net_targets_text())

with st.expander("Why this? (explainability)"):
    st.markdown("- **Hole**: {} (Par {}, HCP {})".format(hole, PAR[hole_idx], HOLE_HANDICAP[hole_idx]))
    st.markdown("- **Matt grades**: {}".format(" ".join(SCORE_TO_GRADE[s] for s in matt_shots) or "—"))
    st.markdown("- **Mike grades**: {}".format(" ".join(SCORE_TO_GRADE[s] for s in mike_shots) or "—"))
    st.markdown("- **Rules fired**:")
    if rules:
        for r in rules:
            st.markdown(f"  - {r}")
    else:
        st.markdown("  - (none yet)")

# Bottom navigation for quick advance
bprev, bnext = st.columns([1,1])
if bprev.button("◀ Prev Hole", use_container_width=True, key=f"bprev_{hole}"):
    st.session_state["hole"] = max(1, hole - 1)
    st.rerun()
if bnext.button("Next Hole ▶", use_container_width=True, key=f"bnext_{hole}"):
    st.session_state["hole"] = min(18, hole + 1)
    st.rerun()

st.markdown("---")
st.markdown("Notes: Matt typically receives a stroke on most holes (and two on HCP 1). In a big field, net stability matters—avoid blowups when a bad streak develops.")
# === OUTPUT END ==============================================================

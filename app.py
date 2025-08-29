# === CONFIG START =============================================================
import streamlit as st
from typing import List

st.set_page_config(page_title="Better-Ball Caddie", page_icon="⛳", layout="centered")

# Course / handicap config
HOLE_HANDICAP = [15, 9, 7, 17, 1, 13, 5, 11, 3, 16, 10, 2, 18, 8, 14, 4, 6, 12]
PAR =            [ 4,  4,  4,  3, 4,  4,  4,  3, 5,  3,  4,  4,  3, 5,  4,  4,  5,  4]

# Letter-grade scoring (A best → F worst)
GRADE_TO_SCORE = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
SCORE_TO_GRADE = {v: k for k, v in GRADE_TO_SCORE.items()}
GRADE_HELP = {
    "A": "Best / Perfect",
    "B": "Good / Green light",
    "C": "Playable / Average",
    "D": "Trouble / Recovery likely",
    "F": "Penalty / Unplayable",
}

# Thresholds & overrides
SAFE_SCORE = 4            # ≥ B is “safe”
BAD_SCORE  = 2            # ≤ D is “trouble”
BAD_STREAK_THRESHOLD = 3  # 3 bad shots in a row → damage control

def strokes_for(hcp: int, hole_index: int) -> int:
    """Standard stroke allocation by hole handicap number."""
    rating = HOLE_HANDICAP[hole_index]  # 1..18 (1 hardest)
    strokes = 1 if hcp >= rating else 0
    extras  = max(0, hcp - 18)          # extra strokes beyond 18 start at HCP 1 upward
    if extras > 0 and rating <= extras:
        strokes += 1
    return strokes

def last(vals: List[int] | None):
    return vals[-1] if vals else None

def bad_streak(grades: List[int]) -> int:
    """Count how many D/F in a row at the end."""
    s = 0
    for v in reversed(grades):
        if v <= BAD_SCORE:
            s += 1
        else:
            break
    return s

# ---- Embedded per-hole strength weights (0..1; higher = stronger on that hole) ----
# Derived from your sheet’s tendencies you described:
# Matt best: 8, 17, 1  | worst: 9, 16, 5
# Mike best: 10, 3, 17 | worst: 12, 9, 14
MATT_W = [0.85, 0.55, 0.55, 0.55, 0.25, 0.40, 0.55, 0.90, 0.25,
          0.55, 0.55, 0.55, 0.55, 0.55, 0.55, 0.30, 0.85, 0.55]
MIKE_W = [0.55, 0.55, 0.85, 0.55, 0.55, 0.55, 0.55, 0.55, 0.30,
          0.90, 0.55, 0.30, 0.55, 0.30, 0.55, 0.55, 0.85, 0.55]
# === CONFIG END ===============================================================



# === SESSION STATE & HOLE INIT (must come first for mobile UI) ===
if "hole" not in st.session_state:
    st.session_state["hole"] = 1
hole = st.session_state["hole"]

hole_idx = hole - 1

# Per-hole state arrays
if f"matt_{hole}" not in st.session_state: st.session_state[f"matt_{hole}"] = []
if f"mike_{hole}" not in st.session_state: st.session_state[f"mike_{hole}"] = []
matt_shots = st.session_state[f"matt_{hole}"]
mike_shots = st.session_state[f"mike_{hole}"]

hole_idx = hole - 1

# Sidebar values (set in session state for top UI use)
matt_hcp = st.session_state.get("matt_hcp", 19)
mike_hcp = st.session_state.get("mike_hcp", 13)
day2 = st.session_state.get("day2", False)
improve_list = st.session_state.get("improve_list", [])
matt_strokes = strokes_for(matt_hcp, hole_idx)
mike_strokes = strokes_for(mike_hcp, hole_idx)

# === CORE LOGIC (must be defined before UI code) ===
def choose_attacker_candidate(m_last: int | None, k_last: int | None) -> str:
    """Pick attacker using last grades + per-hole strengths + bad streak penalty."""
    m_bad = bad_streak(matt_shots)
    k_bad = bad_streak(mike_shots)
    m_score = (m_last or 0) + MATT_W[hole_idx]*0.6 - m_bad*0.4
    k_score = (k_last or 0) + MIKE_W[hole_idx]*0.6 - k_bad*0.4
    return "Matt" if m_score >= k_score else "Mike"

def expected_net_advantage(attacker: str, safe_ball: bool, day2_bias: bool) -> float:
    """Heuristic EV(ATTACK − ANCHOR). Positive favors ATTACK."""
    if attacker == "Matt":
        w = MATT_W[hole_idx]; streak = bad_streak(matt_shots); strokes = matt_strokes
    else:
        w = MIKE_W[hole_idx]; streak = bad_streak(mike_shots); strokes = mike_strokes

    base = w * 0.35
    if day2_bias: base += 0.25
    if safe_ball: base += 0.20
    base += (0.05 if strokes > 0 else -0.05)  # slight boost if receiving a stroke
    risk = 0.15 * min(streak, 3)              # rising risk with bad streak
    if not safe_ball: risk += 0.20            # no safety net → conservative
    return round(base - risk, 2)

def is_deadband(ev: float) -> bool:
    """Treat near-zero EV as 'no clear edge' (avoid fake precision)."""
    return -0.05 <= ev <= 0.05

def role_advice_and_rules(day2: bool, improve_list: List[int]):
    """Return (recommendation, rules, EV, attacker, smart_peek_dict)."""
    rules = []
    m1 = last(matt_shots); k1 = last(mike_shots)

    # Bad-streak guardrails
    matt_bad_run = bad_streak(matt_shots); mike_bad_run = bad_streak(mike_shots)
    if matt_bad_run >= BAD_STREAK_THRESHOLD: rules.append(f"Matt bad streak {matt_bad_run} → no green light.")
    if mike_bad_run >= BAD_STREAK_THRESHOLD: rules.append(f"Mike bad streak {mike_bad_run} → no green light.")

    # Tee order: prefer strokes/comfort to secure a safe ball early
    if len(matt_shots) == 0 and len(mike_shots) == 0:
        matt_pref = (matt_strokes > mike_strokes) or (MATT_W[hole_idx] > MIKE_W[hole_idx])
        who_first = "Matt" if matt_pref else "Mike"
        rules.append(f"Tee order by strokes/comfort → {who_first} tees first.")
        smart_peek = dict(attacker=None, ev=0.0, safe="N/A", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        return (f"{who_first} tees first. First player: put a ball in play. Partner adjusts based on result.",
                rules, 0.0, None, smart_peek)

    # One tee shot taken
    if len(matt_shots) + len(mike_shots) == 1:
        first_who = "Matt" if len(matt_shots) else "Mike"
        first_rating = m1 if len(matt_shots) else k1
        other_who = "Mike" if first_who == "Matt" else "Matt"
        day2_bias = day2 and (hole in improve_list)

        if first_rating >= SAFE_SCORE:
            rules.append(f"{first_who} safe (≥B).")
            ev = expected_net_advantage(other_who, safe_ball=True, day2_bias=day2_bias)
            downgrade = (
                (other_who == "Matt" and matt_bad_run >= BAD_STREAK_THRESHOLD)
                or (other_who == "Mike" and mike_bad_run >= BAD_STREAK_THRESHOLD)
                or ev <= 0 or is_deadband(ev)
            )
            if downgrade:
                rules.append(f"{other_who} attack downgraded (bad-streak or EV≤0 or deadband).")
                smart_peek = dict(attacker=other_who, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
                return (f"{first_who} is safe. {other_who}: controlled target; no hero shots.",
                        rules, ev, other_who, smart_peek)
            smart_peek = dict(attacker=other_who, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
            return (f"{first_who} is safe. {other_who}: ATTACK for a birdie look.",
                    rules, ev, other_who, smart_peek)

        if first_rating <= BAD_SCORE:
            rules.append(f"{first_who} in trouble (≤D).")
            smart_peek = dict(attacker=None, ev=0.0, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
            return (f"{first_who} is in trouble. {other_who}: ANCHOR (fairway finder; center green).",
                    rules, 0.0, None, smart_peek)

        rules.append(f"{first_who} average (C).")
        ev = expected_net_advantage(other_who, safe_ball=False, day2_bias=day2_bias)
        smart_peek = dict(attacker=other_who, ev=ev, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if ev <= 0 or is_deadband(ev):
            return (f"{first_who} is average. {other_who}: conservative line; favor fairway/center.",
                    rules, ev, other_who, smart_peek)
        return (f"{first_who} is average. {other_who}: medium risk line toward best angle.",
                rules, ev, other_who, smart_peek)

    # Both tee shots hit
    if len(matt_shots) == 1 and len(mike_shots) == 1:
        day2_bias = day2 and (hole in improve_list)
        safe_balls = sum(1 for r in [m1, k1] if r is not None and r >= SAFE_SCORE)

        if safe_balls >= 1:
            rules.append("At least one safe tee ball.")
            attacker = choose_attacker_candidate(m1, k1)
            ev = expected_net_advantage(attacker, safe_ball=True, day2_bias=day2_bias)
            partner = "Mike" if attacker == "Matt" else "Matt"
            smart_peek = dict(attacker=attacker, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])

            bad_run = bad_streak(matt_shots) if attacker == "Matt" else bad_streak(mike_shots)
            if bad_run >= BAD_STREAK_THRESHOLD or ev <= 0 or is_deadband(ev):
                rules.append(f"{attacker} attack downgraded (bad-streak or EV≤0 or deadband).")
                return (f"Team has a safe ball. {attacker}: controlled target. {partner}: easy two-putt.",
                        rules, ev, attacker, smart_peek)
            return (f"Team has a safe ball. {attacker}: ATTACK. {partner}: easy two-putt.",
                    rules, ev, attacker, smart_peek)

        if (m1 or 0) <= BAD_SCORE and (k1 or 0) <= BAD_SCORE:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            rules.append("Both tee balls in trouble.")
            smart_peek = dict(attacker=better_who, ev=0.0, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
            return (f"Both in trouble. Play from {better_who}'s better lie. Advance safely; protect bogey "
                    f"(often net par for Matt on stroke holes).",
                    rules, 0.0, better_who, smart_peek)

        attacker = choose_attacker_candidate(m1, k1)
        ev = expected_net_advantage(attacker, safe_ball=False, day2_bias=day2_bias)
        smart_peek = dict(attacker=attacker, ev=ev, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        rules.append("Mixed tee outcomes; attacker chosen by grades + hole strength.")
        if ev <= 0 or is_deadband(ev):
            return (f"Mixed results. Favor {attacker}'s lie but avoid high-risk lines; set up inside-15 ft if easy.",
                    rules, ev, attacker, smart_peek)
        return (f"Mixed results. Favor {attacker}'s lie; attacker aims for inside-15 ft.",
                rules, ev, attacker, smart_peek)

    # Approaches and beyond
    m_last = (last(matt_shots) or 0); k_last = (last(mike_shots) or 0)
    matt_safe = m_last >= SAFE_SCORE; mike_safe = k_last >= SAFE_SCORE
    day2_bias = day2 and (hole in improve_list)

    if matt_safe and not mike_safe:
        rules.append("Matt safe; Mike not safe.")
        ev = expected_net_advantage("Mike", safe_ball=True, day2_bias=day2_bias)
        smart_peek = dict(attacker="Mike", ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if bad_streak(mike_shots) >= BAD_STREAK_THRESHOLD or ev <= 0 or is_deadband(ev):
            rules.append("Mike attack downgraded.")
            return ("Matt is safe. Mike: smart center-green. Matt: avoid short-siding.",
                    rules, ev, "Mike", smart_peek)
        return ("Matt is safe. Mike: ATTACK pin if angle allows. Matt: avoid short-siding.",
                rules, ev, "Mike", smart_peek)

    if mike_safe and not matt_safe:
        rules.append("Mike safe; Matt not safe.")
        ev = expected_net_advantage("Matt", safe_ball=True, day2_bias=day2_bias)
        smart_peek = dict(attacker="Matt", ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if bad_streak(matt_shots) >= BAD_STREAK_THRESHOLD or ev <= 0 or is_deadband(ev):
            rules.append("Matt attack downgraded to damage control.")
            return ("Mike is safe. Matt: stop chasing par; advance; avoid hazard.",
                    rules, ev, "Matt", smart_peek)
        return ("Mike is safe. Matt: ATTACK with freedom. Mike: easy two-putt for par.",
                rules, ev, "Matt", smart_peek)

    if mike_safe and matt_safe:
        rules.append("Both safe.")
        attacker = choose_attacker_candidate(m_last, k_last)
        ev = expected_net_advantage(attacker, safe_ball=True, day2_bias=day2_bias)
        smart_peek = dict(attacker=attacker, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if ev <= 0 or is_deadband(ev):
            return ("Both are safe. Choose best birdie look; both play controlled lines.",
                    rules, ev, attacker, smart_peek)
        return ("Both are safe. Choose best birdie look; one flag-hunts, the other locks par.",
                rules, ev, attacker, smart_peek)

    rules.append("No one safe yet → damage-control bias.")
    smart_peek = dict(attacker=None, ev=0.0, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
    return ("Neither is safe yet. Advance to comfortable yardage; prioritize bogey (often net par for Matt on stroke holes).",
            rules, 0.0, None, smart_peek)

def net_targets_text() -> str:
    par = PAR[hole_idx]
    return f"Par {par}. Strokes — Matt: {matt_strokes}, Mike: {mike_strokes}. Matt bogey often equals net {par}."

def scroll_to_top_js():
    st.components.v1.html('''
    <script>
    window.scrollTo({top: 0, behavior: "smooth"});
    </script>
    ''', height=0)

# Recommendation logic
rec, rules, ev, attacker, peek = role_advice_and_rules(day2, improve_list)

# --- MOBILE-FIRST HEADER & NAVIGATION ---
st.markdown("<h4 style='margin-bottom:0.2em;'>Better-Ball Caddie for MKCC</h4>", unsafe_allow_html=True)

# Next/Prev buttons at top for thumb reach
bprev, bnext = st.columns(2)
if bprev.button("◀ Prev Hole", use_container_width=True, key=f"bprev_{hole}"):
    st.session_state["hole"] = max(1, hole - 1)
    st.rerun()
if bnext.button("Next Hole ▶", use_container_width=True, key=f"bnext_{hole}"):
    st.session_state["hole"] = min(18, hole + 1)
    st.rerun()

# Current hole info
st.markdown(f"<div style='font-size:1.1em; margin-bottom:0.5em;'><b>Hole {hole}</b> (Par {PAR[hole_idx]}, HCP {HOLE_HANDICAP[hole_idx]})</div>", unsafe_allow_html=True)

# Live Recommendation (smaller text)
st.markdown("<div class='sticky-reco' style='font-size:1.05em;'>", unsafe_allow_html=True)
st.markdown("#### Live Recommendation", unsafe_allow_html=True)
st.write(rec)
st.caption(net_targets_text())
st.markdown('</div>', unsafe_allow_html=True)

# Helper text
st.markdown("<div style='font-size:0.98em; color:#555; margin-bottom:0.7em;'>After you hit, grade your shot</div>", unsafe_allow_html=True)

# How to use (expander, still available but not prominent)
with st.expander("How to use this app"):
    st.markdown("""
    Grade each shot for both players using the A/B/C/D/F buttons below. The app instantly gives live, hole-specific recommendations for your team, factoring in:
    - **Handicaps** and per-hole stroke allocation
    - **Per-hole strengths** for each player (based on your tendencies)
    - **Recent shot grades** (bad streaks trigger damage control)
    - **Day-2 Ringer mode** for extra aggression on holes you want to improve
    - **Who is safe** after each shot, and who should attack or anchor

    The advice updates after every shot, helping you optimize team strategy in real time.
    """)

# Keep “hole” in session for big buttons + slider to stay in sync
if "hole" not in st.session_state:
    st.session_state["hole"] = 1
hole = st.session_state["hole"]

# Sidebar (so rec appears at top of page)
with st.sidebar:
    st.subheader("Round Controls")
    # Big Prev/Next for iPhone thumb reach
    cprev, cnext = st.columns(2)
    if cprev.button("◀ Prev", use_container_width=True):
        st.session_state["hole"] = max(1, hole - 1); st.rerun()
    if cnext.button("Next ▶", use_container_width=True):
        st.session_state["hole"] = min(18, hole + 1); st.rerun()

    hole = st.slider("Hole", 1, 18, st.session_state["hole"])
    st.session_state["hole"] = hole

    matt_hcp = st.number_input("Matt handicap", min_value=0, max_value=54, value=19)
    mike_hcp = st.number_input("Mike handicap", min_value=0, max_value=54, value=13)
    st.write("Grades: A=Best, B=Good, C=Playable, D=Trouble, F=Penalty")

    # Day-2 Ringer
    day2 = st.checkbox("Day-2 Ringer mode", value=False, help="Increases attack bias only on holes you pick.")
    improve_list = st.multiselect(
        "Holes to improve today",
        options=list(range(1,19)),
        default=[],
        help="Engine pushes harder on these holes when safe."
    )

    if st.button(f"Reset Hole {hole}", key=f"reset_{hole}", use_container_width=True):
        st.session_state[f"matt_{hole}"] = []
        st.session_state[f"mike_{hole}"] = []
        st.rerun()

# Per-hole state arrays
if f"matt_{hole}" not in st.session_state: st.session_state[f"matt_{hole}"] = []
if f"mike_{hole}" not in st.session_state: st.session_state[f"mike_{hole}"] = []
matt_shots = st.session_state[f"matt_{hole}"]
mike_shots = st.session_state[f"mike_{hole}"]

hole_idx = hole - 1
matt_strokes = strokes_for(matt_hcp, hole_idx)
mike_strokes = strokes_for(mike_hcp, hole_idx)

# === CORE LOGIC (kept near top so rec shows first and updates instantly) ====
def choose_attacker_candidate(m_last: int | None, k_last: int | None) -> str:
    """Pick attacker using last grades + per-hole strengths + bad streak penalty."""
    m_bad = bad_streak(matt_shots)
    k_bad = bad_streak(mike_shots)
    m_score = (m_last or 0) + MATT_W[hole_idx]*0.6 - m_bad*0.4
    k_score = (k_last or 0) + MIKE_W[hole_idx]*0.6 - k_bad*0.4
    return "Matt" if m_score >= k_score else "Mike"

def expected_net_advantage(attacker: str, safe_ball: bool, day2_bias: bool) -> float:
    """Heuristic EV(ATTACK − ANCHOR). Positive favors ATTACK."""
    if attacker == "Matt":
        w = MATT_W[hole_idx]; streak = bad_streak(matt_shots); strokes = matt_strokes
    else:
        w = MIKE_W[hole_idx]; streak = bad_streak(mike_shots); strokes = mike_strokes

    base = w * 0.35
    if day2_bias: base += 0.25
    if safe_ball: base += 0.20
    base += (0.05 if strokes > 0 else -0.05)  # slight boost if receiving a stroke
    risk = 0.15 * min(streak, 3)              # rising risk with bad streak
    if not safe_ball: risk += 0.20            # no safety net → conservative
    return round(base - risk, 2)

def is_deadband(ev: float) -> bool:
    """Treat near-zero EV as 'no clear edge' (avoid fake precision)."""
    return -0.05 <= ev <= 0.05

def role_advice_and_rules(day2: bool, improve_list: List[int]):
    """Return (recommendation, rules, EV, attacker, smart_peek_dict)."""
    rules = []
    m1 = last(matt_shots); k1 = last(mike_shots)

    # Bad-streak guardrails
    matt_bad_run = bad_streak(matt_shots); mike_bad_run = bad_streak(mike_shots)
    if matt_bad_run >= BAD_STREAK_THRESHOLD: rules.append(f"Matt bad streak {matt_bad_run} → no green light.")
    if mike_bad_run >= BAD_STREAK_THRESHOLD: rules.append(f"Mike bad streak {mike_bad_run} → no green light.")

    # Tee order: prefer strokes/comfort to secure a safe ball early
    if len(matt_shots) == 0 and len(mike_shots) == 0:
        matt_pref = (matt_strokes > mike_strokes) or (MATT_W[hole_idx] > MIKE_W[hole_idx])
        who_first = "Matt" if matt_pref else "Mike"
        rules.append(f"Tee order by strokes/comfort → {who_first} tees first.")
        smart_peek = dict(attacker=None, ev=0.0, safe="N/A", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        return (f"{who_first} tees first. First player: put a ball in play. Partner adjusts based on result.",
                rules, 0.0, None, smart_peek)

    # One tee shot taken
    if len(matt_shots) + len(mike_shots) == 1:
        first_who = "Matt" if len(matt_shots) else "Mike"
        first_rating = m1 if len(matt_shots) else k1
        other_who = "Mike" if first_who == "Matt" else "Matt"
        day2_bias = day2 and (hole in improve_list)

        if first_rating >= SAFE_SCORE:
            rules.append(f"{first_who} safe (≥B).")
            ev = expected_net_advantage(other_who, safe_ball=True, day2_bias=day2_bias)
            downgrade = (
                (other_who == "Matt" and matt_bad_run >= BAD_STREAK_THRESHOLD)
                or (other_who == "Mike" and mike_bad_run >= BAD_STREAK_THRESHOLD)
                or ev <= 0 or is_deadband(ev)
            )
            if downgrade:
                rules.append(f"{other_who} attack downgraded (bad-streak or EV≤0 or deadband).")
                smart_peek = dict(attacker=other_who, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
                return (f"{first_who} is safe. {other_who}: controlled target; no hero shots.",
                        rules, ev, other_who, smart_peek)
            smart_peek = dict(attacker=other_who, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
            return (f"{first_who} is safe. {other_who}: ATTACK for a birdie look.",
                    rules, ev, other_who, smart_peek)

        if first_rating <= BAD_SCORE:
            rules.append(f"{first_who} in trouble (≤D).")
            smart_peek = dict(attacker=None, ev=0.0, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
            return (f"{first_who} is in trouble. {other_who}: ANCHOR (fairway finder; center green).",
                    rules, 0.0, None, smart_peek)

        rules.append(f"{first_who} average (C).")
        ev = expected_net_advantage(other_who, safe_ball=False, day2_bias=day2_bias)
        smart_peek = dict(attacker=other_who, ev=ev, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if ev <= 0 or is_deadband(ev):
            return (f"{first_who} is average. {other_who}: conservative line; favor fairway/center.",
                    rules, ev, other_who, smart_peek)
        return (f"{first_who} is average. {other_who}: medium risk line toward best angle.",
                rules, ev, other_who, smart_peek)

    # Both tee shots hit
    if len(matt_shots) == 1 and len(mike_shots) == 1:
        day2_bias = day2 and (hole in improve_list)
        safe_balls = sum(1 for r in [m1, k1] if r is not None and r >= SAFE_SCORE)

        if safe_balls >= 1:
            rules.append("At least one safe tee ball.")
            attacker = choose_attacker_candidate(m1, k1)
            ev = expected_net_advantage(attacker, safe_ball=True, day2_bias=day2_bias)
            partner = "Mike" if attacker == "Matt" else "Matt"
            smart_peek = dict(attacker=attacker, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])

            bad_run = bad_streak(matt_shots) if attacker == "Matt" else bad_streak(mike_shots)
            if bad_run >= BAD_STREAK_THRESHOLD or ev <= 0 or is_deadband(ev):
                rules.append(f"{attacker} attack downgraded (bad-streak or EV≤0 or deadband).")
                return (f"Team has a safe ball. {attacker}: controlled target. {partner}: easy two-putt.",
                        rules, ev, attacker, smart_peek)
            return (f"Team has a safe ball. {attacker}: ATTACK. {partner}: easy two-putt.",
                    rules, ev, attacker, smart_peek)

        if (m1 or 0) <= BAD_SCORE and (k1 or 0) <= BAD_SCORE:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            rules.append("Both tee balls in trouble.")
            smart_peek = dict(attacker=better_who, ev=0.0, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
            return (f"Both in trouble. Play from {better_who}'s better lie. Advance safely; protect bogey "
                    f"(often net par for Matt on stroke holes).",
                    rules, 0.0, better_who, smart_peek)

        attacker = choose_attacker_candidate(m1, k1)
        ev = expected_net_advantage(attacker, safe_ball=False, day2_bias=day2_bias)
        smart_peek = dict(attacker=attacker, ev=ev, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        rules.append("Mixed tee outcomes; attacker chosen by grades + hole strength.")
        if ev <= 0 or is_deadband(ev):
            return (f"Mixed results. Favor {attacker}'s lie but avoid high-risk lines; set up inside-15 ft if easy.",
                    rules, ev, attacker, smart_peek)
        return (f"Mixed results. Favor {attacker}'s lie; attacker aims for inside-15 ft.",
                rules, ev, attacker, smart_peek)

    # Approaches and beyond
    m_last = (last(matt_shots) or 0); k_last = (last(mike_shots) or 0)
    matt_safe = m_last >= SAFE_SCORE; mike_safe = k_last >= SAFE_SCORE
    day2_bias = day2 and (hole in improve_list)

    if matt_safe and not mike_safe:
        rules.append("Matt safe; Mike not safe.")
        ev = expected_net_advantage("Mike", safe_ball=True, day2_bias=day2_bias)
        smart_peek = dict(attacker="Mike", ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if bad_streak(mike_shots) >= BAD_STREAK_THRESHOLD or ev <= 0 or is_deadband(ev):
            rules.append("Mike attack downgraded.")
            return ("Matt is safe. Mike: smart center-green. Matt: avoid short-siding.",
                    rules, ev, "Mike", smart_peek)
        return ("Matt is safe. Mike: ATTACK pin if angle allows. Matt: avoid short-siding.",
                rules, ev, "Mike", smart_peek)

    if mike_safe and not matt_safe:
        rules.append("Mike safe; Matt not safe.")
        ev = expected_net_advantage("Matt", safe_ball=True, day2_bias=day2_bias)
        smart_peek = dict(attacker="Matt", ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if bad_streak(matt_shots) >= BAD_STREAK_THRESHOLD or ev <= 0 or is_deadband(ev):
            rules.append("Matt attack downgraded to damage control.")
            return ("Mike is safe. Matt: stop chasing par; advance; avoid hazard.",
                    rules, ev, "Matt", smart_peek)
        return ("Mike is safe. Matt: ATTACK with freedom. Mike: easy two-putt for par.",
                rules, ev, "Matt", smart_peek)

    if mike_safe and matt_safe:
        rules.append("Both safe.")
        attacker = choose_attacker_candidate(m_last, k_last)
        ev = expected_net_advantage(attacker, safe_ball=True, day2_bias=day2_bias)
        smart_peek = dict(attacker=attacker, ev=ev, safe="Yes", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
        if ev <= 0 or is_deadband(ev):
            return ("Both are safe. Choose best birdie look; both play controlled lines.",
                    rules, ev, attacker, smart_peek)
        return ("Both are safe. Choose best birdie look; one flag-hunts, the other locks par.",
                rules, ev, attacker, smart_peek)

    rules.append("No one safe yet → damage-control bias.")
    smart_peek = dict(attacker=None, ev=0.0, safe="No", matt_w=MATT_W[hole_idx], mike_w=MIKE_W[hole_idx])
    return ("Neither is safe yet. Advance to comfortable yardage; prioritize bogey (often net par for Matt on stroke holes).",
            rules, 0.0, None, smart_peek)

def net_targets_text() -> str:
    par = PAR[hole_idx]
    return f"Par {par}. Strokes — Matt: {matt_strokes}, Mike: {mike_strokes}. Matt bogey often equals net {par}."
st.markdown('</div>', unsafe_allow_html=True)
st.markdown("---")
st.markdown("---")
c1, c2 = st.columns(2, gap="large")
c1, c2 = st.columns(2, gap="large")
def scroll_to_top_js():
    st.components.v1.html('''
    <script>
    window.scrollTo({top: 0, behavior: "smooth"});
    </script>
    ''', height=0)

with c1:
    st.markdown("#### Matt", unsafe_allow_html=True)
    st.markdown('<div class="grade-grid">', unsafe_allow_html=True)
    for g in ["A","B","C","D","F"]:
        if st.button(g, key=f"matt_{hole}_{g}", help=GRADE_HELP[g], use_container_width=True):
            matt_shots.append(GRADE_TO_SCORE[g])
            scroll_to_top_js()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("Matt shots:", " ".join(SCORE_TO_GRADE[s] for s in matt_shots) or "—")

with c2:
    st.markdown("#### Mike", unsafe_allow_html=True)
    st.markdown('<div class="grade-grid">', unsafe_allow_html=True)
    for g in ["A","B","C","D","F"]:
        if st.button(g, key=f"mike_{hole}_{g}", help=GRADE_HELP[g], use_container_width=True):
            mike_shots.append(GRADE_TO_SCORE[g])
            scroll_to_top_js()
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("Mike shots:", " ".join(SCORE_TO_GRADE[s] for s in mike_shots) or "—")

st.markdown("---")

with st.expander("Why this? (full explainability)"):
    st.markdown("- **Hole**: {} (Par {}, HCP {})".format(hole, PAR[hole_idx], HOLE_HANDICAP[hole_idx]))
    st.markdown("- **Matt grades**: {}".format(" ".join(SCORE_TO_GRADE[s] for s in matt_shots) or "—"))
    st.markdown("- **Mike grades**: {}".format(" ".join(SCORE_TO_GRADE[s] for s in mike_shots) or "—"))
    st.markdown("- **Per-hole strength**: Matt {:.2f} · Mike {:.2f}".format(MATT_W[hole_idx], MIKE_W[hole_idx]))
    st.markdown("- **Day-2 mode**: {} · Improve: {}".format("ON" if day2 else "OFF", improve_list or "—"))
    st.markdown("- **Expected Net Advantage (ATTACK vs ANCHOR)**: **{:+.2f}**{}".format(
        ev, f" for {attacker}" if attacker else ""))
    st.markdown("- **Rules fired**:")
    if rules:
        for r in rules:
            st.markdown(f"  - {r}")
    else:
        st.markdown("  - (none yet)")
bprev, bnext = st.columns(2)
if bprev.button("◀ Prev Hole", use_container_width=True, key=f"bprev_{hole}"):
    st.session_state["hole"] = max(1, hole - 1); st.rerun()
if bnext.button("Next Hole ▶", use_container_width=True, key=f"bnext_{hole}"):
    st.session_state["hole"] = min(18, hole + 1); st.rerun()

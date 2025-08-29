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

# Thresholds & overrides
SAFE_SCORE = 4            # >= B is “safe”
BAD_SCORE  = 2            # <= D is “trouble”
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

# --- Per-hole strength weights (0..1) derived from your sheet insights ---
# Meaning: higher = player is more comfortable on that hole → more attack bias and/or safer tee first.
# Matt best: 8, 17, 1; worst: 9, 16, 5
# Mike best: 10, 3, 17; worst: 12, 9, 14
MATT_HOLE_WEIGHT = [
    0.8, 0.5, 0.5, 0.5, 0.2, 0.5, 0.5, 0.8, 0.2,
    0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.2, 0.8, 0.5
]
MIKE_HOLE_WEIGHT = [
    0.5, 0.5, 0.8, 0.5, 0.5, 0.5, 0.5, 0.5, 0.2,
    0.8, 0.5, 0.2, 0.5, 0.2, 0.5, 0.5, 0.8, 0.5
]
# You can fine-tune those arrays as your data grows.
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

    # Day-2 Ringer tools
    day2 = st.checkbox("Day-2 Ringer mode", value=False, help="Increase attack bias on holes you still want to improve.")
    improve_list = st.multiselect(
        "Holes to improve today",
        options=list(range(1,19)),
        default=[],
        help="On these holes the engine increases attack bias when safe."
    )

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
    for g in ["A","B","C","D","F"]:
        if st.button(g, key=f"matt_{hole}_{g}", help=GRADE_HELP[g], use_container_width=True):
            matt_shots.append(GRADE_TO_SCORE[g])
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("Matt shots:", " ".join(SCORE_TO_GRADE[s] for s in matt_shots) or "—")

with c2:
    st.markdown("### Mike — grade this shot")
    st.markdown('<div class="grade-grid">', unsafe_allow_html=True)
    for g in ["A","B","C","D","F"]:
        if st.button(g, key=f"mike_{hole}_{g}", help=GRADE_HELP[g], use_container_width=True):
            mike_shots.append(GRADE_TO_SCORE[g])
    st.markdown('</div>', unsafe_allow_html=True)
    st.write("Mike shots:", " ".join(SCORE_TO_GRADE[s] for s in mike_shots) or "—")
# === UI END ==================================================================


# === LOGIC START =============================================================
def choose_attacker_candidate(m_last: int|None, k_last: int|None) -> str:
    """Choose the best attacker candidate given last grades + per-hole weights + bad streak."""
    m_bad = bad_streak(matt_shots)
    k_bad = bad_streak(mike_shots)

    # Base: last grade (favor higher), plus hole weight, minus penalty for bad streak
    m_score = (m_last or 0) + MATT_HOLE_WEIGHT[hole_idx]*0.6 - m_bad*0.4
    k_score = (k_last or 0) + MIKE_HOLE_WEIGHT[hole_idx]*0.6 - k_bad*0.4

    return "Matt" if m_score >= k_score else "Mike"

def expected_net_advantage(attacker: str, safe_ball: bool, day2_bias: bool) -> float:
    """
    Heuristic expected net advantage of ATTACK over ANCHOR.
    Positive → Attack recommended; Negative → Anchor recommended.
    """
    if attacker == "Matt":
        w = MATT_HOLE_WEIGHT[hole_idx]
        streak = bad_streak(matt_shots)
        strokes = matt_strokes
    else:
        w = MIKE_HOLE_WEIGHT[hole_idx]
        streak = bad_streak(mike_shots)
        strokes = mike_strokes

    base = w * 0.35
    if day2_bias:
        base += 0.25  # push harder on Day-2 target holes
    if safe_ball:
        base += 0.20  # freedom to attack when partner is safe
    # Slight nudge for having a stroke (tolerates bogey lines), slight penalty if none
    base += (0.05 if strokes > 0 else -0.05)

    risk = 0.15 * min(streak, 3)           # rising penalty with bad streak
    if not safe_ball:
        risk += 0.20                        # no safety net → more conservative

    return round(base - risk, 2)

def role_advice_and_rules(day2: bool, improve_list: list[int]):
    """Return (recommendation: str, rules_fired: list[str], ev: float, attacker: str|None) with explainability."""
    rules = []
    m1 = last(matt_shots)  # last score
    k1 = last(mike_shots)

    matt_bad_run = bad_streak(matt_shots)
    mike_bad_run = bad_streak(mike_shots)
    if matt_bad_run >= BAD_STREAK_THRESHOLD:
        rules.append(f"Matt bad streak: {matt_bad_run} (≥{BAD_STREAK_THRESHOLD}) → Matt should NOT attack.")
    if mike_bad_run >= BAD_STREAK_THRESHOLD:
        rules.append(f"Mike bad streak: {mike_bad_run} (≥{BAD_STREAK_THRESHOLD}) → Mike should NOT attack.")

    # Tee order (consider strokes + per-hole comfort)
    if len(matt_shots) == 0 and len(mike_shots) == 0:
        # Prefer the player with a stroke OR higher comfort to tee first to secure a safe ball
        matt_pref = (matt_strokes > mike_strokes) or (MATT_HOLE_WEIGHT[hole_idx] > MIKE_HOLE_WEIGHT[hole_idx])
        who_first = "Matt" if matt_pref else "Mike"
        rules.append(f"Tee order rule: strokes/comfort → {who_first} tees first.")
        return (f"{who_first} tees first. First player: put a ball in play. Partner adjusts based on result.",
                rules, 0.0, None)

    # After only one tee shot
    if len(matt_shots) + len(mike_shots) == 1:
        first_who = "Matt" if len(matt_shots) else "Mike"
        first_rating = m1 if len(matt_shots) else k1
        other_who = "Mike" if first_who == "Matt" else "Matt"
        day2_bias = day2 and (hole in improve_list)

        if first_rating >= SAFE_SCORE:
            rules.append(f"{first_who} safe (≥B).")
            # attacker is the other player by default
            ev = expected_net_advantage(other_who, safe_ball=True, day2_bias=day2_bias)
            if (other_who == "Matt" and matt_bad_run >= BAD_STREAK_THRESHOLD) or \
               (other_who == "Mike" and mike_bad_run >= BAD_STREAK_THRESHOLD) or ev <= 0:
                rules.append(f"{other_who} attack downgraded (bad-streak or EV≤0).")
                return (f"{first_who} is safe. {other_who}: controlled target; no hero shots.",
                        rules, ev, other_who)
            return (f"{first_who} is safe. {other_who}: ATTACK for a birdie look.",
                    rules, ev, other_who)

        if first_rating <= BAD_SCORE:
            rules.append(f"{first_who} in trouble (≤D).")
            return (f"{first_who} is in trouble. {other_who}: ANCHOR (fairway finder; center green).",
                    rules, 0.0, None)

        rules.append(f"{first_who} average (C).")
        ev = expected_net_advantage(other_who, safe_ball=False, day2_bias=day2_bias)
        if ev <= 0:
            return (f"{first_who} is average. {other_who}: conservative line; favor fairway/center.",
                    rules, ev, other_who)
        return (f"{first_who} is average. {other_who}: medium risk line toward best angle.",
                rules, ev, other_who)

    # Both tee shots hit
    if len(matt_shots) == 1 and len(mike_shots) == 1:
        safe_balls = sum(1 for r in [m1, k1] if r is not None and r >= SAFE_SCORE)
        day2_bias = day2 and (hole in improve_list)

        if safe_balls >= 1:
            rules.append("At least one safe tee ball.")
            attacker = choose_attacker_candidate(m1, k1)
            ev = expected_net_advantage(attacker, safe_ball=True, day2_bias=day2_bias)
            partner = "Mike" if attacker == "Matt" else "Matt"

            # downgrade if bad-streak or EV ≤ 0
            bad_run = bad_streak(matt_shots) if attacker == "Matt" else bad_streak(mike_shots)
            if bad_run >= BAD_STREAK_THRESHOLD or ev <= 0:
                rules.append(f"{attacker} attack downgraded (bad-streak or EV≤0).")
                return (f"Team has a safe ball. {attacker}: controlled target. {partner}: secure easy two-putt.",
                        rules, ev, attacker)
            return (f"Team has a safe ball. {attacker}: ATTACK. {partner}: play for easy two-putt.",
                    rules, ev, attacker)

        if (m1 or 0) <= BAD_SCORE and (k1 or 0) <= BAD_SCORE:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            rules.append("Both tee balls in trouble.")
            return (f"Both in trouble. Play from {better_who}'s better lie. Advance safely; protect bogey "
                    f"(often net par for Matt on stroke holes).",
                    rules, 0.0, None)

        # Mixed without a clear safe ball
        attacker = choose_attacker_candidate(m1, k1)
        ev = expected_net_advantage(attacker, safe_ball=False, day2_bias=day2 and (hole in improve_list))
        rules.append("Mixed tee outcomes; attacker chosen by grades + hole strength.")
        if ev <= 0:
            return (f"Mixed results. Favor {attacker}'s lie but avoid high-risk lines; set up inside-15-ft if easy.",
                    rules, ev, attacker)
        return (f"Mixed results. Favor {attacker}'s lie; attacker aims for inside-15-ft.",
                rules, ev, attacker)

    # Approaches and beyond
    m_last = (last(matt_shots) or 0)
    k_last = (last(mike_shots) or 0)
    matt_safe = m_last >= SAFE_SCORE
    mike_safe = k_last >= SAFE_SCORE
    day2_bias = day2 and (hole in improve_list)

    if matt_safe and not mike_safe:
        rules.append("Matt safe; Mike not safe.")
        ev = expected_net_advantage("Mike", safe_ball=True, day2_bias=day2_bias)
        if bad_streak(mike_shots) >= BAD_STREAK_THRESHOLD or ev <= 0:
            rules.append("Mike attack downgraded.")
            return ("Matt is safe. Mike: smart, center-green target. Matt: avoid short-siding.",
                    rules, ev, "Mike")
        return ("Matt is safe. Mike: ATTACK pin if angle allows. Matt: avoid short-siding.",
                rules, ev, "Mike")

    if mike_safe and not matt_safe:
        rules.append("Mike safe; Matt not safe.")
        ev = expected_net_advantage("Matt", safe_ball=True, day2_bias=day2_bias)
        if bad_streak(matt_shots) >= BAD_STREAK_THRESHOLD or ev <= 0:
            rules.append("Matt attack downgraded to damage control.")
            return ("Mike is safe. Matt: stop chasing par; advance to comfy yardage; avoid hazard.",
                    rules, ev, "Matt")
        return ("Mike is safe. Matt: ATTACK with freedom. Mike: play to easy two-putt for par.",
                rules, ev, "Matt")

    if mike_safe and matt_safe:
        rules.append("Both safe.")
        attacker = choose_attacker_candidate(m_last, k_last)
        ev = expected_net_advantage(attacker, safe_ball=True, day2_bias=day2_bias)
        if ev <= 0:
            return ("Both are safe. Choose best birdie look; both play controlled lines.",
                    rules, ev, attacker)
        return ("Both are safe. Choose best birdie look; one goes flag-hunting, other locks in par.",
                rules, ev, attacker)

    rules.append("No one safe yet → damage-control bias.")
    return ("Neither is safe yet. Advance to comfortable yardage; prioritize bogey (often net par for Matt on stroke holes).",
            rules, 0.0, None)

def net_targets_text() -> str:
    par = PAR[hole_idx]
    return f"Par {par}. Strokes here — Matt: {matt_strokes}, Mike: {mike_strokes}. Matt bogey often equals net {par}."
# === LOGIC END ===============================================================


# === OUTPUT START ============================================================
rec, rules, ev, attacker = role_advice_and_rules(day2, improve_list)

st.markdown("### Live Recommendation")
st.write(rec)
st.caption(net_targets_text())

with st.expander("Why this? (explainability)"):
    st.markdown("- **Hole**: {} (Par {}, HCP {})".format(hole, PAR[hole_idx], HOLE_HANDICAP[hole_idx]))
    st.markdown("- **Matt grades**: {}".format(" ".join(SCORE_TO_GRADE[s] for s in matt_shots) or "—"))
    st.markdown("- **Mike grades**: {}".format(" ".join(SCORE_TO_GRADE[s] for s in mike_shots) or "—"))
    st.markdown("- **Per-hole strength**: Matt {:.2f} · Mike {:.2f}".format(MATT_HOLE_WEIGHT[hole_idx], MIKE_HOLE_WEIGHT[hole_idx]))
    st.markdown("- **Day-2 bias**: {} · Improve list: {}".format("ON" if day2 else "OFF", improve_list or "—"))
    st.markdown("- **Expected Net Advantage (ATTACK vs ANCHOR)**: **{:+.2f}**{}".format(
        ev, f" for {attacker}" if attacker else ""))
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
st.markdown("Notes: We bias tee order and attack/anchor by per-hole strengths + strokes. Day-2 mode only increases attack on holes you select to improve. Bad-streak overrides prevent unrealistic “stress-free par” advice.")
# === OUTPUT END ==============================================================

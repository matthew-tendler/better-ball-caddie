import streamlit as st

st.set_page_config(page_title="Better-Ball Caddie", page_icon="⛳", layout="centered")

# -----------------------
# Course and handicap data
# -----------------------
HOLE_HANDICAP = [15, 9, 7, 17, 1, 13, 5, 11, 3, 16, 10, 2, 18, 8, 14, 4, 6, 12]
PAR =            [ 4, 4, 4,  3, 4,  4,  4,  3, 5,  3,  4,  4,  3, 5,  4,  4,  5,  4]

RATING_LABELS = {
    1: "Penalty or unplayable",
    2: "Trouble",
    3: "Playable",
    4: "Good",
    5: "Perfect",
}

SAFE = 4   # rating >= 4 means safe/green light
BAD  = 2   # rating <= 2 means trouble

def strokes_for(hcp: int, hole_index: int) -> int:
    """Standard stroke allocation:
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

# -----------------------
# Sidebar controls
# -----------------------
st.title("On Course Better Ball Caddie")
st.caption("Rate each shot 1 to 5. The app returns a live tactic for Matt and Mike.")

with st.sidebar:
    st.subheader("Round Controls")
    hole = st.slider("Hole", 1, 18, 1)
    matt_hcp = st.number_input("Matt handicap", min_value=0, max_value=54, value=19)
    mike_hcp = st.number_input("Mike handicap", min_value=0, max_value=54, value=13)
    st.write("Ratings: 1 Penalty, 2 Trouble, 3 Playable, 4 Good, 5 Perfect")
    if st.button("Reset current hole", key=f"reset_{hole}"):
        st.session_state[f"matt_{hole}"] = []
        st.session_state[f"mike_{hole}"] = []

# Init session state per hole
if f"matt_{hole}" not in st.session_state:
    st.session_state[f"matt_{hole}"] = []
if f"mike_{hole}" not in st.session_state:
    st.session_state[f"mike_{hole}"] = []

matt_shots = st.session_state[f"matt_{hole}"]
mike_shots = st.session_state[f"mike_{hole}"]

hole_idx = hole - 1
matt_strokes = strokes_for(matt_hcp, hole_idx)
mike_strokes = strokes_for(mike_hcp, hole_idx)

# -----------------------
# Shot entry UI
# -----------------------
c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("### Matt - rate this shot")
    cols = st.columns(5)
    for i, r in enumerate([1, 2, 3, 4, 5]):
        if cols[i].button(f"{r}\n{RATING_LABELS[r]}", key=f"matt_{hole}_{i}", use_container_width=True):
            matt_shots.append(r)
    st.write("Matt shots:", ", ".join(map(str, matt_shots)) if matt_shots else "-")

with c2:
    st.markdown("### Mike - rate this shot")
    cols2 = st.columns(5)
    for i, r in enumerate([1, 2, 3, 4, 5]):
        if cols2[i].button(f"{r}\n{RATING_LABELS[r]}", key=f"mike_{hole}_{i}", use_container_width=True):
            mike_shots.append(r)
    st.write("Mike shots:", ", ".join(map(str, mike_shots)) if mike_shots else "-")

# -----------------------
# Recommendation logic
# -----------------------
def role_advice() -> str:
    m1 = last(matt_shots)
    k1 = last(mike_shots)

    # No tee shots yet
    if len(matt_shots) == 0 and len(mike_shots) == 0:
        who_first = "Matt" if (mike_strokes == 0 and matt_strokes >= 1) else "Mike"
        return f"{who_first} tees first. First player focuses on a ball in play. Partner adjusts based on the result."

    # Only one tee shot taken
    if len(matt_shots) + len(mike_shots) == 1:
        first_who = "Matt" if len(matt_shots) else "Mike"
        first_rating = m1 if len(matt_shots) else k1
        other_who = "Mike" if first_who == "Matt" else "Matt"
        if first_rating is None:
            return "Waiting for the first tee shot rating."
        if first_rating >= SAFE:
            return f"{first_who} is safe. {other_who} can ATTACK with an aggressive line to create a birdie look."
        if first_rating <= BAD:
            return f"{first_who} is in trouble. {other_who} must ANCHOR with a fairway finder and play to the center of the green."
        return f"{first_who} is average. {other_who} takes a medium risk line and favors fairway or center green."

    # Both tee shots hit
    if len(matt_shots) == 1 and len(mike_shots) == 1:
        safe_balls = sum(1 for r in [m1, k1] if r is not None and r >= SAFE)
        if safe_balls >= 1:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            partner = "Mike" if better_who == "Matt" else "Matt"
            return f"Team has a safe ball. {better_who} ATTACKS the green. {partner} plays for a stress free par."
        if (m1 or 0) <= BAD and (k1 or 0) <= BAD:
            better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
            return f"Both drives are in trouble. Play from {better_who}'s better lie, advance safely, and protect bogey. This is often net par for Matt."
        better_who = "Matt" if (m1 or 0) >= (k1 or 0) else "Mike"
        return f"Mixed results off the tee. Favor {better_who}'s lie. The attacker aims for a putt inside 15 feet."

    # Approaches and beyond
    matt_safe = (m1 or 0) >= SAFE
    mike_safe = (k1 or 0) >= SAFE
    if matt_safe and not mike_safe:
        return "Matt is safe. Mike ATTACKS the pin if the angle allows. Matt avoids short siding."
    if mike_safe and not matt_safe:
        return "Mike is safe. Matt ATTACKS with freedom. Mike plays to two putt range for par."
    if mike_safe and matt_safe:
        return "Both are safe. Choose the best birdie look. One goes flag hunting, the other locks in par."
    return "Neither is safe yet. Advance to a comfortable yardage and protect bogey. Bogey is often net par for Matt on stroke holes."

def net_targets_text() -> str:
    par = PAR[hole_idx]
    return f"Par {par}. Strokes on this hole - Matt: {matt_strokes}, Mike: {mike_strokes}. Matt bogey often equals net {par}."

st.markdown("### Live Recommendation")
st.write(role_advice())
st.caption(net_targets_text())

st.markdown("---")
st.markdown("Notes: Matt usually receives a stroke on every hole. On HCP 1 he receives two. Day 2 ringer: press harder on holes not covered on Day 1.")

import threading
import streamlit as st
import db                                    # Appointments.
import memory                                # Memories.
import speech                                # Voice (for the stop button).
import voice                                 # Shared state and the listener loop.

st.set_page_config(page_title="Loop", layout="wide")


@st.cache_resource                           # Runs ONCE; later page reruns reuse the result.
def start_listener():
    thread = threading.Thread(target=voice.listener_loop, daemon=True)   # Its own background thread.
    thread.start()
    return thread


start_listener()                             # Safe to call on every rerun: it only starts once.

st.title("Loop")

# --- Controls (outside the auto-refreshing part, so typing isn't interrupted) ---
col1, col2, col3 = st.columns([1, 1, 4])
if col1.button("Unmute" if voice.state["muted"] else "Mute"):
    voice.state["muted"] = not voice.state["muted"]      # Flip the mute flag the listener reads.
    st.rerun()
if col2.button("Stop speaking"):
    speech.stop()                            # Silence the voice at once.
with col3.form("typed", clear_on_submit=True):
    typed = st.text_input("Typed command", label_visibility="collapsed",
                          placeholder="Type a command, e.g. what is on my calendar")
    if st.form_submit_button("Send") and typed.strip():
        voice.submit_typed(typed.strip())

BANNERS = {                                  # status -> (colour, text)
    "loading":   ("#6b7280", "LOADING models..."),
    "listening": ("#16a34a", "LISTENING: say \"Loop, ...\""),
    "thinking":  ("#ca8a04", "THINKING..."),
    "speaking":  ("#2563eb", "SPEAKING: not listening"),
    "muted":     ("#dc2626", "MUTED: not listening"),
    "error":     ("#7f1d1d", "ERROR"),
}


@st.fragment(run_every=1)                    # Only this block redraws, once per second.
def dashboard():
    status = voice.current_status()
    color, text = BANNERS[status]
    st.markdown(f"<div style='background:{color};color:white;padding:16px;border-radius:8px;"
                f"font-size:24px;font-weight:bold;text-align:center'>{text}</div>",
                unsafe_allow_html=True)
    if status == "error":
        st.error(voice.state["error"])

    left, right = st.columns(2)
    with left:
        st.subheader("Conversation")
        turns = list(voice.state["turns"])               # Copy, because the listener may change it.
        if not turns:
            st.caption("Nothing yet.")
        for turn in reversed(turns[-8:]):                # Newest first.
            st.markdown(f"**{turn['time']} ({turn['source']}) Heard:** {turn['heard']}")
            with st.expander(f"Tool calls ({len(turn['tools'])})"):
                for call in list(turn["tools"]):
                    st.code(f"{call['tool']}({call['args']})\n-> {call['result']}")
            st.markdown(f"**Reply:** {turn['reply'] or '...'}")
            st.divider()
    with right:
        st.subheader("Memories")
        memories = memory.all_memories()
        if memories:
            for m in memories:
                st.write(f"- {m['text']}")
        else:
            st.caption("No memories yet.")
        st.subheader("Appointments")
        appointments = db.get_appointments()
        if appointments:
            st.dataframe(appointments, hide_index=True)
        else:
            st.caption("No appointments.")


dashboard()
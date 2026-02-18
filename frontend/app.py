import streamlit as st
import httpx

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Personal Notes Agent",
    page_icon="📝",
    layout="centered"
)

# ── Constants ──────────────────────────────────────────────────────────────────
BACKEND_URL = "http://localhost:8001"

# ── Session state init ─────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ── Helper: call FastAPI backend ───────────────────────────────────────────────
def send_message(user_message: str) -> str:
    try:
        response = httpx.post(
            f"{BACKEND_URL}/chat",
            json={
                "message": user_message,
                "history": st.session_state.messages
            },
            timeout=60.0
        )
        response.raise_for_status()
        return response.json()["reply"]

    except httpx.ConnectError:
        return "❌ Cannot connect to backend. Make sure FastAPI is running on port 8001."
    except httpx.TimeoutException:
        return "⏱️ Request timed out. The agent is taking too long to respond."
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"

# ── Helper: check backend health ───────────────────────────────────────────────
def check_health() -> bool:
    try:
        response = httpx.get(f"{BACKEND_URL}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False

# ── UI: Header ─────────────────────────────────────────────────────────────────
st.title("📝 Personal Notes Agent")
st.caption("Chat with your AI agent to manage your notes.")

# ── UI: Health indicator ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔌 System Status")

    if st.button("Check Connection"):
        if check_health():
            st.success("Backend is online ✅")
        else:
            st.error("Backend is offline ❌")

    st.divider()
    st.markdown("**Things you can say:**")
    st.markdown("- Add a note called 'shopping' with eggs and milk")
    st.markdown("- Show me all my notes")
    st.markdown("- Read my note called 'shopping'")
    st.markdown("- Delete the note called 'shopping'")

    st.divider()
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# ── UI: Chat history ───────────────────────────────────────────────────────────
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# ── UI: Chat input ─────────────────────────────────────────────────────────────
if prompt := st.chat_input("Talk to your notes agent..."):

    # Show user message immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call backend and show response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            reply = send_message(prompt)
        st.markdown(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
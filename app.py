"""InferDyssey — Research OS for Apple Silicon Inference."""

import streamlit as st

st.set_page_config(
    page_title="InferDyssey",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Sidebar ---
st.sidebar.title("InferDyssey")
st.sidebar.caption("Research OS for Apple Silicon Inference")
st.sidebar.divider()

page = st.sidebar.radio(
    "Navigate",
    ["Learn", "Workspaces", "Specs", "Settings"],
    index=0,
    label_visibility="collapsed",
)

# --- Initialize session state ---
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "hardware" not in st.session_state:
    from core.hardware import detect
    st.session_state.hardware = detect()

# --- Route to pages ---
if page == "Learn":
    from views.learn import render
    render()
elif page == "Workspaces":
    from views.workspaces import render
    render()
elif page == "Specs":
    from views.specs import render
    render()
elif page == "Settings":
    from views.settings import render
    render()

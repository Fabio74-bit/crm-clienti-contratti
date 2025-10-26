# =====================================
# utils/auth.py — gestione login e ruoli
# =====================================
import streamlit as st
import time

LOGO_URL = "https://www.shtsrl.com/template/images/logo.png"

def do_login_fullscreen():
    """Login elegante con sfondo fullscreen"""
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

 st.markdown("""
<style>
div[data-testid="stAppViewContainer"] {
    padding-top: 0 !important;
    background-color: #f8fafc;
}
header[data-testid="stHeader"] {
    display: none !important;
}
.block-container {
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;
    height:100vh;
}
.login-card {
    background:#fff;
    border:1px solid #e5e7eb;
    border-radius:12px;
    box-shadow:0 4px 16px rgba(0,0,0,0.08);
    padding:2rem 2.5rem;
    width:360px;
    text-align:center;
}
.login-title {
    font-size:1.3rem;
    font-weight:600;
    color:#2563eb;
    margin:1rem 0 1.4rem;
}
.stButton>button {
    width:260px;
    font-size:0.9rem;
    background-color:#2563eb;
    color:white;
    border:none;
    border-radius:6px;
    padding:0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

# =====================================
# utils/auth.py — Login Fullscreen pulito con logo locale
# =====================================
import streamlit as st
import time

def do_login_fullscreen():
    """Login elegante fullscreen senza rettangolo bianco"""
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    # CSS per fullscreen + rimozione padding + stile moderno
    st.markdown("""
    <style>
    /* Rimuove margini e padding generali */
    div[data-testid="stAppViewContainer"] {
        padding-top: 0 !important;
    }
    .block-container {
        padding: 0 !important;
        margin: 0 !important;
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100vh;
        background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
    }
    /* Card login */
    .login-card {
        background: rgba(255, 255, 255, 0.6);  /* bianco trasparente */
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 14px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.12);
        padding: 2rem 2.5rem;
        width: 360px;
        text-align: center;
        backdrop-filter: blur(6px);  /* effetto vetro satinato */
    }

    .login-title {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2563eb;
        margin: 1rem 0 1.4rem;
    }
    .stButton>button {
        width: 260px;
        font-size: 0.9rem;
        background-color: #2563eb;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Layout login ---
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)

    username = st.text_input("Nome utente", key="login_user").strip().lower()
    password = st.text_input("Password", type="password", key="login_pass")
    login_btn = st.button("Entra")
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Validazione login ---
    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True
        users = st.secrets["auth"]["users"]

        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })
            st.success(f"✅ Benvenuto {username}!")
            time.sleep(0.3)
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
            st.session_state["_login_checked"] = False

    st.stop()

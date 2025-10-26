# utils/auth.py
import streamlit as st
import time

def do_login_fullscreen():
    """Login fullscreen minimale: logo visibile, niente rettangoli strani."""
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    # --- CSS SOLO per il login ---
    st.markdown("""
    <style>
    /* Sfondo chiaro uniforme */
    html, body, [data-testid="stAppViewContainer"] {
        background: #f5f7fb !important;
    }
    /* Contenuto centrato in pagina */
    .block-container {
        margin: 0 !important;
        padding: 0 !important;
        max-width: 100% !important;
        display: flex; align-items: center; justify-content: center;
        min-height: 100vh;
    }
    /* Card login */
    .login-card {
        width: 420px; background: #fff; border: 1px solid #e6e8eb;
        border-radius: 12px; box-shadow: 0 8px 18px rgba(0,0,0,.06);
        padding: 22px 26px;
    }
    .login-logo { text-align:center; margin-bottom: 10px; }
    .login-title { text-align:center; font-weight:700; color:#2563eb; margin: 6px 0 18px; }
    .stButton>button {
        width: 100%; border-radius: 8px; background:#2563eb; color:#fff; font-weight:600;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Layout login (nessun placeholder “vuoto”) ---
    with st.container():
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.markdown("<div class='login-logo'>", unsafe_allow_html=True)
        st.image("assets/logo-sht.png", width=170)  # <-- logo locale
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)

        username = st.text_input("Nome utente", key="login_user").strip().lower()
        password = st.text_input("Password", type="password", key="login_pass")
        login_btn = st.button("Entra")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- Validazione ---
    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True
        users = st.secrets["auth"]["users"]
        if username in users and users[username]["password"] == password:
            st.session_state.update({
                "user": username,
                "role": users[username].get("role", "viewer"),
                "logged_in": True
            })
            time.sleep(0.2)
            st.rerun()
        else:
            st.error("❌ Credenziali non valide.")
            st.session_state["_login_checked"] = False

    st.stop()

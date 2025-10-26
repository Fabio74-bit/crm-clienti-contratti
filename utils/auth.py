import streamlit as st
import time

# =====================================
# LOGIN FULLSCREEN — versione 2025 corretta
# =====================================
def do_login_fullscreen():
    """Login elegante con sfondo fullscreen"""
    # Se l’utente è già loggato, ritorna subito
    if st.session_state.get("logged_in"):
        return st.session_state["user"], st.session_state["role"]

    # --- Stile ---
    st.markdown("""
    <style>
    header[data-testid="stHeader"] {
        display: none !important;
    }
    div[data-testid="stAppViewContainer"] {
        padding-top: 0 !important;
        background-color: #f8fafc;
    }
    .block-container {
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        height: 100vh;
    }
    .login-card {
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08);
        padding: 2rem 2.5rem;
        width: 360px;
        text-align: center;
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
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        background-color: #1e4ed8;
    }
    </style>
    """, unsafe_allow_html=True)

    # --- Contenuto del login ---
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)
    st.image("https://i.ibb.co/pnWhbYP/logo-sht.png", width=140)
    st.markdown("<div class='login-title'>Accedi al CRM-SHT</div>", unsafe_allow_html=True)

    username = st.text_input("Nome utente", key="login_user").strip().lower()
    password = st.text_input("Password", type="password", key="login_pass")
    login_btn = st.button("Entra")
    st.markdown("</div>", unsafe_allow_html=True)

    # --- Gestione autenticazione ---
    if login_btn or (username and password and not st.session_state.get("_login_checked")):
        st.session_state["_login_checked"] = True
        try:
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
        except Exception as e:
            st.error(f"⚠️ Errore durante il login: {e}")
            st.session_state["_login_checked"] = False

    # Ferma l’app finché non avviene il login
    st.stop()

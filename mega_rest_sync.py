# =====================================
# mega_rest_sync.py — Gestione cloud MEGA (versione REST compatibile Streamlit Cloud)
# =====================================
import base64
import hashlib
import json
import requests
from pathlib import Path
import streamlit as st

API_URL = "https://g.api.mega.co.nz/cs"

# Utility base64-url encode/decode
def b64url_encode(data: bytes) -> str:
    return base64.b64encode(data).decode().replace("+", "-").replace("/", "_").rstrip("=")

def b64url_decode(data: str) -> bytes:
    data += "=" * (-len(data) % 4)
    return base64.b64decode(data.replace("-", "+").replace("_", "/"))

# =====================================
# 🔑 LOGIN MEGA (email + password)
# =====================================
def mega_login():
    email = st.secrets["mega"]["email"]
    password = st.secrets["mega"]["password"]
    # MEGA usa SHA256 dell'email e password come chiavi di derivazione
    pwdkey = hashlib.sha256(password.encode()).digest()
    payload = [{"a": "us", "user": email, "uh": b64url_encode(hashlib.sha256(pwdkey).digest())}]
    r = requests.post(API_URL, json=payload)
    if not r.ok:
        raise RuntimeError("Connessione MEGA fallita")
    resp = r.json()
    if isinstance(resp, list):
        resp = resp[0]
    if "sid" not in resp:
        raise RuntimeError(f"Login MEGA fallito: {resp}")
    st.session_state["mega_sid"] = resp["sid"]
    return resp["sid"]

def get_sid():
    sid = st.session_state.get("mega_sid")
    if not sid:
        sid = mega_login()
    return sid

# =====================================
# 📂 GESTIONE FILE E UPLOAD/DOWNLOAD
# =====================================
def mega_api_call(payload):
    """Esegue una chiamata API MEGA generica"""
    sid = get_sid()
    r = requests.post(f"{API_URL}?id=1&sid={sid}", json=payload)
    if not r.ok:
        raise RuntimeError(f"Errore API MEGA: {r.text}")
    return r.json()

def list_files():
    """Lista dei file/folder nel root"""
    resp = mega_api_call([{"a": "f", "c": 1}])
    files = resp[0]["f"]
    return files

def upload_file(local_path: Path):
    """⚠️ Simulazione upload: per limiti MEGA REST pubblici, carica tramite MEGA web client"""
    st.warning(f"L'upload REST diretto su MEGA non è ancora pienamente supportato in API pubbliche. "
               f"Carica manualmente {local_path.name} su MEGA/CRM-SHT per ora.")
    return

def download_file(file_name: str, local_dir: Path = Path("storage")):
    """Scarica un file se presente in MEGA root"""
    files = list_files()
    for f in files:
        if f["t"] == 0 and f["a"]["n"] == file_name:
            st.toast(f"📥 File trovato su MEGA: {file_name}")
            # Le API REST pubbliche non forniscono direttamente link di download non autenticati.
            st.info("⚙️ Usa client MEGA ufficiale per il download diretto (API limitate).")
            return
    st.warning(f"⚠️ File non trovato su MEGA: {file_name}")

# =====================================
# 🔁 SINCRONIZZAZIONE BASE (simulazione controllata)
# =====================================
def sync_from_mega():
    """Verifica i file nel root MEGA"""
    try:
        files = list_files()
        found = [f["a"]["n"] for f in files if f["t"] == 0]
        st.success(f"📂 File presenti su MEGA: {', '.join(found)}")
        return found
    except Exception as e:
        st.error(f"❌ Errore durante sync MEGA: {e}")
        return []

def upload_to_mega(local_path: Path):
    """Stub compatibile con versione Box → per ora notifica upload"""
    upload_file(local_path)

def save_preventivo_to_mega(file_path: Path, cliente: str, autore: str):
    """Stub: mostra messaggio come promemoria"""
    st.info(f"📤 Preventivo {file_path.name} pronto per MEGA: {autore}/{cliente}")

def sync_gabriele_files():
    """Stub di sincronizzazione per Gabriele"""
    st.info("🔁 Sincronizzazione simulata file Gabriele su MEGA (API limitate).")

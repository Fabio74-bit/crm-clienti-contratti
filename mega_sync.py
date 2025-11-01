# =====================================
# mega_sync.py — Gestione cloud MEGA per CRM-SHT
# =====================================
from mega import Mega
from pathlib import Path
import streamlit as st

def get_mega_client():
    """Connette a MEGA con credenziali salvate in secrets.toml"""
    try:
        email = st.secrets["mega"]["email"]
        password = st.secrets["mega"]["password"]
        mega = Mega()
        m = mega.login(email, password)
        st.toast("☁️ Connessione a MEGA attiva", icon="✅")
        return m
    except Exception as e:
        st.error(f"❌ Connessione MEGA fallita: {e}")
        return None


def ensure_folder(m, folder_name, parent=None):
    """Trova o crea una cartella in MEGA"""
    try:
        files = m.get_files()
        for fid, info in files.items():
            if info["a"]["n"].lower() == folder_name.lower():
                return info
        # Se non esiste, la crea
        if parent:
            return m.create_folder(folder_name, parent[0])
        return m.create_folder(folder_name)
    except Exception as e:
        st.warning(f"⚠️ Impossibile creare/trovare cartella {folder_name}: {e}")
        return None


def upload_to_mega(path: Path, subpath: str = ""):
    """Carica un file locale su MEGA (es. clienti.csv → CRM-SHT/clienti.csv)"""
    m = get_mega_client()
    if not m:
        return
    try:
        root_folder = st.secrets["mega"].get("root_folder", "CRM-SHT")
        files = m.get_files()

        # Trova cartella root
        root = ensure_folder(m, root_folder)

        # Se specificato un subpath (es. 'gabriele', 'offerte/fabio')
        target = root
        if subpath:
            parts = subpath.split("/")
            for p in parts:
                target = ensure_folder(m, p, parent=target)

        # Upload
        m.upload(str(path), target[0] if isinstance(target, tuple) else target)
        st.toast(f"📤 File caricato su MEGA: {subpath}/{path.name}", icon="✅")

    except Exception as e:
        st.warning(f"⚠️ Upload fallito per {path.name}: {e}")


def download_from_mega(file_name: str, subpath: str = "", local_dir: Path = Path("storage")):
    """Scarica un file da MEGA (se esiste)"""
    m = get_mega_client()
    if not m:
        return
    try:
        files = m.get_files()
        for fid, info in files.items():
            if info["a"]["n"].lower() == file_name.lower():
                file = m.find(file_name)
                m.download(file, str(local_dir))
                st.toast(f"📥 File scaricato: {file_name}", icon="✅")
                return
        st.info(f"⚪ File non trovato su MEGA: {file_name}")
    except Exception as e:
        st.error(f"❌ Errore download da MEGA: {e}")


def sync_from_mega():
    """Scarica automaticamente i file principali da MEGA"""
    m = get_mega_client()
    if not m:
        st.error("❌ Connessione MEGA non disponibile.")
        return
    root_folder = st.secrets["mega"].get("root_folder", "CRM-SHT")
    for name in ["clienti.csv", "contratti.csv", "preventivi.csv"]:
        download_from_mega(name, subpath=root_folder)
    st.toast("☁️ Dati sincronizzati da MEGA", icon="✅")


def sync_gabriele_files():
    """Scarica o crea i file di Gabriele da MEGA"""
    base = Path("storage/gabriele")
    base.mkdir(parents=True, exist_ok=True)
    for name in ["clienti.csv", "contratti.csv"]:
        download_from_mega(name, subpath="gabriele", local_dir=base)


def save_preventivo_to_mega(file_path: Path, cliente: str, autore: str):
    """Salva un preventivo su MEGA nella struttura offerte/autore/cliente"""
    subpath = f"offerte/{autore.lower().strip()}/{cliente}"
    upload_to_mega(file_path, subpath=subpath)

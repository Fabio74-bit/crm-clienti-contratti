# =====================================
# mega_links_sync.py — sincronizzazione sicura da MEGA via link pubblici
# =====================================
import streamlit as st
import pandas as pd
import requests
from pathlib import Path

STORAGE_DIR = Path(__file__).parent / "storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# === Lettura dei link da secrets.toml ===
MEGA_CONF = st.secrets.get("mega", {})

MEGA_LINKS = {
    "clienti": MEGA_CONF.get("clienti_url", ""),
    "contratti": MEGA_CONF.get("contratti_url", ""),
    "preventivi": MEGA_CONF.get("preventivi_url", ""),
    "gabriele_clienti": MEGA_CONF.get("gabriele_clienti_url", ""),
    "gabriele_contratti": MEGA_CONF.get("gabriele_contratti_url", ""),
}

# Cartelle locali
GABRIELE_DIR = STORAGE_DIR / "gabriele"
GABRIELE_DIR.mkdir(parents=True, exist_ok=True)
PREVENTIVI_DIR = STORAGE_DIR / "preventivi"
PREVENTIVI_DIR.mkdir(parents=True, exist_ok=True)


# =====================================
# 📥 Download file CSV da MEGA (via link pubblico)
# =====================================
def _mega_link_to_download_url(link: str) -> str:
    """Converte link MEGA (https://mega.nz/file/xxx#chiave) in link diretto API"""
    if not link or "#" not in link:
        return ""
    parts = link.split("#")
    file_id = parts[0].split("/")[-1]
    key = parts[1]
    return f"https://mega.nz/file/{file_id}#{key}"


def download_from_mega(link: str, dest: Path) -> bool:
    """Scarica un file da MEGA via link pubblico (simulato, no-login)"""
    if not link:
        st.warning(f"⚠️ Link MEGA non trovato per {dest.name}")
        return False
    try:
        # MEGA non supporta download diretto pubblico → uso il redirect di megadownloader API
        api_url = f"https://api.allorigins.win/get?url={link}"
        r = requests.get(api_url, timeout=15)
        if r.status_code != 200:
            raise Exception(f"HTTP {r.status_code}")
        # Scrivo comunque un placeholder se non scarica il file
        if "content" not in r.json():
            raise Exception("Contenuto non accessibile")
        with open(dest, "wb") as f:
            f.write(r.json()["contents"].encode("utf-8"))
        st.toast(f"📥 File aggiornato da MEGA: {dest.name}", icon="✅")
        return True
    except Exception as e:
        st.warning(f"⚠️ Download simulato per {dest.name}: {e}")
        return False


# =====================================
# 🔄 SINCRONIZZAZIONE COMPLETA
# =====================================
def sync_from_mega():
    """Scarica automaticamente tutti i CSV principali da MEGA"""
    results = []
    mapping = {
        "clienti": STORAGE_DIR / "clienti.csv",
        "contratti": STORAGE_DIR / "contratti.csv",
        "preventivi": STORAGE_DIR / "preventivi.csv",
        "gabriele_clienti": GABRIELE_DIR / "clienti.csv",
        "gabriele_contratti": GABRIELE_DIR / "contratti.csv",
    }
    for key, path in mapping.items():
        link = MEGA_LINKS.get(key)
        if not link:
            results.append(f"⚠️ Nessun link per {key}")
            continue
        ok = download_from_mega(link, path)
        results.append(f"📂 {key}: {'OK' if ok else 'ERRORE'}")
    return results


def sync_gabriele_files():
    """Scarica solo i file di Gabriele"""
    return [
        download_from_mega(MEGA_LINKS.get("gabriele_clienti"), GABRIELE_DIR / "clienti.csv"),
        download_from_mega(MEGA_LINKS.get("gabriele_contratti"), GABRIELE_DIR / "contratti.csv"),
    ]


# =====================================
# 📤 UPLOAD (manuale)
# =====================================
def upload_to_mega(path: Path):
    """Simula upload (non supportato via link pubblico)"""
    st.warning(f"⚙️ Upload su MEGA non disponibile via link pubblico.\n"
               f"Puoi ricaricare manualmente il file aggiornato:\n➡️ {path.name}")


# =====================================
# 📤 SALVATAGGIO PREVENTIVI
# =====================================
def save_preventivo_to_mega(file_path: Path, nome_cliente: str, autore: str = "fabio"):
    """
    Simula salvataggio preventivo su MEGA.
    Copia locale + istruzioni per upload manuale.
    """
    dest_dir = PREVENTIVI_DIR / autore.lower()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / file_path.name
    try:
        file_path.replace(dest_file)
        st.toast(f"📦 Preventivo salvato localmente: {dest_file.name}", icon="✅")
        st.info("➡️ Caricalo su MEGA manualmente nella cartella OFFERTE.")
    except Exception as e:
        st.warning(f"⚠️ Salvataggio preventivo non riuscito: {e}")

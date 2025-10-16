"""Utility per riparare `app.py` se contiene artefatti di una patch Git incollata.

Quando un comando `git apply` viene copiato/incollato per errore dentro `app.py`,
Python solleva `SyntaxError: invalid decimal literal` (o errori simili) perché
il file non è più un modulo valido ma contiene testo del diff. Questo script
prova a ricostruire il sorgente corretto estraendo le righe contrassegnate con
`+` o con spazio dal diff incollato.

Uso:
    python scripts/repair_app_from_diff.py            # ripara app.py in-place
    python scripts/repair_app_from_diff.py --dry-run  # mostra l'anteprima

Se il file non contiene artefatti riconosciuti il programma termina senza
apportare modifiche.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

PATCH_HEADER_RE = re.compile(r"^diff --git a/(?P<path>.+) b/(?P=path)$")


def extract_file_from_patch(patch_text: str, target: str) -> Optional[str]:
    """Estrae il contenuto del file *target* da un diff Git incollato.

    Restituisce il testo ricostruito o ``None`` se il patch non contiene il
    file specificato.
    """

    lines = patch_text.splitlines()
    collected: list[str] = []
    in_target = False
    in_hunk = False

    for raw_line in lines:
        line = raw_line.rstrip("\n")

        header_match = PATCH_HEADER_RE.match(line)
        if header_match:
            in_target = header_match.group("path") == target
            in_hunk = False
            continue

        if not in_target:
            continue

        if line.startswith("index "):
            continue
        if line.startswith("--- ") or line.startswith("+++ "):
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if line.startswith("\\ No newline"):
            continue

        if not in_hunk:
            continue

        if line.startswith("+") and not line.startswith("+++"):
            collected.append(line[1:])
        elif line.startswith(" "):
            collected.append(line[1:])
        # Le righe che iniziano con '-' appartengono alla vecchia versione e
        # vengono ignorate. Qualsiasi altra linea viene scartata.

    if not collected:
        return None

    # Assicura la newline finale, in modo coerente con i file di testo.
    return "\n".join(collected) + "\n"


def maybe_repair_file(path: Path, *, dry_run: bool = False) -> bool:
    original = path.read_text(encoding="utf-8")

    # Cerca il blocco diff all'interno del file. Spesso l'utente incolla anche
    # il comando `(cd ... git apply <<'EOF'`, quindi scartiamo tutto ciò che
    # precede la prima occorrenza di ``diff --git``.
    marker = "diff --git "
    if marker not in original:
        return False

    patch_text = original.split(marker, 1)[1]
    patch_text = marker + patch_text

    repaired = extract_file_from_patch(patch_text, path.name)
    if repaired is None or repaired.strip() == "":
        return False

    if dry_run:
        print(repaired)
        return True

    path.write_text(repaired, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Ripara file contaminati da diff Git incollati.")
    parser.add_argument(
        "path",
        nargs="?",
        default="app.py",
        type=Path,
        help="Percorso del file da ripristinare (default: app.py)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostra l'output previsto senza modificare il file",
    )
    args = parser.parse_args()

    target_path: Path = args.path
    if not target_path.exists():
        parser.error(f"Il file {target_path} non esiste.")

    repaired = maybe_repair_file(target_path, dry_run=args.dry_run)
    if repaired:
        action = "Anteprima generata" if args.dry_run else "File riparato"
        print(f"✅ {action}: {target_path}")
    else:
        print(f"ℹ️ Nessun artefatto diff riconosciuto in {target_path}.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Réduit chaque dossier de fruits à 5 images les plus différentes possibles (hachage perceptuel) 
avec journalisation détaillée pour le débogage.

- Dépendances : pillow, imagehash, numpy, tqdm
- Python ≥ 3.8 (testé 3.10)
- Auteur : ChatGPT – 20 juin 2025
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Tuple

import numpy as np
from PIL import Image
import imagehash
from tqdm import tqdm

# ========= CONFIGURATION ========= #
ROOT_DIR = Path("data/Test1")  # <-- à personnaliser
HASH_SIZE = 16                 # 16×16 bits → phash de 256 bits
KEEP = 5                       # nombre d’images à conserver
MAX_WORKERS = os.cpu_count() or 4
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}
VERBOSE = True                 # Mettre False pour désactiver la verbosité
# ================================= #


def log(msg: str) -> None:
    """Affiche un message si VERBOSE=True."""
    if VERBOSE:
        print(msg)


# ---------------------------------------------------------------------------
# Utilitaires de hachage
# ---------------------------------------------------------------------------

def compute_phash(img_path: Path) -> np.ndarray | None:
    """Retourne le hachage perceptuel (tableau plat de uint8) ou None si erreur."""
    try:
        with Image.open(img_path) as im:
            im_hash = imagehash.phash(im, hash_size=HASH_SIZE)
        # im_hash.hash est un array bool (HASH_SIZE, HASH_SIZE) → on le met à plat.
        return im_hash.hash.flatten().astype(np.uint8)
    except Exception as e:
        log(f"❌ Erreur phash pour {img_path.name}: {e}")
        return None


# ---------------------------------------------------------------------------
# Algorithme de sélection Farthest‑First Traversal
# ---------------------------------------------------------------------------

def best_diverse_subset(hashes: np.ndarray, k: int = KEEP) -> List[int]:
    """Renvoie les indices des k éléments maximisant la diversité (distance de Hamming)."""
    n = len(hashes)
    if n <= k:
        return list(range(n))

    # Calcul matrice de distances Hamming (n × n) – chaque entrée est sur [0, 256]
    # hashes.shape -> (n, 256)
    diff = hashes[:, None] ^ hashes   # (n, n, 256)
    H = diff.sum(axis=2, dtype=np.uint16)  # (n, n)

    # 1) image la plus « centrale » (somme des distances max)
    central = int(np.argmax(H.sum(axis=1)))
    current = [central]
    remaining = set(range(n)) - {central}

    # 2) itérations gloutonnes
    for _ in range(1, k):
        rem_list = list(remaining)
        # distance min à l’ensemble choisi
        min_dists = H[np.ix_(rem_list, current)].min(axis=1)
        next_idx = rem_list[int(np.argmax(min_dists))]
        current.append(next_idx)
        remaining.remove(next_idx)

    return current


# ---------------------------------------------------------------------------
# Parcours et traitement des dossiers
# ---------------------------------------------------------------------------

def process_folder(folder: Path) -> int:
    """Conserve uniquement KEEP images les plus différentes dans *folder*.
    Retourne le nombre de fichiers supprimés.
    """
    log(f"\n📂 Analyse du dossier : {folder}")

    image_paths = sorted([
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    ])

    log(f" - {len(image_paths)} fichier(s) image détecté(s).")
    for p in image_paths:
        log(f"   📄 {p.name}")

    if len(image_paths) <= KEEP:
        log(f" ➤ {len(image_paths)} ≤ {KEEP} → aucune suppression.")
        return 0

    # 1. Calcul des hachages (parallélisé)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as exe:
        hashes_list = list(exe.map(compute_phash, image_paths))

    # Filtre images valides
    valid_pairs: List[Tuple[Path, np.ndarray]] = [
        (p, h) for p, h in zip(image_paths, hashes_list) if h is not None
    ]

    if not valid_pairs:
        log(" ⚠️ Aucune image lisible trouvée → on saute ce dossier.")
        return 0

    if len(valid_pairs) <= KEEP:
        log(f" ➤ {len(valid_pairs)} images valides (≤ {KEEP}) → on garde tout.")
        return 0

    log(f" - {len(valid_pairs)} image(s) valides :")
    for p, _ in valid_pairs:
        log(f"   ✅ {p.name}")

    image_paths_valid, hashes_valid = zip(*valid_pairs)
    hashes_arr = np.stack(hashes_valid, axis=0)  # (n, 256)

    # 2. Sélection des images à conserver
    keep_indices = best_diverse_subset(hashes_arr, k=KEEP)
    keep_set = {image_paths_valid[i] for i in keep_indices}

    log(" - Images conservées :")
    for p in keep_set:
        log(f"   🛡️ {p.name}")

    # 3. Suppression des autres
    deleted = 0
    for p in image_paths_valid:
        if p not in keep_set:
            try:
                p.unlink()
                log(f"   🗑️ Suppression : {p.name}")
                deleted += 1
            except Exception as e:
                print(f"⚠️ Impossible de supprimer {p}: {e}", file=sys.stderr)

    return deleted


def walk_fruit_folders(root: Path) -> None:
    """Parcourt récursivement *root* et appelle process_folder sur chaque dossier contenant des images."""
    folders_to_process: List[Path] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        if any(f.lower().endswith(tuple(EXTENSIONS)) for f in filenames):
            folders_to_process.append(Path(dirpath))

    total_deleted = 0
    for folder in tqdm(folders_to_process, desc="Traitement des dossiers"):
        total_deleted += process_folder(folder)

    print(f"\n✅ Terminé ! {total_deleted} fichier(s) supprimé(s).")


if __name__ == "__main__":
    if not ROOT_DIR.exists():
        sys.exit(f"Erreur : ROOT_DIR n’existe pas ({ROOT_DIR})")

    walk_fruit_folders(ROOT_DIR)

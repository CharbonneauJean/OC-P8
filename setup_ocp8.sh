#!/usr/bin/env bash
set -euo pipefail

# ── Détection du bon utilisateur et son HOME ─────────────
REAL_USER="${SUDO_USER:-$USER}"
USER_HOME=$(eval echo "~$REAL_USER")

# ── Paramètres personnalisés ─────────────────────────────
REPO_URL="https://github.com/CharbonneauJean/OC-P8"
ENV_NAME="ocp8_env"
PY_VERSION="3.10"
CONDA_ROOT="$USER_HOME/miniconda3"
CONDA_BIN="$CONDA_ROOT/bin/conda"
WORKSPACE="$USER_HOME/Workspace"
BASHRC="$USER_HOME/.bashrc"

# ── Dépendances système ─────────────────────────────────
echo "🔄  Mise à jour APT et dépendances de base…"
apt-get update -y
apt-get install -y git wget curl bzip2 ca-certificates \
                   openjdk-17-jdk-headless build-essential \
                   libglib2.0-0 libxext6 libsm6 libxrender1

# ── Création du dossier Workspace ────────────────────────
echo "📁  Création du dossier $WORKSPACE"
mkdir -p "$WORKSPACE"
chown "$REAL_USER":"$REAL_USER" "$WORKSPACE"

# ── Clonage du projet Git ───────────────────────────────
if [[ ! -d "$WORKSPACE/OC-P8" ]]; then
  echo "⬇️  Clonage du projet OC-P8…"
  sudo -u "$REAL_USER" git clone "$REPO_URL" "$WORKSPACE/OC-P8"
else
  echo "ℹ️  Le dépôt existe déjà, skip."
fi

# ── Installation silencieuse de Miniconda ───────────────
if [[ ! -x "$CONDA_BIN" ]]; then
  echo "🐍 Installation de Miniconda dans $CONDA_ROOT …"
  sudo -u "$REAL_USER" wget -qO /tmp/miniconda.sh \
       https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  sudo -u "$REAL_USER" bash /tmp/miniconda.sh -b -p "$CONDA_ROOT"
  echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> "$BASHRC"
  rm /tmp/miniconda.sh
fi

# ── Charge conda.sh pour ce shell root ──────────────────
source "$CONDA_ROOT/etc/profile.d/conda.sh"

# ── (Re)création de l’environnement virtuel ─────────────
if conda env list | grep -q "$ENV_NAME"; then
  echo "♻️  Suppression ancienne env $ENV_NAME …"
  conda env remove -y -n "$ENV_NAME"
fi

echo "🆕  Création de l'env $ENV_NAME (python $PY_VERSION)…"
conda create -y -n "$ENV_NAME" python="$PY_VERSION"

# ── Activation env & installation des packages ──────────
echo "📦  Installation des bibliothèques (conda + pip)…"
conda activate "$ENV_NAME"

conda install -y pandas pillow pyarrow jupyter notebook
pip install --no-cache-dir pyspark==3.5.5
pip install --no-cache-dir 'tensorflow==2.16.*'
conda clean -afy

# ── Alias d'activation rapide ajouté au .bashrc ─────────
cat <<EOS >> "$BASHRC"

# >>> OC-P8 helper >>>
alias ocp8_activate='source ~/miniconda3/etc/profile.d/conda.sh && conda activate ocp8_env && cd ~/Workspace/OC-P8'
# <<< OC-P8 helper <<<
EOS

echo
echo "✅ Installation terminée."
echo "------------------------------------------------------"
echo "Pour travailler :"
echo " 1) Ouvre un terminal ou exécute :"
echo "     source ~/miniconda3/etc/profile.d/conda.sh"
echo "     conda activate $ENV_NAME"
echo " 2) Va dans le dossier :"
echo "     cd ~/Workspace/OC-P8"
echo " 3) Lance Jupyter :"
echo "     jupyter notebook --ip 0.0.0.0 --no-browser"
echo "------------------------------------------------------"

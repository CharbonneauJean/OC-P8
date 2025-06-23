#!/bin/bash
set -e -x

# Install required libraries system-wide to avoid PATH issues
sudo python3 -m pip install \
    pandas \
    numpy \
    pillow \
    pyarrow \
    matplotlib \
    seaborn \
    scikit-learn \
    h5py

# Install TensorFlow separately to handle potential conflicts
sudo python3 -m pip install 'tensorflow==2.15.0'
#!/usr/bin/env bash

cd /home/ubuntu

source /home/ubuntu/miniconda3/etc/profile.d/conda.sh

conda activate ocp8_env

cd /home/ubuntu/Workspace/OC-P8

jupyter notebook --ip 0.0.0.0 --no-browser



#!/bin/bash
export $(grep -v '^#' .env | xargs)
echo "Starting Umbral Bot..."
python3 main.py

#!/bin/bash
echo "Starting Content Master backend..."
cd backend
pip install -r requirements.txt
python app.py

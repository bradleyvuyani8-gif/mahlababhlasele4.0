#!/data/data/com.termux/files/usr/bin/bash

termux-wake-lock

uvicorn backend.main:app \
--host 0.0.0.0 \
--port 8000 \
--workers 1

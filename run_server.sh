#!/bin/bash
# Builds the frontend and starts the backend API.
# It also serves the frontend statically using FastAPI.

echo "Building frontend..."
cd web
npm install
npm run build
cd ..

echo "Starting backend API server..."
export PYTHONPATH=$PYTHONPATH:.
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000

#!/bin/sh
# Start Ollama server in background, pull the model, then keep running
ollama serve &

# Wait for server to be ready
echo "Waiting for Ollama server to start..."
until curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; do
  sleep 1
done
echo "Ollama server is ready."

# Pull the vision model if not already present
echo "Pulling qwen2.5vl:3b model..."
ollama pull qwen2.5vl:3b
echo "Model ready."

# Keep the server running in foreground
wait

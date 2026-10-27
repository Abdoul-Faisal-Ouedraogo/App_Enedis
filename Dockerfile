# Use Python 3.13 slim image as base
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV package manager
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies using UV
RUN uv sync --frozen

# Copy application code
COPY . .

# Expose Streamlit and FastAPI ports
EXPOSE 8501
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV FASTAPI_HOST=0.0.0.0
ENV FASTAPI_PORT=8000

# Create startup script that launches BOTH FastAPI and Streamlit
RUN echo '#!/bin/bash\n\
    set -e\n\
    \n\
    # Create Streamlit secrets if MAPBOX_API_KEY is provided\n\
    if [ -n "${MAPBOX_API_KEY}" ]; then\n\
    mkdir -p .streamlit\n\
    echo "MAPBOX_API_KEY = \"${MAPBOX_API_KEY}\"" > .streamlit/secrets.toml\n\
    fi\n\
    \n\
    # Start FastAPI backend in background (exposed publicly)\n\
    echo "Starting FastAPI backend..."\n\
    uv run uvicorn backend.main:app --host 0.0.0.0 --port 8000 &\n\
    FASTAPI_PID=$!\n\
    \n\
    # Wait for FastAPI to be ready\n\
    echo "Waiting for FastAPI to start..."\n\
    sleep 3\n\
    \n\
    # Start Streamlit frontend (exposed)\n\
    echo "Starting Streamlit frontend..."\n\
    uv run streamlit run home.py --server.port=8501 --server.address=0.0.0.0\n\
    \n\
    # If Streamlit exits, kill FastAPI\n\
    kill $FASTAPI_PID 2>/dev/null || true\n\
    ' > /app/start.sh && chmod +x /app/start.sh

# Run the application
CMD ["/app/start.sh"]
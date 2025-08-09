FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY pyproject.toml ./
RUN pip install uv
RUN uv pip install --system fastmcp pydantic rich google-generativeai requests fastapi uvicorn

# Copy application code
COPY . .

# Create config from sample (users will need to set their API key)
RUN cp config.json.sample config.json

# Set default environment variables
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Create directory for mounted volume
RUN mkdir -p /data

# Don't initialize database in build - it will be on mounted volume

# Expose port for unified server
EXPOSE 8000

# Create an entrypoint script to handle database initialization
RUN echo '#!/bin/bash\n\
if [ ! -f "/data/signals_agent.db" ]; then\n\
    echo "Initializing database..."\n\
    python database.py\n\
fi\n\
exec "$@"' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Use entrypoint to ensure database exists
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command runs the unified server
CMD ["uvicorn", "unified_server:app", "--host", "0.0.0.0", "--port", "8000"]
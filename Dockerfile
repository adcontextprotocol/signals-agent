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

# Initialize database
RUN python database.py

# Expose port for unified server
EXPOSE 8000

# Run the unified server supporting both MCP and A2A protocols  
CMD ["uvicorn", "unified_server:app", "--host", "0.0.0.0", "--port", "8000"]
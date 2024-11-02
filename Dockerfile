FROM python:3.11-slim

LABEL maintainer="Your Name <your@email.com>"
LABEL description="Python Script Controller for Unraid"

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7447 \
    VIRTUAL_ENV=/venv \
    FLASK_ENV=production

# Set work directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Create and activate virtual environment
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /scripts /logs /venv && \
    chmod -R 755 /scripts /logs /venv

# Volume configuration
VOLUME ["/scripts", "/logs", "/venv"]

# Expose port
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/ || exit 1

# Start the application
CMD ["python", "app.py"]

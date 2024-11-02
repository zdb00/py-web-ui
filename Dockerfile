# Dockerfile
FROM python:3.11-slim

# Install git
RUN apt-get update && \
    apt-get install -y git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Clone the repository (this will be replaced with your repo URL)
ARG REPO_URL=https://github.com/zdb00/py-web-ui/
ARG REPO_BRANCH=main

# Clone specific branch and remove .git directory to keep image size down
RUN git clone --branch ${REPO_BRANCH} ${REPO_URL} . && \
    rm -rf .git

# Install controller requirements
RUN pip install -r requirements.txt

# Create virtual environment for user scripts
ENV VIRTUAL_ENV=/venv
RUN python -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Volume configuration
VOLUME ["/scripts", "/logs", "/venv"]

# Default port (can be overridden in Unraid)
ENV PORT=7447
EXPOSE ${PORT}

# Start the application
CMD ["python", "app.py"]

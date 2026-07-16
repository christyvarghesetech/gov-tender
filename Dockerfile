# Use a lightweight official Python image
FROM python:3.11-slim

# Set environment variables
# Prevent Python from writing .pyc files to disc
ENV PYTHONDONTWRITEBYTECODE=1
# Prevent Python from buffering stdout and stderr
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# Install system dependencies if required (psycopg2-binary is used, so we don't need pg_config or libpq-dev)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage Docker cache
COPY backend/requirements.txt /app/backend/requirements.txt

# Install python dependencies
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend and frontend codebase into the container
# This preserves the directory structure:
# /app/backend
# /app/frontend
COPY backend /app/backend
COPY frontend /app/frontend
COPY esignet /app/esignet

# Ensure the uploads directory exists
RUN mkdir -p /app/backend/uploads

# Expose the port FastAPI will run on
EXPOSE 8080

# Change working directory to backend so uvicorn can find app.main
WORKDIR /app/backend

# Run FastAPI app using uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

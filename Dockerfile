# chore_chart_project/Dockerfile

# Use an official Python runtime as a parent image
# Using python:3.9-slim as a base for a smaller image size.
FROM python:3.14.0rc1-slim

# Set the working directory in the container to /app
WORKDIR /app

# Copy the requirements.txt file into the container at /app
# This is done first to leverage Docker's layer caching. If requirements.txt
# doesn't change, this layer won't be rebuilt.
COPY requirements.txt .

# Install any needed Python packages specified in requirements.txt
# --no-cache-dir reduces image size by not storing the pip cache.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code (app.py, templates, static)
# into the container at /app
COPY . .

# Make port 5000 available to the world outside this container.
# This is the port Gunicorn will listen on.
EXPOSE 5000

# Define environment variables.
# ADMIN_PASSWORD can be overridden at runtime using `docker run -e`.
ENV ADMIN_PASSWORD="supersecret"
# FLASK_APP tells Flask which file to run (primarily for 'flask run' command).
ENV FLASK_APP=app.py
# FLASK_RUN_HOST makes the Flask dev server (if used) accessible externally.
ENV FLASK_RUN_HOST=0.0.0.0
# Explicitly add the working directory to PYTHONPATH.
# This helps Gunicorn and Python's import system locate the 'app' module.
ENV PYTHONPATH /app

# Command to run the application.
# Uses Gunicorn for a more production-ready WSGI server.
# -b 0.0.0.0:5000 binds Gunicorn to all network interfaces on port 5000.
# app:app refers to the Flask application instance 'app' in the 'app.py' file.
#
# The app.py script now handles DB initialization on startup if the DB file doesn't exist.
# For more complex initialization (e.g., migrations), an entrypoint script
# that runs `flask initdb` (or other commands) before starting Gunicorn would be more robust.
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

# Alternative command for development using Flask's built-in server (if Gunicorn is not preferred for dev):
# CMD ["flask", "run"]
# Note: If using `flask run`, ensure FLASK_APP and FLASK_RUN_HOST are set.
# Also, `flask run` is generally not recommended for production.

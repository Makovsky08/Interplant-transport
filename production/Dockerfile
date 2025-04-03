FROM python:3.9

# This is the full Python image which includes more dependencies
# But you'll still need the Microsoft drivers if you're connecting to SQL Server:
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Nastavení proxy pro sestavení
ENV DASH_BASE_PATHNAME=/rcmpsp/results/


WORKDIR /app

# Copy requirements file
COPY requirements.txt .


# Install dependencies
RUN pip install --no-cache-dir --timeout=600 -r requirements.txt

# Copy application code
COPY . .

# Make sure the data directory exists for SQLite
RUN mkdir -p /app/data
RUN mkdir -p /app/static/uploads
RUN mkdir -p /app/static/exports
RUN mkdir -p /var/log/gunicorn

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/SchedLine.db


# Expose port for the application
EXPOSE 5000

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create log directory
RUN mkdir -p /var/log/gunicorn

#CMD ["python", "-c", "import app; print('Import successful'); import gunicorn.app.wsgiapp; gunicorn.app.wsgiapp.run()"]

# Command to run the application with Gunicorn including logging
# Use 4 worker processes (can be adjusted based on your server's CPU cores)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--timeout", "60", "--access-logfile", "/var/log/gunicorn/access.log", "--error-logfile", "/var/log/gunicorn/error.log", "app:app"]


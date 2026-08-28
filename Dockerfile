FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port (Google Cloud Run provides the PORT environment variable, usually 8080)
ENV PORT=8080
EXPOSE $PORT

# Change working directory to src where app.py is located
WORKDIR /app/src

# Run Streamlit with Cloud Run specific settings
CMD streamlit run src/app.py --server.port=${PORT} --server.address=0.0.0.0 --server.headless=true --server.enableCORS=false

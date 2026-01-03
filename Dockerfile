# Use the official Playwright image which includes Python and Browser dependencies
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy all files from your local directory to the container
COPY . .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Install the Chromium browser engine
RUN playwright install chromium

# Expose the port FastAPI will run on
EXPOSE 8080

# Command to run the application using Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
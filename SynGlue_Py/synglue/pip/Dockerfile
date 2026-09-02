# Use an official Python runtime as the base image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /app

# Copy necessary files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir .

# Set the default command to run when the container starts
CMD ["python"]

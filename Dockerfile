# Use official Python image
FROM python:3.12-slim

# Set working directory
WORKDIR /code

# Copy only pyproject.toml first (to leverage Docker cache)
COPY pyproject.toml /code/

# Install dependencies from pyproject.toml
RUN pip install --upgrade pip \
    && pip install .

# Copy the rest of the application code
COPY . /code

# Use exec form for proper signal handling
CMD ["fastapi", "run", "app.py", "--port", "10500", "--reload"]

# --- ULTIMATE FALLBACK DOCKERFILE ---
# Use a standard Ubuntu base image
FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Update, add the official UbuntuGIS PPA for up-to-date geospatial libraries,
# and install GDAL, its Python bindings, and pip.
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:ubuntugis/ppa && \
    apt-get update && \
    apt-get install -y gdal-bin python3-gdal python3-pip && \
    rm -rf /var/lib/apt/lists/*

# Now, continue with the rest of the application setup
WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

COPY ./app /app/app

RUN mkdir -p /app/data/raw && mkdir -p /app/data/processed

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
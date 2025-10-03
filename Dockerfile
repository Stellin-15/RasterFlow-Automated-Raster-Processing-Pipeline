# 1. Use an official base image that has GDAL pre-installed.
# This saves a huge amount of time and avoids compilation errors.
FROM osgeo/gdal:ubuntu-small-latest

# 2. Set the working directory inside the container
WORKDIR /app

# 3. Install Python and Pip
RUN apt-get update && apt-get install -y python3-pip gdal-bin python3-gdal && \
    rm -rf /var/lib/apt/lists/*

# 4. Copy and install Python requirements
COPY ./requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r requirements.txt

# 5. Copy the application code into the container
COPY ./app /app/app

# 6. Create data directories inside the container (though we will mount them)
RUN mkdir -p /app/data/raw && mkdir -p /app/data/processed

# 7. Expose the port the app will run on
EXPOSE 8000

# 8. Define the command to run the application using Uvicorn
# The --reload flag is great for development
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
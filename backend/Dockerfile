FROM python:3.12-slim

WORKDIR /app

# Configure pip to use Tsinghua mirror
#RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
#    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set script execution permissions
RUN chmod +x run.sh

# Set environment variables
ENV PYTHONPATH=/app

# Expose port
EXPOSE 8000

# Start command
CMD ["./run.sh"] 
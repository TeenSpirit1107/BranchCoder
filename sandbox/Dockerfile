FROM ubuntu:22.04

# Avoid interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Set hostname to sandbox
ENV HOSTNAME=sandbox

# Update and install basic tools
RUN apt-get update && apt-get install -y \
    sudo \
    bc \
    curl \
    wget \
    gnupg \
    software-properties-common \
    xvfb \
    x11vnc \
    xterm \
    socat \
    supervisor \
    websockify \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install system dependencies for data analysis packages
RUN apt-get update && apt-get install -y \
    build-essential \
    gfortran \
    libopenblas-dev \
    liblapack-dev \
    libatlas-base-dev \
    libhdf5-dev \
    pkg-config \
    libfreetype6-dev \
    libpng-dev \
    libjpeg-dev \
    libffi-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncurses5-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libgdbm-dev \
    libc6-dev \
    libbz2-dev \
    libffi-dev \
    liblzma-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Rust toolchain for compiling dependencies like cryptography
ENV PATH="/root/.cargo/bin:${PATH}"
RUN curl https://sh.rustup.rs -sSf | sh -s -- -y

# Create user ubuntu and grant sudo privileges
RUN useradd -m -d /home/ubuntu -s /bin/bash ubuntu && \
    echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu

# Install Python 3.10.12
RUN add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.10 python3.10-venv python3.10-dev python3-pip && \
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20.18.0
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install VS Code Server
RUN curl -fsSL https://code-server.dev/install.sh | sh && \
    mkdir -p /home/ubuntu/.config/code-server && \
    chown -R ubuntu:ubuntu /home/ubuntu/.config

# Install Google Chrome
RUN add-apt-repository ppa:xtradeb/apps -y && \
    apt-get update && \
    apt-get install -y chromium  --no-install-recommends && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install Chinese fonts and language support
RUN apt-get update && apt-get install -y \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    language-pack-zh-hans \
    locales \
    && locale-gen zh_CN.UTF-8 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install document processing tools
RUN apt-get update && apt-get install -y \
    pandoc \
    poppler-utils \
    libreoffice \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set default locale
ENV LANG=zh_CN.UTF-8 \
    LANGUAGE=zh_CN:zh \
    LC_ALL=zh_CN.UTF-8

# Add uv/uvx and npm global packages to PATH
ENV PATH="/root/.local/bin:/home/ubuntu/.local/bin:$PATH"
# Share playwright browsers path between users to avoid double downloads
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Enable debug mode for uv/uvx
ENV UV_VERBOSITY=3

# Set working directory
WORKDIR /app

# Configure pip and uv mirrors (Tsinghua University)
ENV UV_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
ENV UV_TRUSTED_HOST="pypi.tuna.tsinghua.edu.cn"
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /root/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /root/.pip/pip.conf && \
    mkdir -p /home/ubuntu/.pip && \
    echo "[global]" > /home/ubuntu/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /home/ubuntu/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /home/ubuntu/.pip/pip.conf && \
    chown -R ubuntu:ubuntu /home/ubuntu/.pip

# Copy project files (copy dependency files first to leverage cache)
COPY requirements.txt .

# # 升级 pip / setuptools / wheel，避免构建 kiwisolver 等包时报错
# RUN pip3 install --no-cache-dir -U pip setuptools wheel packaging build

# # Install Python dependencies
# RUN pip3 install --no-cache-dir -r requirements.txt

# # # Pre-install common MCP servers to avoid runtime timeouts
# # RUN pip3 install --no-cache-dir \
# #     mcp-server-sis \
# #     mcp-server-booking \
# #     mcp-server-time \
# #     mcp-server-email-cuhksz

# Install uv and uvx for Python package management
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> /home/ubuntu/.bashrc && \
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> /root/.bashrc && \
    /root/.local/bin/uv --version

# 让 uv 将受管 Python 安装到对 ubuntu 可访问的位置
ENV UV_PYTHON_INSTALL_DIR=/opt/uv_python

# 使用 uv 安装 Python 3.13 并创建独立 venv（不修改系统 Python 3.10）
RUN /root/.local/bin/uv python install 3.13 && \
    /root/.local/bin/uv venv -p 3.13 /opt/py313 && \
    /opt/py313/bin/python --version && \
    /opt/py313/bin/python -m ensurepip --upgrade && \
    /opt/py313/bin/python -m pip --version

# 确保 uv Python 安装目录对 ubuntu 可读可执行
RUN chown -R ubuntu:ubuntu /opt/uv_python || true && \
    chmod -R a+rX /opt/uv_python

# 让运行时优先使用 3.13 venv
ENV VIRTUAL_ENV=/opt/py313
ENV PATH="/opt/py313/bin:$PATH"

# 在 3.13 venv 中安装 Python 依赖
RUN /opt/py313/bin/python -m pip install --no-cache-dir -r /app/requirements.txt

# Ensure ubuntu user can execute and access the 3.13 venv binaries
RUN chown -R ubuntu:ubuntu /opt/py313 && \
    chmod -R a+rx /opt/py313/bin

# Ensure uvx and npx are available for the ubuntu user
RUN su - ubuntu -c "curl -LsSf https://astral.sh/uv/install.sh | sh" && \
    chown -R ubuntu:ubuntu /home/ubuntu/.local 2>/dev/null || true && \
    su - ubuntu -c "echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc" && \
    su - ubuntu -c "/home/ubuntu/.local/bin/uv --version"

# Install patchright browsers with all required Linux dependencies
# This will apt-install system libraries like libgtk-4-1, libvpx7, libwebpdemux2, etc.
RUN /opt/py313/bin/python -m patchright install --with-deps chromium && \
    chown -R ubuntu:ubuntu /ms-playwright || true

# Verify npx is available (comes with Node.js)
RUN npx --version && \
    su - ubuntu -c "npx --version"

# Copy remaining project files
COPY . .

# Copy VS Code Server configuration
COPY code-server-config.yaml /home/ubuntu/.config/code-server/config.yaml
RUN chown ubuntu:ubuntu /home/ubuntu/.config/code-server/config.yaml

# Configure supervisor
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# Expose ports
EXPOSE 8080 9222 5900 5901 8443

ENV UVI_ARGS=""
ENV CHROME_ARGS=""

WORKDIR /home/ubuntu

# Use supervisor to start all services
CMD ["supervisord", "-n", "-c", "/app/supervisord.conf"] 
# Configure domestic mirror sources for faster downloads in China
# Configure apt mirror (Tsinghua University)
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy main restricted universe multiverse" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-updates main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-backports main restricted universe multiverse" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/ubuntu/ jammy-security main restricted universe multiverse" >> /etc/apt/sources.list

# Configure pip mirror (Tsinghua University)
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /root/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /root/.pip/pip.conf && \
    mkdir -p /home/ubuntu/.pip && \
    echo "[global]" > /home/ubuntu/.pip/pip.conf && \
    echo "index-url = https://pypi.tuna.tsinghua.edu.cn/simple" >> /home/ubuntu/.pip/pip.conf && \
    echo "trusted-host = pypi.tuna.tsinghua.edu.cn" >> /home/ubuntu/.pip/pip.conf && \
    chown -R ubuntu:ubuntu /home/ubuntu/.pip

# Configure npm mirror (Taobao)
RUN npm config set registry https://registry.npmmirror.com && \
    su - ubuntu -c "npm config set registry https://registry.npmmirror.com"

# Configure yarn mirror (if yarn is installed)
RUN if command -v yarn >/dev/null 2>&1; then \
        yarn config set registry https://registry.npmmirror.com && \
        su - ubuntu -c "yarn config set registry https://registry.npmmirror.com"; \
    fi 

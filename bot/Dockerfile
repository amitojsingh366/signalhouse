FROM python:3.11-slim

# Install TA-Lib C library (required by ta-lib Python package via trader-api)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make wget && \
    wget -q https://github.com/TA-Lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz && \
    tar xzf ta-lib-0.6.4-src.tar.gz && \
    cd ta-lib-0.6.4 && \
    ./configure --prefix=/usr && \
    make -j$(nproc) && make install && \
    cd .. && rm -rf ta-lib-0.6.4 ta-lib-0.6.4-src.tar.gz && \
    apt-get purge -y gcc g++ make wget && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install api package first (bot depends on it)
COPY api/pyproject.toml /app/api/pyproject.toml
COPY api/src/ /app/api/src/
RUN pip install --no-cache-dir /app/api

# Install bot package
COPY bot/pyproject.toml /app/bot/pyproject.toml
COPY bot/src/ /app/bot/src/
RUN pip install --no-cache-dir /app/bot

# Optional start guard: skip bot boot when Discord vars are missing
COPY bot/docker-entrypoint.sh /usr/local/bin/bot-entrypoint.sh
RUN chmod +x /usr/local/bin/bot-entrypoint.sh

# Config directory mounted as volume at runtime
RUN mkdir -p /app/config

CMD ["/usr/local/bin/bot-entrypoint.sh"]

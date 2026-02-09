FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc curl && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv sync --no-dev

COPY src/ ./src/
RUN mkdir -p logs

CMD ["/root/.local/bin/uv", "run", "python", "src/app_mcp.py"]

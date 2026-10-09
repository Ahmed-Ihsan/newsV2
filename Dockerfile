FROM python:3.12-slim

LABEL maintainer="Jane-o-O-o-O" \
      description="Trend Radar — Multi-source tech intelligence CLI + Web Dashboard" \
      version="0.5.0"

WORKDIR /app

# Install dependencies first for better caching
COPY pyproject.toml README.md LICENSE ./
COPY trend_radar/ trend_radar/

RUN pip install --no-cache-dir ".[all]" && \
    rm -rf /root/.cache

# Create data directory
RUN mkdir -p /data/.trend-radar && \
    ln -sf /data/.trend-radar /root/.trend-radar

EXPOSE 8765

# Default: start web dashboard
# Override with: docker run trend-radar trend-radar fetch
ENTRYPOINT ["trend-radar"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8765", "--no-browser"]

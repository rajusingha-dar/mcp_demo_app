FROM python:3.11-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy only mcp_server contents
COPY mcp_server/ .

# Install dependencies using UV
RUN uv sync

# Expose SSE port
EXPOSE 8000

# Run the MCP server
CMD ["uv", "run", "python", "server.py"]
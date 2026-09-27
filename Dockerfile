# AgentCore Runtime requires linux/arm64 images.
# Build with: docker build --platform linux/arm64 -t customer-support-agent .
FROM --platform=linux/arm64 python:3.11-slim

WORKDIR /app

# Install only the core (deployment) dependencies from pyproject.toml —
# local_api.py's fastapi/uvicorn extra is a dev-only convenience and is not
# needed by the deployed agent (bedrock_agentcore already pulls in the
# uvicorn/starlette it needs to serve the entrypoint).
COPY pyproject.toml ./
RUN pip install --no-cache-dir .

# Only the modules the deployed agent actually uses — not local_api.py,
# tests/, or docs.
COPY config.py tools.py db.py graph.py agentcore_app.py ./

EXPOSE 8080

CMD ["python", "agentcore_app.py"]

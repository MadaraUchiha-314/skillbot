FROM python:3.13-slim
RUN apt-get update && apt-get install -y nodejs npm bash curl && rm -rf /var/lib/apt/lists/*
RUN npm install -g tsx
RUN useradd -m -u 1000 skillbot
USER skillbot
WORKDIR /workspace

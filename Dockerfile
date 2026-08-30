FROM python:3.12-slim
WORKDIR /app
COPY server.py CHARTER.md PRIMER.md treasury.example.json ./
ENV BAZAAR_HOST=0.0.0.0
ENV BAZAAR_PORT=8787
EXPOSE 8787
CMD ["python3", "server.py"]

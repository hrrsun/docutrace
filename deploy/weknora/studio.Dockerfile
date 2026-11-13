FROM wechatopenai/weknora-docreader:v0.9.0
WORKDIR /workspace
RUN uv pip install --python /app/.venv/bin/python fastapi==0.140.0 uvicorn==0.51.0 cryptography==46.0.3 requests==2.34.2 python-multipart==0.0.32 PyMuPDF==1.28.0 numpy==2.2.6
COPY studio/ ./studio/
COPY examples/course-calculus.md examples/course-machine-learning.md ./examples/
COPY ingest.py engine.py local_model.py activity.py weknora_import.py ./
RUN mkdir -p /data && chown 65534:65534 /data
USER 65534:65534
ENTRYPOINT ["/app/.venv/bin/python","-m","uvicorn"]
CMD ["studio.api:app","--host","0.0.0.0","--port","8711","--no-access-log"]

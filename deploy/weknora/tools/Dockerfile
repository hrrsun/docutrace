FROM wechatopenai/weknora-docreader:v0.9.0
WORKDIR /service
RUN uv pip install --python /app/.venv/bin/python mcp==1.26.0
COPY server.py .
USER 65534:65534
ENTRYPOINT ["/app/.venv/bin/python", "-B"]
CMD ["/service/server.py"]

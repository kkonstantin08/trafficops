FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
WORKDIR /app
COPY demo/app.py /app/demo/app.py
USER 65532:65532
EXPOSE 8080
CMD ["python", "/app/demo/app.py"]

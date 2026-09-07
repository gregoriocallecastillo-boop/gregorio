FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN groupadd --gid 10001 nexo && useradd --uid 10001 --gid nexo --create-home nexo
COPY --chown=nexo:nexo . .
RUN mkdir -p /app/staticfiles && chown nexo:nexo /app/staticfiles
USER nexo
EXPOSE 8000
ENTRYPOINT ["python", "scripts/entrypoint.py"]

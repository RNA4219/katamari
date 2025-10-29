
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN groupadd -r app && useradd --no-log-init -r -g app app \
    && chown -R app:app /app
USER app
ENV PORT=8787
EXPOSE 8787
# デフォルトで Chainlit CLI をエントリポイントとして公開
ENTRYPOINT ["chainlit","run"]
CMD ["src/app.py","--host","0.0.0.0","--port","8787"]

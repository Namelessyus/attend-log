FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/opt/venv
WORKDIR /app
RUN pip install --no-cache-dir uv==0.12.23
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
RUN groupadd --system attendlog && useradd --system --gid attendlog attendlog
RUN mkdir -p /app/runtime/mail && chown -R attendlog:attendlog /app/runtime
COPY --chown=attendlog:attendlog attendlog ./attendlog
COPY --chown=attendlog:attendlog migrations ./migrations
COPY --chown=attendlog:attendlog alembic.ini ./
USER attendlog
EXPOSE 8000
CMD ["/opt/venv/bin/gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "--access-logformat", "%(h)s %(t)s %(m)s %(U)s %(s)s", "attendlog:create_app()"]

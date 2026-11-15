# Development image for the fact tracker.
#
# Python 3.13 with the project's dependencies installed by uv, exactly as
# pinned in uv.lock. In development the code is not taken from this image:
# compose.yaml mounts the repository over /app, so edits show up at once.

FROM python:3.13-slim

# Install uv, the tool that installs the project's dependencies. The version
# is pinned so that builds are repeatable.
RUN pip install --no-cache-dir uv==0.13.8

# PYTHONDONTWRITEBYTECODE  keeps .pyc files out of the mounted source tree.
# PYTHONUNBUFFERED         prints output at once, so `docker compose logs` is live.
# UV_PROJECT_ENVIRONMENT   puts the virtual environment outside /app, so that
#                          mounting the code over /app does not hide it.
# UV_LINK_MODE=copy        copies packages into the environment; hard links
#                          don't work across Docker's filesystem layers.
# UV_PYTHON_DOWNLOADS      stops uv from downloading another Python: the one
#                          in this image is the one to use.
# PATH                     makes `python` mean the virtual environment's Python.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install the dependencies first, as their own layer. Docker reuses this
# layer until pyproject.toml or uv.lock change, so editing code does not
# trigger a reinstall. --frozen means "install exactly what uv.lock says".
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen

# Copy the project in. In development compose.yaml mounts over this.
COPY . .

EXPOSE 8000

# Django's development server, listening on every interface so that it can
# be reached from outside the container.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

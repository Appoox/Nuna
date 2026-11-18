# Fact tracker (working title)

Backend for a tracker of false, misleading and unsupported statements by a
government, with the evidence behind each one. Built with Django 5.2 and
Wagtail 7.4 on PostgreSQL 18. The site does not have a name yet.

So far it holds the project scaffold, the first two lists (speakers and
topics), and sources with their saved copies. The other data models, the
public API and the production setup arrive in later changes.

## Requirements

- Docker with Docker Compose
- [uv](https://docs.astral.sh/uv/), only when you change dependencies

## First run

```sh
cp .env.example .env                                           # local settings
docker compose build                                           # build the image
docker compose run --rm web python manage.py migrate           # create the tables
docker compose run --rm web python manage.py createsuperuser   # your admin login
docker compose up                                              # start Postgres and Django
```

Then open <http://localhost:8000/admin/> and log in.

## Everyday commands

```sh
docker compose up                                        # start (Ctrl+C stops)
docker compose down                                      # stop and remove the containers
docker compose run --rm web python manage.py test        # run the tests
docker compose run --rm web python manage.py migrate     # apply new migrations
docker compose logs -f web                               # follow Django's output
```

Code edits reload the development server automatically. Rebuild the image
(`docker compose build`) only after `pyproject.toml` or `uv.lock` change.

## Layout

| Path | What it is |
| --- | --- |
| `config/` | Project settings, URL routes and the server entry point |
| `entries/` | Speakers and topics; fact sheets and actions join them later |
| `evidence/` | Sources and their saved copies; citations join them later |
| `manage.py` | Django's command-line tool |
| `pyproject.toml`, `uv.lock` | Dependencies and their exact pinned versions |
| `Dockerfile`, `compose.yaml` | The development environment |
| `.env.example` | Every setting the project reads, with development values |
| `docs/spec.md` | The agreed specification: data model, rules and open questions |
| `CLAUDE.md` | Working rules and build plan for Claude Code |

## Changing dependencies

Edit `pyproject.toml`, run `uv lock`, then `docker compose build`.
Commit `pyproject.toml` and `uv.lock` together.

## Data

The database and uploaded files live in Docker volumes, so they survive
`docker compose down`. To wipe them and start again: `docker compose down -v`.

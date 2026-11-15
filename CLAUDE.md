# CLAUDE.md

Instructions for Claude Code in this repository. They carry over decisions the
owner made while the project was designed in a chat.

**Read `docs/spec.md` before changing any model, admin screen, rule or API.**
It is the agreed specification. It also lists what is parked, what is still
undecided, and what must be asked before each remaining step.

## The project

- Backend for a fact-check tracker: statements by the current Kerala
  government that are false, misleading or unsupported, the evidence for each,
  and government actions that contradict a statement. A personal project.
- Working title "Fact tracker". The site has no name yet. Never invent one.
- The front end is on hold. Build the backend only: models, Wagtail admin,
  background worker, API. No public pages and no public addresses.

## Working rules (the owner's standing decisions)

1. **Never assume.** If something is undecided or ambiguous, ask, and let the
   owner decide. Give a recommendation when asked or when it helps, but do not
   act on it until it is chosen. This applies to design, tooling and naming.
2. **Never commit and never push.** A cloud session normally ends by pushing
   a branch to GitHub: do not do that here, and do not open pull requests.
   Deliver every change as a `.patch` file attached to your chat reply
   (procedure below). The owner downloads it, applies it, tests, commits and
   pushes.
3. **One step at a time.** After delivering a patch, stop. Start the next step
   only when the owner says the previous patch is applied and has passed.
4. **Every patch comes with a test checklist** the owner can tick off: exact
   commands, and what to look for in the admin. Put it in the chat reply.
5. **Comment all code**, including configuration files, migrations and tests.
   **Never remove existing comments**; update them when the code changes.
6. **Report honestly.** Say what you verified and what you could not. List
   every choice you made that the owner did not decide.
7. **Earlier decisions are open to challenge.** When reviewing a plan or a
   design, raise concerns about any decision, old or new, then let the owner
   decide. Never silently work around a decision.
8. **Wording.** Fields and exports say "statement". Never "lie", never
   "claim". The ratings are False, Misleading and Unsupported.

## Delivering a patch

The owner runs Claude Code in the browser. The session works in its own
clone of the GitHub repository, so nothing here touches the owner's machine.

The owner pushes to GitHub before each new chat, not between patches. So:

- **At the start of a chat** the clone is the owner's latest work. The first
  patch of the chat is the difference from `HEAD`.
- **Within a chat, patches are progressive.** Each patch builds on the one
  before it and holds only what is new since that patch. Never build a later
  patch against the untouched repository, and never reset the clone between
  patches: the owner applies them in order on their own machine.

Steps for every patch:

1. Make the change and run the tests in the session (see Commands).
2. Stage everything: `git add -A`.
3. Write the patch to a file outside the repository:
   `git diff --cached --binary <baseline> > /tmp/NNNN-short-name.patch`.
   `<baseline>` is `HEAD` for the first patch of the chat. For every later
   patch it is the tree id recorded in step 6 for the previous patch.
4. Check the patch the way the owner will use it. Keep one clean copy per
   chat, made once with `git worktree add --detach /tmp/check HEAD`.
   `git -C /tmp/check apply --check <patch>` must print nothing. Then apply
   the patch there, so the copy always matches what the owner has after
   applying every patch of this chat in order.
5. Attach the `.patch` file to your reply, so the owner can download it from
   the chat. If the session has no way to attach a file, stop and tell the
   owner. Never push a branch, open a pull request or add the patch to the
   repository as a substitute.
6. Record the new baseline: `git write-tree` prints the id of the staged
   tree. It marks "everything delivered so far" without making a commit.
7. Number patches in order, continuing across chats from the last one listed
   under Build plan.
8. If the owner reports a problem with a delivered patch, ask whether to
   reissue that patch or to send a follow-up patch on top of it.

## Commands

Development runs entirely in Docker Compose. There is no Caddy locally.
Cloud sessions have Docker and Docker Compose, so the same commands run
there, with PostgreSQL 18 from `compose.yaml`.

```sh
cp .env.example .env                                     # first time only
docker compose build                                     # after dependency changes
docker compose run --rm web python manage.py migrate     # apply migrations
docker compose run --rm web python manage.py test        # run the tests
docker compose run --rm web python manage.py makemigrations --check --dry-run
docker compose up                                        # http://localhost:8000/admin/
```

Dependencies are managed with uv: edit `pyproject.toml`, run `uv lock`,
rebuild the image, and include both files in the patch.

## Stack (decided)

- Python 3.13, Django 5.2 LTS, Wagtail 7.4 LTS, PostgreSQL 18.
- uv with `pyproject.toml` and `uv.lock`.
- One settings file, `config/settings.py`, driven by environment variables.
- Three apps beside `config`: `entries`, `evidence`, `api`.
- Django-Q2 for the background worker, with its queue in PostgreSQL.
- Django REST Framework for the read-only API.
- Tests use Django's own test runner.
- Uploaded files stay on the server's disk for now.

## Conventions already in the code

- Models are split into modules inside `<app>/models/` and re-exported from
  `<app>/models/__init__.py`.
- Wagtail admin screens are `SnippetViewSet` classes in `<app>/wagtail_hooks.py`
  with `add_to_admin_menu = True`. Every model gets its own main-menu item.
  Menu order: Fact sheets 110, Actions 120, Sources 130, Speakers 140, Topics 150.
- Bilingual text is a pair of fields, `<name>_en` and `<name>_ml`.
  `entries.models.lookups.BilingualName` shows the pattern for names.
- Tests live in `<app>/tests/test_*.py`. Admin screens are tested through the
  Django test client as a superuser.
- Generated migrations get a short comment at the top saying what they do.
- Settings are read with the `env`, `env_bool` and `env_list` helpers, and
  every variable is documented in `.env.example`.

## Build plan

Delivered so far:

- `0001` project scaffold
- `0002` speakers and topics
- `0003` this handoff

Remaining, in this order. Each is one patch. Ask the questions listed for the
step in `docs/spec.md` before building it.

4. Sources and saved copies (`evidence` app)
5. Fact sheets, with their citations and corrections
6. Actions, with their citations and corrections
7. The Wayback capture job (Django-Q2)
8. The public API and bulk downloads (`api` app)
9. Sample data
10. Production setup, with separate instructions for development and production

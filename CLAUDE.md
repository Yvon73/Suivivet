# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`Projet_veto` is a Django 6 web app (French UI) for a veterinary/pet-tracking practice: it manages
animals, their vaccinations/treatments, consultations (with a FullCalendar-based calendar view), invoices,
and documents, with login-gated CRUD views, CSV/Excel import-export, PDF export, and Celery-based email
reminders.

## Commands

Use the project virtualenv at `.venv/` (`source .venv/bin/activate`, or call `.venv/bin/python` directly).

- Install deps: `pip install -r requirements.txt`
- Run dev server: `python manage.py runserver`
- Apply/create migrations: `python manage.py migrate` / `python manage.py makemigrations`
- Run all tests: `python manage.py test` (or `pytest`, configured via `pytest.ini` to run
  `accueil/tests.py`, `animaux/tests.py`, `consultations/tests.py` and `factures/tests.py` — the only
  apps with real test suites; the other apps' `tests.py` are empty stubs)
- Run one app's tests: `python manage.py test animaux`
- Run a single test: `python manage.py test animaux.tests.SomeTestCase.test_something`
- Create an admin user: `python manage.py createsuperuser`
- Run a Celery worker (needed for the reminder emails): `celery -A Projet_veto worker -l info`
- Collect static files before a production deploy (required — `STORAGES['staticfiles']` switches to
  `whitenoise.storage.CompressedManifestStaticFilesStorage` once `DEBUG=False`, which needs the manifest
  `collectstatic` builds; skip this and `{% static %}` tags raise `ValueError` at request time, not just
  look wrong): `python manage.py collectstatic --noinput`
- Serve in production with gunicorn (added to `requirements.txt`), e.g. `gunicorn Projet_veto.wsgi:application
  --bind 0.0.0.0:8000` — behind a reverse proxy for TLS termination in any real deployment.

### Configuration

Settings load from a `.env` file in `Projet_veto/` via `django-environ` — `Projet_veto/.env.example`
documents every variable (required and optional) with production-oriented comments; copy it to
`Projet_veto/.env` and fill in real values rather than reverse-engineering settings.py from scratch.
Required vars: `SECRET_KEY`, `DB_URL` (parsed with `env.db()` — the project uses `psycopg` for Postgres),
`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`. Optional: `CELERY_BROKER_URL` /
`CELERY_RESULT_BACKEND` (default to a local Redis at `redis://localhost:6379/0`); `EDITEUR_NOM` /
`EDITEUR_ADRESSE` / `EDITEUR_EMAIL` / `EDITEUR_TELEPHONE` / `HEBERGEUR_NOM` / `HEBERGEUR_ADRESSE`
(legal-notice/RGPD info shown on the `accueil` homepage — the app is aimed at general-public,
non-professional use by an individual developer/publisher, not a business, so this is framed as personal
contact info, not company details; defaults to visible placeholder strings, must be set to the real
identity before going live).

Production-oriented settings, all no-ops until you flip `DEBUG=False` (or opt in explicitly): `ADMINS`
(`"Nom:email"` pairs, comma-separated — receives an email on every unhandled server error once live, via
both Django's own 500-handler and the `mail_admins` logging handler below) / `SERVER_EMAIL` (defaults to
`EMAIL_HOST_USER`); `BEHIND_REVERSE_PROXY` (set only if a trusted proxy terminates TLS and forwards
`X-Forwarded-Proto` — enables `SECURE_PROXY_SSL_HEADER`, never turn this on directly exposed to the
Internet); `CONN_MAX_AGE` (persistent DB connections under gunicorn; 0 in dev, 60s by default in prod);
`LOG_LEVEL` / `DJANGO_LOG_LEVEL` (see logging below).

**Logging** (`LOGGING` in settings.py): rotating `logs/app.log` (everything at `LOG_LEVEL`, created
automatically) and `logs/erreurs.log` (errors only, for a quick scan), console output (verbose in dev,
quieter in prod — distinguished via Django's `RequireDebugTrue`/`RequireDebugFalse` filters), and
`AdminEmailHandler` wired to `ADMINS` for `django.request`/`django.security` once `DEBUG=False`. Any
`logging.getLogger(__name__)` in app code (e.g. `animaux/views.py`'s CSV import) falls through to `root`
and gets all of this for free — no per-app logger config needed. Chatty third-party libraries
(`matplotlib`, `PIL`, `fontTools`, `weasyprint` — all exercised by the weight chart / PDF export) are
explicitly capped at `WARNING` so a routine chart render doesn't flood `app.log`; add another entry there
rather than lowering the global `LOG_LEVEL` if a new dependency turns out to be just as noisy.

**Static files in production**: `STORAGES['staticfiles']` and `whitenoise.middleware.WhiteNoiseMiddleware`
(inserted into `MIDDLEWARE` only when `DEBUG=False`, to avoid a `collectstatic`-not-run warning in dev)
switch to WhiteNoise's compressed, hashed-filename storage — run `collectstatic` as part of every deploy
(see Commands above).

Two things the DB role needs beyond just existing:
- The `DB_URL` database itself must already exist — Django won't create it for you (`CREATE DATABASE`).
- The role needs `CREATEDB` — `manage.py test` creates/drops a `test_<dbname>` database on every run.

A local Redis server must be reachable at `CELERY_BROKER_URL` (even for tests): saving a `Consultation`
with a future date schedules a reminder email via `apply_async`, which fails immediately if no broker is
reachable.

## Architecture

The project root package is `Projet_veto` (settings module `Projet_veto.settings`, root urlconf
`Projet_veto.urls`, Celery app defined in `Projet_veto/celery.py`). The actual features live in five
per-domain apps, all FK'd back to `animaux.Animal` as the central model, plus a small **accueil** app
hosting the public homepage:

- **accueil** — the only unauthenticated-facing part of the app, mounted at the true root `/` (the
  `animaux` app that used to own `/` was moved to `/animaux/` — a routing-only change, every internal
  link uses namespaced `reverse()`/`{% url %}` so nothing else needed to change). `AccueilView` shows the
  app pitch (general public / personal, non-professional use — not a veterinary practice's client
  portal), a login form (posts straight to the existing `login` view), the mandatory EU legal notice /
  RGPD blurb (driven by the `EDITEUR_*`/`HEBERGEUR_*` settings above, worded for an individual
  publisher) and an accessibility statement, plus a "create the first account" call to action gated on
  `not User.objects.exists()`. `PremierUtilisateurCreateView` is that first-account form — a stand-in for
  `createsuperuser` from the browser — and refuses to run (redirecting to `accueil:accueil`) once any
  user already exists, since otherwise it would be an open, unauthenticated account-creation endpoint.
  The site-wide accessibility panel (`templates/partials/panneau_accessibilite.html` +
  `static/js/accessibilite.js` + the `html.a11y-*` classes in `static/css/style.css`) offers independent
  controls — 3-step text size, high contrast, a low-vision-oriented font (Atkinson Hyperlegible), reduced
  animations, a colorblind-safe palette swap (Okabe-Ito, overriding Bootstrap's
  danger/success/warning/info everywhere plus the calendar's `.fc-event-*` classes), and a text-to-speech
  "read this page aloud" button (Web Speech API) — plus an always-on visible focus outline and
  skip-to-content link. It's shared (via `{% include %}`) between `templates/base.html` and
  `accueil`'s/`registration/login.html`'s standalone templates, which don't extend `base.html` since they
  must render for anonymous, pre-login visitors. The app already avoids conveying anything by color alone
  (every badge/status carries text or an icon too), so the palette swap is a discriminability
  improvement, not a fix for a missing text label.

  Where these settings are memorized differs by whether there's an account: for a logged-in user they're
  `accueil.PreferenceAccessibilite` (one row per user, editable from `PremierUtilisateurForm`'s
  accessibility checkboxes at account creation, or later from the panel itself via the
  `accueil:preferences_accessibilite` AJAX endpoint) — rendered straight into `<html class="...">` by
  `Projet_veto.context_processors.preferences_accessibilite_context`, so they apply from the moment of
  login, on any browser, with no JS/localStorage round-trip or flash-of-unstyled-content. For an
  anonymous visitor (no account to attach preferences to) the panel falls back to localStorage, scoped to
  that one browser — `panneau_accessibilite.html`'s `data-authentifie`/`data-url-maj` attributes tell
  `accessibilite.js` which of the two to use.

- **animaux** — `Animal` (species/breed/chip id/owner) and `Poids` (weight history, one entry per
  animal/date; charted via `matplotlib`). Beyond CRUD, this app also has: an advanced search form
  (`AnimalSearchForm` — filters by nom/espece/race/age range/lof/robe, not a single free-text `q` param),
  CSV/Excel export and CSV import (`pandas`/`openpyxl`), and a per-animal PDF summary
  (`generer_pdf_fiche_animal`, via `weasyprint`) pulling in weights, vaccines/treatments, consultations and
  invoices. This is the app every other app depends on.
- **vaccins** — `Vaccin`, `Traitement` (catalog tables) and `SuiviVaccinTraitement`, which links an
  animal to either a vaccine or a treatment (`SET_NULL` on delete) with a dose date and next-due date.
- **consultations** — `Consultation` (animal, datetime, motif, compte-rendu, vétérinaire), plus a
  FullCalendar-based calendar view (`CalendrierView` + `get_consultations_json`, loaded via CDN in
  `base.html`) showing upcoming consultations and 2-day-out reminders. Saving a new consultation schedules
  a Celery task (`envoyer_rappel_consultation`, in `consultations/tasks.py`) via `apply_async(eta=...)` to
  email the owner a reminder 2 days before the appointment; the model imports the task lazily inside
  `save()` to avoid a circular import with `tasks.py` (which imports the model back via `apps.get_model`).
- **factures** — `Facture` (invoice: animal, amount, scanned file, `type_depense` of `VETERINAIRE` or
  `ALIMENTAIRE`) with classmethods `depenses_mensuelles`/`depenses_annuelles` used to aggregate spend for
  the invoice list view's dashboard context. An invoice can optionally be itemized ("ventilée", via the
  "Ventiler la facture" button on the create/update form): `LigneFacture` rows (designation from the
  `Designation` catalog, quantity, unit price, auto-computed `prix_total`) each attribute their cost to one
  `Animal` or to `pour_tous_les_animaux` (shared equally). `Facture.montant` is auto-recalculated from the
  lines whenever any exist (`Facture.recalculer_montant()`, called from `LigneFacture.save()`/`delete()`).
  Once a `Facture` has at least one line (`est_ventilee()`), editing it (`FactureUpdateView`) locks every
  field of the invoice itself and of each existing line except that line's animal/`pour_tous_les_animaux`
  (`FactureForm`/`LigneFactureForm`'s `disabled` fields, driven by `VentilationFactureMixin._verrouillee()`)
  — only reassigning a line's animal, deleting a line, or adding a new one stays possible after that point.
  `Facture.cout_revient_animal(animal, annee, mois=None)` / `couts_revient_annuels(annee)` compute an
  animal's "coût de revient": its own ventilated lines + a non-ventilated invoice fully attributed to it if
  one names it directly, plus an equal share (÷ total animal count) of "shared" costs — `pour_tous_les_animaux`
  lines and non-ventilated invoices with no animal at all. Surfaced on the animal detail page (monthly +
  annual) and as an annual-only column on the global animal list.
- **documents** — `Document` + `TypeDocument`, generic file attachments per animal.

`Projet_veto_1` is an earlier, monolithic scaffold (same models duplicated in one app) that predates the
split into the five apps above. It's still in `INSTALLED_APPS` and has migrations, but it isn't wired
into `Projet_veto/urls.py` and has no views — treat it as legacy, not a place to add features.

### Request/view conventions

Views are Django class-based views (`ListView`/`DetailView`/`CreateView`/`UpdateView`/`DeleteView`), all
gated with `LoginRequiredMixin`. Each app follows the same template layout:
`<app>/templates/<app>/{liste,detail,form,confirm_delete}.html`, all extending the shared
`templates/base.html` (Bootstrap 5 + DataTables + FullCalendar, all via CDN, plus `static/css/style.css`).
List views commonly accept an `animal_id` URL kwarg to scope results to one animal (e.g.
`consultation_list_animal`, `suivi_list_animal`). Auth uses `django.contrib.auth`'s built-in login/logout
views at `/accounts/login/` and `/accounts/logout/`.

**Every app sets `app_name` in its `urls.py` and is namespaced accordingly** (`animaux:`, `vaccins:`,
`consultations:`, `factures:`, `documents:`, `accueil:`). Always qualify `reverse()`/`reverse_lazy()`/`{% url %}` calls
with the app namespace (e.g. `reverse('animaux:animal_detail', ...)`), including for cross-app links (a
`factures` template linking to an animal uses `{% url 'animaux:animal_detail' ... %}`). Only `login`,
`logout` and `admin:*` are unnamespaced, since they're registered directly in the root `Projet_veto/urls.py`.
An unqualified name (`reverse('animal_list')`) will raise `NoReverseMatch`.

**Model field names have no accents** even where the French label does (`Animal.proprietaire`,
`Consultation.veterinaire` — not `propriétaire`/`vétérinaire`). This has been a repeated source of bugs
(`TypeError`/`AttributeError`/`FieldError`) in views, templates and tests that used the accented spelling;
double-check the actual model field name rather than the `verbose_name` when referencing these fields.
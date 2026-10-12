# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

`Projet_veto` is a Django 6 web app (French UI) for a veterinary/pet-tracking practice: it manages
animals, their vaccinations/treatments, consultations (with a server-rendered calendar view), invoices,
and documents, with login-gated CRUD views, CSV/Excel import-export, PDF export, and Celery-based email
reminders.

## Commands

Use the project virtualenv at `.venv/` (`source .venv/bin/activate`, or call `.venv/bin/python` directly).

- Install deps: `pip install -r requirements.txt`
- Run dev server: `python manage.py runserver`
- Apply/create migrations: `python manage.py migrate` / `python manage.py makemigrations`
- Run all tests: `python manage.py test` (or `pytest`, configured via `pytest.ini` to run
  `accueil/tests.py`, `animaux/tests.py`, `consultations/tests.py`, `factures/tests.py` and
  `vaccins/tests.py` — the only apps with real test suites; the other apps' `tests.py` are empty stubs)
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
`EMAIL_HOST`, `EMAIL_PORT` (465 — implicit SSL, `EMAIL_USE_SSL = True`), `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`. Optional: `CELERY_BROKER_URL` /
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
`X-Forwarded-Proto` — enables `SECURE_PROXY_SSL_HEADER`, and makes `Projet_veto.throttling` read the
visitor's address from the last `X-Forwarded-For` entry instead of `REMOTE_ADDR`, which is empty behind
gunicorn on a unix socket; never turn this on directly exposed to the Internet); `CONN_MAX_AGE` (persistent DB connections under gunicorn; 0 in dev, 60s by default in prod);
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
  `accueil/accessibilite.py` + the `html.a11y-*` classes in `static/css/style.css`) offers independent
  controls — 3-step text size, high contrast, a low-vision-oriented font (Atkinson Hyperlegible), reduced
  animations, a colorblind-safe palette swap (Okabe-Ito, overriding Bootstrap's
  danger/success/warning/info everywhere plus the calendar's `.evenement-*` classes), and a text-to-speech
  "read this page aloud" button (Web Speech API, `static/js/lecture-voix-haute.js` — the only hand-written
  script left in the project, since speech synthesis only exists in the browser) — plus an always-on visible focus outline and
  skip-to-content link. It's shared (via `{% include %}`) between `templates/base.html` and
  `accueil`'s/`registration/login.html`'s standalone templates, which don't extend `base.html` since they
  must render for anonymous, pre-login visitors. The app already avoids conveying anything by color alone
  (every badge/status carries text or an icon too), so the palette swap is a discriminability
  improvement, not a fix for a missing text label.

  The panel has no JavaScript for its settings: it is a `<form>` that htmx posts whole on every change
  (`hx-trigger="change"`, with a `<noscript>` submit button as fallback) to
  `accueil:preferences_accessibilite`, which stores them and then sends the browser back to the page it was
  on (`HX-Redirect`) — the server applies them at render time, straight into `<html class="...">` via
  `Projet_veto.context_processors.preferences_accessibilite_context`, so there is no script, no localStorage
  and no flash-of-unstyled-content. Where they are stored differs by whether there's an account
  (`accueil/accessibilite.py`): for a logged-in user they're `accueil.PreferenceAccessibilite` (one row per
  user, also editable from `PremierUtilisateurForm`'s accessibility checkboxes at account creation), so they
  follow the account on any browser; for an anonymous visitor (no account to attach preferences to) they go
  into a signed cookie scoped to that one browser — which is why that endpoint is *not* login-required.
  Changing a setting therefore reloads the current page.

- **animaux** — `Animal` (species/breed/chip id/owner) and `Poids` (weight history, one entry per
  animal/date; charted via `matplotlib`). Beyond CRUD, this app also has: an advanced search form
  (`AnimalSearchForm` — filters by nom/espece/race/age range/lof/robe, not a single free-text `q` param),
  CSV/Excel export and CSV import (`pandas`/`openpyxl`), and a per-animal PDF summary
  (`generer_pdf_fiche_animal`, via `weasyprint`) pulling in weights, vaccines/treatments, consultations and
  invoices. This is the app every other app depends on. The animal create/update form is entirely driven by
  htmx through `animaux/formulaire.py` (no script of its own, no Tom Select): choosing a species restricts
  the "Race" `<select>` to its breeds and a "Filtrer les races" field narrows it further (filtering is done
  by `AnimalForm._choix_races`, accent- and case-insensitive; the currently selected breed is always kept),
  the selected breed's info card and the photo preview are rendered by the server, and the
  organisme/identification rows are added/removed by posting the formset state — same principle as the
  invoice ventilation zone below.
  "Deleting" a `Proprietaire` is a soft delete (`actif=False`; the row stays for the animals that reference
  it, FK is `RESTRICT`: it cannot be hard-deleted on its own, only together with its animals when the whole
  account is deleted). It is never reactivated: creating an owner again with the same email (form, quick-add
  panel or CSV import) gives a brand-new row that takes nothing from the archived one — which is why the
  `(utilisateur, email)` unique constraint is conditional on `actif=True`, and why every lookup of an
  existing owner filters on `actif=True`.
  Deleting an `Animal` cascades to its identifications, weights, vaccine/treatment follow-ups,
  consultations and documents, and also removes its invoices — see **factures** below;
  `animaux/confirm_delete.html` lists the real counts.
- **vaccins** — `Vaccin`, `Traitement` (catalog tables: seeded reference entries + per-account entries, see
  "Catalogues belong to the account that created them" below) and `SuiviVaccinTraitement`, which links an
  animal to either a vaccine or a treatment (`SET_NULL` on delete) with a dose date and next-due date.
- **consultations** — `Consultation` (animal, datetime, motif, compte-rendu, vétérinaire), plus a
  server-rendered calendar view (`CalendrierView` + `consultations/calendrier.py` +
  `consultations/partials/calendrier.html`, no FullCalendar) showing upcoming consultations, 2-day-out
  reminders and vaccine reminders: a month grid and a "planning" list (the list is what phones get by
  default, via Bootstrap's responsive classes), navigated with plain `?annee=&mois=&vue=` links that htmx
  boosts; the zone also refreshes itself when the window regains focus (`hx-trigger="focus from:window"`),
  since events open in a new tab where they may be edited or deleted. Saving a new consultation schedules a Celery task
  (`envoyer_rappel_consultation`, in `consultations/tasks.py`) via `apply_async(eta=...)` to email the
  owner a reminder 2 days before the appointment; the model imports the task lazily inside `save()` to
  avoid a circular import with `tasks.py` (which imports the model back via `apps.get_model`).
  `Consultation.rappel_task_id` holds the id of the only task allowed to send that reminder (`save()` picks
  the id and stores it *before* publishing): the bound task claims it with a conditional `UPDATE`
  (`filter(pk=..., rappel_task_id=self.request.id).update(rappel_task_id=None)`) and sends nothing if no row
  matched — so a lost revocation, a rescheduled/cancelled/deleted consultation or a redelivered message can
  never send a stale or duplicate reminder. A send failure after the claim is logged and not retried. In
  tests, run it with `envoyer_rappel_consultation.apply(args=(pk,), task_id=...)`: a direct call has no id
  and sends nothing.
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
  Deleting an animal deletes its invoices with it (a `pre_delete` signal on `Animal` in `factures/models.py`,
  so it holds for the view, the admin, the shell and `QuerySet.delete()`; `factures_emportees_par(animal)`
  is the single definition, shared with the confirmation page): its ventilated lines (remaining invoices get
  their `montant` recalculated; an invoice left with no line is deleted) and the non-ventilated invoices
  naming it, scanned files included (`Projet_veto/fichiers.py`). `pour_tous_les_animaux` lines and invoices
  without an animal are untouched. The `animal` FKs stay `SET_NULL` (a ventilated invoice that keeps other
  lines survives) and the "— Animal supprimé : à réattribuer —" option only serves legacy rows.
  The create/update form has **no JavaScript of its own**: it is driven by htmx. Every interaction in the ventilation zone (`factures/partials/ventilation.html`)
  posts the current formset state to `ventilation_facture` (`factures:facture_ventilation`, with or without
  a `pk`), and `factures/ventilation.py` does what the old inline script did — line totals, invoice total,
  last-price comparison, adding/removing/renumbering lines, creating a `Designation` — then returns HTML.
  Typing triggers a recalculation that only sends back the totals as `hx-swap-oob` fragments (never the
  input being typed in); buttons re-render the whole zone. Nothing but a new `Designation` is saved there —
  the invoice and its lines are still saved by the normal form POST.
- **documents** — `Document` + `TypeDocument`, generic file attachments per animal.

**Catalogues belong to the account that created them.** `consultations.Veterinaire`, `vaccins.Vaccin`,
`vaccins.Traitement`, `factures.Designation` and `documents.TypeDocument` each carry a `utilisateur` FK (set
from `request.user` by their forms — pass `user=` — including the quick-add "+" views, the ventilation zone
and `DocumentForm`'s "nouveau type") and are only listed, selectable, editable or deletable by that account
and its household: always filter them with `accueil.utils.filtre_catalogue(user)` (same visibility rule as
`comptes_accessibles`), never `.objects.all()`. Two accounts may therefore own entries with the same name
(`Designation` is unique per `(utilisateur, nom)`; `DesignationForm.clean_nom` rejects a duplicate within the
household). `Veterinaire` and `Designation` require the account; on `Vaccin`, `Traitement` and `TypeDocument`
an empty `utilisateur` marks a **reference entry** seeded by the project's migrations, offered to every
account (`filtre_catalogue(user, reference=True)`, `est_reference`) and only editable in the Django admin.
In a form's `<select>`, pass `garder=<current pk>` so the entry an edited object already points to stays
selected even if it left the filter (never silently blank a FK on save). The `animaux` catalogues (species,
breeds, coats, registries) are shared reference data and are not concerned. Existing rows were attached by
the data migration `accueil/migrations/0007_rattacher_catalogues_aux_comptes.py` (entries used by several
households were duplicated, one copy each).
Three consequences of that sharing to keep in mind:
- **Deleting an account** — those five `utilisateur` FKs use `on_delete=accueil.catalogues.REATTRIBUER_OU_SUPPRIMER`
  (not `CASCADE`, never `SET_NULL`: an empty account would mean "reference entry visible to everyone"): an
  entry still used by another account's object is handed over to that account (the heaviest user, the oldest
  on a tie; if it already owns a same-named `Designation` — or was just handed one by another account deleted
  in the same operation — its lines are re-pointed to that one instead), the rest cascades. `Animal.proprietaire`
  and `Consultation.veterinaire` are `RESTRICT`, not `PROTECT`, so an account can be deleted with its own
  animals and consultations (`PROTECT` refuses even when the referencing rows are deleted too). It is an `on_delete` rather than a `pre_delete` signal because Django collects everything it
  will delete *before* sending any `pre_delete`. Register any new FK to one of
  these catalogues in `accueil.catalogues.REFERENTS`.
- **htmx fragments that rebuild an unbound form** must know the object being edited, or the redrawn `<select>`
  loses the `garder=` entry: their URL takes an optional `pk` (`vaccins:suivi_choix`,
  `vaccins:vaccin_ajout_rapide`, `vaccins:traitement_ajout_rapide`, like `factures:facture_ventilation`),
  loaded with the same access check as the update view (404 otherwise).
- **Same-named `Designation`s inside a household** (each member created theirs before joining):
  `LigneFactureForm` shows one option per name (`Designation.cle_nom`, case- and edge-space-insensitive —
  the line's current one first, then the logged-in account's, then the oldest) while still validating
  against the full queryset, `dernier_prix_unitaire` looks the price up by name across the household's
  invoices, and `DesignationForm.clean_nom` rejects a duplicate with the same comparison.

- **notifications** — in-app notifications (`notifications:*` URLs, the bell in `base.html`'s navbar fed
  by `Projet_veto.context_processors.notifications_context`). Opening a notification is a plain link;
  every action that changes one (mark as read, mark all as read, delete) is a POST form with a CSRF
  token — the views are `@require_POST`.

`accueil` also hosts open sign-up (`InscriptionCreateView` — the email must be unique, case-insensitively)
and household sharing (`PartageCompteView`, `InvitationFoyer`/`MembreFoyer`): an invitation is tied to the
invited *account* (`InvitationFoyer.invite`), never matched by email alone, and data is scoped to the
accounts of the user's household everywhere. Only the household's founder can remove a member
(`retirer_membre_foyer`, and the "Retirer" button only shows for them) — having invited someone gives no
such right; anyone can leave (`quitter_foyer`); the founder cannot be removed. The founder is derived, not
stored: `Foyer.membre_fondateur()` is the oldest member (`date_adhesion`, then pk), so when the founder
leaves, the oldest remaining member takes over. Don't use `MembreFoyer.invite_par is None` for that — it is
informational only (also nulled when the inviter's account is deleted).

Cross-cutting pieces in `Projet_veto/`: `throttling.py` (3 attempts per IP on login/sign-up, 5 per hour on
`password_reset`; `/admin/login/` redirects to the throttled `login` view); `middleware.py`'s
`ConnexionRequiseHtmxMiddleware` (an htmx request whose session has expired gets `204` + `HX-Redirect` to
the login page instead of the login page being swapped into a fragment); standalone error pages
`templates/{404,403,500,403_csrf}.html` (`500.html` and `403_csrf.html` are static HTML, no template tags);
`CELERY_BROKER_TRANSPORT_OPTIONS['visibility_timeout']` is set far above the reminder horizon, otherwise
Redis redelivers every `eta` task hourly and reminders go out several times.

### Request/view conventions

Views are Django class-based views (`ListView`/`DetailView`/`CreateView`/`UpdateView`/`DeleteView`), all
gated with `LoginRequiredMixin`. Each app follows the same template layout:
`<app>/templates/<app>/{liste,detail,form,confirm_delete}.html`, all extending the shared
`templates/base.html` (Bootstrap 5 + htmx, plus `static/css/style.css`). **No CDN**: every front-end
library (Bootstrap, Bootstrap Icons, htmx, the Atkinson Hyperlegible font) is self-hosted under
`static/vendor/` (versions/licences in its `README.md`), and the CSP in `Projet_veto/middleware.py` allows
`'self'` only — add new libraries there too, never a CDN URL.
A page-specific library's CSS would go in the `vendor_css` block (before `style.css`, so that it can override
its classes at equal specificity), not `extra_css`.
**Mobile**: below 768px, every `table.table` with ≥4 header columns is re-rendered as one card per row
(`Projet_veto.tableaux.TableauxEmpilablesMiddleware` copies each `<th>` text into a `data-label` on its
cells, in the HTML of every response — full pages and htmx fragments alike; the "Mobile" section of
`style.css` displays them) — so give every column of a new table a meaningful `<th>`, and name the button
column `Actions` (or leave its `<th>` empty) so its buttons line up at the bottom of the card. A table that
must stay a grid on phones (the calendar) simply doesn't use the `table` class. Rows of buttons need
`flex-wrap` to avoid overflowing a phone screen.
List views commonly accept an `animal_id` URL kwarg to scope results to one animal (e.g.
`consultation_list_animal`, `suivi_list_animal`). Auth uses `django.contrib.auth`'s built-in login/logout
views at `/accounts/login/` and `/accounts/logout/`.

### No hand-written JavaScript: htmx everywhere

All interactivity goes through htmx (loaded by `base.html` and by the standalone public templates): a page
asks the server for the HTML to display instead of running its own script. The only scripts served are
Bootstrap's bundle, htmx, and `static/js/lecture-voix-haute.js` (text-to-speech, which cannot be done
server-side). There is no inline `<script>` and no `on…=""` attribute anywhere — keep it that way: a new
interaction means a small view returning an HTML fragment, not a script. Building blocks to reuse:

- **Quick-add "+" next to a `<select>`** (`Projet_veto/ajout_rapide.py` +
  `templates/partials/ajout_rapide_{champ,panneau,form,reponse}.html`): the "+" unfolds a Bootstrap collapse
  whose fields belong, through their `form` attribute, to a small htmx `<form>` placed *outside* the main
  form (so Enter creates the catalogue entry instead of saving the page). The view re-renders the panel
  (folded on success, open with errors otherwise) plus, on success, the `<select>` with the new entry
  selected as an `hx-swap-oob` fragment. Used for vétérinaire, vaccin, traitement, propriétaire, espèce,
  race, robe, organisme. Give the quick-add form a `prefix`.
- **Sortable/searchable/paginated lists** (`Projet_veto.listes.ListeTriableMixin` +
  `templates/partials/liste_{recherche,pagination,entete_tri}.html` + the `{% entete_tri %}` tag from
  `{% load listes %}`): search text, sort column and page are plain URL parameters (`q`, `tri`, `sens`,
  `page`) applied to the SQL query, so the list works with ordinary links and a GET form; htmx only swaps
  the `#zoneListe` zone (`hx-boost` on the `<thead>` and the pagination — never on the table rows — with
  `hx-select`). Declare `champs_recherche`, `colonnes_tri`, `tri_defaut` and end `get_queryset()` with
  `self.filtrer_et_trier(queryset)`.
- **Dependent fields / live zones**: a wrapper with `hx-post … hx-trigger="change" hx-swap="none"` and a view
  answering only `hx-swap-oob` fragments (never the field being typed in or the `<select>` just used, which
  would lose focus or scroll position) — see `vaccins:suivi_choix`, `animaux:animal_choix_race`,
  `factures:facture_ventilation`. Rebuild the fields from an *unbound* form whose `initial` is the posted
  data, so no validation error shows up mid-typing.

Things to know: an element with `hx-post` inside a `<form>` sends that whole form, so whitelist with
`hx-params` (and always exclude file inputs unless you want the upload); the CSRF token travels in the
`X-CSRFToken` header set once on `<body>`; return 200 (not 4xx) with the errors in the fragment, htmx does
not swap error responses; `htmx-config` disables the history cache (pages contain personal data and would
be copied into localStorage) and `allowEval` — the CSP has no `'unsafe-eval'`, so don't use htmx features
that evaluate code (`hx-on`, `hx-vals='js:…'`, `hx-trigger` filters like `[key=='Enter']`).

**Every app sets `app_name` in its `urls.py` and is namespaced accordingly** (`animaux:`, `vaccins:`,
`consultations:`, `factures:`, `documents:`, `notifications:`, `accueil:`). Always qualify `reverse()`/`reverse_lazy()`/`{% url %}` calls
with the app namespace (e.g. `reverse('animaux:animal_detail', ...)`), including for cross-app links (a
`factures` template linking to an animal uses `{% url 'animaux:animal_detail' ... %}`). Only `login`,
`logout`, `password_reset*`, `password_change*` and `admin:*` are unnamespaced, since they're registered directly in the root `Projet_veto/urls.py`.
An unqualified name (`reverse('animal_list')`) will raise `NoReverseMatch`.

**Model field names have no accents** even where the French label does (`Animal.proprietaire`,
`Consultation.veterinaire` — not `propriétaire`/`vétérinaire`). This has been a repeated source of bugs
(`TypeError`/`AttributeError`/`FieldError`) in views, templates and tests that used the accented spelling;
double-check the actual model field name rather than the `verbose_name` when referencing these fields.
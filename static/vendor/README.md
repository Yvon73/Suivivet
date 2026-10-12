# Bibliothèques front-end hébergées localement

Ces fichiers étaient auparavant chargés depuis des CDN (jsdelivr, code.jquery.com,
cdn.datatables.net, Google Fonts). Ils sont désormais servis par l'application
elle-même (WhiteNoise en production), ce qui permet une CSP limitée à `'self'` et
évite de transmettre l'adresse IP des visiteurs à des tiers (RGPD).

Seules deux bibliothèques JavaScript restent : Bootstrap (menus, panneaux
dépliables) et htmx, par lequel passe toute l'interactivité de l'application
(cf. `CLAUDE.md`). FullCalendar, DataTables, jQuery et Tom Select ont été
retirés : calendrier, listes triables et menus Espèce/Race sont rendus par le
serveur.

| Dossier                  | Bibliothèque             | Version | Licence     | Source                                            |
|--------------------------|--------------------------|---------|-------------|---------------------------------------------------|
| `bootstrap/`             | Bootstrap                | 5.3.2   | MIT         | npm `bootstrap/dist`                              |
| `bootstrap-icons/`       | Bootstrap Icons          | 1.11.1  | MIT         | npm `bootstrap-icons/font`                        |
| `htmx/`                  | htmx                     | 2.0.11  | 0BSD        | npm `htmx.org/dist` (`htmx.min.js`)               |
| `atkinson-hyperlegible/` | Atkinson Hyperlegible    | 400     | SIL OFL 1.1 | npm `@fontsource/atkinson-hyperlegible@5`         |

Fichiers téléchargés tels quels, à une exception près : les commentaires
`sourceMappingURL` ont été retirés de `bootstrap.min.css` et
`bootstrap.bundle.min.js`. Les `.map` ne sont pas fournis, or
`ManifestStaticFilesStorage` fait échouer `collectstatic` quand une référence
de ce type pointe vers un fichier absent.

Pour mettre à jour une bibliothèque : remplacer ses fichiers, retirer à nouveau
un éventuel `sourceMappingURL`, puis vérifier avec
`DEBUG=False python manage.py collectstatic --noinput` avant de déployer.

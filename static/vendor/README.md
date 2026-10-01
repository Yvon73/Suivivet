# Bibliothèques front-end hébergées localement

Ces fichiers étaient auparavant chargés depuis des CDN (jsdelivr, code.jquery.com,
cdn.datatables.net, Google Fonts). Ils sont désormais servis par l'application
elle-même (WhiteNoise en production), ce qui permet une CSP limitée à `'self'` et
évite de transmettre l'adresse IP des visiteurs à des tiers (RGPD).

| Dossier                  | Bibliothèque             | Version | Licence     | Source                                            |
|--------------------------|--------------------------|---------|-------------|---------------------------------------------------|
| `bootstrap/`             | Bootstrap                | 5.3.2   | MIT         | npm `bootstrap/dist`                              |
| `bootstrap-icons/`       | Bootstrap Icons          | 1.11.1  | MIT         | npm `bootstrap-icons/font`                        |
| `fullcalendar/`          | FullCalendar             | 5.11.3  | MIT         | npm `fullcalendar` (+ `locales/fr.js`)            |
| `datatables/`            | DataTables + Bootstrap 5 | 1.13.6  | MIT         | cdn.datatables.net (+ `plug-ins/i18n/fr-FR.json`) |
| `jquery/`                | jQuery                   | 3.7.0   | MIT         | code.jquery.com                                   |
| `tom-select/`            | Tom Select               | 2.6.2   | Apache-2.0  | npm `tom-select/dist`                             |
| `atkinson-hyperlegible/` | Atkinson Hyperlegible    | 400     | SIL OFL 1.1 | npm `@fontsource/atkinson-hyperlegible@5`         |

Fichiers téléchargés tels quels, à une exception près : les commentaires
`sourceMappingURL` ont été retirés de `bootstrap.min.css`,
`bootstrap.bundle.min.js`, `tom-select.bootstrap5.min.css` et
`tom-select.complete.min.js`. Les `.map` ne sont pas fournis, or
`ManifestStaticFilesStorage` fait échouer `collectstatic` quand une référence
de ce type pointe vers un fichier absent.

Pour mettre à jour une bibliothèque : remplacer ses fichiers, retirer à nouveau
un éventuel `sourceMappingURL`, puis vérifier avec
`DEBUG=False python manage.py collectstatic --noinput` avant de déployer.

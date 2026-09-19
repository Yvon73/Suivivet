# Déploiement sur le VPS (Debian 13 + ISPConfig + Apache)

Ce VPS tourne sous **ISPConfig** (panneau LWS), avec un site déjà créé pour
le domaine `suivivet.fr` (utilisateur système dédié `web2`, groupe
`client0`). Ces fichiers réutilisent cet utilisateur/groupe plutôt que
d'en créer un nouveau, pour qu'Apache (qui exécute les requêtes de ce site
sous `mpm_itk` avec cet UID/GID) puisse accéder directement au socket
gunicorn sans bidouille de permissions.

**Important** : ne pas éditer `/etc/apache2/sites-available/suivivet.fr.vhost`
à la main — ISPConfig régénère ce fichier depuis sa propre base et
écraserait toute modification manuelle dès que le site est retouché dans le
panneau. La configuration Apache spécifique à l'appli se colle dans le champ
**Apache Directives** du site, dans ISPConfig (voir étape 6).

Le code applicatif vit dans `/opt/projet_veto` (hors de l'arborescence
`/var/www/suivivet.fr` gérée par ISPConfig, pour ne pas interférer avec ses
quotas/sauvegardes), mais appartient à `web2:client0`.

## 1. Code de l'application

Déjà fait si tu as suivi les étapes précédentes : dépôt public, cloné
directement sur le VPS.

```bash
git clone https://github.com/Yvon73/Suivivet.git /opt/projet_veto
sudo chown -R web2:client0 /opt/projet_veto
```

## 2. Environnement virtuel

```bash
cd /opt/projet_veto
sudo -u web2 python3 -m venv .venv
sudo -u web2 .venv/bin/pip install -r requirements.txt
```

## 3. Fichier `.env`

Copie `Projet_veto/production.env` (préparé côté dev, jamais commité) vers
`/opt/projet_veto/Projet_veto/.env` sur le VPS, par un canal chiffré, puis :

```bash
sudo chown web2:client0 /opt/projet_veto/Projet_veto/.env
sudo chmod 640 /opt/projet_veto/Projet_veto/.env
```

## 4. Base de données

```bash
sudo -u postgres psql -c "CREATE ROLE mon_user WITH LOGIN CREATEDB PASSWORD '<le mot de passe du DB_URL>';"
sudo -u postgres psql -c 'CREATE DATABASE "Projet_veto" OWNER mon_user;'
```

## 5. Migrations, statiques, dossiers

```bash
cd /opt/projet_veto
sudo -u web2 .venv/bin/python manage.py migrate
sudo -u web2 .venv/bin/python manage.py collectstatic --noinput
sudo -u web2 mkdir -p media logs
```

Le tout premier compte se crée ensuite depuis le navigateur, via la page
d'accueil (`PremierUtilisateurCreateView`) — pas besoin de `createsuperuser`.

## 6. Services systemd (gunicorn + celery)

```bash
sudo cp deploy/systemd/projet-veto-gunicorn.service /etc/systemd/system/
sudo cp deploy/systemd/projet-veto-celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now projet-veto-gunicorn projet-veto-celery
sudo systemctl status projet-veto-gunicorn projet-veto-celery
```

## 7. Apache — via le panneau ISPConfig

Dans ISPConfig : **Sites > suivivet.fr > Options > Apache Directives**, colle
le contenu de `deploy/apache/ispconfig-directives.conf`, puis enregistre.
ISPConfig régénère le vhost avec ce bloc inclus.

Modules Apache requis (normalement déjà actifs) :
```bash
apache2ctl -M | grep -E 'proxy|headers'
# sinon : sudo a2enmod proxy proxy_http headers && sudo systemctl reload apache2
```

## 8. Test avant que le DNS de suivivet.fr ne pointe vers ce VPS

Tant que `suivivet.fr` ne résout pas encore vers cette IP, teste en simulant
l'en-tête `Host` (Apache route par nom, pas par IP) :

```bash
curl -H "Host: suivivet.fr" http://192.162.68.76/
```

Une fois le DNS propagé, teste directement `http://suivivet.fr/`, puis
active le **Let's Encrypt** (case à cocher SSL du site dans ISPConfig — le
support ACME est déjà câblé dans Apache). Une fois le certificat obtenu,
voir les instructions HTTPS en tête de `ispconfig-directives.conf`.

## 9. Logs / dépannage

```bash
sudo journalctl -u projet-veto-gunicorn -f
sudo journalctl -u projet-veto-celery -f
tail -f /opt/projet_veto/logs/app.log /opt/projet_veto/logs/erreurs.log
tail -f /var/log/ispconfig/httpd/suivivet.fr/error.log
```

## Mettre à jour une installation déjà déployée

```bash
cd /opt/projet_veto
sudo -u web2 git pull
sudo -u web2 .venv/bin/pip install -r requirements.txt
sudo -u web2 .venv/bin/python manage.py migrate
sudo -u web2 .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart projet-veto-gunicorn projet-veto-celery
```

Si `deploy/apache/ispconfig-directives.conf` a changé (comme lors du retrait
de l'Alias `/media/`, cf. avertissement dans ce fichier), recopie son contenu
dans ISPConfig (Sites > suivivet.fr > Options > Apache Directives >
Enregistrer) — un `git pull` seul ne suffit pas, ISPConfig ne lit pas ce
fichier directement.

## À faire avant un vrai lancement public

- **HTTPS** : activer le Let's Encrypt ISPConfig dès que le DNS de
  `suivivet.fr` pointe vers ce VPS (voir étape 8), puis repasser
  `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` à
  `True` et `BEHIND_REVERSE_PROXY` à `True` dans `Projet_veto/.env`.
- **Mention légale RGPD** : `EDITEUR_ADRESSE`/`EDITEUR_TELEPHONE` restent à
  compléter dans `.env` quand tu sors du mode test.

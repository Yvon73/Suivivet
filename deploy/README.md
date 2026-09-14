# Déploiement sur le VPS (Debian 13 + Apache)

Ces fichiers supposent que le code vit dans `/opt/projet_veto` sur le VPS et
tourne sous un utilisateur système dédié `projetveto`. Adapte les chemins
dans les 3 fichiers si tu choisis un autre emplacement/utilisateur.

## 1. Dépendances système

```bash
sudo apt update
sudo apt install python3-venv python3-pip postgresql redis-server apache2
sudo a2enmod proxy proxy_http headers
```

## 2. Utilisateur système dédié

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin \
    --home-dir /opt/projet_veto --gid www-data projetveto
```

(`--gid www-data` : le groupe primaire de `projetveto` est `www-data`, pour
qu'Apache puisse lire le socket gunicorn — voir le service systemd.)

## 3. Code de l'application

```bash
sudo mkdir -p /opt/projet_veto
sudo chown projetveto:www-data /opt/projet_veto
# depuis ta machine de dev :
#   rsync -avz --exclude .venv --exclude media --exclude staticfiles \
#       /home/yvon/PycharmProjects/DjangoProject/ vps:/opt/projet_veto/
# puis sur le VPS :
cd /opt/projet_veto
sudo -u projetveto python3 -m venv .venv
sudo -u projetveto .venv/bin/pip install -r requirements.txt
```

Copie ensuite `Projet_veto/production.env` (généré côté dev, jamais commité)
vers `/opt/projet_veto/Projet_veto/.env` sur le VPS, par un canal chiffré
(`scp`/`rsync` via SSH) :

```bash
scp Projet_veto/production.env vps:/opt/projet_veto/Projet_veto/.env
```

## 4. Base de données

```bash
sudo -u postgres psql -c "CREATE ROLE mon_user WITH LOGIN CREATEDB PASSWORD 'change-moi';"
sudo -u postgres psql -c "CREATE DATABASE \"Projet_veto\" OWNER mon_user;"
```

⚠️ Remplace `mon_user`/`change-moi` par le rôle/mot de passe réel indiqués
dans `Projet_veto/.env` (le `DB_URL`) — voir l'avertissement dans
`production.env` sur le mot de passe faible actuel, à changer ici.

## 5. Migrations, statiques, dossiers

```bash
cd /opt/projet_veto
sudo -u projetveto .venv/bin/python manage.py migrate
sudo -u projetveto .venv/bin/python manage.py collectstatic --noinput
sudo -u projetveto .venv/bin/python manage.py createsuperuser   # ou compte via /
sudo mkdir -p /opt/projet_veto/media /opt/projet_veto/logs
sudo chown projetveto:www-data /opt/projet_veto/media /opt/projet_veto/logs
sudo chmod 750 /opt/projet_veto/media /opt/projet_veto/logs
```

## 6. Services systemd

```bash
sudo cp deploy/systemd/projet-veto-gunicorn.service /etc/systemd/system/
sudo cp deploy/systemd/projet-veto-celery.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now projet-veto-gunicorn projet-veto-celery
sudo systemctl status projet-veto-gunicorn projet-veto-celery
```

## 7. Apache

```bash
sudo cp deploy/apache/projet-veto.conf /etc/apache2/sites-available/projet-veto.conf
sudo a2ensite projet-veto
sudo systemctl reload apache2
```

Teste ensuite `http://192.162.68.76/`.

## 8. Logs / dépannage

```bash
sudo journalctl -u projet-veto-gunicorn -f
sudo journalctl -u projet-veto-celery -f
tail -f /opt/projet_veto/logs/app.log /opt/projet_veto/logs/erreurs.log
tail -f /var/log/apache2/projet-veto-error.log
```

## À faire avant un vrai lancement public

- **HTTPS** : pas de nom de domaine pour l'instant (accès par IP nue) → pas
  de certificat TLS possible. Dès que tu as un domaine (même gratuit type
  DuckDNS), fais `sudo certbot --apache` puis repasse `SESSION_COOKIE_SECURE`,
  `CSRF_COOKIE_SECURE`, `SECURE_SSL_REDIRECT` à `True` et
  `BEHIND_REVERSE_PROXY` à `True` dans `Projet_veto/.env`, et décommente la
  ligne `RequestHeader set X-Forwarded-Proto "https"` dans le vhost.
- **Mot de passe Postgres** : change `mot_de_passe` pour une valeur générée.
- **Mention légale RGPD** : `EDITEUR_ADRESSE`/`EDITEUR_TELEPHONE` restent à
  compléter dans `.env` quand tu sors du mode test.
- **Fichiers `/media/`** : servis sans authentification par Apache (cf.
  commentaire dans `projet-veto.conf`) — à revoir si des documents/factures
  sensibles ne doivent pas être accessibles par URL directe.

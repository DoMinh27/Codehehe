# CodeHehe deployment runbook

This runbook deploys Django on the same Ubuntu 22.04 Azure VM as Judge0.
Judge0 remains private on `127.0.0.1:2358`; only SSH, HTTP, and HTTPS are
public. The local SSH tunnel and `.pem` file are not used after the app is
deployed on that VM.

Replace every value wrapped in `<...>` before running a command.

## 1. Azure DNS and network

Assign a unique DNS label to the VM public IP:

```bash
az network public-ip update \
  --resource-group <RESOURCE_GROUP> \
  --name <PUBLIC_IP_RESOURCE> \
  --dns-name <UNIQUE_CODEHEHE_LABEL>

az network public-ip show \
  --resource-group <RESOURCE_GROUP> \
  --name <PUBLIC_IP_RESOURCE> \
  --query dnsSettings.fqdn \
  --output tsv
```

The returned FQDN becomes `<CODEHEHE_FQDN>`. Allow inbound TCP 22, 80, and
443 in the NSG. Do not expose port 2358.

Azure creates an A record for a Public IP DNS label:
https://learn.microsoft.com/azure/virtual-network/ip-services/public-ip-addresses

## 2. One-time server setup

```bash
sudo apt update
sudo apt install -y git python3-venv nginx certbot python3-certbot-nginx sqlite3 nodejs npm

sudo adduser --system --group --home /opt/codehehe codehehe
sudo usermod -a -G codehehe azureuser
sudo mkdir -p /opt/codehehe /var/lib/codehehe /var/www/codehehe/static /etc/codehehe
sudo chown azureuser:codehehe /opt/codehehe
sudo chown codehehe:www-data /var/lib/codehehe /var/www/codehehe/static
sudo chmod 750 /var/lib/codehehe /etc/codehehe
```

Sign out and reconnect after adding `azureuser` to the `codehehe` group.
Clone the repository and create the production environment:

```bash
git clone <REPOSITORY_URL> /opt/codehehe/app
python3 -m venv /opt/codehehe/venv
/opt/codehehe/venv/bin/pip install --upgrade pip
/opt/codehehe/venv/bin/pip install -r /opt/codehehe/app/requirements-prod.txt
```

Create `/etc/codehehe/codehehe.env` from the tracked production template. The
file must stay outside the repository:

```bash
sudo cp /opt/codehehe/app/deploy/codehehe.env.example /etc/codehehe/codehehe.env
sudo chown root:codehehe /etc/codehehe/codehehe.env
sudo chmod 640 /etc/codehehe/codehehe.env
sudoedit /etc/codehehe/codehehe.env
```

Replace every `<...>` placeholder before starting the services. The resulting
file must contain:

```text
DJANGO_SECRET_KEY=<RANDOM_SECRET>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=<CODEHEHE_FQDN>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<CODEHEHE_FQDN>
DJANGO_DB_PATH=/var/lib/codehehe/db.sqlite3
DJANGO_STATIC_ROOT=/var/www/codehehe/static
DJANGO_SQLITE_TIMEOUT=20
DJANGO_TIME_ZONE=Asia/Ho_Chi_Minh
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_COOKIES=False
DJANGO_HSTS_SECONDS=0
DJANGO_HSTS_PRELOAD=False
AI_REVIEW_ENABLED=True
AI_REVIEW_PROVIDER=groq
GROQ_API_KEY=<GROQ_API_KEY>
GEMINI_API_KEY=
OPENROUTER_API_KEY=
OPENROUTER_HTTP_REFERER=https://<CODEHEHE_FQDN>
OPENROUTER_APP_TITLE=CodeHehe
AI_REVIEW_MODEL=openai/gpt-oss-120b
AI_REVIEW_REASONING_EFFORT=none
AI_REVIEW_PROMPT_VERSION=v2
AI_REVIEW_MAX_OUTPUT_TOKENS=2048
AI_REVIEW_MAX_ATTEMPTS=5
AI_REVIEW_MAX_MANUAL_RETRIES=1
AI_REVIEW_REQUESTS_PER_MINUTE=15
AI_REVIEW_STALE_SECONDS=300
AI_REVIEW_MAX_SOURCE_CHARS=16000
DJANGO_LOG_LEVEL=INFO
MATCH_PENDING_SUBMISSION_TIMEOUT_SECONDS=120
MATCH_DURATION_SECONDS=300
MATCH_SUBMIT_RATE_LIMIT=30
MATCH_RUN_RATE_LIMIT=60
MATCH_RATE_LIMIT_WINDOW_SECONDS=60
READINESS_CHECK_JUDGE0=True
JUDGE0_BASE_URL=http://127.0.0.1:2358
JUDGE0_API_KEY=
```

Generate `DJANGO_SECRET_KEY` with:

```bash
/opt/codehehe/venv/bin/python -c "from secrets import token_urlsafe; print(token_urlsafe(50))"
```

Install the tracked service and Nginx templates:

```bash
sudo cp /opt/codehehe/app/deploy/codehehe.service /etc/systemd/system/codehehe.service
sudo cp /opt/codehehe/app/deploy/codehehe-sweep.service /etc/systemd/system/codehehe-sweep.service
sudo cp /opt/codehehe/app/deploy/codehehe-sweep.timer /etc/systemd/system/codehehe-sweep.timer
sudo cp /opt/codehehe/app/deploy/codehehe-ai-review.service /etc/systemd/system/codehehe-ai-review.service
sudo cp /opt/codehehe/app/deploy/codehehe-ai-review.timer /etc/systemd/system/codehehe-ai-review.timer
sed "s/CODEHEHE_FQDN/<CODEHEHE_FQDN>/g" \
  /opt/codehehe/app/deploy/nginx-codehehe.conf \
  | sudo tee /etc/nginx/sites-available/codehehe >/dev/null
sudo ln -s /etc/nginx/sites-available/codehehe /etc/nginx/sites-enabled/codehehe
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl daemon-reload
```

Verify Judge0 is bound only to loopback before exposing the web service:

```bash
sudo ss -ltnp | grep ':2358'
```

The output must show `127.0.0.1:2358` (or `[::1]:2358`), not `0.0.0.0:2358`.

## 3. First release

```bash
cd /opt/codehehe/app
npm ci
npm run build
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py migrate
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py collectstatic --noinput
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py seed_problems
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py createsuperuser
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py check
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py check --deploy
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py judge0_spike

sudo systemctl enable --now codehehe
sudo systemctl enable --now codehehe-sweep.timer
sudo systemctl enable --now codehehe-ai-review.timer
sudo systemctl enable --now nginx
sudo systemctl status codehehe --no-pager
sudo systemctl status codehehe-sweep.timer --no-pager
sudo systemctl status codehehe-ai-review.timer --no-pager
curl --fail http://127.0.0.1:8000/health/
curl --fail http://127.0.0.1:8000/health/ready/
```

Enable HTTPS:

```bash
sudo certbot --nginx -d <CODEHEHE_FQDN> --redirect
sudo certbot renew --dry-run
```

After HTTPS works, change these environment values and restart:

```text
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_COOKIES=True
DJANGO_HSTS_SECONDS=3600
DJANGO_HSTS_PRELOAD=False
```

```bash
sudo systemctl restart codehehe
sudo systemctl restart codehehe-sweep.timer
sudo systemctl restart codehehe-ai-review.timer
curl --fail https://<CODEHEHE_FQDN>/health/
curl --fail https://<CODEHEHE_FQDN>/health/ready/
```

After the HTTPS E2E and certificate renewal test are stable, use the final
release values and rerun `manage.py check --deploy`:

```text
DJANGO_HSTS_SECONDS=31536000
DJANGO_HSTS_PRELOAD=True
```

## 4. Routine deployment

Record the current commit and make a consistent database backup:

```bash
cd /opt/codehehe/app
git rev-parse HEAD
sudo systemctl stop codehehe-ai-review.timer
sudo systemctl stop codehehe
sudo mkdir -p /var/backups/codehehe
sudo cp --preserve=all \
  /var/lib/codehehe/db.sqlite3 \
  /var/backups/codehehe/db-$(date +%Y%m%d-%H%M%S).sqlite3
sudo systemctl start codehehe
```

Deploy the reviewed commit:

```bash
cd /opt/codehehe/app
git fetch origin
git checkout <RELEASE_COMMIT>
/opt/codehehe/venv/bin/pip install -r requirements-prod.txt
npm ci
npm run build
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py migrate
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py collectstatic --noinput
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py check
sudo cp deploy/codehehe-ai-review.service /etc/systemd/system/codehehe-ai-review.service
sudo cp deploy/codehehe-ai-review.timer /etc/systemd/system/codehehe-ai-review.timer
sudo systemctl daemon-reload
sudo systemctl restart codehehe
sudo systemctl start codehehe-ai-review.timer
sudo systemctl reload nginx
curl --fail https://<CODEHEHE_FQDN>/health/ready/
```

## 5. Rollback

If code rollback does not require restoring the database:

```bash
cd /opt/codehehe/app
git checkout <PREVIOUS_RELEASE_COMMIT>
/opt/codehehe/venv/bin/pip install -r requirements-prod.txt
sudo -u codehehe /opt/codehehe/venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart codehehe
```

If migrations are incompatible, restore the backup while Django is stopped:

```bash
sudo systemctl stop codehehe
sudo cp <BACKUP_FILE> /var/lib/codehehe/db.sqlite3
sudo chown codehehe:www-data /var/lib/codehehe/db.sqlite3
sudo systemctl start codehehe
```

## 6. Release-candidate checks

```bash
sudo systemctl status codehehe --no-pager
sudo systemctl status codehehe-sweep.timer --no-pager
sudo systemctl status codehehe-ai-review.timer --no-pager
sudo journalctl -u codehehe -n 100 --no-pager
sudo nginx -t
sudo certbot certificates
df -h
```

Run the public two-player flow:

```text
Register/Login → Create → Join → Start
→ Run Custom Input → Submit correct/wrong code
→ Score/First-solve → Surrender or timeout → Result
```

Watch the service journal during two simultaneous matches. Treat any
`database is locked`, HTTP 500, hidden-test leak, incorrect winner, or stuck
pending match as a release blocker.

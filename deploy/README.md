# Deploying RAPT

One Linux server runs everything with Docker Compose:

| Container | What it does |
|---|---|
| `web` | Caddy: serves the app, proxies `/api` to the API, gets and renews the HTTPS certificate |
| `api` | FastAPI + the agents, as the restricted database role `rapt_app` |
| `db` | Postgres 17 with pgvector; not reachable from the internet |
| `migrate` | Runs on every deploy: creates `rapt_app`, applies migrations, exits |
| `backup` | A compressed dump every night at 03:00, kept 14 days in `deploy/backups/` |
| `ops` | Operator commands (tenants, users) with the owner connection, on demand |

The server needs about 3 GB of RAM (the embedding and classifier models) and a public IP.
It's tested on Ubuntu 24.04, ARM64 and x86-64.

## 1. A server on Azure for Students (free credit, no card)

1. Sign up at <https://azure.microsoft.com/free/students> with your school email. You get
   $100 of credit for 12 months (renewable each year while you're a student).
2. **Set a budget alert first:** Portal → *Cost Management* → *Budgets* → *Add*: $80,
   alert at 50%, 80% and 100% to your email. Credit-only subscriptions stop when the
   credit runs out rather than charging you, but the alert tells you in time to move.
3. Portal → *Virtual machines* → *Create*:
   - **Image:** Ubuntu Server 24.04 LTS, **Arm64** (it matches the images tested on an M2 Mac).
   - **Size:** `B2pls_v2` (2 vCPU, 4 GiB, Arm) — or `B2s` (2 vCPU, 4 GiB, x86) if Arm isn't
     offered in your region. Check the monthly price the portal shows next to the size;
     with the $100 credit this should last about 3 months. (The free `B1s`, 1 GiB, is too
     small for now; see "Staying on free resources" below.)
   - **Authentication:** SSH public key (download the key the portal creates, or paste yours).
   - **Inbound ports:** SSH (22), HTTP (80), HTTPS (443).
   - **Disk:** Standard SSD, 30 GB is plenty.
4. When it's created, note its **public IP address**. In the VM's *Configuration*, set the
   public IP to **Static**, so it doesn't change on restart.

## 2. A free hostname (DuckDNS)

HTTPS needs a hostname. If you don't own a domain:

1. Sign in at <https://www.duckdns.org> (GitHub or Google login), create a subdomain such
   as `rapt-yourname`, and set its IP to the server's public IP.
2. Your address is `rapt-yourname.duckdns.org`.

(With your own domain, add an `A` record pointing to the server's IP instead.)

## 3. Set up the server (once)

```bash
ssh -i ~/path/to/key.pem azureuser@<public-ip>
git clone https://github.com/Daksh-Upadhayay/RAPT.git
cd RAPT
./deploy/setup-server.sh          # Docker, firewall (22/80/443 only), auto-updates, swap
exit                               # log out and in again so docker works without sudo
```

## 4. Configure and deploy

```bash
ssh -i ~/path/to/key.pem azureuser@<public-ip>
cd RAPT
cp deploy/.env.example deploy/.env
nano deploy/.env                   # RAPT_DOMAIN, the passwords, JWT_SECRET, GROQ_API_KEY
                                   # (generate each secret with: openssl rand -hex 32)
chmod 600 deploy/.env
./deploy/deploy.sh                 # builds (~10 min the first time), migrates, starts
```

Then open `https://rapt-yourname.duckdns.org`. The first visit can take a minute while
Caddy gets the certificate. `https://rapt-yourname.duckdns.org/api/health` should say
`{"status":"ok"}`.

## 5. Create the first business and its admin

```bash
ops() { docker compose -f deploy/docker-compose.yml --env-file deploy/.env run --rm ops "$@"; }
ops python -m scripts.tenants create-tenant --name "Acme Homewares" --slug acme
ops python -m scripts.tenants create-user --tenant acme --email owner@acme.com --name "Ada" --role admin
```

The last command prints a one-time password: send it to the admin privately. From then on
they add their help documents (Knowledge base) and their team (Team) themselves. After a
prospect's trial: `ops python -m scripts.tenants delete-tenant --slug acme --yes`.

The production database starts with no demo data. The migrations do create one empty
business, `dev` (it held the data from before businesses existed); remove it with
`ops python -m scripts.tenants delete-tenant --slug dev --yes`. Seed scripts are for
local development only.

## Everyday operations

| Task | Command (from `~/RAPT`) |
|---|---|
| Update to the latest code | `./deploy/deploy.sh` |
| Status | `docker compose -f deploy/docker-compose.yml --env-file deploy/.env ps` |
| API logs | `docker compose -f deploy/docker-compose.yml --env-file deploy/.env logs -f api` |
| Backup now | `./deploy/backup-now.sh` |
| Restore a backup (replaces all data) | `./deploy/restore.sh deploy/backups/<file>.dump` |
| Copy backups to your laptop | `scp -i key.pem azureuser@<ip>:RAPT/deploy/backups/*.dump .` |

Copy backups off the server now and then: a backup on the same disk doesn't survive
losing the server.

## Security notes

- Only ports 22, 80 and 443 are open (Azure's inbound rules and `ufw`); SSH accepts keys only.
- The database has no public port. The API connects as `rapt_app`, so row-level security
  keeps every query inside the signed-in user's tenant; the owner password is only used by
  `migrate`, `ops` and `backup`.
- `deploy/.env` holds every secret. It's gitignored and excluded from Docker images
  (`.dockerignore`); keep it `chmod 600`.
- Caddy sends HSTS and a strict Content-Security-Policy; the session cookie is `Secure`,
  `HttpOnly`, `SameSite=Lax`.

## Staying on free resources

The free `B1s` VM (1 GiB) can't hold the current models. A later step can move the
embedding models to ONNX Runtime so the API fits in 1 GiB; then the app can run on the
free VM for 12 months without using the credit.

## Testing the stack locally

With Docker Desktop, from the repo root (a certificate from Caddy's own local CA, so the
browser warns once):

```bash
cp deploy/.env.example /tmp/rapt-local.env    # RAPT_DOMAIN=localhost, HTTP_PORT=8080, HTTPS_PORT=8443, secrets
docker compose -f deploy/docker-compose.yml --env-file /tmp/rapt-local.env up -d --build
open https://localhost:8443
docker compose -f deploy/docker-compose.yml --env-file /tmp/rapt-local.env down -v   # remove it all
```

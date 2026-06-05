# .env Configuration Structure

OpenCloudTouch uses multiple `.env` files for different purposes:

## 📁 File Overview

```
opencloudtouch/
├── .env                          # Your personal config (gitignored)
├── .env.template                 # Template for root .env
└── deployment/
    └── local/
        ├── .env                  # Your deployment config (gitignored)
        └── .env.template         # Template for deployment config
```

## 🎯 When to use which file

### Root `.env` — Backend Development
**Use for:** Running backend locally with `python -m opencloudtouch`

```bash
# Start backend in dev mode
cd apps/backend
python -m opencloudtouch
```

**Contains:**
- Backend server settings (host, port, log level)
- Database path (local dev database)
- Discovery settings
- Deployment config for `deploy-to-server.ps1`

**Setup:**
```powershell
cp .env.template .env
# Edit .env with your values
```

### `deployment/local/.env` — Remote Deployment
**Use for:** Deploying to remote server via `deploy-to-server.ps1`

```powershell
# Deploy to test container (default)
.\deployment\local\deploy-to-server.ps1

# Deploy to production
.\deployment\local\deploy-to-server.ps1 -Prod
```

**Contains:**
- Remote server credentials (host, user, sudo)
- Container configuration (name, tag, port)
- Remote paths (data, logs, images)

**Setup:**
```powershell
cd deployment/local
cp .env.template .env
# Edit .env with your server details
```

## 🔒 Secrets Management

**Never commit secrets to .env files!**

For sensitive data (passwords, tokens), use `.env.local`:

```powershell
# .env.local (also gitignored)
SSH_PASSWORD=your_password
TELEGRAM_TOKEN=your_token
GITHUB_TOKEN=your_github_pat
```

Both `.env` and `.env.local` are in `.gitignore`.

## 📝 Configuration Priority

The root `.env` contains both:
1. **Backend dev settings** (used when running backend locally)
2. **Deployment settings** (used by `deploy-to-server.ps1`)

The `deployment/local/.env` is loaded by `config.ps1` and takes precedence for deployment operations.

## ⚙️ Available Variables

### Backend (Runtime)
```bash
OCT_HOST=0.0.0.0
OCT_PORT=7777
OCT_LOG_LEVEL=INFO
OCT_LOG_DIR=/logs
OCT_DB_PATH=/data/oct.db
OCT_MOCK_MODE=false
OCT_DISCOVERY_ENABLED=true
OCT_DISCOVERY_TIMEOUT=3
OCT_STATION_DESCRIPTOR_BASE_URL=http://localhost:7777
OCT_MANUAL_DEVICE_IPS=192.168.1.100,192.168.1.101
OCT_DEVICE_HTTP_PORT=8090
OCT_DEVICE_WS_PORT=8080
```

### Deployment (deploy-to-server.ps1)
```bash
DEPLOY_HOST=192.168.1.11
DEPLOY_USER=yourusername
DEPLOY_USE_SUDO=false
CONTAINER_NAME=opencloudtouch
CONTAINER_TAG=opencloudtouch:latest
CONTAINER_PORT=7777
REMOTE_DATA_PATH=/mnt/tank/applications/opencloudtouch/data
REMOTE_LOG_PATH=/mnt/tank/applications/opencloudtouch/logs
REMOTE_IMAGE_PATH=/tmp
LOCAL_DATA_PATH=./deployment/data-local
```

## 🚀 Quick Start

### Local Backend Development
```powershell
# 1. Setup backend env
cp .env.template .env
# Edit .env with your local settings

# 2. Run backend
cd apps/backend
python -m opencloudtouch
```

### Deploy to Remote Server
```powershell
# 1. Setup deployment env
cd deployment/local
cp .env.template .env
# Edit .env with server details

# 2. Deploy (test container by default)
.\deploy-to-server.ps1

# 3. Deploy to production stack
.\deploy-to-server.ps1 -Prod
```

## 🔍 Troubleshooting

**Q: Which .env is loaded when I run `deploy-to-server.ps1`?**  
A: `deployment/local/.env` via `config.ps1`. The root `.env` deployment vars are fallback defaults.

**Q: Can I use the same values in both .env files?**  
A: Yes, but they serve different purposes. Root `.env` is for local dev + deployment config, `deployment/local/.env` is deployment-only.

**Q: Where do I put secrets?**  
A: In `.env.local` (root) or `deployment/local/.env.local`. Both are gitignored.

**Q: Why are deployment settings in root .env?**  
A: Historical reason — originally mixed. Now `deployment/local/.env` is the canonical source for deployment, root `.env` provides fallback defaults.

# Supporters API — GitHub Actions Integration

Automatically fetches the latest supporters list from opencloudtouch.org during Docker image builds.

## Setup

### 1. Add GitHub Secret

Repository → Settings → Secrets and variables → Actions → New repository secret:

- **Name**: `SUPPORTERS_API_PASS`
- **Value**: `vzvHjJ7J.GAdCEESg1M4` (FTP password from `.local/bmc.properties`)

### 2. Workflow Integration

Already configured in `.github/workflows/build-images.yml`:

```yaml
- name: Fetch supporters from opencloudtouch.org
  env:
    SUPPORTERS_API_USER: oct-ci
    SUPPORTERS_API_PASS: ${{ secrets.SUPPORTERS_API_PASS }}
  run: |
    AUTH=$(echo -n "$SUPPORTERS_API_USER:$SUPPORTERS_API_PASS" | base64)
    curl -H "Authorization: Basic $AUTH" \
      https://opencloudtouch.org/api/supporters/get.php \
      -o apps/frontend/public/supporters.csv --fail --silent --show-error || {
      echo "⚠️ Failed to fetch supporters, using empty CSV"
      echo "name,type,amount,monthlyAmount,firstSupportDate" > apps/frontend/public/supporters.csv
    }
```

**Runs before**: Frontend build step  
**Fallback**: Empty CSV if fetch fails (no build failure)

### 3. Verify

After next release build:
1. Check workflow logs: "✅ Supporters: XX lines"
2. Download Docker image → inspect `supporters.csv` inside

## How It Works

```
New Donation
    ↓
BuyMeACoffee Webhook
    ↓
opencloudtouch.org/api/supporters/webhook.php (updates CSV)
    ↓
GitHub Actions Build (fetches CSV)
    ↓
Docker Image (includes CSV in frontend/public/)
    ↓
User's OCT Instance (shows supporters in About page)
```

## Manual CSV Update

If you need to manually update supporters (e.g., webhook missed an event):

```powershell
# In opencloudtouch repo
cd .local
.\deploy-supporters-api.ps1  # Re-uploads latest CSV from BMC exports
```

## Troubleshooting

**Build fails with "Failed to fetch supporters"**
- Check if `SUPPORTERS_API_PASS` secret is set correctly
- Verify API endpoint is accessible: `curl -u oct-ci:PASSWORD https://opencloudtouch.org/api/supporters/get.php`
- Check opencloudtouch.org server status

**Supporters not showing in About page**
- Clear browser cache
- Check if `supporters.csv` exists in built image: `docker run --rm oct-image cat /app/frontend/supporters.csv`
- Verify frontend code loads CSV correctly (check browser console)

**New donation not appearing**
- Check BMC webhook status: Dashboard → Webhooks → Event History
- Download logs: `cd .local && .\download-logs.ps1`
- Verify signature in webhook-debug.log
- Manually retry failed webhook from BMC Dashboard

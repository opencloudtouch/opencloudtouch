# OpenCloudTouch API Reference

## Overview

OpenCloudTouch exposes a RESTful API on port 7777 (default).

The API follows REST conventions and returns JSON responses. All endpoints are prefixed with `/api/` except system endpoints like `/health`.

## Interactive Documentation

When the server is running, you can access interactive API documentation:

- **Swagger UI**: http://localhost:7777/docs
- **ReDoc**: http://localhost:7777/redoc
- **OpenAPI Spec**: http://localhost:7777/openapi.json

## Base URL

```
http://localhost:7777/api
```

## Endpoints

### Devices

#### List All Devices
```http
GET /api/devices
```

Returns all devices currently known to the system (discovered or manually configured).

**Response:**
```json
[
  {
    "device_id": "AA:BB:CC:DD:EE:FF",
    "name": "Living Room",
    "ip": "192.168.1.100",
    "type": "SoundTouch 30",
    "created_at": "2026-02-13T10:00:00Z",
    "updated_at": "2026-02-13T10:00:00Z"
  }
]
```

#### Run Device Discovery
```http
POST /api/devices/discover
```

Initiates SSDP discovery for SoundTouch devices on the network.

**Query Parameters:**
- `timeout` (optional): Discovery timeout in seconds (default: 10)

**Response:**
```json
[
  {
    "device_id": "AA:BB:CC:DD:EE:FF",
    "ip": "192.168.1.100",
    "name": "Living Room",
    "type": "SoundTouch 30"
  }
]
```

#### Sync Discovered Devices
```http
POST /api/devices/sync
```

Synchronizes discovered devices to the database. Typically called after `/api/devices/discover`.

**Response:**
```json
{
  "synced_count": 3
}
```

#### Get Device Details
```http
GET /api/devices/{device_id}
```

Retrieves detailed information about a specific device.

**Response:**
```json
{
  "device_id": "AA:BB:CC:DD:EE:FF",
  "name": "Living Room",
  "ip": "192.168.1.100",
  "type": "SoundTouch 30",
  "firmware": "4.8.1.24047",
  "created_at": "2026-02-13T10:00:00Z",
  "updated_at": "2026-02-13T10:00:00Z"
}
```

#### Delete All Devices
```http
DELETE /api/devices
```

Removes all devices from the database.

**Response:**
```json
{
  "deleted_count": 3
}
```

---

### Presets

#### Get Device Presets
```http
GET /api/devices/{device_id}/presets
```

Retrieves all configured presets (slots 1-6) for a device.

**Response:**
```json
[
  {
    "device_id": "AA:BB:CC:DD:EE:FF",
    "preset_number": 1,
    "station_name": "BBC Radio 1",
    "station_url": "http://stream.example.com/bbc1",
    "created_at": "2026-02-13T10:00:00Z"
  }
]
```

#### Set Preset
```http
PUT /api/devices/{device_id}/presets/{slot}
```

Assigns a radio station to a preset slot (1-6).

**Path Parameters:**
- `device_id`: Device MAC address
- `slot`: Preset number (1-6)

**Request Body:**
```json
{
  "station_name": "BBC Radio 1",
  "station_url": "http://stream.example.com/bbc1"
}
```

**Response:**
```json
{
  "device_id": "AA:BB:CC:DD:EE:FF",
  "preset_number": 1,
  "station_name": "BBC Radio 1",
  "station_url": "http://stream.example.com/bbc1",
  "created_at": "2026-02-13T10:30:00Z"
}
```

#### Clear Preset
```http
DELETE /api/devices/{device_id}/presets/{slot}
```

Removes a preset from the specified slot.

**Response:**
```json
{
  "deleted": true
}
```

---

### Radio

#### Search Radio Stations
```http
GET /api/radio/search
```

Searches for radio stations via RadioBrowser.info API.

**Query Parameters:**
- `query` (optional): Search term (station name)
- `country` (optional): ISO country code (e.g., "GB")
- `tag` (optional): Genre/tag filter (e.g., "pop")
- `limit` (optional): Max results (default: 50)

**Response:**
```json
[
  {
    "station_id": "uuid-12345",
    "name": "BBC Radio 1",
    "url": "http://stream.example.com/bbc1",
    "country": "GB",
    "codec": "MP3",
    "bitrate": 128,
    "tags": ["pop", "rock"],
    "favicon": "http://example.com/logo.png",
    "homepage": "http://bbc.co.uk/radio1",
    "provider": "radiobrowser"
  }
]
```

#### List Countries
```http
GET /api/radio/countries
```

Returns all available countries with station counts.

**Response:**
```json
[
  {
    "code": "GB",
    "name": "United Kingdom",
    "station_count": 1234
  }
]
```

#### List Genres/Tags
```http
GET /api/radio/genres
```

Returns all available genre tags.

**Response:**
```json
[
  {
    "name": "pop",
    "station_count": 5678
  }
]
```

---

### Settings

#### Get Manual Device IPs
```http
GET /api/settings/manual-ips
```

Retrieves the list of manually configured device IPs.

**Response:**
```json
{
  "ips": ["192.168.1.100", "192.168.1.101"]
}
```

#### Update Manual Device IPs
```http
PUT /api/settings/manual-ips
```

Updates the list of manual device IPs (persisted to database).

**Request Body:**
```json
{
  "ips": ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
}
```

**Response:**
```json
{
  "ips": ["192.168.1.100", "192.168.1.101", "192.168.1.102"]
}
```

---

### System

#### Health Check
```http
GET /health
```

Returns server health status.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-13T10:00:00Z"
}
```

#### System Information
```http
GET /api/system/info
```

Returns system metadata (version, build info).

**Response:**
```json
{
  "version": "0.2.0",
  "environment": "production"
}
```

---

## Error Handling

All endpoints return consistent error responses:

### 400 Bad Request
```json
{
  "detail": "Invalid preset number. Must be between 1 and 6."
}
```

### 404 Not Found
```json
{
  "detail": "Device not found: AA:BB:CC:DD:EE:FF"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to connect to device"
}
```

---

## CORS Configuration

By default, CORS allows requests from:
- `http://localhost:3000` (development)
- `http://localhost:5173` (Vite dev server)
- `http://localhost:7777` (production)

Configure custom origins via:
```yaml
# config.yaml
cors_origins:
  - "http://truenas.local:7777"
```

**⚠️ Security Warning:** Never use `["*"]` in production environments.

---

## Authentication

**None.** OpenCloudTouch is designed for local network use only.

For production deployments, consider adding reverse proxy authentication (nginx, Caddy) if exposing to untrusted networks.

---

## Rate Limiting

No rate limits applied. API is designed for single-user/household use on local network.

---

## Versioning

API version follows application version (currently `v0.2.0`).

Breaking changes will increment the minor version (e.g., `v0.2.x` → `v0.3.0`).

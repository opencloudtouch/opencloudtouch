"""Setup Wizard — server-info / strategy-detection / hostname-validation.

Pre-Step-3 discovery endpoints: these run before the user picks a wizard
path, so they take no WizardService dependency.
"""

import asyncio
import ipaddress
import logging
import socket
from typing import Any, Dict

import httpx
from fastapi import APIRouter, Request

from opencloudtouch.core.config import get_config
from opencloudtouch.setup.api_models import (
    DetectStrategyResponse,
    ValidateHostnameRequest,
    ValidateHostnameResponse,
)
from opencloudtouch.setup.wizard_helpers import check_port_443

logger = logging.getLogger(__name__)

strategy_router = APIRouter()


@strategy_router.get("/wizard/server-info")
async def wizard_server_info(request: Request) -> Dict[str, Any]:
    """Get OCT server info for auto-filling wizard forms.

    Returns server URL that frontend can use as default.
    Detects host/port from incoming HTTP request headers.
    Also resolves the hostname to an IP for /etc/hosts usage.
    """
    # Extract from actual HTTP request
    url = request.url
    hostname = url.hostname or "127.0.0.1"

    # Resolve actual LAN IP for /etc/hosts (requires numeric IP).
    # Do NOT use the request hostname — behind Docker/port-forwarding it's
    # "localhost" which resolves to 127.0.0.1 and breaks device hosts entries.
    try:
        server_ip = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        # Fallback: try resolving request hostname (better than nothing)
        try:
            server_ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            server_ip = hostname

    # Guard against loopback IPs (common in Docker where /etc/hosts maps
    # the container ID to 127.0.0.1).  Use a UDP connect trick to find
    # the real outgoing interface IP without sending any traffic.
    #
    # How: Opening a UDP socket and connect()ing to an external address
    # (here 8.8.8.8) causes the OS to select the outgoing network interface
    # without actually sending a packet.  getsockname() then returns the
    # local IP of that interface — i.e. the LAN IP the device can reach.
    if server_ip.startswith("127."):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.connect(("8.8.8.8", 80))
                server_ip = s.getsockname()[0]
            finally:
                s.close()
        except OSError:
            # UDP trick failed — fall back to request hostname
            if not hostname.startswith("127."):
                server_ip = hostname

    # Build server_url using the resolved IP so the frontend gets a
    # reachable address, not the browser hostname (e.g. "hera").
    server_url = f"{url.scheme}://{server_ip}:{url.port or get_config().port}"

    return {
        "server_url": server_url,
        "server_ip": server_ip,
        "default_port": get_config().port,
        "supported_protocols": ["http", "https"],
    }


@strategy_router.get("/wizard/detect-strategy", response_model=DetectStrategyResponse)
async def wizard_detect_strategy(request: Request) -> DetectStrategyResponse:
    """Detect whether an HTTPS reverse proxy is available on port 443.

    If a reverse proxy (e.g. Nginx) terminates SSL on 443 and forwards
    to OCT, then the device only needs ``/etc/hosts`` changes (Strategy B).
    Otherwise, the BMX URL in the device config must also be changed
    (Strategy A + hosts).
    """
    hostname = request.url.hostname or "127.0.0.1"

    proxy_available = check_port_443(hostname)

    if proxy_available:
        return DetectStrategyResponse(
            proxy_available=True,
            strategy="hosts_only",
            message=(
                "HTTPS Reverse-Proxy auf Port 443 erkannt. "
                "Es reicht, die /etc/hosts-Datei zu �ndern."
            ),
        )
    return DetectStrategyResponse(
        proxy_available=False,
        strategy="bmx_and_hosts",
        message=(
            "Kein Reverse-Proxy auf Port 443 erkannt. "
            "Die BMX-URL muss zus�tzlich ge�ndert werden."
        ),
    )


async def _check_oct_reachability(hostname: str, port: int) -> tuple[bool, str | None]:
    """Check if OpenCloudTouch is reachable at hostname:port.

    Returns:
        Tuple of (reachable, error_message)
    """
    url = f"http://{hostname}:{port}/health"  # noqa: S5332
    logger.info("Checking OCT reachability: %s", url)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)

            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("service") == "opencloudtouch":
                        logger.info("OCT reachable at %s", url)
                        return True, None
                    else:
                        error = f"Server at {hostname}:{port} is not OpenCloudTouch"
                        logger.warning("Non-OCT response at %s: %s", url, data)
                        return False, error
                except Exception:
                    error = f"Invalid response from {hostname}:{port}"
                    logger.warning("Invalid JSON at %s", url, exc_info=True)
                    return False, error
            else:
                error = f"HTTP {response.status_code} from {hostname}:{port}"
                logger.warning("HTTP %s from %s", response.status_code, url)
                return False, error

    except httpx.ConnectError:
        error = f"Connection refused at {hostname}:{port}"
        logger.warning("Connection refused: %s", url)
        return False, error
    except httpx.TimeoutException:
        error = f"Connection timeout to {hostname}:{port}"
        logger.warning("Timeout: %s", url)
        return False, error
    except Exception as e:
        error = f"Could not reach {hostname}:{port}"
        logger.warning("OCT check failed for %s: %s", url, e, exc_info=True)
        return False, error


@strategy_router.post("/wizard/validate-hostname")
async def wizard_validate_hostname(
    request: ValidateHostnameRequest,
) -> ValidateHostnameResponse:
    """Validate a hostname or IP via DNS resolution and OCT reachability.

    Used by Wizard Step 5 when the user enters a hostname or IP address.
    For hostnames: validates DNS resolution and checks if OCT is reachable.
    For IPs: skips DNS resolution and only checks if OCT is reachable.

    Returns whether the hostname/IP resolves, if it matches the expected IP,
    and whether OCT is reachable at the given hostname:port.
    """
    hostname = request.hostname
    port = request.port
    logger.info("Validating hostname/IP and OCT reachability: %s", hostname)

    # Check if input is an IP address (skip DNS resolution for IPs)
    is_ip = False
    try:
        ipaddress.ip_address(hostname)
        is_ip = True
        logger.info("Input is an IP address, skipping DNS resolution")
    except ValueError:
        pass  # Not an IP, proceed with DNS resolution

    # For IPs: skip DNS resolution, only check OCT reachability
    if is_ip:
        oct_reachable, oct_error = await _check_oct_reachability(hostname, port)
        return ValidateHostnameResponse(
            resolvable=True,  # IPs are always "resolvable" (they resolve to themselves)
            resolved_ip=hostname,
            matches_expected=None,  # No DNS comparison needed for IPs
            oct_reachable=oct_reachable,
            error=None,
            oct_error=oct_error,
        )

    # For hostnames: perform DNS resolution
    try:
        result = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        if not result:
            return ValidateHostnameResponse(
                resolvable=False,
                resolved_ip=None,
                matches_expected=None,
                oct_reachable=False,
                error=f"DNS resolution returned no results for '{hostname}'",
                oct_error=None,
            )

        resolved_ip: str = str(result[0][4][0])

        matches = None
        if request.expected_ip is not None:
            matches = resolved_ip == request.expected_ip

        logger.info(
            "Hostname '%s' resolved to %s (expected: %s, match: %s)",
            hostname,
            resolved_ip,
            request.expected_ip,
            matches,
        )

        # Check if OCT is reachable at hostname:port
        oct_reachable, oct_error = await _check_oct_reachability(hostname, port)

        return ValidateHostnameResponse(
            resolvable=True,
            resolved_ip=resolved_ip,
            matches_expected=matches,
            oct_reachable=oct_reachable,
            error=None,
            oct_error=oct_error,
        )

    except socket.gaierror as e:
        logger.warning("DNS resolution failed for '%s': %s", hostname, e)
        # Provide user-friendly error message based on errno
        if e.errno == -2:  # EAI_NONAME
            user_msg = f"Hostname '{hostname}' could not be resolved"
        elif e.errno == -3:  # EAI_AGAIN
            user_msg = f"DNS server temporarily unavailable for '{hostname}'"
        elif e.errno == -5:  # EAI_NODATA
            user_msg = f"No IP address found for hostname '{hostname}'"
        else:
            user_msg = f"DNS resolution failed for '{hostname}'"

        return ValidateHostnameResponse(
            resolvable=False,
            resolved_ip=None,
            matches_expected=None,
            oct_reachable=False,
            error=user_msg,
            oct_error=None,
        )
    except Exception:
        logger.exception("Unexpected error during DNS validation")
        return ValidateHostnameResponse(
            resolvable=False,
            resolved_ip=None,
            matches_expected=None,
            oct_reachable=False,
            error=f"Could not validate hostname '{hostname}'",
            oct_error=None,
        )

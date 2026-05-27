"""
Regression tests for bugfixes.

Each test documents a specific bug that was fixed and ensures
it does not reoccur. Tests are organized by bug ID and date.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from opencloudtouch.radio.providers.mock import MockRadioAdapter


class TestBugfix001MockRadioStationFieldMismatch:
    """
    BUGFIX 001: MockRadioAdapter used RadioBrowser-specific fields.

    Date: 2026-02-11
    Symptom: TypeError: RadioStation.__init__() got an unexpected keyword
             argument 'url_resolved'
    Root Cause: MockAdapter imported RadioStation from radiobrowser.py
                instead of models.py and used RadioBrowser-specific fields:
                - station_uuid instead of station_id
                - tags as comma-separated string instead of List[str]
                - RadioBrowser-only fields: url_resolved, countrycode, state,
                  language, languagecodes, votes, hls, lastcheckok,
                  clickcount, clicktrend
    Fix: Changed import to models.RadioStation, renamed station_uuid to
         station_id, converted tags to List[str], removed RadioBrowser-only
         fields, added provider="mock"
    Impact: E2E tests for ERROR_503/504/500 simulation failed before fix
    """

    @pytest.mark.asyncio
    async def test_mock_stations_use_station_id_not_uuid(self):
        """Verify MockAdapter uses station_id (not station_uuid)."""
        adapter = MockRadioAdapter()
        stations = await adapter.search_by_country("Germany")

        assert len(stations) > 0
        for station in stations:
            # Verify RadioStation model has station_id field
            assert hasattr(station, "station_id")
            assert isinstance(station.station_id, str)
            assert station.station_id.startswith("mock-")

            # Verify NO RadioBrowser-specific uuid field
            assert not hasattr(station, "station_uuid")

    @pytest.mark.asyncio
    async def test_mock_stations_tags_are_list_not_string(self):
        """Verify tags field is List[str], not comma-separated string."""
        adapter = MockRadioAdapter()
        stations = await adapter.search_by_country("United Kingdom")

        assert len(stations) > 0
        for station in stations:
            # Verify tags is a list
            assert isinstance(station.tags, list)
            # Verify list contains strings
            if station.tags:
                assert all(isinstance(tag, str) for tag in station.tags)

    @pytest.mark.asyncio
    async def test_mock_stations_no_radiobrowser_only_fields(self):
        """Verify mock stations don't have RadioBrowser-only fields."""
        adapter = MockRadioAdapter()
        stations = await adapter.search_by_country("France")

        assert len(stations) > 0
        station = stations[0]

        # Verify RadioBrowser-only fields do NOT exist
        radiobrowser_only_fields = [
            "url_resolved",
            "countrycode",  # We use 'country' instead
            "state",
            "language",  # Removed (not in models.RadioStation)
            "languagecodes",
            "votes",
            "hls",
            "lastcheckok",
            "clickcount",
            "clicktrend",
        ]

        for field in radiobrowser_only_fields:
            assert not hasattr(
                station, field
            ), f"RadioStation should not have RadioBrowser-only field: {field}"

    @pytest.mark.asyncio
    async def test_mock_stations_have_provider_field(self):
        """Verify mock stations have provider='mock' field."""
        adapter = MockRadioAdapter()
        stations = await adapter.search_by_country("Germany")

        assert len(stations) > 0
        for station in stations:
            assert hasattr(station, "provider")
            assert station.provider == "mock"

    @pytest.mark.asyncio
    async def test_error_simulation_throws_exceptions_correctly(self):
        """Verify ERROR_500/503/504 simulation works via search_by_name() method."""
        adapter = MockRadioAdapter()

        # Test ERROR_500 simulation
        with pytest.raises(Exception) as exc_info:
            await adapter.search_by_name("ERROR_500")
        assert "Internal server error" in str(exc_info.value) or "500" in str(
            exc_info.value
        )

        # Test ERROR_503 simulation
        with pytest.raises(Exception) as exc_info:
            await adapter.search_by_name("ERROR_503")
        assert "Service unavailable" in str(exc_info.value) or "503" in str(
            exc_info.value
        )

        # Test ERROR_504 simulation
        with pytest.raises(Exception) as exc_info:
            await adapter.search_by_name("ERROR_504")
        assert "timeout" in str(exc_info.value).lower() or "504" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_search_by_country_uses_country_field_not_countrycode(self):
        """Verify search_by_country uses 'country' field (not 'countrycode')."""
        adapter = MockRadioAdapter()

        # Search should work with country name
        uk_stations = await adapter.search_by_country(query="United Kingdom")
        assert len(uk_stations) > 0
        for station in uk_stations:
            assert station.country == "United Kingdom"

        # Verify 'countrycode' field doesn't exist
        assert not hasattr(uk_stations[0], "countrycode")

    @pytest.mark.asyncio
    async def test_get_by_uuid_uses_station_id_property(self):
        """Verify get_by_uuid searches by station_id (not station_uuid)."""
        adapter = MockRadioAdapter()

        # Search by station_id should work
        station = await adapter.get_by_uuid(uuid="mock-bbc-1")
        assert station is not None
        assert station.station_id == "mock-bbc-1"
        assert station.name == "BBC Radio 1"

        # Verify station has station_id, not station_uuid
        assert hasattr(station, "station_id")
        assert not hasattr(station, "station_uuid")


class TestBugfix002ManualIpNotUsedAfterStartup:
    """
    BUGFIX 002: Manual IPs added via UI are not used in device sync.

    Date: 2026-05-01
    Issue: #106
    Symptom: User adds a device IP via Settings → Manual IPs, triggers
             discovery — device never appears. The 4th speaker is reachable
             via curl but OCT ignores it.
    Root Cause: DeviceSyncService is initialized once at startup with
                manual_ips from environment config (OCT_MANUAL_DEVICE_IPS).
                IPs added at runtime via the UI are stored in the SQLite DB
                (settings_repo) but DeviceSyncService.manual_ips is a static
                list that is NEVER updated from the DB.
    Fix: DeviceSyncService accepts an optional SettingsRepository. When
         provided, _discover_via_manual_ips() fetches the current IP list
         from the DB at sync time instead of using the stale startup list.
    Impact: Any user who adds manual IPs via the UI — they are silently ignored.
    """

    @pytest.fixture
    def mock_device_repo(self):
        repo = AsyncMock()
        repo.upsert = AsyncMock()
        return repo

    @pytest.fixture
    def mock_device_info(self):
        info = MagicMock()
        info.device_id = "DEADBEEF0004"
        info.name = "SoundTouch 10 Bedroom"
        info.type = "SoundTouch 10"
        info.mac_address = "DE:AD:BE:EF:00:04"
        info.firmware_version = "27.0.6.46330"
        return info

    @pytest.mark.asyncio
    async def test_manual_ip_added_at_runtime_is_used_in_next_sync(
        self, mock_device_repo, mock_device_info, monkeypatch
    ):
        """
        IPs added via the UI (stored in SettingsRepository) must be picked up
        by the NEXT sync — not just at container startup.

        Regression: before the fix, DeviceSyncService.manual_ips was set once
        at construction time and never refreshed from the DB.
        """
        from opencloudtouch.devices.services.sync_service import DeviceSyncService

        # Simulate SettingsRepository that returns a newly-added IP
        mock_settings_repo = AsyncMock()
        mock_settings_repo.get_manual_ips = AsyncMock(return_value=["192.168.1.40"])

        # Disable SSDP so only manual IPs are in play
        async def no_ssdp(self):
            return []

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", no_ssdp)

        mock_client = AsyncMock()
        mock_client.get_info = AsyncMock(return_value=mock_device_info)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        # Service constructed with empty startup list but a settings_repo
        service = DeviceSyncService(
            repository=mock_device_repo,
            manual_ips=[],  # empty at startup — IP was added later via UI
            discovery_enabled=False,
            settings_repo=mock_settings_repo,
        )

        result = await service.sync()

        # The runtime-added IP must have been discovered and synced
        assert (
            result.discovered == 1
        ), "Device added via UI must be discovered in the next sync"
        assert result.synced == 1
        mock_settings_repo.get_manual_ips.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_ips_used_when_no_settings_repo(
        self, mock_device_repo, mock_device_info, monkeypatch
    ):
        """
        Backward compat: when no settings_repo is provided (e.g. env-var only
        setup), the static startup list is still used.
        """
        from opencloudtouch.devices.services.sync_service import DeviceSyncService

        async def no_ssdp(self):
            return []

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", no_ssdp)

        mock_client = AsyncMock()
        mock_client.get_info = AsyncMock(return_value=mock_device_info)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            lambda url: mock_client,
        )

        service = DeviceSyncService(
            repository=mock_device_repo,
            manual_ips=["192.168.1.50"],
            discovery_enabled=False,
            # no settings_repo
        )

        result = await service.sync()

        assert result.discovered == 1
        assert result.synced == 1

    @pytest.mark.asyncio
    async def test_db_ips_take_precedence_over_startup_ips_when_settings_repo_present(
        self, mock_device_repo, mock_device_info, monkeypatch
    ):
        """
        When settings_repo is present, the DB list is the authoritative source —
        it replaces (not merges with) the static startup list.
        This avoids confusion when a user removes an IP via the UI but it still
        lingers in the env var.
        """
        from opencloudtouch.devices.services.sync_service import DeviceSyncService

        contacted_ips = []

        async def no_ssdp(self):
            return []

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", no_ssdp)

        def capturing_client(base_url):
            contacted_ips.append(base_url)
            client = AsyncMock()
            client.get_info = AsyncMock(return_value=mock_device_info)
            return client

        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            capturing_client,
        )

        # DB has only one IP; startup list has a different IP
        mock_settings_repo = AsyncMock()
        mock_settings_repo.get_manual_ips = AsyncMock(return_value=["192.168.1.60"])

        service = DeviceSyncService(
            repository=mock_device_repo,
            manual_ips=["192.168.1.99"],  # stale env-var IP
            discovery_enabled=False,
            settings_repo=mock_settings_repo,
        )

        result = await service.sync()

        assert result.discovered == 1
        # Only the DB IP must have been contacted, not the stale env-var IP
        assert any(
            "192.168.1.60" in url for url in contacted_ips
        ), "DB IP must be contacted"
        assert not any(
            "192.168.1.99" in url for url in contacted_ips
        ), "Stale startup IP must NOT be contacted when settings_repo is present"


class TestBugfix002ParseApiErrorMissingFunction:
    """
    BUGFIX 002: parseApiError() function missing in types.ts.

    Date: 2026-02-11
    Symptom: E2E test failure "parseApiError is not defined"
    Root Cause: RadioSearch.tsx called parseApiError() but function
                didn't exist in types.ts
    Fix: Added parseApiError() function to types.ts (lines 90-110)
         with JSON content-type check and isApiError validation
    Impact: E2E radio-search-robustness tests failed before fix

    NOTE: This is a frontend (TypeScript) bug - cannot write Python
          unit test for it. E2E test coverage exists in:
          apps/frontend/cypress/e2e/radio/radio-search-robustness.cy.ts
    """

    def test_frontend_regression_tracked_in_e2e(self):
        """Document that parseApiError() is tested in E2E suite."""
        # This bugfix is tested in E2E tests:
        # - apps/frontend/cypress/e2e/radio/radio-search-robustness.cy.ts
        # - Tests verify ERROR_503/504/500 error messages display correctly
        # - Tests verify parseApiError extracts ErrorDetail from responses
        assert True, "parseApiError() regression coverage exists in E2E suite"


class TestNoDeviceCountLimit:
    """
    Verify there is no hard limit on the number of discoverable devices.

    Historically the mock adapter shipped with exactly 3 devices, which led
    to user reports suspecting a 3-device cap (issue #106).
    These tests confirm that 4, 5, and 6 devices are all discovered and synced
    without truncation, rejection, or silent drops.
    """

    def _make_device_info(self, index: int) -> MagicMock:
        info = MagicMock()
        info.device_id = f"DEVICE{index:06X}"
        info.name = f"SoundTouch {index}"
        info.type = "SoundTouch 10"
        info.mac_address = f"AA:BB:CC:DD:EE:{index:02X}"
        info.firmware_version = "27.0.6.46330"
        return info

    def _make_discovered(self, count: int):
        from opencloudtouch.discovery import DiscoveredDevice

        return [
            DiscoveredDevice(ip=f"192.168.1.{100 + i}", port=8090) for i in range(count)
        ]

    async def _run_sync(self, count: int, monkeypatch) -> int:
        from opencloudtouch.devices.services.sync_service import DeviceSyncService

        devices = self._make_discovered(count)

        async def mock_ssdp(self):
            return devices

        call_index = {"i": 0}

        def mock_client(base_url):
            client = AsyncMock()
            client.get_info = AsyncMock(
                return_value=self._make_device_info(call_index["i"])
            )
            call_index["i"] += 1
            return client

        monkeypatch.setattr(DeviceSyncService, "_discover_via_ssdp", mock_ssdp)
        monkeypatch.setattr(
            "opencloudtouch.devices.services.sync_service.get_device_client",
            mock_client,
        )
        monkeypatch.setattr(
            DeviceSyncService,
            "_fetch_marge_account_uuid",
            staticmethod(AsyncMock(return_value=None)),
        )

        repo = AsyncMock()
        repo.upsert = AsyncMock()
        service = DeviceSyncService(repository=repo, discovery_enabled=True)
        result = await service.sync()
        return result.synced

    @pytest.mark.asyncio
    async def test_four_devices_all_synced(self, monkeypatch):
        """4 devices must all be discovered and synced — no 3-device cap."""
        synced = await self._run_sync(4, monkeypatch)
        assert synced == 4, f"Expected 4 synced devices, got {synced}"

    @pytest.mark.asyncio
    async def test_five_devices_all_synced(self, monkeypatch):
        """5 devices must all be discovered and synced."""
        synced = await self._run_sync(5, monkeypatch)
        assert synced == 5, f"Expected 5 synced devices, got {synced}"

    @pytest.mark.asyncio
    async def test_six_devices_all_synced(self, monkeypatch):
        """6 devices must all be discovered and synced."""
        synced = await self._run_sync(6, monkeypatch)
        assert synced == 6, f"Expected 6 synced devices, got {synced}"


class TestBugfix003RadioSearchImportIncomplete:
    """
    BUGFIX 003: RadioSearch.tsx missing parseApiError import.

    Date: 2026-02-11
    Symptom: Runtime error when error handling code executes
    Root Cause: RadioSearch.tsx line 88 called parseApiError(response)
                but function was not imported from types.ts
    Fix: Added parseApiError to import statement (line 2)
    Impact: Radio search error handling failed at runtime

    NOTE: This is a frontend (TypeScript) bug - cannot write Python
          unit test for it. E2E test coverage exists in:
          apps/frontend/cypress/e2e/radio/radio-search-robustness.cy.ts
    """

    def test_frontend_import_regression_tracked_in_e2e(self):
        """Document that RadioSearch error handling is tested in E2E suite."""
        # This bugfix is tested in E2E tests:
        # - apps/frontend/cypress/e2e/radio/radio-search-robustness.cy.ts
        # - Tests verify error handling executes without import errors
        # - Tests verify ERROR_503 displays "Dienst nicht verfügbar"
        assert True, "RadioSearch error handling coverage exists in E2E suite"


class TestBugfix188HardcodedDeviceIdInStreamingAccount:
    """
    BUGFIX 188: /streaming/account/{account_id}/full used hardcoded device_id.

    Date: 2026-05-12
    Issue: https://github.com/opencloudtouch/opencloudtouch/issues/188
    Reporter: Zimbo88
    Symptom: Device boots, calls /streaming/account/5522049/full,
             receives empty presets because code used hardcoded
             device_id="689E194F7D2F" instead of resolving via
             margeAccountUUID mapping.
    Root Cause: streaming_full_account() had a TODO comment and
                hardcoded device_id instead of looking up the device
                by its margeAccountUUID from the database.
    Fix: - Added marge_account_uuid column to devices table
         - Sync service fetches UUID from device /info on discovery
         - streaming_full_account resolves device via DB lookup
    """

    def test_no_hardcoded_device_id_in_streaming_route(self):
        """Ensure streaming_full_account does not contain hardcoded device IDs."""
        import inspect
        from opencloudtouch.marge.routes import streaming_full_account

        source = inspect.getsource(streaming_full_account)
        assert (
            "689E194F7D2F" not in source
        ), "streaming_full_account must not contain hardcoded device ID"
        assert "# TODO: Get from account mapping" not in source

    @pytest.mark.asyncio
    async def test_resolves_device_by_account_uuid(self):
        """Account UUID maps to correct device → presets loaded for that device."""
        from opencloudtouch.marge.routes import streaming_full_account
        from opencloudtouch.marge.service import MargeService

        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(
            return_value="10CEA9A6FA71"
        )
        mock_marge.get_full_account = AsyncMock(return_value=([], []))

        await streaming_full_account("5522049", mock_marge)

        # Must have looked up by account UUID, not used hardcoded ID
        mock_marge.resolve_device_id_for_account.assert_called_once_with("5522049")
        # Must have loaded full account for the RESOLVED device
        mock_marge.get_full_account.assert_called_once_with("10CEA9A6FA71")

    @pytest.mark.asyncio
    async def test_unknown_account_returns_empty_not_crash(self):
        """Unknown account UUID → empty presets, no crash, no guessing."""
        from opencloudtouch.marge.routes import streaming_full_account
        from opencloudtouch.marge.service import MargeService
        from xml.etree import ElementTree

        mock_marge = AsyncMock(spec=MargeService)
        mock_marge.resolve_device_id_for_account = AsyncMock(return_value=None)

        result = await streaming_full_account("UNKNOWN", mock_marge)

        assert result.status_code == 200
        root = ElementTree.fromstring(result.body.decode())
        presets = root.find("presets")
        assert len(presets.findall("preset")) == 0
        # Must NOT have tried to load presets with some guessed device
        mock_marge.get_full_account.assert_not_called()

    @pytest.mark.asyncio
    async def test_mock_mode_skips_marge_uuid_fetch(self, monkeypatch):
        """In mock mode, _fetch_marge_account_uuid must skip HTTP call."""
        from opencloudtouch.devices.services.sync_service import DeviceSyncService

        monkeypatch.setenv("OCT_MOCK_MODE", "true")
        result = await DeviceSyncService._fetch_marge_account_uuid("192.168.1.100")
        assert result is None

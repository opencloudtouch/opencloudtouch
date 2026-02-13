"""
Regression tests for bugfixes.

Each test documents a specific bug that was fixed and ensures
it does not reoccur. Tests are organized by bug ID and date.
"""

import pytest
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

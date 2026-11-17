from __future__ import annotations

import pytest

from booking_precheck import BookingPrecheckService


@pytest.fixture(scope="session")
def service() -> BookingPrecheckService:
    return BookingPrecheckService()


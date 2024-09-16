"""Tests standard tap features using the built-in SDK tests library."""

from singer_sdk.testing import get_tap_test_class

from govdata.tap import TapNarodniKatalog

SAMPLE_CONFIG = {
    "iris": [
        "https://data.gov.cz/zdroj/datové-sady/00025593/790624c7263aca615ce9ddd24e7db464",
    ]
}


# Run standard built-in tap tests from the SDK:
TestTapNarodniKatalog = get_tap_test_class(
    tap_class=TapNarodniKatalog,
    config=SAMPLE_CONFIG,
)


# TODO: Create additional tests as appropriate for your tap.

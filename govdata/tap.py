"""NarodniKatalog tap class."""

from singer_sdk import Tap
from singer_sdk import typing as th

from govdata.client import NarodniKatalogStream


class TapNarodniKatalog(Tap):
    """NarodniKatalog tap class."""

    name = "tap-narodnikatalog"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "iris",
            th.ArrayType(th.StringType),
            required=True,
            description="List of IRIs to retrieve dataset for.",
        )
    ).to_dict()

    def discover_streams(self) -> list[NarodniKatalogStream]:
        """Return a list of discovered streams.

        Returns:
            A list of discovered streams.
        """
        return [NarodniKatalogStream.create_stream_from_iri(iri)(self) for iri in self.config["iris"]]


if __name__ == "__main__":
    TapNarodniKatalog.cli()

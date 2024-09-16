"""data.gov.cz GraphQL client."""

from __future__ import annotations

import csv
import datetime
import logging
import tempfile
from collections.abc import Callable, Generator, Iterable, Sequence
from dataclasses import dataclass, field
from email.policy import EmailPolicy
from typing import Any

import httpx
from gql import Client as GraphQLClient
from gql import gql
from gql.transport.httpx import HTTPXTransport
from singer_sdk import typing as th
from singer_sdk.helpers.types import Context
from singer_sdk.streams import Stream
from slugify import slugify

CSV_SNIFF_SAMPLE_SIZE = 8192

logger = logging.getLogger(__name__)


@dataclass
class OpenDataDistribution:
    """OpenData Distribution attribute."""

    accessURL: str  # noqa: N815
    conformsTo: str  # noqa: N815


@dataclass
class OpenDataDataset:
    """OpenData dataset."""

    iri: str
    title: str
    description: str
    accrualPeriodicity: str | None = None  # noqa: N815
    documentation: str | None = None
    isPartOf: str | None = None  # noqa: N815
    distribution: list[OpenDataDistribution] = field(default_factory=list)

    @property
    def title_slug(self) -> str:
        """A slugified dataset title to be used as a stream name."""
        return slugify(self.title, separator="_")

    def __post_init__(self) -> None:
        """Cast the nested attributes."""
        self.distribution = list(
            map(
                lambda dist: (OpenDataDistribution(**dist) if isinstance(dist, dict) else dist),
                self.distribution,
            )
        )
        if not self.distribution:
            raise ValueError(f"No distribution found for IRI {self.iri!r}.")
        if len(self.distribution) > 1:
            raise NotImplementedError(
                f"Dataset for IRI {self.iri!r} has multiple distributions, this is not supported."
            )


COLUMN_TYPE_MAPPING: dict[str, type[th.JSONTypeHelper[Any]]] = {
    "string": th.StringType,
    "date": th.DateType,
    "number": th.NumberType,
}

COLUMN_TYPE_CAST_MAPPING: dict[str, Callable[[str], Any]] = {
    "date": lambda s: datetime.datetime.strptime(s, "%Y-%m-%d").date(),  # noqa: DTZ007
    "number": float,
}


@dataclass
class OpenDataDocumentColumn:
    """OpenData document schema column."""

    name: str
    titles: str
    description: str
    required: bool
    datatype: str

    def to_json_helper(self) -> th.Property[Any]:
        """Get JSONHelper property from the column."""
        return th.Property(
            self.name,
            COLUMN_TYPE_MAPPING.get(self.datatype, th.StringType),
            required=self.required,
            description=self.description,
        )


@dataclass
class OpenDataDocumentSchema:
    """OpenData document schema."""

    primaryKey: str  # noqa: N815
    columns: list[OpenDataDocumentColumn] = field(default_factory=list)

    def to_json_helper(self) -> th.PropertiesList:
        """Get JSON properties list made from columns of the schema."""
        return th.PropertiesList(*[column.to_json_helper() for column in self.columns])


class OpenDataGQLClient:
    """GraphQL client for data.gov.cz."""

    _dataset_query = """query{
        dataset(iri: "%(iri)s") {
            iri
            accrualPeriodicity
            documentation
            isPartOf
            distribution {
                accessURL
                conformsTo
            }
            description {
                cs
            }
            title {
                cs
            }
        }
    }"""

    default_base_url = "https://data.gov.cz/graphql"

    def __init__(self, base_url: str = default_base_url) -> None:
        """Initialize OpenData GraphQL client."""
        self.base_url = base_url

    def get_dataset_by_iri(self, iri: str) -> OpenDataDataset:
        """Get a dataset metadata by its IRI."""
        logger.info(f"Retrieving dataset metadata for {iri=}.")
        query = gql(self._dataset_query % {"iri": iri})
        graph_client = GraphQLClient(
            transport=HTTPXTransport(url=self.base_url),
            fetch_schema_from_transport=True,
        )
        logger.debug(f"Executing GraphQL query: {query}")
        result = graph_client.execute(query)
        return OpenDataDataset(
            title=result["dataset"].pop("title")["cs"],
            description=result["dataset"].pop("description")["cs"],
            **result["dataset"],
        )

    def get_dataset_schema(self, dataset: OpenDataDataset) -> OpenDataDocumentSchema:
        """Get dataset schema for the distribution."""
        logger.info(f"Retrieving schema for dataset {dataset.iri}.")
        with httpx.Client() as client:
            logger.info(f"GET {dataset.distribution[0].conformsTo!r}.")
            response = client.get(dataset.distribution[0].conformsTo)
            response.raise_for_status()
            payload = response.json()
            return OpenDataDocumentSchema(
                primaryKey=payload["tableSchema"]["primaryKey"],
                columns=[
                    OpenDataDocumentColumn(
                        column["name"],
                        column["titles"],
                        column["dc:description"],
                        column["required"],
                        column["datatype"],
                    )
                    for column in payload["tableSchema"]["columns"]
                ],
            )

    def retrieve_dataset(self, dataset: OpenDataDataset) -> Generator[dict[str, Any], None, None]:
        """Retrieve the dataset's data and yield it row by row."""
        logger.info(f"Retrieving data for dataset {dataset.iri}.")
        schema = self.get_dataset_schema(dataset)
        column_convertors: dict[str, Callable[[str], Any]] = {
            column.name: COLUMN_TYPE_CAST_MAPPING[column.datatype]
            for column in schema.columns
            if column.datatype in COLUMN_TYPE_CAST_MAPPING
        }
        with httpx.Client() as client:
            logger.info(f"GET {dataset.distribution[0].accessURL!r}.")
            response = client.get(dataset.distribution[0].accessURL)
            response.raise_for_status()
            content_type_header = EmailPolicy.header_factory("content-type", response.headers.get("content-type"))
            if content_type_header.content_type != "text/csv":
                raise NotImplementedError(f"Unsupported content type header {content_type_header.content_type!r}.")
            with tempfile.TemporaryFile("w+", encoding="utf-8", newline="") as file:
                file.write(response.text)
                file.seek(0)
                dialect = csv.Sniffer().sniff(response.text[:CSV_SNIFF_SAMPLE_SIZE])
                reader = csv.DictReader(file, dialect=dialect)
                yield from (
                    {
                        key: column_convertors[key](value) if key in column_convertors else value
                        for key, value in line.items()
                    }
                    for line in reader
                )


class NarodniKatalogStream(Stream):
    """Stream class for NarodniKatalog streams."""

    stream_iri: str

    @classmethod
    def create_stream_from_iri(cls, iri: str) -> type[NarodniKatalogStream]:
        """A stream factory for data sources.

        Creates a Stream type from IRI.
        """
        client = OpenDataGQLClient()
        dataset = client.get_dataset_by_iri(iri)
        schema = client.get_dataset_schema(dataset)

        class _GeneratedStream(NarodniKatalogStream):
            name = dataset.title_slug
            stream_iri = iri

            @property
            def schema(self) -> dict[str, Any]:
                """The schema getter."""
                return schema.to_json_helper().to_dict()

            @property
            def primary_keys(self) -> Sequence[str] | None:
                """Primary keys getter."""
                return [schema.primaryKey]

            @primary_keys.setter
            def primary_keys(self, value: Sequence[str] | None) -> None:
                # Setter is not needed, we have the primaryKey dynamically discovered
                return

        return _GeneratedStream

    def get_records(self, context: Context | None) -> Iterable[dict[str, Any]]:
        """Return a generator of record-type dictionary objects."""
        client = OpenDataGQLClient()
        dataset = client.get_dataset_by_iri(self.stream_iri)
        yield from client.retrieve_dataset(dataset)

# tap-narodnikatalog

This tap is designed to interface with the "NarodniKatalog" (data.gov.cz), the national catalog of open data
in the Czech Republic. This tap uses the Singer SDK to extract datasets published in this catalog,
leveraging the power of GraphQL to query and retrieve the data efficiently.

## What the Tap Downloads

When using this tap, you provide a list of `IRIs` (Internationalized Resource Identifiers) corresponding
to the datasets you are interested in. The tap then connects to the `NarodniKatalog`,
and retrieves metadata about these datasets.

- Data Analysts and Researchers: Who need to access structured data from the Czech Republic's open data portal
for analysis or research purposes.
- Developers and Data Engineers: Who want to integrate open data from NarodniKatalog into their data pipelines
for ETL (Extract, Transform, Load) processes.
- Policy Makers and Public Officials: Who need up-to-date data to inform decision-making and policy development.

By using this tap, you can easily extract valuable datasets from the NarodniKatalog and integrate them into your
data workflow, enabling data-driven insights and decision-making.

## Usage

### Direct Usage

You can install this tap after cloning the repository by running:

```bash
poetry install
```

Create a config file `config.json` with the following structure:

```json
{
  "iris": [
    "..."
  ]
}
```

e.g. to download inflation data:

```json
{
  "iris": [
    "https://data.gov.cz/zdroj/datové-sady/00025593/790624c7263aca615ce9ddd24e7db464"
  ]
}
```

Then discover the catalog and download the data:

```bash
poetry run tap-narodnikatalog --config config.json --discover > catalog.json
poetry run tap-narodnikatalog --config config.json --catalog catalog.json
```

### Usage with Meltano

You can also use this tap with Meltano, a command-line tool for orchestrating Singer taps and targets.
To do so, you can add this tap as a source to your Meltano project by running:

```bash
meltano add extractor tap-airtable --from-ref https://raw.githubusercontent.com/tomasvotava/tap-narodnikatalog/master/tap-narodnikatalog.yml
```

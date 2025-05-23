# Earthquake Monitoring Module

This module provides a flexible and extensible foundation for monitoring seismic events using the ObsPy library. It supports both real-time earthquake monitoring via the FDSN network and simulated earthquake events for testing and development purposes.

## Overview

The module is centered around two primary classes:

* **`EarthquakeMonitor`**
  Connects to an FDSN data provider (e.g., IRIS) to fetch and process real earthquakes, including downloading waveform data from nearby stations, estimating arrival times, and exporting results in various formats.

* **`DebugEarthquakeMonitor`**
  Inherits from `EarthquakeMonitor` and generates synthetic earthquake events and waveforms. This mode is useful for development and debugging without needing real seismic activity or network access.

## Key Features

### Earthquake Detection & Processing

* Polls real events from an FDSN client (`IRIS` by default).
* Filters events by magnitude and time interval.
* Converts ObsPy `Event` to a local `Earthquake` dataclass for easier handling.

### Station Query & Waveform Capture

* Finds nearby stations within a configurable radius.
* Estimates P- and S-wave arrival times to build appropriate time windows.
* Retrieves and saves waveform data in:

  * `.mseed` (MiniSEED)
  * `.wav` (normalized audio)
  * `.png` (waveform plots)

### Mock Event Generation (Debug Mode)

* Periodically generates randomized `Event` instances.
* Simulates waveform data using sine waves for known station IDs.
* Saves outputs using the same format as real events.

## Configuration

The module supports runtime configuration via CLI flags:

```bash
python producer.py [--debug] [--poll-interval SECONDS] [--max-events N]
```

* `--debug`: run in synthetic/mock mode.
* `--poll-interval`: seconds between polling cycles (default: 60 for real, 10 for debug).
* `--max-events`: limit number of generated events (debug mode only).

## Class Summary

### `Earthquake`

A simple dataclass representing an event with ID, time, location, and magnitude.

### `EarthquakeMonitor`

Handles:

* Polling real earthquakes
* Querying stations
* Downloading and saving waveform data

### `DebugEarthquakeMonitor`

Overrides:

* `poll_earthquakes()` to inject synthetic events
* `poll_waveforms()` to generate fake data

## Implementation Notes

* Uses `obspy.clients.fdsn.Client` for event and waveform access.
* `save_waveform()` and `save_all_formats()` handle I/O and conversion.
* WAV files are generated with adjustable amplitude scaling and playback speed.
* Output structure: one directory per event, containing all waveform assets.

## Extensibility

* Customize `poll_waveforms()` to handle other station/channel types.
* Extend `generate_mock_waveform()` to simulate different seismic profiles.
* Plug into a monitoring dashboard or pipeline with minimal effort.


## Testing the ObsPy Producer
(*NOTE:* This is a flat script during initial development.)
```
make build
make run ARGS="--count 10 --debug"
```
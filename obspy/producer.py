import os
import random
import numpy as np
import argparse
import time
import sys
import json
from dataclasses import dataclass

import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from kafka import KafkaProducer
from kafka.errors import KafkaError

from obspy import Trace, UTCDateTime
from obspy.clients.fdsn import Client
from obspy.core.event import Event, Origin, Magnitude, ResourceIdentifier
from obspy.core.stream import Stream
from obspy.geodetics import gps2dist_azimuth
from scipy.io.wavfile import write
from obspy.clients.fdsn.header import FDSNException


@dataclass
class Earthquake:
    """
    A class to represent an earthquake event.

    Attributes
    ----------
    id : str
        The unique event identifier.
    time : obspy.UTCDateTime
        The time of the earthquake.
    latitude : float
        Latitude of the epicenter.
    longitude : float
        Longitude of the epicenter.
    magnitude : float
        Magnitude of the event.
    """

    id: str
    time: UTCDateTime
    latitude: float
    longitude: float
    magnitude: float


class EarthquakeMonitor:
    """
    A base class for monitoring earthquakes and saving waveform data.
    """

    def __init__(self, base_dir: str = "earthquakes", fdsn_client: str = "IRIS"):
        """
        Initialize the EarthquakeMonitor.

        Params
        ------
        base_dir: str
            Directory where earthquake data will be saved.
        fdsn_client: str
            FDSN client to use for querying.
        """
        self.client = Client(fdsn_client)
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.captured_stations = {}

        # S3 Configuration
        self.s3_bucket_name = os.getenv("S3_BUCKET_NAME")
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        self.aws_region_name = os.getenv("AWS_DEFAULT_REGION")
        self.s3_client = None

        # Check S3 credentials and bucket name
        if not self.s3_bucket_name:
            print(f"[{UTCDateTime.now()}] Warning: S3_BUCKET_NAME not set. S3 uploads will be skipped.")
        elif not self.aws_access_key_id or not self.aws_secret_access_key:
            print(
                f"[{UTCDateTime.now()}] Warning: AWS credentials (ID or Key) not fully set. S3 uploads will be skipped."
            )
        else:
            # Initialize S3 client
            try:
                self.s3_client = boto3.client(
                    "s3",
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                    region_name=self.aws_region_name,
                )
                print(f"[{UTCDateTime.now()}] S3 client initialized for bucket: {self.s3_bucket_name}")
            except (NoCredentialsError, PartialCredentialsError):
                print(
                    f"[{UTCDateTime.now()}] Error: AWS credentials not found or incomplete. S3 uploads will fail."
                )
                self.s3_client = None
            except ClientError as e:
                print(f"[{UTCDateTime.now()}] Error initializing S3 client: {e}. S3 uploads will fail.")
                self.s3_client = None
            except Exception as e:
                print(
                    f"[{UTCDateTime.now()}] An unexpected error occurred initializing S3 client: {e}. S3 uploads will fail."
                )
                self.s3_client = None

        # Kafka Configuration
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
        self.kafka_topic = os.getenv("KAFKA_TOPIC")
        self.kafka_producer = None
        try:
            self.kafka_producer = KafkaProducer(
                bootstrap_servers=self.kafka_bootstrap_servers.split(","),
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                retries=5,
                acks="all",
            )
            print(
                f"[{UTCDateTime.now()}] Kafka producer initialized for topic '{self.kafka_topic}' at {self.kafka_bootstrap_servers}"
            )
        except KafkaError as e:
            print(f"[{UTCDateTime.now()}] Error initializing Kafka producer: {e}. Messages will not be sent.")
            self.kafka_producer = None
        except Exception as e:  # Catch any other unexpected errors during Kafka init
            print(
                f"[{UTCDateTime.now()}] An unexpected error occurred initializing Kafka producer: {e}. Messages will not be sent."
            )
            self.kafka_producer = None

    def poll_earthquakes(self, min_magnitude=1.0, poll_interval=60, lookback_interval=1000):
        """
        Continuously poll for new earthquakes and process them.

        Params
        ------
        min_magnitude: float
            Minimum magnitude for earthquakes to be considered.
        poll_interval: int
            Time interval (in seconds) between API polls.
        lookback_interval: int
            Time interval (in seconds) to look back for earthquakes.
        """
        while True:
            try:
                # Get new events
                now = UTCDateTime.now()
                events = self.client.get_events(
                    starttime=now - lookback_interval,
                    endtime=now,
                    minmagnitude=min_magnitude,
                    orderby="time",
                )

                # Process each event
                for event in events:
                    self.process_earthquake(event)

                print(f"Events: {[event.resource_id.id.split('=')[-1] for event in events]}")
            except FDSNException:
                print(f"[{now}] No events found")
                pass

            time.sleep(poll_interval)

    def process_earthquake(self, event: Event):
        """
        Process a detected earthquake by polling nearby stations for waveforms.

        Params
        ------
        event: obspy.core.event.Event
            The earthquake event to process.
        """
        origin = event.preferred_origin()

        # Extract event details
        quake = Earthquake(
            id=event.resource_id.id.split("=")[-1],
            time=origin.time,
            latitude=origin.latitude,
            longitude=origin.longitude,
            magnitude=event.preferred_magnitude().mag,
        )

        print(
            f"[{UTCDateTime.now()}] New earthquake detected ({quake.id}): {quake.time}, "
            f"Location: ({quake.latitude}, {quake.longitude}), Magnitude: {quake.magnitude}"
        )

        # Create directory for the event
        event_dir = os.path.join(self.base_dir, f"{quake.id}_{quake.magnitude}")
        os.makedirs(event_dir, exist_ok=True)

        # Track queried stations by event ID
        if quake.id not in self.captured_stations:
            self.captured_stations[quake.id] = set()

        # Poll waveforms and get S3 URIs for all stations
        station_reports = self.poll_waveforms(quake, event_dir)

        # Send to Kafka
        if self.kafka_producer:
            # Prepare earthquake data, converting UTCDateTime to ISO string
            quake_data = {
                "id": quake.id,
                "time": quake.time.isoformat(),
                "latitude": quake.latitude,
                "longitude": quake.longitude,
                "magnitude": quake.magnitude,
            }
            # station_reports might be empty if no stations were processed or if all S3 uploads failed,
            # but we still send the main earthquake event.
            message = {"earthquake": quake_data, "station_reports": station_reports if station_reports else []}
            try:
                # Send to Kafka (non-blocking)
                self.kafka_producer.send(self.kafka_topic, message)
                log_message = f"[{UTCDateTime.now()}] Sent data for earthquake {quake.id} to Kafka topic '{self.kafka_topic}'."
                if not station_reports:
                    log_message += " (No station data was included)."
                print(log_message)
            except KafkaError as e:
                print(f"[{UTCDateTime.now()}] Error sending message to Kafka for earthquake {quake.id}: {e}")
            except Exception as e:
                print(
                    f"[{UTCDateTime.now()}] An unexpected error occurred sending message to Kafka for earthquake {quake.id}: {e}"
                )
        else:  # Kafka producer not available
            print(
                f"[{UTCDateTime.now()}] Kafka producer not available. Skipping Kafka message for earthquake {quake.id}."
            )

    def poll_waveforms(
        self,
        quake: Earthquake,
        event_dir: str,
        max_radius: float = 1.8,
        avg_p_speed: float = 6.0,
        avg_s_speed: float = 3.5,
    ) -> list:
        """
        Poll stations near the earthquake epicenter for waveform data.

        Params
        ------
        quake: Earthquake
            The earthquake to process.
        event_dir: str
            Directory to save waveform data.
        max_radius: float
            Maximum radius for querying stations (in degrees).
        avg_p_speed: float
            Average P-wave speed (in km/s).
        avg_s_speed: float
            Average S-wave speed (in km/s).
        """
        # Query nearby stations and networks
        try:
            stations = self.client.get_stations(
                latitude=quake.latitude,
                longitude=quake.longitude,
                maxradius=max_radius,
                starttime=quake.time,
                endtime=quake.time + 3600,
                level="channel",
            )
        except TimeoutError:
            print(f"[{UTCDateTime.now()}] TimeoutError: Cannot load stations")
            return

        # Iterate over all stations / networks
        all_station_reports = []
        for network in stations:
            for station in network:
                station_id = f"{network.code}.{station.code}"
                if station_id not in self.captured_stations[quake.id]:
                    # Distance to station
                    dist_m, _, _ = gps2dist_azimuth(
                        quake.latitude, quake.longitude, station.latitude, station.longitude
                    )
                    dist_km = dist_m / 1000.0

                    # Calculate P and S wave arrival times
                    p_arrival = quake.time + (dist_km / avg_p_speed)
                    s_arrival = quake.time + (dist_km / avg_s_speed)

                    # Define time window for waveform data
                    start_time = p_arrival - 180
                    end_time = s_arrival + 240
                    filename_prefix = f"{dist_km:.2f}_{station_id}"

                    s3_uris_for_station = self.save_waveform(
                        quake,  # Pass the full Earthquake object
                        network.code,
                        station.code,
                        "*",  # location
                        "BHZ",  # channel
                        start_time,
                        end_time,
                        event_dir,
                        filename_prefix,
                    )
                    # Always add station report, s3_uris_for_station might be empty if S3 failed or no waveform
                    all_station_reports.append(
                        {
                            "station_id": station_id,
                            "network_code": network.code,
                            "station_code": station.code,
                            "latitude": station.latitude,
                            "longitude": station.longitude,
                            "distance_km": round(dist_km, 2),
                            "p_arrival_time": p_arrival.isoformat(),
                            "s_arrival_time": s_arrival.isoformat(),
                            "waveform_start_time": start_time.isoformat(),
                            "waveform_end_time": end_time.isoformat(),
                            "files": s3_uris_for_station if s3_uris_for_station else {},  # Ensure 'files' is a dict
                        }
                    )
                    self.captured_stations[quake.id].add(station_id)  # Mark as processed
        return all_station_reports

    def save_all_formats(
        self,
        stream: Stream,
        event_dir: str,  # Local event directory path
        filename_prefix: str,  # Filename prefix (e.g., "dist_station")
        quake_id: str,  # For S3 path
        quake_magnitude: float,  # For S3 path
        formats: list = ["MSEED", "WAV", "PNG"],
    ):
        """
        Save waveform data in multiple formats locally and upload to S3.
        Returns a dictionary of S3 URIs for uploaded files.
        """
        s3_uris = {}
        if not stream:
            print(f"[{UTCDateTime.now()}] No stream data to save for {filename_prefix}.")
            return s3_uris

        for fmt_upper in formats:
            fmt = fmt_upper.lower()  # Use lowercase for extensions
            local_path = os.path.join(event_dir, f"{filename_prefix}.{fmt}")

            try:
                if fmt_upper == "MSEED":
                    stream.write(local_path, format="MSEED")
                    print(f"[{UTCDateTime.now()}] Saved MiniSEED locally: {local_path}")
                elif fmt_upper == "WAV":
                    self.convert_to_wav(stream, local_path)
                    print(f"[{UTCDateTime.now()}] Saved WAV locally: {local_path}")
                elif fmt_upper == "PNG":
                    # Ensure stream is not empty for plotting
                    if stream:
                        stream.plot(outfile=local_path, show=False)  # show=False to prevent GUI
                        print(f"[{UTCDateTime.now()}] Saved PNG locally: {local_path}")
                    else:
                        print(f"[{UTCDateTime.now()}] Empty stream, skipping PNG for {filename_prefix}")
                        continue  # Skip S3 upload for this format
                else:
                    print(f"[{UTCDateTime.now()}] Unsupported format: {fmt_upper}. Skipping...")
                    continue

                # Upload to S3
                if self.s3_client and self.s3_bucket_name:
                    # S3 key structure: earthquakes/<quake_id>_<magnitude>/<filename_prefix>.<format_extension>
                    s3_key = f"earthquakes/{quake_id}_{quake_magnitude}/{filename_prefix}.{fmt}"
                    try:
                        self.s3_client.upload_file(local_path, self.s3_bucket_name, s3_key)
                        s3_uri = f"s3://{self.s3_bucket_name}/{s3_key}"
                        s3_uris[fmt] = s3_uri
                        print(f"[{UTCDateTime.now()}] Uploaded {fmt_upper} to S3: {s3_uri}")
                        # Optionally, remove local file after upload
                        # os.remove(local_path)
                        # print(f"[{UTCDateTime.now()}] Removed local file: {local_path}")
                    except FileNotFoundError:
                        print(f"[{UTCDateTime.now()}] Error: Local file not found for S3 upload: {local_path}")
                    except ClientError as e:
                        print(f"[{UTCDateTime.now()}] Error uploading {fmt_upper} to S3 ({s3_key}): {e}")
                    except Exception as e:
                        print(
                            f"[{UTCDateTime.now()}] An unexpected error occurred during S3 upload of {fmt_upper} ({s3_key}): {e}"
                        )
                else:
                    print(f"[{UTCDateTime.now()}] S3 client not configured. Skipping S3 upload for {fmt_upper}.")

            except Exception as e:
                print(
                    f"[{UTCDateTime.now()}] Error processing/saving format {fmt_upper} for {filename_prefix}: {e}"
                )

        return s3_uris

    def save_waveform(
        self,
        quake: Earthquake,  # Changed from quake_id to full Earthquake object
        network: str,
        station: str,
        location: str,
        channel: str,
        starttime: UTCDateTime,
        endtime: UTCDateTime,
        event_dir: str,  # Local directory for this event's files
        filename_prefix: str,  # Filename prefix (e.g., "dist_station")
    ) -> dict:
        """
        Fetch waveform data, save it in multiple formats locally, upload to S3,
        and return S3 URIs.

        Params
        ------
        quake: Earthquake
            The earthquake event object.
        network: str
            Network code.
        station: str
            Station code.
        location: str
            Location code.
        channel: str
            Channel code.
        starttime: obspy.UTCDateTime
            Start time for the waveform data.
        endtime: obspy.UTCDateTime
            End time for the waveform data.
        event_dir: str
            Directory to save the waveform data locally.
        filename_prefix: str
            Prefix for local filenames and part of S3 key.

        Returns
        -------
        dict
            A dictionary of S3 URIs for the uploaded files, or empty if fails.
        """
        s3_uris = {}
        try:
            waveform = self.client.get_waveforms(
                network=network,
                station=station,
                location=location,
                channel=channel,
                starttime=starttime,
                endtime=endtime,
            )

            if not waveform or len(waveform) == 0:
                print(
                    f"[{UTCDateTime.now()}] No waveform data returned for {network}.{station} {channel} at {starttime}"
                )
                return s3_uris  # Return empty dict

            # Persist the waveform data locally and upload to S3
            s3_uris = self.save_all_formats(
                waveform,
                event_dir,
                filename_prefix,
                quake.id,  # Pass quake.id for S3 path
                quake.magnitude,  # Pass quake.magnitude for S3 path
            )

        except FDSNException as e:
            if "No data available" in str(e) or "204" in str(e):  # No content
                print(f"[{UTCDateTime.now()}] No data available for {network}.{station} {channel} via FDSN: {e}")
            else:
                print(f"[{UTCDateTime.now()}] FDSNException for {network}.{station}: {e}")
        except Exception as e:
            print(
                f"[{UTCDateTime.now()}] An unexpected error occurred in save_waveform for {network}.{station}: {e}"
            )

        return s3_uris

    def convert_to_wav(
        self,
        stream: Stream,
        wav_path: str,
        amplitude_scaling: float = 0.9,
        playback_speed: int = 50,
    ):
        """
        Convert an ObsPy stream to a WAV file.

        Params
        ------
        stream: from obspy.core.stream
            The ObsPy stream to convert.
        wav_path: str
            The path to save the WAV file.
        amplitude_scaling: float
            Amplitude scaling factor.
        playback_speed: int
            Playback speed multiplier.
        """
        try:
            # Grab first trace
            trace = stream[0]
            data = trace.data.astype(np.float32)

            # Normalize and scale
            data /= np.max(np.abs(data))
            data *= amplitude_scaling

            # Convert to PCM and save as WAV
            sampling_rate = int(trace.stats.sampling_rate * playback_speed)
            data_pcm = (data * 32767).astype(np.int16)

            # Write to WAV file
            write(wav_path, sampling_rate, data_pcm)
        except Exception as e:
            print(f"Error converting to WAV: {e}")


class DebugEarthquakeMonitor(EarthquakeMonitor):
    """
    A subclass of EarthquakeMonitor for simulating mock earthquake events and waveforms.
    Intended for development and testing without relying on real-time data.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the DebugEarthquakeMonitor.

        Params
        ------
        *args, **kwargs: arguments passed to the base EarthquakeMonitor class.
        """
        super().__init__(*args, **kwargs)

    def poll_earthquakes(self, poll_interval=10, max_events=None):
        """
        Simulate repeated mock earthquake events and process them every poll_interval seconds.

        Params
        ------
        poll_interval: int
            Time interval (in seconds) between mock events.
        max_events: int or None
            Maximum number of events to simulate; None for infinite.
        """
        count = 0
        while True:
            now = UTCDateTime.now()
            mock_event = self.generate_mock_event(now)
            self.process_earthquake(mock_event)
            count += 1
            if max_events is not None and count >= max_events:
                break
            time.sleep(poll_interval)

    def generate_mock_event(self, event_time: UTCDateTime):
        """
        Generate a mock ObsPy Event object with randomized parameters.

        Params
        ------
        event_time: obspy.UTCDateTime
            Timestamp to assign to the event.

        Returns
        -------
        obspy.core.event.Event
            Mock event with random origin and magnitude.
        """
        event_id = f"{random.randint(1000, 9999)}"
        lat = random.uniform(-90, 90)
        lon = random.uniform(-180, 180)
        mag = random.uniform(1.0, 2.0)

        origin = Origin(time=event_time, latitude=lat, longitude=lon)
        magnitude = Magnitude(mag=mag)

        event = Event(
            resource_id=ResourceIdentifier(f"debug/{event_id}"),
            origins=[origin],
            magnitudes=[magnitude],
        )
        event.preferred_origin_id = origin.resource_id
        event.preferred_magnitude_id = magnitude.resource_id

        return event

    def poll_waveforms(self, quake: Earthquake, event_dir: str, **kwargs):
        """
        Simulate downloading waveform data for mock stations and save as MiniSEED.

        Params
        ------
        quake: Earthquake
            The simulated earthquake to process.
        event_dir: str
            Directory to save the simulated waveform data.
        """
        station_ids = ["XX.TEST1", "YY.DEBUG2"]  # Made them slightly more unique
        all_station_reports = []
        for sid in station_ids:
            # For debug, filename_prefix can be simpler, e.g., just station ID
            filename_prefix = f"debug_{sid}"
            stream = self.generate_mock_waveform()

            # Save the waveform data locally and attempt S3 upload
            s3_uris_for_station = self.save_all_formats(
                stream,
                event_dir,
                filename_prefix,
                quake.id,  # Pass quake.id for S3 path
                quake.magnitude,  # Pass quake.magnitude for S3 path
            )
            # Always add station report, s3_uris_for_station might be empty if S3 failed or no waveform
            all_station_reports.append(
                {
                    "station_id": sid,
                    "network_code": sid.split(".")[0] if "." in sid else "XX",
                    "station_code": sid.split(".")[1] if "." in sid else "MOCK",
                    "latitude": round(random.uniform(-90, 90), 4),  # Mock data
                    "longitude": round(random.uniform(-180, 180), 4),  # Mock data
                    "distance_km": round(random.uniform(10, 100), 2),
                    "p_arrival_time": (quake.time + random.randint(10, 60)).isoformat(),  # Mock data
                    "s_arrival_time": (quake.time + random.randint(70, 180)).isoformat(),  # Mock data
                    "waveform_start_time": (quake.time - 30).isoformat(),  # Mock data
                    "waveform_end_time": (quake.time + 300).isoformat(),  # Mock data
                    "files": s3_uris_for_station if s3_uris_for_station else {},  # Ensure 'files' is a dict
                }
            )
        return all_station_reports  # Return aggregated S3 URIs/reports

    def generate_mock_waveform(self, npts=1000, sampling_rate=100):
        """
        Generate a synthetic waveform using a 5 Hz sine wave.

        Params
        ------
        npts: int
            Number of points in the waveform.
        sampling_rate: int
            Sampling rate in Hz.

        Returns
        -------
        obspy.Stream
            Stream containing a single synthetic Trace.
        """
        t = np.linspace(0, 1, npts)
        data = np.sin(2 * np.pi * 5 * t)
        trace = Trace(data=data)
        trace.stats.station = "MOCK"
        trace.stats.network = "XX"
        trace.stats.sampling_rate = sampling_rate
        trace.stats.starttime = UTCDateTime.now()
        return Stream(traces=[trace])


# Run the EarthquakeMonitor
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Earthquake Monitor")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode with mock data")
    parser.add_argument("--poll-interval", type=int, help="Seconds between events")
    parser.add_argument("--max-events", default=10, type=int, help="Stop after N mock events (debug mode only)")
    args = parser.parse_args()

    if not args.debug and args.max_events is not None:
        print("Error: --max-events can only be used with --debug")
        sys.exit(1)

    # Apply default poll interval only if not provided explicitly
    poll_interval = args.poll_interval if args.poll_interval is not None else (10 if args.debug else 60)

    if args.debug:
        monitor = DebugEarthquakeMonitor()
        # Use the provided max_events or default to 2
        max_events = args.max_events if args.max_events is not None else 2
        monitor.poll_earthquakes(poll_interval=poll_interval, max_events=max_events)
    else:
        monitor = EarthquakeMonitor()
        monitor.poll_earthquakes(min_magnitude=1.0, poll_interval=poll_interval)

import os
import time
from dataclasses import dataclass

from obspy.clients.fdsn import Client
from obspy.core.event import Event
from obspy.core.stream import Stream
from obspy import UTCDateTime
from obspy.geodetics import gps2dist_azimuth
from scipy.io.wavfile import write
from obspy.clients.fdsn.header import FDSNException
import numpy as np


@dataclass
class Earthquake:
    """
    A class to represent an earthquake event.

    Attributes
    ----------
    time : obspy.UTCDateTime
        The time of the earthquake.
    latitude : float
        The latitude of the earthquake's epicenter.
    longitude : float
        The longitude of the earthquake's epicenter.
    magnitude : float
        The magnitude of the earthquake.
    """

    def __init__(
        self,
        id: str,
        time: UTCDateTime,
        latitude: float,
        longitude: float,
        magnitude: float,
    ):
        self.id = id
        self.time = time
        self.latitude = latitude
        self.longitude = longitude
        self.magnitude = magnitude


class EarthquakeMonitor:
    """
    A class to monitor earthquakes, poll stations for waveform data,
    and save the results as MiniSEED, WAV, and PNG files.

    Attributes
    ----------
    client : obspy.clients.fdsn.Client
        FDSN client for querying.
    base_dir : str
        Base directory for saving earthquake data.
    queried_stations : dict
        Dictionary to track queried stations by event ID.
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

    def poll_earthquakes(
        self, min_magnitude=1.0, poll_interval=60, lookback_interval=1000
    ):
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

                for event in events:
                    self.process_earthquake(event)

                print(
                    f"Events: {[event.resource_id.id.split('=')[-1] for event in events]}"
                )
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

        # Poll waveforms
        self.poll_waveforms(quake, event_dir)

    def poll_waveforms(
        self,
        quake: Earthquake,
        event_dir: str,
        max_radius: float = 1.8,
        avg_p_speed: float = 6.0,
        avg_s_speed: float = 3.5,
    ):
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
        for network in stations:
            for station in network:
                station_id = f"{network.code}.{station.code}"
                if station_id not in self.captured_stations[quake.id]:
                    # Distance to station
                    dist_m, _, _ = gps2dist_azimuth(
                        quake.latitude,
                        quake.longitude,
                        station.latitude,
                        station.longitude,
                    )
                    dist_km = dist_m / 1000.0

                    # Calculate P and S wave arrival times
                    p_arrival = quake.time + (dist_km / avg_p_speed)
                    s_arrival = quake.time + (dist_km / avg_s_speed)

                    # Define time window for waveform data
                    start_time = p_arrival - 180
                    end_time = s_arrival + 240

                    # Announce
                    # print(
                    #    f"[{UTCDateTime.now()}] Station: {station_id}, Distance: {dist_km:.2f} km, "
                    #    f"P arrival: {p_arrival}, S arrival: {s_arrival}"
                    # )

                    # Save waveform data
                    filename_prefix = f"{dist_km:.2f}_{station_id}"
                    self.save_waveform(
                        quake.id,
                        network.code,
                        station.code,
                        "*",
                        "BHZ",
                        start_time,
                        end_time,
                        event_dir,
                        filename_prefix,
                    )

    def save_waveform(
        self,
        quake_id: str,
        network: str,
        station: str,
        location: str,
        channel: str,
        starttime: UTCDateTime,
        endtime: UTCDateTime,
        event_dir: str,
        filename_prefix: str,
    ):
        """
        Save waveform data as MiniSEED, WAV, and PNG files.

        Params
        ------
        quake_id: str
            The earthquake ID.
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
            Directory to save the waveform data.
        filename_prefix: str
            Prefix for filenames.
        """
        try:
            # Fetch waveform data
            waveform = self.client.get_waveforms(
                network=network,
                station=station,
                location=location,
                channel=channel,
                starttime=starttime,
                endtime=endtime,
            )

            # Save miniSEED
            mseed_path = os.path.join(event_dir, f"{filename_prefix}.mseed")
            waveform.write(mseed_path, format="MSEED")
            print(f"[{UTCDateTime.now()}] Saved MiniSEED: {mseed_path}")

            # Convert to WAV
            wav_path = os.path.join(event_dir, f"{filename_prefix}.wav")
            self.convert_to_wav(waveform, wav_path)
            print(f"[{UTCDateTime.now()}] Saved WAV: {wav_path}")

            # Plot and save PNG
            png_path = os.path.join(event_dir, f"{filename_prefix}.png")
            waveform.plot(outfile=png_path)
            print(f"[{UTCDateTime.now()}] Saved PNG: {png_path}")

            # Mark this station as queried for this event
            self.captured_stations[quake_id].add(f"{network}.{station}")

        except Exception as e:
            if "204" in str(e):
                pass
            else:
                print(f"An unexpected error occurred: {e}")

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


# Run the EarthquakeMonitor
if __name__ == "__main__":
    monitor = EarthquakeMonitor()
    monitor.poll_earthquakes(min_magnitude=1.0, poll_interval=60)

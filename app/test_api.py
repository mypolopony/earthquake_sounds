from datetime import datetime, timezone

from api import InvalidAPIResponse, USGSEarthquakeAPI

if __name__ == "__main__":
    api_client = USGSEarthquakeAPI()

    try:
        # Parameters for the query
        now_utc = datetime.now(timezone.utc)  # Modern replacement for utcnow()
        params = {
            # "starttime": (now_utc - timedelta(days=1)).strftime('%Y-%m-%d'),
            # "endtime": now_utc.strftime('%Y-%m-%d'),  # Consistent formatting
            "limit": 20,
            "minmagnitude": 2,
        }

        # Fetch
        data = api_client.fetch_earthquakes(params)

        # Parse
        earthquakes = api_client.parse_earthquake_data(data)

        # Display
        if earthquakes:
            print("Template:")
            print(data["features"][0])

            print("Recent Earthquakes:")
            for quake in earthquakes:
                timestamp = datetime.fromtimestamp(int(quake["time"] / 1000)).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                print(f"- {quake['place']} (Mag: {quake['magnitude']}) at {timestamp}")
        else:
            print("No recent earthquakes found.")
    except InvalidAPIResponse as e:
        print(f"Error parsing API response: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

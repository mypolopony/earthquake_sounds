from api import InvalidAPIResponse, USGSEarthquakeAPI

if __name__ == "__main__":
    api_client = USGSEarthquakeAPI()

    try:
        params = {
            "starttime": "2025-01-14",
            "endtime": "2025-01-15",
            "minmagnitude": 5,
        }
        data = api_client.fetch_earthquakes(params)
        earthquakes = api_client.parse_earthquake_data(data)
        if earthquakes:
            print("Template:")
            print(data["features"][0])
            print("Recent Earthquakes:")
            for quake in earthquakes:
                print(
                    f"- {quake['place']} (Mag: {quake['magnitude']}) at {quake['time']}"
                )
        else:
            print("No recent earthquakes found.")
    except InvalidAPIResponse as e:
        print(f"Error parsing API response: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

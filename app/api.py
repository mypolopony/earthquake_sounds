from typing import Any, Dict, Optional

import requests


class InvalidAPIResponse(Exception):
    """
    Exception raised for errors in the API response.

    Parameters
    ----------
    data : dict
        The raw data received from the API.
    """

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        super().__init__(f"Invalid API response: {data}")


class USGSEarthquakeAPI:
    """
    A minimalist client for the USGS Earthquake API.
    """

    BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"

    def __init__(self, format: str = "geojson"):
        """
        Initialize the API client.

        Parameters
        ----------
        format : str
            Response format (default is "geojson").
        """

        self.format = format

    def fetch_earthquakes(
        self, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch earthquake data from the USGS API.

        Parameters
        ----------
        params : dict
            Query parameters for filtering results.

        Returns
        -------
        dict
            A dictionary containing the earthquake data.
        """

        if params is None:
            params = {}

        # Add the format to query parameters
        params["format"] = self.format

        try:
            response = requests.get(self.BASE_URL, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching data from USGS API: {e}")
            return {}

    @staticmethod
    def parse_earthquake_data(data: Dict[str, Any]) -> Optional[list]:
        """
        Parse earthquake data into a list of minimal details. We don't necessarily need
        to connect this method to the API client, as it can be used independently.

        Parameters
        ----------
        data : dict
            The raw earthquake data from the API.

        Returns
        -------
        list
            A list of parsed earthquake information.

        Raises
        ------
        InvalidAPIResponse
            If the data is missing the "features" key.
        """

        if "features" not in data:
            raise InvalidAPIResponse(data)

        return [
            {
                "id": feature["id"],
                "place": feature["properties"].get("place", ""),
                "magnitude": feature["properties"].get("mag", 0),
                "time": feature["properties"].get("time"),
            }
            for feature in data["features"]
        ]

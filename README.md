# Earthquake Sounds

![Project Banner](https://github.com/mypolopony/earthquake_sounds/blob/develop/img/huddled.png)

## Overview
Earthquake Sounds is a Python package that listens to earthquakes in real-time and reports on them via a front-end interface. It continuously fetches seismic data, processes it, and provides real-time visual and audio feedback on detected seismic activity.

## Features
- Listens to real-time earthquake data from monitoring sources.
- Processes and converts seismic signals into audio feedback.
- Provides real-time earthquake reports on an interactive front-end.
- Visualizes seismic waveforms and spectrograms.
- Dockerized for easy deployment.
- Built using Python and `obspy` for robust seismic analysis.
- Uses Terraform for cloud infrastructure automation.
- Flask-based web interface for front-end visualization.

## Installation

### Prerequisites
Ensure you have the following installed:
- Python 3.8+
- Docker (if using the containerized setup)
- Terraform (for cloud deployment)

### Local Installation
1. Clone the repository:
   ```sh
   git clone https://github.com/mypolopony/earthquake_sounds.git
   cd earthquake_sounds
   ```
2. Install dependencies using Poetry:
   ```sh
   poetry install
   ```
3. Run the application:
   ```sh
   poetry run python app/main.py
   ```

### Using Docker
1. Build and start the Docker container:
   ```sh
   docker-compose up --build
   ```
2. The service should now be running and accessible.

### Deploying with Terraform
There are two types of Snowflake deployments and each has its own Terraform configuration. Navigate to

`obspy/tf/kafka` for the Kafka, swift messaging version
or
`obs/tf/direct_put` for the jenky HTTPS PUT from 40 years ago that works 88% of the time, 99% of the time.

## Usage
After running the application, the system will listen to real-time seismic data and generate corresponding reports on the front end. Users can:
- View earthquake data updates in real-time.
- Listen to seismic waveforms converted into audio.
- Access the Flask-based web interface for earthquake reports and visualization.
- Adjust parameters in `config.yaml` to modify data sources and output preferences.

## Project Structure
```
├── app/
│   ├── main.py      # Main script to fetch and process seismic data
│   ├── sound.py     # Converts seismic data into sound
│   ├── visualize.py # Generates waveform and spectrograms
│   ├── frontend/    # Flask-based web interface for real-time reporting
├── obspy/           # Helper scripts for handling seismic data
├── terraform/       # Terraform configuration for cloud deployment
├── docker-compose.yml # Docker configuration
├── requirements.txt # Required dependencies
└── README.md        # Project documentation
```

## Output

-> ECS, Kafka, Snowflake, Lambda, MLFlow, etc


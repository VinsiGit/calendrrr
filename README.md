# calendrrr

This project integrates Google Calendar with AI to help manage and schedule events efficiently.

https://developers.google.com/calendar/api/quickstart/python



## Instructions

### 1. Setup

Run the following command to start the Docker container:
```cmd
docker compose up
```

Then, pull the required model:
```cmd
docker exec -it ollama ollama pull llama3.2:3b
```

Install the required Python packages:
```cmd
python -m pip install -r requirements.txt
```

### 2. Running the Application

Run the main file:
```cmd
python main.py
```

### 3. Documentation

#### AI Techniques and Planning Logic

The AI agent in this project uses the `Swarm` and `Agent` classes from the `swarm_ollama` library to interact with the Google Calendar API. The AI agent helps in scheduling events by checking for conflicts and suggesting free dates.

#### Using the AI Agent

The AI agent can be used to add both single and recurring events to the calendar. Below are examples of how to use the agent:



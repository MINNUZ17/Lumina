# Lumina – Safety-Score Based Navigation System

Lumina is a web-based navigation system designed to help users explore routes with safety-related environmental information, in addition to route distance and travel time.

## Features

- Route planning between source and destination locations
- Interactive map using Leaflet.js and OpenStreetMap
- Route information retrieved using the OSRM routing service
- Environmental data collection using the Overpass API
- Review submission and review statistics
- Sentiment analysis of user reviews using TextBlob

## Technology Stack

- **Frontend:** HTML, CSS, JavaScript, Leaflet.js
- **Backend:** Python, Flask, Flask-CORS
- **Map Data:** OpenStreetMap
- **Routing:** OSRM
- **Environmental Data:** Overpass API
- **NLP:** TextBlob

## Project Structure

```text
Lumina/
├── backend/
│   ├── app.py
│   ├── reviews.json
│   └── test_nlp.py
├── frontend/
│   └── index.html
└── README.md
```

## Live Demo

- **Website:** https://jovial-gelato-bacef6.netlify.app
- **Backend:** https://lumina-r7xz.onrender.com

## Running Locally

1. Install Python and the required dependencies.
2. Open a terminal in the backend directory.
3. Install the dependencies:

   `pip install Flask flask-cors requests textblob`

4. Start the backend:

   `python app.py`

5. Open `frontend/index.html` using a local web server.

## Future Enhancements

- Improve safety-based route selection by comparing multiple candidate routes.
- Incorporate more reliable and up-to-date safety information.
- Enhance route scoring and user feedback analysis.
- Improve accessibility and mobile responsiveness.

## Disclaimer

Lumina provides safety-related route information for exploration and research purposes. Its safety scores and environmental data should not be treated as a guarantee of personal safety.

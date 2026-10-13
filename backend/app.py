from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from datetime import datetime
import math
import json
import os
import re
from textblob import TextBlob

app = Flask(__name__)
CORS(app)

OSRM_URL = "https://router.project-osrm.org/route/v1/driving/"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
session = requests.Session()

ERNAKULAM_BOUNDS = "75.98,9.55,76.85,10.35"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REVIEWS_FILE = os.path.join(BASE_DIR, "reviews.json")

# ------------------------------------------
# NLP: Classify Feedback
# ------------------------------------------
def classify_feedback(text):
    if not text or len(text.strip()) < 3:
        return "N/A"
    
    try:
        analysis = TextBlob(text)
        polarity = analysis.sentiment.polarity
        
        # Keywords that strongly suggest a complaint regardless of tone
        complaint_keywords = ["dark", "unsafe", "scary", "bad", "error", "wrong", "issue", "problem", "broken", "danger", "poor", "accident", "pothole"]
        good_keywords = ["safe", "well-lit", "clean", "good", "excellent", "best", "perfect", "smooth", "bright", "secure", "friendly", "positive", "helpful"]
        
        text_lower = text.lower()
        has_issue = any(kw in text_lower for kw in complaint_keywords)
        is_good = any(kw in text_lower for kw in good_keywords)
        
        if (polarity > 0.1 or is_good) and not has_issue:
            return "Good Review"
        else:
            return "Complaint"
    except:
        return "Unclassified"

# ------------------------------------------
# Helper: Sample points along route
# ------------------------------------------
def get_route_samples(geometry, n=25):
# ... (rest of the helper functions)
    coords = geometry.get("coordinates", [])
    if not coords:
        return []
    
    if len(coords) <= n:
        return [(c[1], c[0]) for c in coords]
    
    indices = [int(i * (len(coords) - 1) / (n - 1)) for i in range(n)]
    samples = [coords[i] for i in indices]
    
    return [(c[1], c[0]) for c in samples]

# ------------------------------------------
# Fetch nearby features (Max-Differentiation)
# ------------------------------------------
def fetch_environment_data(points):
    if not points:
        return 0, 0, 0

    # Balanced 45m radius for precision route-specific feature isolation
    radius = 45 

    query = "[out:json][timeout:25];"
    
    # Street Lamps
    query += "("
    for lat, lon in points:
        query += f'node["highway"="street_lamp"](around:{radius},{lat},{lon});'
    query += ")->.lamps;"
    
    # Vibrancy (Shops/Amenities)
    query += "("
    for lat, lon in points:
        query += f'node["shop"](around:{radius},{lat},{lon});'
        query += f'node["amenity"~"restaurant|cafe|marketplace"](around:{radius},{lat},{lon});'
    query += ")->.vibrancy;"
    
    # Critical Infrastructure
    query += "("
    for lat, lon in points:
        query += f'node["amenity"~"police|hospital"](around:{radius},{lat},{lon});'
    query += ")->.critical;"
    
    query += ".lamps out count; .vibrancy out count; .critical out count;"

    try:
        res = session.post(OVERPASS_URL, data={"data": query}, timeout=30)
        data = res.json()
        
        elements = data.get("elements", [])
        
        lamps = 0
        vibrancy = 0
        critical = 0
        
        if len(elements) > 0 and "tags" in elements[0]:
            lamps = int(elements[0]["tags"].get("nodes", 0))
        if len(elements) > 1 and "tags" in elements[1]:
            vibrancy = int(elements[1]["tags"].get("nodes", 0))
        if len(elements) > 2 and "tags" in elements[2]:
            critical = int(elements[2]["tags"].get("nodes", 0))

        return lamps, vibrancy, critical

    except Exception as e:
        print(f"Overpass Error: {e}")
        return 0, 0, 0

# ------------------------------------------
# Safety Score (Max-Differentiation)
# ------------------------------------------
def compute_safety_score(route):
    # Use 40 samples for high detail and reliable differentiation
    samples = get_route_samples(route["geometry"], n=40)
    if not samples:
        return 40.0

    lamps, vibrancy, critical = fetch_environment_data(samples)

    # IST handling
    hour = datetime.now().hour 
    is_night = hour < 6 or hour >= 20

    # Low Baseline 20.0 to make detected features matter more
    base = 20.0 
    
    # Lighting: 2.0 pts per lamp, max 80 (Higher weight for better differentiation)
    lighting_score = min(80.0, lamps * 2.0)
    
    # Vibrancy: 1.5 pts per shop, max 15.0 (Potent differentiator)
    vibrancy_score = min(15.0, vibrancy * 1.5)
    
    # Critical: 5.0 pts PER infrastructure (police/hospital), can stack to 10.0
    critical_score = min(10.0, critical * 5.0)

    # Tie-breaker: Subtract tiny fraction of duration (shorter = slightly safer/less exposure)
    tie_breaker = (route.get("duration", 0) / 5000.0)
    
    final_score = base + lighting_score + vibrancy_score + critical_score - tie_breaker
    print(f"DEBUG: Route features: Lamps={lamps}, Vibrancy={vibrancy}, Critical={critical}. Final Score={final_score}")
    
    if is_night:
        # Heavily penalize dark roads
        if lighting_score < 30: 
            final_score -= 25.0
        else:
            # Reward excellent lighting at night
            final_score += 5.0

    return round(max(10.0, min(100.0, final_score)), 2)

# ------------------------------------------
# ROUTES API
# ------------------------------------------
@app.route("/routes")
def routes():
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        return jsonify({"error": "Missing coordinates"}), 400

    try:
        s_lat, s_lon = start.split(',')
        e_lat, e_lon = end.split(',')
        
        url = f"{OSRM_URL}{s_lon},{s_lat};{e_lon},{e_lat}?alternatives=true&overview=full&geometries=geojson"
        
        response = session.get(url, timeout=10)
        data = response.json()

        if data.get("code") != "Ok":
            return jsonify({"error": "Route calculation failed"}), 404

        results = []
        for r in data["routes"]:
            real_duration_sec = r["duration"] * 1.5
            
            results.append({
                "distance_km": round(r["distance"]/1000, 2),
                "duration_min": round(real_duration_sec/60, 1),
                "duration_sec": int(real_duration_sec),
                "safety_score": float(compute_safety_score(r)),
                "geometry": r["geometry"]
            })

        return jsonify({"routes": results})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------
# GEOCODE API
# ------------------------------------------
@app.route("/geocode")
def geocode():
    place = request.args.get("place")
    if not place:
        return jsonify({"error": "Missing place"}), 400

    headers = {"User-Agent": "LuminaErnakulam/1.0"}
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={place}&viewbox={ERNAKULAM_BOUNDS}&bounded=1&limit=5&countrycodes=in"

    try:
        res = session.get(url, headers=headers, timeout=10)
        data = res.json()

        if not data:
            return jsonify({"error": "Location not found"}), 404

        results = []
        for item in data:
            results.append({
                "name": item["display_name"],
                "lat": float(item["lat"]),
                "lon": float(item["lon"])
            })
        return jsonify(results)
    except:
        return jsonify({"error": "Geocoding error"}), 503

# ------------------------------------------
# REVIEW API
# ------------------------------------------
@app.route("/review", methods=["POST"])
def submit_review():
    try:
        data = request.json
        print(f"DEBUG: Received Review Data: {data}")
        print(f"DEBUG: Saving to: {REVIEWS_FILE}")
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        email = data.get("email", "").strip()
        
        # Strict email validation
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            print(f"DEBUG: Email Validation Failed: {email}")
            return jsonify({"error": "Invalid email format"}), 400
            
        review = {
            "email": email,
            "rating": data.get("rating"),
            "comment": data.get("comment"),
            "route_key": data.get("route_key"),
            "category": classify_feedback(data.get("comment")),
            "timestamp": datetime.now().isoformat()
        }
        
        reviews = []
        if os.path.exists(REVIEWS_FILE):
            with open(REVIEWS_FILE, "r") as f:
                try:
                    reviews = json.load(f)
                except Exception as e:
                    print(f"DEBUG: JSON Read Error: {e}")
                    reviews = []
        
        reviews.append(review)
        with open(REVIEWS_FILE, "w") as f:
            json.dump(reviews, f, indent=4)
            print("DEBUG: File write successful.")

        return jsonify({"message": "Review saved successfully"}), 201
    except Exception as e:
        print(f"DEBUG: Submission Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/review_stats", methods=["GET"])
def get_review_stats():
    route_key = request.args.get("route_key")
    if not route_key:
        return jsonify({"error": "No route_key provided"}), 400
    
    reviews = []
    if os.path.exists(REVIEWS_FILE):
        with open(REVIEWS_FILE, "r") as f:
            try:
                reviews = json.load(f)
            except:
                reviews = []

    # Filter reviews for this specific route
    # Fallback: Also include "legacy" reviews that don't have the |type suffix
    base_key = route_key.rsplit('|', 1)[0] if '|' in route_key and (route_key.endswith('|fastest') or route_key.endswith('|safest')) else route_key
    
    route_reviews = [r for r in reviews if r.get("route_key") == route_key or r.get("route_key") == base_key]
    
    if not route_reviews:
        return jsonify({
            "thumbs_up": 0,
            "thumbs_down": 0,
            "average_rating": 0,
            "total_reviews": 0
        })

    thumbs_up = sum(1 for r in route_reviews if r.get("category") == "Good Review")
    thumbs_down = sum(1 for r in route_reviews if r.get("category") == "Complaint")
    
    ratings = [r.get("rating") for r in route_reviews if r.get("rating") is not None]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0

    return jsonify({
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "average_rating": round(avg_rating, 1),
        "total_reviews": len(route_reviews),
        "reviews": route_reviews
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)
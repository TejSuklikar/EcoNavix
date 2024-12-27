import requests
import openai
import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_energy_data(EIA_API_KEY):
    try:
        eia_url = (
            "https://api.eia.gov/v2/petroleum/pri/gnd/data/"
            f"?frequency=weekly&data[0]=value&sort[0][column]=period"
            f"&sort[0][direction]=desc&offset=0&length=5000&api_key={EIA_API_KEY}"
        )
        response = requests.get(eia_url)
        if response.status_code == 200:
            data = response.json()
            latest_data = data['response']['data'][0]
            return {
                "price_per_gallon": latest_data['value'],
                "period": latest_data['period']
            }
        else:
            print(f"Failed to get petroleum price data: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error in get_energy_data: {str(e)}")
        return None

def calculate_emissions(distance_km, CARBON_INTERFACE_API_KEY):
    try:
        url = "https://www.carboninterface.com/api/v1/estimates"
        headers = {
            "Authorization": f"Bearer {CARBON_INTERFACE_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "type": "vehicle",
            "distance_unit": "km",
            "distance_value": distance_km,
            "vehicle_model_id": "7268a9b7-17e8-4c8d-acca-57059252afe9"
        }
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 201:
            emissions_data = response.json()
            return {
                "carbon_g": emissions_data['data']['attributes']['carbon_g'],
                "carbon_kg": emissions_data['data']['attributes']['carbon_g'] / 1000
            }
        else:
            print(f"Failed to calculate carbon emissions: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Error in calculate_emissions: {str(e)}")
        return None

def get_weather_data(location, WEATHER_API_KEY):
    try:
        weather_url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={location}&appid={WEATHER_API_KEY}&units=metric"
        )
        response = requests.get(weather_url)
        if response.status_code == 200:
            weather_data = response.json()
            return {
                "temperature": weather_data['main']['temp'],
                "weather": weather_data['weather'][0]['description'],
                "wind_speed": weather_data['wind']['speed']
            }
        else:
            print(f"Failed to get weather data: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error in get_weather_data: {str(e)}")
        return None

def get_eco_route(origin_coords, destination_coords, OPENROUTESERVICE_API_KEY):
    try:
        # Ensure coordinates are in [lon, lat] for ORS
        formatted_origin = [origin_coords[1], origin_coords[0]]
        formatted_destination = [destination_coords[1], destination_coords[0]]
        
        headers = {
            "Authorization": OPENROUTESERVICE_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "coordinates": [formatted_origin, formatted_destination],
            "profile": "driving-car"
        }
        
        ors_url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
        response = requests.post(ors_url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"ORS Error: {response.status_code}, {response.text}")
            return None
            
        route_data = response.json()
        
        if "features" in route_data and route_data["features"]:
            route_feature = route_data["features"][0]
            coords = route_feature["geometry"]["coordinates"]
            properties = route_feature["properties"]
            
            # Convert coords to [lat, lon] for frontend
            converted_coordinates = [[c[1], c[0]] for c in coords]
            
            duration_minutes = round(properties["segments"][0]["duration"] / 60)
            distance_km = properties["segments"][0]["distance"] / 1000
            
            directions = []
            for segment in properties["segments"]:
                for step in segment.get("steps", []):
                    if "instruction" in step:
                        directions.append(step["instruction"])
            
            return {
                "distance_km": distance_km,
                "duration_minutes": duration_minutes,
                "coordinates": converted_coordinates,
                "directions": directions
            }
        else:
            print("No route found in the ORS response.")
            return None
            
    except Exception as e:
        print(f"Error in get_eco_route: {str(e)}")
        return None

def simulate_optimized_route(route_data):
    """
    Stub to simulate an 'optimized' route. Adjust logic as needed.
    """
    return {
        "optimized_distance_km": route_data["distance_km"],  # same distance
        "optimized_duration_minutes": round(route_data["duration_minutes"] * 0.95),
        "optimized_carbon_emissions": {
            "carbon_kg": route_data["emissions"]["carbon_kg"] * 0.9
        }
    }

def generate_openai_prompt(route_data, energy_data, carbon_emissions, weather_origin, weather_destination, vehicle):
    prompt = (
        f"Based on the following information:\n"
        f"- Distance: {route_data['distance_km']} km\n"
        f"- Estimated Time: {route_data['duration_minutes']} minutes\n"
        f"- Energy Price: ${energy_data['price_per_gallon']} per gallon\n"
        f"- Estimated Carbon Emissions: {carbon_emissions['carbon_kg']:.2f} kg of CO₂\n"
        f"- Weather at Origin: {weather_origin['weather']}, "
        f"  Temperature: {weather_origin['temperature']}°C, "
        f"  Wind Speed: {weather_origin['wind_speed']} m/s\n"
        f"- Weather at Destination: {weather_destination['weather']}, "
        f"  Temperature: {weather_destination['temperature']}°C, "
        f"  Wind Speed: {weather_destination['wind_speed']} m/s\n"
        f"- Vehicle Type: {vehicle['type']}, "
        f"  Fuel Efficiency: {vehicle['efficiency']} km/l, "
        f"  Fuel Type: {vehicle['fuel_type']}\n"
        f" Provide a recommendation for reducing emissions and optimizing energy consumption for this route. Dont number the first part with based on the information part. Then the others should be indented in and then numbered starting a 1 "
    )
    return prompt

def get_openai_recommendation(prompt, OPENAI_API_KEY):
    try:
        openai.api_key = OPENAI_API_KEY  # Set the key for this request
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI assistant that provides route and energy optimization advice."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=200,
            temperature=0.7
        )
        return response['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"Error calling OpenAI API: {e}")
        return "Failed to generate recommendation."

@app.route('/get_route_recommendation', methods=['POST'])
def get_route_recommendation():
    try:
        data = request.json
        
        # Extract user-provided coords, vehicle info, and all API keys
        origin_coords = data.get('origin_coords')
        destination_coords = data.get('destination_coords')
        vehicle = data.get('vehicle')
        api_keys = data.get('api_keys', {})
        
        # Pull each key from the request
        EIA_API_KEY = api_keys.get('EIA_API_KEY')
        CARBON_INTERFACE_API_KEY = api_keys.get('CARBON_INTERFACE_API_KEY')
        WEATHER_API_KEY = api_keys.get('WEATHER_API_KEY')
        OPENROUTESERVICE_API_KEY = api_keys.get('OPENROUTESERVICE_API_KEY')
        OPENAI_API_KEY = api_keys.get('OPENAI_API_KEY')
        
        # Validate that all keys are present
        if not all([EIA_API_KEY, CARBON_INTERFACE_API_KEY, WEATHER_API_KEY, OPENROUTESERVICE_API_KEY, OPENAI_API_KEY]):
            return jsonify({"error": "All five API keys are required."}), 400
        
        if not (origin_coords and destination_coords):
            return jsonify({"error": "Both origin_coords and destination_coords must be provided."}), 400
        
        # 1. Get route data
        route_data = get_eco_route(origin_coords, destination_coords, OPENROUTESERVICE_API_KEY)
        if not route_data:
            return jsonify({"error": "Unable to calculate route with provided coordinates."}), 400
        
        # 2. Get energy data
        energy_data = get_energy_data(EIA_API_KEY)
        if not energy_data:
            # Fallback or raise an error
            return jsonify({"error": "Unable to retrieve energy data from EIA API."}), 400
        
        # 3. Get weather data (use actual city names as needed)
        weather_origin = get_weather_data("San Francisco", WEATHER_API_KEY) or {
            "temperature": 20,
            "weather": "clear",
            "wind_speed": 5
        }
        weather_destination = get_weather_data("Los Angeles", WEATHER_API_KEY) or {
            "temperature": 25,
            "weather": "clear",
            "wind_speed": 5
        }
        
        # 4. Calculate emissions
        carbon_emissions = calculate_emissions(route_data["distance_km"], CARBON_INTERFACE_API_KEY)
        if not carbon_emissions:
            # Provide some fallback or error handling
            carbon_emissions = {
                "carbon_g": route_data["distance_km"] * 2310,
                "carbon_kg": route_data["distance_km"] * 2.31
            }
        
        route_data["emissions"] = carbon_emissions
        
        # 5. Simulate optimized route
        optimized_route = simulate_optimized_route(route_data)
        
        # 6. Generate AI recommendation
        prompt = generate_openai_prompt(route_data, energy_data, carbon_emissions, 
                                        weather_origin, weather_destination, vehicle)
        recommendation = get_openai_recommendation(prompt, OPENAI_API_KEY)
        
        # 7. Compare original vs. optimized
        comparison = {
            "original": {
                "distance_km": route_data["distance_km"],
                "duration_minutes": route_data["duration_minutes"],
                "carbon_emissions_kg": carbon_emissions["carbon_kg"]
            },
            "optimized": {
                "distance_km": optimized_route["optimized_distance_km"],
                "duration_minutes": optimized_route["optimized_duration_minutes"],
                "carbon_emissions_kg": optimized_route["optimized_carbon_emissions"]["carbon_kg"]
            }
        }
        
        return jsonify({
            "route": route_data["coordinates"],
            "directions": route_data["directions"],
            "comparison": comparison,
            "recommendation": recommendation
        })
    except Exception as e:
        print(f"Error in route recommendation: {e}")
        return jsonify({"error": f"Internal server error: {e}"}), 500

if __name__ == "__main__":
    # Run Flask in debug mode for local dev only
    app.run(host="0.0.0.0", port=5050, debug=True)

import csv
from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import numpy as np
import os
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
import plotly.express as px
import json

app = Flask(__name__)
app.secret_key = 'bilateral'

# Mapping for city name normalization
city_name_map = {
    "City of Davao": "Davao City",
    "City of Dagupan": "Dagupan City",
    "City of Palayan": "Palayan City",
    "City of Legazpi": "Legazpi City",
    "City of Iloilo": "Iloilo City",
    "City of Mandaue": "Mandaue City",
    "City of Tacloban": "Tacloban City",
    "City of Zamboanga": "Zamboanga City",
    "City of Cagayan De Oro": "Cagayan De Oro City",
    "City of Mandaluyong": "Mandaluyong City",
    "City of Navotas": "Navotas City",
    "City of Muntinlupa": "Muntinlupa City",
}

# Function to add lagged features
def add_lag_features(data, target_col, lags=5):
    for lag in range(1, lags + 1):
        data[f"{target_col}_lag{lag}"] = data[target_col].shift(lag)
    return data

# Function to validate city data
def validate_city_data(data, min_rows=5):
    city_counts = data['adm3_en'].value_counts()
    valid_cities = city_counts[city_counts >= min_rows].index
    return data[data['adm3_en'].isin(valid_cities)]

# Function to sanitize data for JSON serialization
def sanitize_for_json(data):
    if isinstance(data, list):
        return [sanitize_for_json(item) for item in data]
    elif isinstance(data, dict):
        return {key: sanitize_for_json(value) for key, value in data.items()}
    elif isinstance(data, (np.int64, np.float64)):
        return int(data) if isinstance(data, np.int64) else float(data)
    elif isinstance(data, pd.Timestamp):
        return data.strftime('%Y-%m-%d')
    return data


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    # Load CSV data
    disease_data = []
    with open('static/disease_risk_by_city_historical.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            disease_data.append(row)

    return render_template('dashboard.html', disease_data=disease_data)


@app.route('/location', methods=["GET", "POST"])
def location():
    if request.method == "POST":
        uploaded_file = request.files['file']
        selected_disease = request.form.get('disease', 'dengue')

        if not uploaded_file.filename:
            return "No file selected.", 400

        input_data = pd.read_csv(uploaded_file)
        session['uploaded_file_name'] = uploaded_file.filename

        input_data['date'] = pd.to_datetime(input_data['date'])
        input_data = input_data.sort_values(by=['adm3_en', 'date'])
        session['last_date'] = input_data['date'].max().strftime('%Y-%m-%d')

        valid_data = validate_city_data(input_data)
        valid_data['adm3_en'] = valid_data['adm3_en'].str.strip().str.lower()  # Standardize city names
        feature_columns = ['tave', 'tmin', 'tmax', 'heat_index', 'pr', 'wind_speed', 'rh', 'solar_rad', 'uv_rad']
        scaler = MinMaxScaler()
        valid_data[feature_columns] = scaler.fit_transform(valid_data[feature_columns])

        valid_data = add_lag_features(valid_data, 'case_total', lags=5).dropna()

        predictions = []
        forecast_horizon = 5

        for city in valid_data['adm3_en'].unique():
            city_data = valid_data[valid_data['adm3_en'] == city].copy()
            model_path = f"./models/{selected_disease}/{city}_lstm_model.h5"

            try:
                model = load_model(model_path)
            except Exception as e:
                print(f"Model not found for {city}: {e}")
                continue

            feature_columns_lstm = feature_columns + [f"case_total_lag{i}" for i in range(1, 6)]
            city_data = city_data.sort_values(by="date")
            X = city_data[feature_columns_lstm].values.reshape(city_data.shape[0], 1, len(feature_columns_lstm))
            y_pred = model.predict(X).flatten()
            city_data['Predicted_Cases'] = np.round(y_pred).astype(int)

            last_row = city_data.iloc[-1]
            future_dates = pd.date_range(last_row['date'] + pd.Timedelta(days=7), periods=forecast_horizon, freq='7D')

            for future_date in future_dates:
                lagged_features = [last_row[f"case_total_lag{i}"] for i in range(1, 5)]
                lagged_features = [last_row['Predicted_Cases']] + lagged_features
                lagged_features.reverse()

                future_features = np.array(last_row[feature_columns].tolist() + lagged_features).reshape(1, 1, -1)
                future_pred = model.predict(future_features).flatten()[0]

                last_row['Predicted_Cases'] = np.round(future_pred).astype(int)
                last_row['date'] = future_date

                for i in range(5, 0, -1):
                    if i == 1:
                        last_row[f"case_total_lag{i}"] = last_row['Predicted_Cases']
                    else:
                        last_row[f"case_total_lag{i}"] = last_row[f"case_total_lag{i-1}"]

                predictions.append({'date': future_date, 'adm3_en': city, 'Predicted_Cases': last_row['Predicted_Cases']})

            predictions.extend(city_data[['date', 'adm3_en', 'Predicted_Cases']].to_dict('records'))
            
        predictions = pd.DataFrame(predictions)
        predictions['adm3_en'] = predictions['adm3_en'].str.strip().str.lower() # Standardize city names again
        
        # Save predictions in session as JSON
        session['predictions'] = predictions.to_json(orient='records', date_format='iso')
        session['selected_disease'] = selected_disease
        return redirect(url_for('location'))

    # Check if predictions exist in the session and are properly formatted
    predictions_data = session.get('predictions', [])
    if predictions_data:
        predictions = pd.read_json(predictions_data, orient='records')
    else:
        predictions = pd.DataFrame()  # Empty DataFrame if no predictions are found
    
    graph_html = ""
    if not predictions.empty:
        predictions['date'] = pd.to_datetime(predictions['date'])
        last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))
        predictions['Type'] = 'Historical'
        predictions.loc[predictions['date'] > last_date, 'Type'] = 'Forecast'

        fig = px.line(
            predictions,
            x='date',
            y='Predicted_Cases',
            color='adm3_en',
            line_dash='Type',
            title=f"{session.get('selected_disease', 'Disease')} Case Predictions"
        )
        graph_html = fig.to_html(full_html=False)

    return render_template('location.html', graph_html=graph_html)



@app.route('/info')
def info():
    return render_template('info.html')

@app.route('/leptos')
def leptos():
    return render_template('Leptos.html')

@app.route('/typhoid')
def typhoid():
    return render_template('Typhoid.html')

@app.route('/abd')
def abd():
    return render_template('ABD.html')

@app.route('/dengue')
def dengue():
    return render_template('Dengue.html')

@app.route('/geojson/cities')
def geojson_cities():
    with open('static/filtered_cities.geojson', 'r') as f:
        geojson_data = json.load(f)

    # Retrieve predictions from session
    predictions = pd.read_json(session.get('predictions', '[]'), orient='records')
    if not predictions.empty:
        predictions['date'] = pd.to_datetime(predictions['date'])
        latest_predictions = predictions.loc[predictions.groupby('adm3_en')['date'].idxmax()]

        # Define risk levels based on predicted cases
        def get_risk_level(cases):
            if cases <= 10:
                return "low"
            elif 10 < cases <= 30:
                return "medium"
            elif 30 < cases <= 50:
                return "high"
            else:
                return "severe"

        # Assign risk levels to predictions
        latest_predictions['risk_level'] = latest_predictions['Predicted_Cases'].apply(get_risk_level)

        # Normalize city names in predictions
        latest_predictions['adm3_en_normalized'] = latest_predictions['adm3_en'].map(
            lambda x: city_name_map.get(x, x).lower().strip()
        )

        # Debugging: Print city names
        print("GeoJSON city names:", [feature['properties'].get('adm3_en') for feature in geojson_data['features']])
        print("Prediction city names:", latest_predictions['adm3_en'].unique())
        
        # Normalize city names in GeoJSON and match predictions
        for feature in geojson_data['features']:
            geojson_city_name = feature['properties'].get('adm3_en', '').strip()
            normalized_city_name = city_name_map.get(geojson_city_name, geojson_city_name).lower()

            # Match GeoJSON city with normalized prediction data
            city_data = latest_predictions[
                latest_predictions['adm3_en_normalized'] == normalized_city_name
            ]

            # Assign risk level to GeoJSON property
            if not city_data.empty:
                feature['properties']['risk_level'] = city_data.iloc[0]['risk_level']
            else:
                feature['properties']['risk_level'] = "none"

    return geojson_data


@app.route('/filtered-graph')
def filtered_graph():
    city = request.args.get('city', '').strip().lower()
    print(f"Requested city: {city}")

    predictions_data_str = session.get('predictions', None)  # Get predictions data (as a string)
    print(f"Predictions data type: {type(predictions_data_str)}")

    if not predictions_data_str:
        print("Predictions dataset is empty or None.")
        return "<p>No data available for this city.</p>"

    try:
        # If it's a JSON string, parse it into a Python structure
        predictions_data = json.loads(predictions_data_str)
        print(f"Parsed predictions data: {predictions_data[:5]}")  # Log the first few elements
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return "<p>There was an error processing the data.</p>"

    try:
        predictions = pd.DataFrame(predictions_data)
    except Exception as e:
        print(f"Error creating DataFrame: {e}")
        return "<p>There was an error processing the data.</p>"

    predictions['adm3_en'] = predictions['adm3_en'].str.lower()
    predictions['date'] = pd.to_datetime(predictions['date'])
    last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))
    predictions['Type'] = 'Historical'
    predictions.loc[predictions['date'] > last_date, 'Type'] = 'Forecast'

    # Filter predictions for the selected city
    filtered_predictions = predictions[predictions['adm3_en'] == city]
    print(f"Filtered predictions for {city}:\n", filtered_predictions)

    if filtered_predictions.empty:
        return "<p>No data available for this city.</p>"

    fig = px.line(
        filtered_predictions,
        x='date',
        y='Predicted_Cases',
        color='adm3_en',
        line_dash='Type',
        title=f"Disease Case Predictions for {city.title()}"
    )
    return fig.to_html(full_html=False)

if __name__ == '__main__':
    app.run(debug=True)

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
    # Load historical disease data from the CSV file
    disease_data = []
    with open('static/disease_risk_by_city_historical.csv', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            disease_data.append(row)

    # Load prediction data from the session
    predictions_data = session.get('predictions', {})
    unique_cities = session.get('unique_cities', [])
    selected_disease = session.get('selected_disease', 'Disease').title()
    
    # Parse the predictions data if it exists
    if predictions_data:
        predictions = pd.read_json(predictions_data, orient='records')
    else:
        predictions = pd.DataFrame()

    # Check if the 'adm3_en' column exists in predictions
    if 'adm3_en' not in predictions.columns:
        print("adm3_en column is missing!")
        # Fix column names by stripping extra spaces and converting to lowercase
        predictions.columns = [col.strip().lower() for col in predictions.columns]
        print("Columns in predictions:", predictions.columns)
    else:
        print("adm3_en column exists.")

    # Generate city_totals from predictions
    city_totals = {}
    if 'adm3_en' in predictions.columns:
        for city, total_cases in predictions.groupby('adm3_en')['Predicted_Cases'].sum().items():
            standardized_city = city.strip().lower()
            city_totals[standardized_city] = total_cases

    # Ensure city_totals is a dictionary and keys are properly standardized
    print("City Totals Generated from Predictions:", city_totals)
    
    # Ensure city_totals is a dictionary and keys are properly standardized
    city_totals = dict(sorted(city_totals.items(), key=lambda x: x[1], reverse=True))  # Sort by total cases descending
    top_4_cities = dict(list(city_totals.items())[:4])  # Get the top 4 cities
    
    # Generate weekly_totals from predictions (using only forecasted data)
    weekly_totals = {}
    if not predictions.empty:
        # Ensure the 'date' column is in datetime format
        predictions['date'] = pd.to_datetime(predictions['date'], errors='coerce')

        # Filter predictions to include only forecasted data (after the last actual date)
        last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))
        forecast_predictions = predictions[predictions['date'] > last_date]

        # Add 'week' column based on forecasted dates
        forecast_start_date = forecast_predictions['date'].min()  # Earliest forecasted date
        forecast_predictions['week'] = forecast_predictions['date'].apply(
            lambda x: f"Week {(x - forecast_start_date).days // 7 + 1}"
        )
        forecast_predictions['week'] = forecast_predictions['week'].replace({'Week 6': 'Week 5'})  # Handle overflow if any

        # Group by week and city
        grouped = forecast_predictions.groupby(['week', 'adm3_en'])['Predicted_Cases'].sum()

        # Transform into nested dictionary: weekly_totals[week][city] = total_cases
        for (week, city), total_cases in grouped.items():
            if week not in weekly_totals:
                weekly_totals[week] = {}
            standardized_city = city.strip().lower()
            weekly_totals[week][standardized_city] = total_cases
    
    return render_template(
        'dashboard.html',
        disease_data=disease_data,
        top_4_cities=top_4_cities,
        city_totals=city_totals,
        weekly_totals=weekly_totals,
        unique_cities=unique_cities,
        selected_disease=selected_disease
    )



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

            forecast_predictions = []

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

                forecast_predictions.append({'date': future_date, 'adm3_en': city, 'Predicted_Cases': last_row['Predicted_Cases']})

            # Only add the forecasted predictions, not the historical data
            predictions.extend(forecast_predictions)

        predictions = pd.DataFrame(predictions)
        predictions['adm3_en'] = predictions['adm3_en'].str.strip().str.lower()  # Standardize city names again
        
        # Get unique cities and total predicted cases per city
        # unique_cities = predictions['adm3_en'].unique()
        
        # Get the last actual date
        last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))

        # Filter predictions to include only forecasted values (after the last actual date)
        forecast_predictions = predictions[predictions['date'] > last_date]

        # Get unique cities and total predicted cases per city (only forecasted)
        unique_cities = forecast_predictions['adm3_en'].unique()
        city_totals = forecast_predictions.groupby('adm3_en')['Predicted_Cases'].sum().to_dict()

        # Print to console for debugging or logging purposes
        print("Unique Cities:")
        print(unique_cities)

        print("\nTotal Predicted Cases Per City:")
        for city, total in city_totals.items():
            print(f"{city}: {total}")
            
        # Save predictions in session as JSON
        session['predictions'] = predictions.to_json(orient='records', date_format='iso')
        session['selected_disease'] = selected_disease
        session['unique_cities'] = unique_cities.tolist()
        city_totals = {city.lower(): total for city, total in city_totals.items()}
        session['city_totals'] = city_totals
        return redirect(url_for('location'))

    predictions_data = session.get('predictions', [])
    if predictions_data:
        predictions = pd.read_json(predictions_data, orient='records')
        # Get the last actual date
        last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))

        # Filter predictions to include only forecasted values (after the last actual date)
        forecast_predictions = predictions[predictions['date'] > last_date]
        unique_cities = session.get('unique_cities', [])
        city_totals = session.get('city_totals', {})
    else:
        predictions = pd.DataFrame()  # Empty DataFrame if no predictions are found
        forecast_predictions = pd.DataFrame() 
        unique_cities = []
        city_totals = {}

    
    graph_html = ""
    if not forecast_predictions.empty:
        forecast_predictions['date'] = pd.to_datetime(forecast_predictions['date'])
        forecast_predictions['Type'] = 'Forecast'

        # Create the plot using only forecast data
        fig = px.line(
            forecast_predictions,
            x='date',
            y='Predicted_Cases',
            color='adm3_en',
            line_dash='Type',
            title=f"{session.get('selected_disease', 'Disease').title()} Case Predictions"
        )
        fig.update_layout(
    title=dict(
        text=f"{session.get('selected_disease', 'Disease').title()} Case Predictions",
        font=dict(size=20, color="#F2F2F2"),  # Title font size and color
        x=0.5  # Center the title
    ),
    xaxis=dict(
        title="Date",
        titlefont=dict(size=16, color="#F2F2F2"),
        tickfont=dict(size=14, color="#F2F2F2"),
        showgrid=False,
        zeroline=False
    ),
    yaxis=dict(
        title="Predicted Cases",
        titlefont=dict(size=16, color="#F2F2F2"),
        tickfont=dict(size=14, color="#F2F2F2"),
        gridcolor="#444444",
        zeroline=False
    ),
    paper_bgcolor="#191919",  # Background of the entire figure
    plot_bgcolor="#1E1E1E",  # Background of the graph
    legend=dict(
        title=dict(text="Cities", font=dict(size=14, color="#F2F2F2")),
        font=dict(size=12, color="#F2F2F2"),
        bgcolor="#1E1E1E",
        bordercolor="#191919",
        borderwidth=1,
        orientation='h',  # Horizontal legend
        yanchor='bottom',  # Align legend at the bottom
        y=-0.75,  # Adjusted margin below the graph
        xanchor='center',  # Center align the legend horizontally
        x=0.5  # Position the legend at the center
    ),
    height=600  # Set the height of the graph (adjust as needed)
)

    graph_html = fig.to_html(full_html=False, config={"displayModeBar": False})
    
    return render_template(
        'location.html',
        graph_html=graph_html,
        unique_cities=unique_cities,
        city_totals=city_totals
    )

@app.route('/about')
def about():
    return render_template('about.html')

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
        
        # Calculate the sum of predicted cases over the forecasted period (5 weeks)
        sum_predictions = predictions.groupby('adm3_en')['Predicted_Cases'].sum().reset_index()

        # Define risk levels based on total predicted cases
        def get_risk_level(cases):
            if cases <= 17:
                return "low"
            elif 17 < cases <= 34:
                return "medium"
            elif 34 < cases <= 66:
                return "high"
            else:
                return "severe"

        # Assign risk levels to predictions
        sum_predictions['risk_level'] = sum_predictions['Predicted_Cases'].apply(get_risk_level)

        # Normalize city names in predictions
        sum_predictions['adm3_en_normalized'] = sum_predictions['adm3_en'].map(
            lambda x: city_name_map.get(x, x).lower().strip()
        )

        # Debugging: Print city names
        print("GeoJSON city names:", [feature['properties'].get('adm3_en') for feature in geojson_data['features']])
        print("Prediction city names:", sum_predictions['adm3_en'].unique())
        
        # Normalize city names in GeoJSON and match predictions
        for feature in geojson_data['features']:
            geojson_city_name = feature['properties'].get('adm3_en', '').strip()
            normalized_city_name = city_name_map.get(geojson_city_name, geojson_city_name).lower()

            # Match GeoJSON city with normalized prediction data
            city_data = sum_predictions[
                sum_predictions['adm3_en_normalized'] == normalized_city_name
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

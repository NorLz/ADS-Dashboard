from flask import Flask, render_template, request, redirect, url_for, session, send_file
import pandas as pd
import numpy as np
import os
from tensorflow.keras.models import load_model
from sklearn.preprocessing import MinMaxScaler
import plotly.express as px

app = Flask(__name__)
app.secret_key = 'bilateral'

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/location', methods=["GET", "POST"])
def location():
    if request.method == "POST":
        uploaded_file = request.files['file']
        if not uploaded_file.filename:
            return "No file selected.", 400

        # Process uploaded data
        input_data = pd.read_csv(uploaded_file)
        session['uploaded_file_name'] = uploaded_file.filename

        # Ensure 'date' is in datetime format and sorted
        input_data['date'] = pd.to_datetime(input_data['date'])
        input_data = input_data.sort_values(by=['adm3_en', 'date'])

        # Save last known date for forecast distinction
        session['last_date'] = input_data['date'].max().strftime('%Y-%m-%d')

        # Validate and normalize data
        valid_data = validate_city_data(input_data)
        feature_columns = ['tave', 'tmin', 'tmax', 'heat_index', 'pr', 'wind_speed', 'rh', 'solar_rad', 'uv_rad']
        scaler = MinMaxScaler()
        valid_data[feature_columns] = scaler.fit_transform(valid_data[feature_columns])

        # Add lagged features
        valid_data = add_lag_features(valid_data, 'case_total', lags=5).dropna()

        # Predictions
        predictions = []
        forecast_horizon = 5
        # Sanitize before storing in session
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
        
        for city in valid_data['adm3_en'].unique():
            city_data = valid_data[valid_data['adm3_en'] == city].copy()
            model_path = f"./models/dengue/{city}_lstm_model.h5"
            try:
                model = load_model(model_path)
            except:
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

        session['predictions'] = sanitize_for_json(predictions)
        return redirect(url_for('location'))

    predictions = pd.DataFrame(session.get('predictions', []))
    graph_html = ""
    if not predictions.empty:
        # Convert 'date' column in predictions to datetime
        predictions['date'] = pd.to_datetime(predictions['date'])
        
        # Ensure last_date is also a Timestamp
        last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))
        
        predictions['Type'] = 'Historical'
        predictions.loc[predictions['date'] > last_date, 'Type'] = 'Forecast'

        fig = px.line(
            predictions,
            x='date',
            y='Predicted_Cases',
            color='adm3_en',
            line_dash='Type',
            title="Disease Case Predictions"
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
    return send_file('static/filtered_cities.geojson', mimetype='application/json')

@app.route('/filtered-graph')
def filtered_graph():
    city = request.args.get('city', '')
    print(f"Requested city: {city}")  # Log requested city
    predictions = pd.DataFrame(session.get('predictions', []))

    if predictions.empty:
        print("Predictions dataset is empty.")  # Log empty dataset
        return "<p>No data available for this city.</p>"

    predictions['date'] = pd.to_datetime(predictions['date'])
    last_date = pd.to_datetime(session.get('last_date', pd.Timestamp.now()))
    predictions['Type'] = 'Historical'
    predictions.loc[predictions['date'] > last_date, 'Type'] = 'Forecast'

    # Filter predictions for the selected city
    filtered_predictions = predictions[predictions['adm3_en'].str.lower() == city.lower()]
    print(f"Filtered predictions for {city}:\n", filtered_predictions)

    if filtered_predictions.empty:
        return "<p>No data available for this city.</p>"

    fig = px.line(
        filtered_predictions,
        x='date',
        y='Predicted_Cases',
        color='adm3_en',
        line_dash='Type',
        title=f"Disease Case Predictions for {city}"
    )
    return fig.to_html(full_html=False)



if __name__ == '__main__':
    app.run(debug=True)

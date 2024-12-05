from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/location')
def location():
    return render_template('location.html')

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

if __name__ == '__main__':
    app.run(debug=True)

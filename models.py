from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Usage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    monthly_requests = db.Column(db.Integer, default=0)
    requests_in_current_minute = db.Column(db.Integer, default=0)
    last_request_time = db.Column(db.DateTime)
    total_requests = db.Column(db.Integer, default=0)
    daily_requests = db.Column(db.Integer, default=0)
    weekly_requests = db.Column(db.Integer, default=0)

    def increment_requests(self):
        """Increment request counts."""
        self.monthly_requests = (self.monthly_requests or 0) + 1
        self.requests_in_current_minute = (self.requests_in_current_minute or 0) + 1
        self.total_requests = (self.total_requests or 0) + 1
        self.daily_requests = (self.daily_requests or 0) + 1
        self.weekly_requests = (self.weekly_requests or 0) + 1
        self.last_request_time = datetime.utcnow()

    def reset_usage(self):
        """Reset the monthly request counts."""
        self.monthly_requests = 0
        self.requests_in_current_minute = 0
        self.daily_requests = 0
        self.weekly_requests = 0
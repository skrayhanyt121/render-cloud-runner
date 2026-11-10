import os

# Gunicorn configuration for Render Cloud Deployment
bind = f"0.0.0.0:{os.environ.get('PORT', 5050)}"
workers = 1
threads = 8
timeout = 180
accesslog = "-"
errorlog = "-"

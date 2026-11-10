import os

# Gunicorn configuration for Render Cloud Deployment
bind = f"0.0.0.0:{os.environ.get('PORT', 5050)}"
workers = 1
threads = 8
timeout = 180
accesslog = "-"
errorlog = "-"

def post_fork(server, worker):
    """Ensure bot background subprocess starts cleanly inside worker, never in master."""
    try:
        import server as app_server
        app_server.ensure_bot_running()
    except Exception as e:
        print(f"Error starting bot in post_fork: {e}")

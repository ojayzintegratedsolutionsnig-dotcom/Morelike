import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5002')}"
worker_class = "eventlet"
timeout = 300
loglevel = "info"

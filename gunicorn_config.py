# Gunicorn config file - reduced for macOS
bind = "0.0.0.0:8080"

# Reduced workers for macOS
workers = 3

# Threads per worker
threads = 2

# Timeout in seconds
timeout = 600

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

import multiprocessing
import os

workers = (2 * multiprocessing.cpu_count()) + 1
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 60
keepalive = 5
loglevel = os.getenv("LOG_LEVEL", "info").lower()
accesslog = "-"
errorlog = "-"

listen "0.0.0.0:8000", :tcp_nopush => false
worker_processes 1
timeout 600
preload_app true

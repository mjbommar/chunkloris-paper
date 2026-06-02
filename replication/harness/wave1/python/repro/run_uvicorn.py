import uvicorn
uvicorn.run("app:app", host="0.0.0.0", port=8000, http="h11",
            log_level="warning", access_log=False)

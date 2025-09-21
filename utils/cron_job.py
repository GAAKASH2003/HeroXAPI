
import threading
import time
import schedule
from flask import Flask, request, jsonify
from datetime import datetime

# =========================================================================
# The Flask Application
# =========================================================================

app = Flask(__name__)

# This function defines the task that will be scheduled and executed.
# It simply prints a message to the console.
def job_function(task_name):
    """
    A simple task function that prints a message.
    In a real-world scenario, this could be a call to another service,
    a database operation, or a file processing script.
    """
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Executing scheduled job: {task_name}")

@app.route("/schedule_job", methods=["POST"])
def schedule_job():
    """
    API endpoint to schedule a job.
    Expects a JSON payload with 'task_name' and 'time'.

    Example POST request body (JSON):
    {
        "task_name": "daily_report_generation",
        "time": "14:30"
    }

    The time format should be "HH:MM".
    """
    # 1. Validate and parse the incoming request data
    try:
        data = request.get_json()
        if not data or "task_name" not in data or "time" not in data:
            return jsonify({"error": "Missing 'task_name' or 'time' in request body"}), 400

        task_name = data["task_name"]
        schedule_time = data["time"]

        # Basic time format validation (e.g., "14:30")
        try:
            datetime.strptime(schedule_time, "%H:%M")
        except ValueError:
            return jsonify({"error": "Invalid time format. Use 'HH:MM'."}), 400

    except Exception as e:
        # Handle JSON parsing errors or other request issues
        return jsonify({"error": f"Failed to parse request: {e}"}), 400

    # 2. Schedule the job using the `schedule` library
    # The `do()` method takes the function to be called and any arguments for that function.
    schedule.every().day.at(schedule_time).do(job_function, task_name)
    print(f"Successfully scheduled job '{task_name}' to run every day at {schedule_time}.")

    # 3. Respond to the client
    return jsonify({
        "message": f"Job '{task_name}' scheduled successfully.",
        "scheduled_time": schedule_time
    }), 200

# =========================================================================
# The Scheduler Thread
# =========================================================================

# This function runs the scheduling loop in a separate thread.
# This is crucial because `schedule.run_pending()` is a blocking call,
# and we need the Flask app to remain responsive to incoming requests.
def run_schedule():
    """
    Runs the `schedule.run_pending()` loop in an infinite loop.
    This function will be started in a separate thread.
    """
    while True:
        schedule.run_pending()
        time.sleep(1) # Sleep for a second to prevent high CPU usage

# =========================================================================
# Main Execution Block
# =========================================================================

if __name__ == "__main__":
    # Start the scheduler in a background thread.
    scheduler_thread = threading.Thread(target=run_schedule)
    scheduler_thread.daemon = True # Allows the main program to exit even if the thread is still running
    scheduler_thread.start()

    # Set up basic Flask logging
    app.logger.setLevel('INFO')

    # Run the Flask app
    app.run(host="0.0.0.0", port=5000)


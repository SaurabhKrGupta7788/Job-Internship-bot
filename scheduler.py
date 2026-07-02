import subprocess
import sys
import os
import platform

def get_task_command():
    """Creates a .bat file to run the task and returns its path."""
    python_exe = sys.executable
    runner_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "runner.py"))
    bat_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "run_bot.bat"))
    
    with open(bat_path, "w") as f:
        f.write(f'@echo off\n"{python_exe}" "{runner_path}"\n')
        
    return f'"{bat_path}"'

def schedule_task(time_str="10:00", interval_days=2):
    """
    Registers a scheduled task in Windows Task Scheduler.
    Runs the runner.py script every N days at the specified time.
    """
    if platform.system() != "Windows":
        return False, "Scheduling is only supported on Windows operating systems."

    task_name = "JobCraftAutomation"
    run_cmd = get_task_command()
    
    # schtasks command
    # /create: create a new task
    # /tn: task name
    # /tr: task run command
    # /sc: schedule type (daily)
    # /mo: modifier (every 2 days)
    # /st: start time
    # /f: force creation (overwrite existing)
    # /rl: RUNLEVEL (Highest to run with elevated permissions if user is admin)
    cmd = [
        "schtasks", "/create", 
        "/tn", task_name,
        "/tr", run_cmd,
        "/sc", "daily",
        "/mo", str(interval_days),
        "/st", time_str,
        "/f"
    ]
    
    try:
        # Run command
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, f"Successfully scheduled task. Output: {result.stdout.strip()}"
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or str(e)
        # Often needs admin rights or quotes escaping issues. Let's provide a helpful hint.
        if "Access is denied" in error_msg:
            return False, "Access Denied. Please run the terminal or Flask server as Administrator to register scheduled tasks."
        return False, f"Failed to schedule task: {error_msg.strip()}"

def unschedule_task():
    """Removes the scheduled task from Windows Task Scheduler."""
    if platform.system() != "Windows":
        return False, "Scheduling is only supported on Windows."
        
    task_name = "JobCraftAutomation"
    cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, f"Successfully unscheduled task. Output: {result.stdout.strip()}"
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr or e.stdout or str(e)
        if "The system cannot find the file specified" in error_msg:
            return True, "Task was not scheduled (nothing to delete)."
        return False, f"Failed to unschedule task: {error_msg.strip()}"

def is_task_scheduled():
    """Checks if the task is currently scheduled in Windows."""
    if platform.system() != "Windows":
        return False
        
    task_name = "JobCraftAutomation"
    cmd = ["schtasks", "/query", "/tn", task_name, "/fo", "LIST"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return "TaskName:" in result.stdout.replace(" ", "") or task_name in result.stdout
    except subprocess.CalledProcessError:
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
        if action == "schedule":
            success, msg = schedule_task()
            print(msg)
        elif action == "unschedule":
            success, msg = unschedule_task()
            print(msg)
        elif action == "status":
            scheduled = is_task_scheduled()
            print(f"Task Scheduled: {scheduled}")
    else:
        # Default status check
        print(f"Checking schedule status...")
        print(f"Is Scheduled: {is_task_scheduled()}")

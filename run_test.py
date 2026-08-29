import traceback
import runpy

try:
    runpy.run_path("analytics_dashboard/src/app.py", run_name="__main__")
except Exception as e:
    with open("err_log.txt", "w") as f:
        traceback.print_exc(file=f)

import subprocess
from CORE import Debug, CORE

python_alias = "python3"
can_run_gemini = False
can_run_telebot = False
code_name = ""
version = ""

code_name = input("code_name > ")

def get_settings():
    global console_log, can_run_gemini, can_run_telebot, version
    can_run_gemini=CORE.get_setting("can_run_gemini")=="True"
    can_run_telebot=CORE.get_setting("can_run_telebot")=="True"
    version=CORE.get_setting(f"{code_name}_version")

Debug.log_warning("Running diagnostics...")
CORE.make_diagnostics()
get_settings()
Debug.log("Done")

if can_run_telebot:
    while True:
        try:
            print("\nLOADING")
            print(f"Version: {version}")
            print("Starting bot...")

            subprocess.run([python_alias, f"./{code_name.lower()}.py"], check=True)

        except subprocess.CalledProcessError as e:
            Debug.log_error( f"\nLAUNCHER ERROR: {e}. ")
            with open(f"{code_name}_crash.txt" , "w") as f:
                f.write(str(e))
else:
    Debug.log_error("Unable to run :(")

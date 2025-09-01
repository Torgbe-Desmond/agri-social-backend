import subprocess
import shlex
import json
from datetime import datetime
from pathlib import Path

LOG_FILE = "dependencies.json"

def load_dependencies():
    if Path(LOG_FILE).exists():
        if Path(LOG_FILE).stat().st_size == 0: 
            data = {}
        else:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    # file exists but invalid JSON
                    data = {}
    else:
        data = {}

    # Ensure required structure (patch missing keys)
    data.setdefault("name", "my-python-project")
    data.setdefault("version", "0.1.0")
    data.setdefault("private", True)
    data.setdefault("private_dependencies", {})
    data.setdefault("dependencies", {})
    data.setdefault("history", [])

    return data


def save_dependencies(data):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def main():
    deps_data = load_dependencies()

    process = subprocess.Popen(
        "cmd.exe",
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=True
    )

    while True:
        try:
            command = input(">>> ")
            if command.strip().lower() in ("exit", "quit"):
                print("Exiting...")
                break

            # Run command in real shell (currently disabled)
            process.stdin.write(command + "\n")
            process.stdin.flush()

            # Print output back to user
            while True:
                line = process.stdout.readline()
                if not line.strip():
                    break
                print(line, end="")

            # Handle pip installs (local)
            if command.strip().startswith("pip install -l"):
                parts = shlex.split(command)
                private_dependencies = parts[3:]  # everything after "pip install -l"

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for dep in private_dependencies:
                    if "==" in dep:  # explicit version
                        name, version = dep.split("==", 1)
                        deps_data["private_dependencies"][name] = version
                    else:
                        deps_data["private_dependencies"][dep] = "latest"

                deps_data["history"].append({
                    "date": timestamp,
                    "installed": private_dependencies,
                    "type": "local"
                })

                save_dependencies(deps_data)

            # Handle pip installs (global)
            elif command.strip().startswith("pip install"):
                parts = shlex.split(command)
                dependencies = parts[2:]  # everything after "pip install"

                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                for dep in dependencies:
                    if "==" in dep:  # explicit version
                        name, version = dep.split("==", 1)
                        deps_data["dependencies"][name] = version
                    else:
                        deps_data["dependencies"][dep] = "latest"

                deps_data["history"].append({
                    "date": timestamp,
                    "installed": dependencies,
                    "type": "global"
                })

                save_dependencies(deps_data)

        except KeyboardInterrupt:
            print("\nInterrupted. Exiting...")
            break

if __name__ == "__main__":
    main()

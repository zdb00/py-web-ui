from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import subprocess
import psutil
import os
import signal
import threading
import queue
import json
from datetime import datetime
import pkg_resources
import sys

app = Flask(__name__)
socketio = SocketIO(app)

SCRIPTS_DIR = "/scripts"
LOGS_DIR = "/logs"
VENV_DIR = "/venv"
PORT = int(os.getenv('PORT', 7447))

class ScriptProcess:
    def __init__(self, name, script_path, folder_path=None):
        self.name = name
        self.script_path = script_path
        self.folder_path = folder_path
        self.process = None
        self.output_queue = queue.Queue()
        self.is_running = False

    def start(self):
        if not self.is_running:
            env = os.environ.copy()
            env['PYTHONPATH'] = self.folder_path if self.folder_path else SCRIPTS_DIR
            env['PATH'] = f"{VENV_DIR}/bin:{env['PATH']}"
            env['VIRTUAL_ENV'] = VENV_DIR

            self.process = subprocess.Popen(
                [f"{VENV_DIR}/bin/python", self.script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
                cwd=self.folder_path if self.folder_path else SCRIPTS_DIR
            )
            self.is_running = True
            
            threading.Thread(target=self._read_output, daemon=True).start()
            
            with open(os.path.join(LOGS_DIR, f"{self.name}.log"), "a") as f:
                f.write(f"\n[{datetime.now()}] Script started\n")

    def _read_output(self):
        while self.is_running:
            line = self.process.stdout.readline()
            if line:
                self.output_queue.put(line)
                socketio.emit('script_output', {
                    'script': self.name,
                    'output': line
                })
                with open(os.path.join(LOGS_DIR, f"{self.name}.log"), "a") as f:
                    f.write(line)
            
            if self.process.poll() is not None:
                self.is_running = False
                break

    def stop(self):
        if self.is_running:
            self.process.terminate()
            self.is_running = False
            with open(os.path.join(LOGS_DIR, f"{self.name}.log"), "a") as f:
                f.write(f"\n[{datetime.now()}] Script stopped\n")

running_scripts = {}

def discover_scripts():
    scripts = []
    for root, dirs, files in os.walk(SCRIPTS_DIR):
        for file in files:
            if file.endswith('.py'):
                rel_path = os.path.relpath(root, SCRIPTS_DIR)
                script_path = os.path.join(root, file)
                folder_path = root if rel_path != '.' else None
                
                # Check for requirements.txt in the script's folder
                req_path = os.path.join(root, 'requirements.txt')
                has_requirements = os.path.exists(req_path)
                
                scripts.append({
                    'name': f"{os.path.basename(root)}/{file}" if rel_path != '.' else file,
                    'path': script_path,
                    'folder': folder_path,
                    'has_requirements': has_requirements,
                    'running': False
                })
    return scripts

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scripts', methods=['GET'])
def list_scripts():
    scripts = discover_scripts()
    for script in scripts:
        script_name = script['name']
        if script_name in running_scripts:
            script['running'] = running_scripts[script_name].is_running
    return jsonify(scripts)

@app.route('/api/start', methods=['POST'])
def start_script():
    script_data = request.json
    script_name = script_data['script']
    script_path = script_data['path']
    folder_path = script_data.get('folder')
    
    if script_name not in running_scripts:
        running_scripts[script_name] = ScriptProcess(script_name, script_path, folder_path)
    
    running_scripts[script_name].start()
    return jsonify({'status': 'started'})

@app.route('/api/stop', methods=['POST'])
def stop_script():
    script_name = request.json['script']
    if script_name in running_scripts:
        running_scripts[script_name].stop()
    return jsonify({'status': 'stopped'})

@app.route('/api/packages', methods=['GET'])
def list_packages():
    installed_packages = [{'name': pkg.key, 'version': pkg.version}
                         for pkg in pkg_resources.working_set]
    return jsonify(installed_packages)

@app.route('/api/packages/install', methods=['POST'])
def install_package():
    package_name = request.json['package']
    try:
        result = subprocess.run(
            [f"{VENV_DIR}/bin/pip", "install", package_name],
            capture_output=True,
            text=True
        )
        success = result.returncode == 0
        return jsonify({
            'success': success,
            'output': result.stdout if success else result.stderr
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'output': str(e)
        })

@app.route('/api/packages/uninstall', methods=['POST'])
def uninstall_package():
    package_name = request.json['package']
    try:
        result = subprocess.run(
            [f"{VENV_DIR}/bin/pip", "uninstall", "-y", package_name],
            capture_output=True,
            text=True
        )
        success = result.returncode == 0
        return jsonify({
            'success': success,
            'output': result.stdout if success else result.stderr
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'output': str(e)
        })

@app.route('/api/install-requirements', methods=['POST'])
def install_requirements():
    script_data = request.json
    folder_path = script_data.get('folder', SCRIPTS_DIR)
    req_path = os.path.join(folder_path, 'requirements.txt')
    
    if os.path.exists(req_path):
        try:
            result = subprocess.run(
                [f"{VENV_DIR}/bin/pip", "install", "-r", req_path],
                capture_output=True,
                text=True
            )
            success = result.returncode == 0
            return jsonify({
                'success': success,
                'output': result.stdout if success else result.stderr
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'output': str(e)
            })
    return jsonify({
        'success': False,
        'output': 'requirements.txt not found'
    })

@app.route('/api/logs/<path:script_name>')
def get_logs(script_name):
    log_path = os.path.join(LOGS_DIR, f"{script_name}.log")
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            return jsonify({'logs': f.read()})
    return jsonify({'logs': ''})

if __name__ == '__main__':
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(VENV_DIR, exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=PORT)

"""
Script Name: WebUI Integration
Description: A PySide6-based application to integrate with Open WebUI, manage server processes, and display web content.
Date: 2024-12-12
Author: Azad Djan

Requirements:
- PySide6==6.8.1
- open-webui==0.4.7
"""

import os
import sys
import socket
import random
import logging
import platform
import requests
from pathlib import Path
from PySide6.QtCore import QUrl, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings, QWebEnginePage

# Configure logger
logger = logging.getLogger("WebUI")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(name)s][%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("webui.log")
    ]
)

# Utility function: Check if a port is in use
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

# Utility function: Kill all processes using a specific port
def kill_process_on_port(port):
    """
    Kill all processes using the specified port.
    """
    if platform.system() == "Windows":
        try:
            result = os.popen(f"netstat -ano | findstr :{port}").read().strip()
            lines = result.split("\n")
            for line in lines:
                parts = line.split()
                pid = parts[-1]
                logger.info(f"Killing process with PID {pid} on port {port}")
                os.system(f"taskkill /F /PID {pid}")
        except Exception as e:
            logger.error(f"Error killing process on port {port}: {e}")
    else:
        try:
            result = os.popen(f"lsof -t -i:{port}").read().strip()
            pids = result.split("\n")
            for pid in pids:
                logger.info(f"Killing process with PID {pid} on port {port}")
                os.kill(int(pid), 9)
        except Exception as e:
            logger.error(f"Error killing process on port {port}: {e}")

# Utility function: Find an available port
def find_available_port(start_port=1024, end_port=65535):
    while True:
        port = random.randint(start_port, end_port)
        if not is_port_in_use(port):
            return port

# Utility function: Get an available port (with preferred option)
def get_available_port(preferred_port=8080, start_port=1024, end_port=65535):
    if is_port_in_use(preferred_port):
        logger.warning(f"Port {preferred_port} is in use. Attempting to free it.")
        kill_process_on_port(preferred_port)

    if is_port_in_use(preferred_port):
        logger.warning(f"Port {preferred_port} is still in use. Selecting a random port.")
        return find_available_port(start_port, end_port)

    return preferred_port

# Initialize port
SERVER_PORT = get_available_port(8080)
SERVER_HOST = "localhost"
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
WEBUI_ENV = {
    'WEBUI_AUTH': 'False',
    'HOST': SERVER_HOST,
    'PORT': str(SERVER_PORT)
}

# Utility function: Check if the server is returning HTTP 200
def is_server_available(host, port):
    """
    Checks if the server is up and returning HTTP 200.
    :param host: Hostname or IP of the server
    :param port: Port the server is running on
    :return: True if the server responds with HTTP 200, False otherwise
    """
    url = f"http://{host}:{port}"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            return True
    except requests.RequestException:
        pass
    return False

# WebPage class to handle console messages from the web view
class WebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, line, source):
        logger.debug(f"JS Console [{level}] {message} (line {line}, source: {source})")

# Main window to host the webui and manage subprocesses
class WebUIWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Open WebUI")

        self.resize(1200, 800)

        # Setup web engine view
        self.profile = QWebEngineProfile("WebUI", self)
        self.web_view = QWebEngineView(self)
        self.web_page = WebPage(self.profile, self.web_view)
        self.web_view.setPage(self.web_page)
        self.web_view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)

        # Layout setup
        central_widget = QWidget(self)
        layout = QVBoxLayout(central_widget)
        layout.addWidget(self.web_view)
        self.setCentralWidget(central_widget)

        # Start with an empty page
        self.web_view.setHtml("")

        # Server process ID
        self.server_pid = None

        # Start server and begin checking its status
        self.start_server()
        self.check_server_loop()

    def start_server(self):
        """
        Start the webui server using os.spawnlp with port as a command-line argument.
        """
        try:
            logger.info(f"Starting server process on port {SERVER_PORT}...")
            env = os.environ.copy()
            env.update(WEBUI_ENV)

            self.server_pid = os.spawnlp(
                os.P_NOWAIT, "open-webui", "open-webui", "serve", "--port", str(SERVER_PORT)
            )
            logger.info(f"Server started with PID {self.server_pid}.")
        except FileNotFoundError:
            self.web_view.setHtml("<h1>Error: open-webui not found. Ensure it is installed.</h1>")
            logger.error("open-webui command not found.")
        except Exception as e:
            self.web_view.setHtml(f"<h1>Error: Failed to start server: {e}</h1>")
            logger.exception("Failed to start server.")

    def check_server_loop(self):
        """
        Periodically check if the server is available, and update the web view when it is.
        """
        # Add an animated spinner to the waiting page
        self.web_view.setHtml("""
            <html>
            <head>
                <style>
                    body {
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                        font-family: Arial, sans-serif;
                        background-color: #f8f9fa;
                    }
                    .spinner {
                        width: 50px;
                        height: 50px;
                        border: 5px solid #f3f3f3;
                        border-top: 5px solid #007bff;
                        border-radius: 50%;
                        animation: spin 1s linear infinite;
                    }
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                    h1 {
                        margin-top: 20px;
                        font-size: 18px;
                        color: #555;
                    }
                </style>
            </head>
            <body>
                <div class="spinner"></div>
                <h1>Waiting for the server to start...</h1>
            </body>
            </html>
        """)

        def server_check():
            if is_server_available(SERVER_HOST, SERVER_PORT):
                logger.info(f"Server is available at {SERVER_URL}. Loading into web view.")
                self.web_view.setUrl(QUrl(SERVER_URL))
                self.timer.stop()  # Stop the timer once the server is available
            else:
                logger.debug("Server not available yet. Retrying...")

        # Use a QTimer for periodic checks
        self.timer = QTimer(self)
        self.timer.timeout.connect(server_check)
        self.timer.start(1000)  # Check every 1 second

    def stop_server(self):
        """
        Stop the webui server using the stored PID.
        """
        if self.server_pid:
            logger.info(f"Stopping server process with PID {self.server_pid}...")
            try:
                os.kill(self.server_pid, 9)
                logger.info(f"Server process {self.server_pid} terminated.")
            except ProcessLookupError:
                logger.warning(f"Process with PID {self.server_pid} already terminated.")
            except Exception as e:
                logger.exception(f"Error stopping server process: {e}")
            finally:
                self.server_pid = None

    def closeEvent(self, event):
        logger.info("Closing application...")
        self.stop_server()

        # Cleanup web components
        self.web_view.setPage(None)
        if hasattr(self, 'web_page'):
            self.web_page.deleteLater()
        if hasattr(self, 'profile'):
            self.profile.deleteLater()

        # Accept the close event to exit the application
        event.accept()

# Main entry point
def main():
    app = QApplication(sys.argv)
    icon_path = Path(__file__).parent / "favicon.png"  # Use absolute path
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        logger.error(f"Icon file {icon_path} not found. Using default icon.")
    window = WebUIWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
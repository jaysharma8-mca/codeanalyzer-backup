import os
import datetime
import paramiko
from scp import SCPClient
import subprocess
import smtplib
from email.mime.text import MIMEText
import logging
import shutil
import base64
import requests

# ===== UTILITY FUNCTIONS =====

def generate_timestamped_folder_name():
    return f"codeanalyzer_{datetime.datetime.now().strftime('%Y-%m-%d_%I-%M%p')}"

def create_destination_folder(base_path, folder_name):
    full_path = os.path.join(base_path, folder_name)
    os.makedirs(full_path, exist_ok=True)
    return full_path

def scp_transfer(host, port, username, password, linux_path, windows_dest):
    for attempt in range(3):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=host, port=port, username=username, password=password)
            with SCPClient(ssh.get_transport()) as scp:
                scp.get(linux_path, local_path=windows_dest, recursive=True)
            ssh.close()
            return True
        except Exception as e:
            logging.warning(f"scp_transfer failed on attempt {attempt + 1}: {e}")
    logging.error("scp_transfer failed after 3 attempts.")
    return False

def get_linux_folder_size(host, port, username, password):
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(hostname=host, port=port, username=username, password=password)
        stdin, stdout, stderr = ssh.exec_command(f'du -sh /home/{username}/codeanalyzer')
        size = stdout.read().decode().split()[0]
        ssh.close()
        return size
    except Exception as e:
        logging.error(f"Failed to retrieve Linux folder size: {e}")
        return "N/A"

def get_windows_folder_size(path):
    total = 0
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total += os.path.getsize(fp)
    return total  # bytes

def format_windows_size(size_in_bytes, linux_size_unit):
    if linux_size_unit.endswith('K'):
        return f"{round(size_in_bytes / 1024, 2)} KB"
    elif linux_size_unit.endswith('M'):
        return f"{round(size_in_bytes / (1024 * 1024), 2)} MB"
    else:
        return f"{round(size_in_bytes / 1024, 2)} KB"

def send_email(sender, receivers, password, subject, body, smtp_server, smtp_port):
    msg = MIMEText(body, "html")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(receivers)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())

def upload_zip_to_github(zip_path):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
    GITHUB_REPO = os.getenv("GITHUB_REPO")
    GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")
    COMMITTER_NAME = os.getenv("GITHUB_COMMIT_NAME", "Backup Bot")
    COMMITTER_EMAIL = os.getenv("GITHUB_COMMIT_EMAIL", "bot@example.com")

    if not all([GITHUB_TOKEN, GITHUB_REPO]):
        logging.error("GitHub credentials not set in environment.")
        return False

    filename = os.path.basename(zip_path)
    api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    with open(zip_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    commit_message = f"Backup on {datetime.datetime.now().strftime('%Y-%m-%d %I-%M%p')}"
    get_response = requests.get(api_url, headers=headers)
    sha = get_response.json().get("sha") if get_response.status_code == 200 else None

    payload = {
        "message": commit_message,
        "branch": GITHUB_BRANCH,
        "committer": {
            "name": COMMITTER_NAME,
            "email": COMMITTER_EMAIL
        },
        "content": content
    }

    if sha:
        payload["sha"] = sha

    response = requests.put(api_url, json=payload, headers=headers)

    if response.status_code in [200, 201]:
        logging.info("✅ Backup ZIP uploaded to GitHub successfully.")
        return True
    else:
        logging.error(f"❌ GitHub upload failed: {response.json()}")
        return False

# ===== CONFIGURATION =====
HOST = 'localhost'
PORT = 2222
USERNAME = 'jay'
PASSWORD = '5570'
LINUX_FOLDER = f'/home/{USERNAME}/codeanalyzer/src'
# WINDOWS_BACKUP_BASE = r'D:\Ansu\codeanalyzer-backups'
WINDOWS_BACKUP_BASE = os.path.join(os.path.dirname(__file__), "codeanalyzer-backups")
SENDER_EMAIL = "jaysharma155.cmpica@gmail.com"
RECEIVER_EMAILS = [
    "jaysharma155.cmpicamca15@gmail.com",
    "niveditasinghec1011@gmail.com",
]
EMAIL_PASSWORD = "zrok phoy fycd uwnm"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# ===== LOGGING SETUP =====
logging.basicConfig(
    filename='backup.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ===== MAIN FUNCTION =====
def main(send_email_flag=True):
    result = {"success": False, "message": ""}
    logging.info(">>> Starting backup process...")
    try:
        folder_name = generate_timestamped_folder_name()
        destination_path = create_destination_folder(WINDOWS_BACKUP_BASE, folder_name)
        logging.info(f"Created backup folder: {destination_path}")

        logging.info("Starting SCP transfer...")
        if not scp_transfer(HOST, PORT, USERNAME, PASSWORD, LINUX_FOLDER, destination_path):
            result["message"] = "SCP transfer failed after 3 retries."
            return result

        zip_file = shutil.make_archive(destination_path, 'zip', destination_path)
        logging.info(f"Created zip archive: {zip_file}")

        if not upload_zip_to_github(zip_file):
            result["message"] = "GitHub upload failed via API."
            return result

        linux_size = get_linux_folder_size(HOST, PORT, USERNAME, PASSWORD)
        win_bytes = get_windows_folder_size(os.path.join(destination_path, 'src'))
        win_size = format_windows_size(win_bytes, linux_size)
        logging.info(f"Linux folder size  : {linux_size}")
        logging.info(f"Windows folder size: {win_size}")

        if send_email_flag:
            try:
                email_subject = "CodeAnalyzer Backup Successful"
                email_body = f"""
                <h2>✅ <span style='color:#0066cc;'>CodeAnalyzer Backup Summary</span></h2>
                <p>Backup completed successfully on <b>{folder_name[13:]}</b>.</p>
                <table border="1" cellpadding="5" cellspacing="0">
                  <tr><th>Source</th><th>Size</th></tr>
                  <tr><td>Linux Folder</td><td>{linux_size}</td></tr>
                  <tr><td>Windows Folder</td><td>{win_size}</td></tr>
                </table>
                <p><b>Backup Location:</b><br>{destination_path}</p>
                <p style='color:green;'>✅ Backup ZIP has been pushed to GitHub.</p>
                <br><p>Regards,<br><i>Your Backup Script 🤖</i></p>
                """
                send_email(SENDER_EMAIL, RECEIVER_EMAILS, EMAIL_PASSWORD, email_subject, email_body, SMTP_SERVER, SMTP_PORT)
                logging.info("Email sent successfully.")
            except Exception as e:
                logging.error(f"Failed to send email: {e}")

        result["success"] = True
        result["message"] = "Backup completed successfully."
        return result

    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        result["message"] = f"Unhandled exception: {e}"
        return result

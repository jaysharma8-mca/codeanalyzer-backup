import os
import datetime
import shutil
import paramiko
from scp import SCPClient
import subprocess
import smtplib
from email.mime.text import MIMEText
import logging

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

def git_commit_push(repo_path, folder_name, commit_label):
    os.chdir(repo_path)
    subprocess.run(["git", "add", folder_name], check=True)
    subprocess.run(["git", "commit", "-m", f"Backup on {commit_label}"], check=True)
    subprocess.run(["git", "push"], check=True)

def send_email(sender, receivers, password, subject, body, smtp_server, smtp_port):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(receivers)
    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender, password)
        server.sendmail(sender, receivers, msg.as_string())

# ===== CONFIGURATION =====
HOST = 'localhost'
PORT = 2222
USERNAME = 'jay'
PASSWORD = '5570'
LINUX_FOLDER = f'/home/{USERNAME}/codeanalyzer/src'
WINDOWS_BACKUP_BASE = r'D:\Ansu\codeanalyzer-backups'
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

        try:
            logging.info("Starting GitHub push of ZIP file...")
            git_commit_push(WINDOWS_BACKUP_BASE, os.path.basename(zip_file), folder_name[13:])
            logging.info("Git commit and push completed successfully.")
        except Exception as e:
            logging.error(f"Git push failed: {e}")
            result["message"] = f"Git push failed: {e}"
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
Hi Jay,

✅ Backup completed successfully on {folder_name[13:]}.

Linux folder size  : {linux_size}
Windows folder size: {win_size}

Backup location:
{destination_path}

✅ Folder has also been pushed to GitHub.

Regards,
Your Backup Script 🤖
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

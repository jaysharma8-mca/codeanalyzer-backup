import unittest
from unittest.mock import patch, MagicMock, call
import os
import shutil
import datetime
import logging

# Setup logging for tests
logging.basicConfig(level=logging.INFO)

# Assuming your main script is named codeanalyzer_backup.py
import codeanalyzer_backup as bkup

class TestCodeAnalyzerBackup(unittest.TestCase):

    def setUp(self):
        self.test_dir = "test_folder"
        os.makedirs(self.test_dir, exist_ok=True)
        with open(os.path.join(self.test_dir, "dummy.txt"), "w") as f:
            f.write("x" * 1024)  # 1KB

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_generate_timestamped_folder_name(self):
        name = bkup.generate_timestamped_folder_name()
        self.assertTrue(name.startswith("codeanalyzer_"))

    def test_create_destination_folder(self):
        folder = bkup.create_destination_folder(".", "temp_backup")
        self.assertTrue(os.path.exists(folder))
        shutil.rmtree(folder)

    def test_get_windows_folder_size(self):
        size = bkup.get_windows_folder_size(self.test_dir)
        self.assertEqual(size, 1024)

    def test_format_windows_size_kb(self):
        result = bkup.format_windows_size(2048, '16K')
        self.assertEqual(result, "2.0 KB")

    def test_format_windows_size_mb(self):
        result = bkup.format_windows_size(1048576, '1.0M')
        self.assertEqual(result, "1.0 MB")

    def test_format_windows_size_default(self):
        result = bkup.format_windows_size(3072, 'bytes')
        self.assertEqual(result, "3.0 KB")

    @patch("codeanalyzer_backup.subprocess.run")
    def test_git_commit_push(self, mock_run):
        mock_run.return_value = MagicMock()
        bkup.git_commit_push(".", "folder_name", "label")
        mock_run.assert_has_calls([
            call(["git", "add", "folder_name"], check=True),
            call(["git", "commit", "-m", "Backup on label"], check=True),
            call(["git", "push"], check=True)
        ])

    @patch("codeanalyzer_backup.smtplib.SMTP")
    def test_send_email(self, mock_smtp):
        instance = mock_smtp.return_value.__enter__.return_value
        bkup.send_email("from@example.com", ["to@example.com"], "pass",
                         "Subject", "Body", "smtp.example.com", 587)
        instance.sendmail.assert_called_once()

    @patch("codeanalyzer_backup.paramiko.SSHClient")
    def test_get_linux_folder_size(self, mock_ssh):
        mock_instance = mock_ssh.return_value
        mock_stdout = MagicMock()
        mock_stdout.read.return_value = b"12K\t/home/jay/codeanalyzer\n"
        mock_instance.exec_command.return_value = (None, mock_stdout, None)
        result = bkup.get_linux_folder_size("host", 22, "user", "pass")
        self.assertEqual(result, "12K")

    @patch("codeanalyzer_backup.paramiko.SSHClient")
    @patch("codeanalyzer_backup.SCPClient")
    def test_scp_transfer(self, mock_scp, mock_ssh):
        ssh_instance = mock_ssh.return_value
        scp_instance = mock_scp.return_value.__enter__.return_value
        bkup.scp_transfer("host", 22, "user", "pass", "/linux/path", "/win/path")
        scp_instance.get.assert_called_once_with("/linux/path", local_path="/win/path", recursive=True)

if __name__ == '__main__':
    unittest.main()

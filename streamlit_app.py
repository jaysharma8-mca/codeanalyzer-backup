import streamlit as st
import os
import glob
from datetime import datetime
import zipfile
import sys
import pandas as pd
import requests

# ===== Load GitHub secrets for cloud deployment =====
if "GITHUB_TOKEN" in st.secrets:
    os.environ["GITHUB_TOKEN"] = st.secrets["GITHUB_TOKEN"]
    os.environ["GITHUB_REPO"] = st.secrets["GITHUB_REPO"]
    os.environ["GITHUB_BRANCH"] = st.secrets.get("GITHUB_BRANCH", "main")
    os.environ["GITHUB_COMMIT_EMAIL"] = st.secrets["GITHUB_COMMIT_EMAIL"]
    os.environ["GITHUB_COMMIT_NAME"] = st.secrets["GITHUB_COMMIT_NAME"]

sys.path.append(os.path.dirname(__file__))
from codeanalyzer_backup import main, WINDOWS_BACKUP_BASE

# Set Streamlit page config
st.set_page_config(page_title="CodeAnalyzer Backup Dashboard", layout="wide")

# Sidebar Navigation with Logo
st.sidebar.markdown("""
    <div style='display: flex; justify-content: center; margin-bottom: 10px;'>
        <img src='https://upload.wikimedia.org/wikipedia/commons/thumb/6/6b/Meetup_Logo.png/512px-Meetup_Logo.png' width='120'/>
    </div>
""", unsafe_allow_html=True)
page = st.sidebar.radio(" ", ["📊 Overview", "📁 Latest Backup Info", "📂 Contents of Latest Backup"])

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), 'backup.log')

def get_latest_backup_zip():
    zips = sorted(glob.glob(os.path.join(WINDOWS_BACKUP_BASE, "*.zip")), key=os.path.getmtime, reverse=True)
    return zips[0] if zips else None

def show_log_tail(log_path, num_lines=20):
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            lines = f.readlines()[-num_lines:]
            return "".join(lines)
    return "Log file not found."

def list_recent_backups(n=5):
    backups = sorted(glob.glob(os.path.join(WINDOWS_BACKUP_BASE, "*.zip")), key=os.path.getmtime, reverse=True)
    return backups[:n]

def get_zip_folder_contents(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            return [f for f in zip_ref.namelist() if not f.endswith('/')]
    except Exception as e:
        return [f"Error reading zip: {e}"]

def get_backup_size_trend_from_github():
    token = os.getenv("GITHUB_TOKEN")
    repo = os.getenv("GITHUB_REPO")
    branch = os.getenv("GITHUB_BRANCH", "main")
    api_url = f"https://api.github.com/repos/{repo}/contents?ref={branch}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    res = requests.get(api_url, headers=headers)
    if res.status_code != 200:
        return pd.DataFrame()

    backups = [f for f in res.json() if f["name"].startswith("codeanalyzer_") and f["name"].endswith(".zip")]
    date_size_map = {}
    for file in backups:
        try:
            name = file["name"].replace("codeanalyzer_", "").replace(".zip", "")
            dt = datetime.strptime(name, "%Y-%m-%d_%I-%M%p").date()
            size_kb = round(file["size"] / 1024, 2)
            date_size_map[dt] = date_size_map.get(dt, 0) + size_kb
        except:
            continue

    return pd.DataFrame({
        "Date": list(date_size_map.keys()),
        "Total Size (KB)": list(date_size_map.values())
    })

# ======================== Pages ========================
if page == "📊 Overview":
    st.markdown("<h1 style='text-align: center;'>🛡️ CodeAnalyzer Backup Utility</h1>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("⚙️ Run Backup")
    send_email_flag = st.checkbox("Send Email Notification", value=True)
    if st.button("Run Backup Now"):
        st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
        with st.spinner("Running backup... this may take a few seconds..."):
            result = main(send_email_flag=send_email_flag)
            if isinstance(result, dict):
                if result.get("success"):
                    st.success(f"✅ {result.get('message')}")
                else:
                    st.error(f"❌ {result.get('message')}")
            else:
                st.error("❌ Unexpected result from backup script.")

    st.markdown("<br><br>", unsafe_allow_html=True)
    st.subheader("📊 Daily Backup Size Chart")
    trend_df = get_backup_size_trend_from_github()
    if not trend_df.empty:
        try:
            import plotly.express as px
            fig = px.bar(
                trend_df,
                x="Date",
                y="Total Size (KB)",
                title="Daily Backup Size Chart",
                labels={"Date": "Date", "Total Size (KB)": "Backup Size (KB)"},
                text_auto='.2f'
            )
            fig.update_layout(xaxis_title="Date", yaxis_title="Backup Size (KB)", height=400)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.warning(f"Chart rendering failed: {e}")
    else:
        st.info("No backup data found in GitHub.")

elif page == "📁 Latest Backup Info":
    st.markdown("## 📁 Latest Backup Info")
    latest_zip = get_latest_backup_zip()
    if latest_zip:
        zip_name = os.path.basename(latest_zip)
        timestamp = zip_name.replace("codeanalyzer_", "").replace(".zip", "")
        st.markdown(f"**Backup Name:** `{zip_name}`")
        st.markdown(f"**Backup Time:** `{timestamp}`")
        with open(latest_zip, "rb") as f:
            st.download_button("📥 Download ZIP", f, file_name=zip_name)
    else:
        st.warning("No backup zip files found.")

    with st.expander("📜 Backup Log (Last 20 lines)"):
        log_output = show_log_tail(LOG_FILE_PATH)
        st.code(log_output, language="text")

    with st.expander("🧾 Recent Backup Files"):
        recent = list_recent_backups()
        for f in recent:
            size = round(os.path.getsize(f) / 1024, 2)
            ts = os.path.basename(f).replace("codeanalyzer_", "").replace(".zip", "")
            st.markdown(f"- `{os.path.basename(f)}` — **{size} KB** @ `{ts}`")

elif page == "📂 Contents of Latest Backup":
    st.markdown("## 📂 Contents of Latest Backup")
    latest_zip = get_latest_backup_zip()
    if latest_zip:
        contents = get_zip_folder_contents(latest_zip)
        st.code("\n".join(contents), language="text")
    else:
        st.warning("No backup zip files found.")

import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import plotly.express as px
import time
import json

# --- הגדרת עמוד ---
st.set_page_config(page_title="Race Telemetry", layout="wide")
st.title("🏎️ Live Race Telemetry")

# --- חיבור לענן בצורה מאובטחת ---
# הפונקציה הזו דואגת שלא נתחבר פעמיים
if not firebase_admin._apps:
    # בדיקה: האם אנחנו רצים בענן של סטרימליט?
    if 'firebase_key' in st.secrets:
        # המרת המידע מה-Secrets (סוג של מילון מיוחד) למילון רגיל של פייתון
        key_dict = dict(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
    else:
        # אחרת, אנחנו במחשב בבית - נשתמש בקובץ הרגיל
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://racetelemetry-ea720-default-rtdb.firebaseio.com/'  # <--- תדביק פה שוב את הכתובת שלך!!!
    })


# --- מכאן הכל אותו דבר... ---
def get_data():
    races_ref = db.reference('races')
    return races_ref.get()


data = get_data()

if data:
    race_ids = list(data.keys())
    selected_race = st.selectbox("Select Race", race_ids, index=len(race_ids) - 1)

    race_data = data[selected_race]
    status = race_data.get('status', 'UNKNOWN')
    st.write(f"Status: **{status}**")

    if 'telemetry' in race_data:
        telemetry_dict = race_data['telemetry']
        df = pd.DataFrame.from_dict(telemetry_dict, orient='index')

        last_row = df.iloc[-1]

        col1, col2, col3 = st.columns(3)
        col1.metric("Speed (km/h)", last_row['speed_kph'])
        col2.metric("Throttle (%)", last_row['throttle'])
        col3.metric("G-Force", last_row['g_force_x'])

        st.subheader("Speed Analysis")
        fig = px.line(df, x='timestamp', y='speed_kph', title='Speed over Time')
        st.plotly_chart(fig, use_container_width=True)

        if st.button('Refresh Data 🔄'):
            st.rerun()

        if status == "LIVE":
            time.sleep(2)
            st.rerun()
    else:
        st.write("No telemetry data yet...")
else:
    st.write("Wait for data...")
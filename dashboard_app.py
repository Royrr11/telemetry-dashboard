import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import plotly.express as px
import time

st.set_page_config(page_title="Race Telemetry Pro", layout="wide")

# --- חיבור לענן ---
if not firebase_admin._apps:
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred, {
        # עדכן את הכתובת שלך כאן!
        'databaseURL': 'https://racetelemetry-ea720-default-rtdb.firebaseio.com/'
    })


# --- פונקציות חישוב ---
def get_all_races():
    ref = db.reference('races')
    data = ref.get()
    if not data: return []

    races_list = []
    for r_id, r_data in data.items():
        r_data['id'] = r_id
        r_data['type'] = r_data.get('type', 'UNKNOWN')
        races_list.append(r_data)
    return races_list


def calculate_stats(df):
    """חישוב סטטיסטיקות למירוץ בודד"""
    max_speed = df['speed_kph'].max()
    avg_speed = df['speed_kph'].mean()
    duration = df['timestamp'].max() - df['timestamp'].min()
    return max_speed, avg_speed, duration


def get_category_averages(races_list, race_type):
    """חישוב ממוצעים של כל המירוצים מאותו סוג"""
    relevant_races = [r for r in races_list if r['type'] == race_type and 'telemetry' in r]
    if not relevant_races:
        return 0, 0

    total_avg_speeds = []
    for r in relevant_races:
        telemetry = r['telemetry']
        df_temp = pd.DataFrame.from_dict(telemetry, orient='index')
        total_avg_speeds.append(df_temp['speed_kph'].mean())

    # ממוצע של כל הממוצעים
    global_avg = sum(total_avg_speeds) / len(total_avg_speeds)
    best_ever = max(total_avg_speeds)
    return global_avg, best_ever


# --- ממשק משתמש ---
st.title("🏎️ Racing Telemetry Analysis")

races = get_all_races()

if not races:
    st.info("No races found yet. Start the car simulation!")
    st.stop()

# --- סרגל צד: סינון ובחירה ---
st.sidebar.header("🏁 Race Archive")

# 1. סינון לפי סוג
types = list(set([r['type'] for r in races]))
selected_type = st.sidebar.selectbox("Filter by Type", ["ALL"] + types)

if selected_type != "ALL":
    filtered_races = [r for r in races if r['type'] == selected_type]
else:
    filtered_races = races

# מיון מהחדש לישן
filtered_races.sort(key=lambda x: x['id'], reverse=True)

# 2. בחירת מירוץ
race_options = {r['id']: f"{r.get('start_time', r['id'])} | {r['type']}" for r in filtered_races}
selected_id = st.sidebar.selectbox("Select Session", options=list(race_options.keys()),
                                   format_func=lambda x: race_options[x])

# --- תצוגת המירוץ הנבחר ---
if selected_id:
    # שליפת המידע
    race = next((r for r in filtered_races if r['id'] == selected_id), None)

    # כותרת עם סטטוס
    status = race.get('status', 'FINISHED')
    status_color = "green" if status == "LIVE" else "red"
    st.markdown(f"### Session: {race.get('type')} <span style='color:{status_color}'>[{status}]</span>",
                unsafe_allow_html=True)
    st.caption(f"Start Time: {race.get('start_time', 'N/A')} | ID: {race['id']}")

    if 'telemetry' in race:
        # עיבוד דאטה
        df = pd.DataFrame.from_dict(race['telemetry'], orient='index')
        df['time_str'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%H:%M:%S')
        df = df.sort_values('timestamp')  # מוודא שהגרף מסודר כרונולוגית

        # --- חלק א: סיכום סטטיסטי (מה שביקשת!) ---
        st.divider()
        st.subheader("📊 Session Summary")

        max_s, avg_s, dur = calculate_stats(df)

        # חישוב השוואה להיסטוריה (רק אם בחרנו סוג ספציפי)
        global_avg, global_best = get_category_averages(races, race.get('type'))

        delta_avg = None
        if global_avg > 0:
            delta_avg = avg_s - global_avg  # ההפרש מהממוצע ההיסטורי

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Max Speed", f"{max_s:.1f} km/h")
        col2.metric("Avg Speed", f"{avg_s:.1f} km/h", delta=f"{delta_avg:.1f} vs Avg" if delta_avg else None)
        col3.metric("Duration", f"{dur:.1f} sec")
        col4.metric("Distance (Est)", f"{int(avg_s * (dur / 3600))} km")

        # --- חלק ב: גרפים ---
        st.divider()
        st.subheader("📈 Telemetry Trace")

        # גרף מהירות
        fig = px.line(df, x='time_str', y='speed_kph', title='Velocity over Time', markers=False)
        # צביעת אזור מתחת לגרף למראה יפה יותר
        fig.update_traces(fill='tozeroy')
        st.plotly_chart(fig, use_container_width=True)

        # תצוגת דאטה גולמי (אופציונלי - בתוך "אקורדיון" כדי לא להעמיס)
        with st.expander("View Raw Data Table"):
            st.dataframe(df)

        # רענון אוטומטי אם זה לייב
        if status == "LIVE":
            time.sleep(1)
            st.rerun()

    else:
        st.warning("No telemetry data available for this session.")
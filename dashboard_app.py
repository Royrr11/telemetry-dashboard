import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import plotly.express as px
import plotly.graph_objects as go
import time

st.set_page_config(page_title="Racing Team Pro", layout="wide", page_icon="🏎️")

if not firebase_admin._apps:
    if 'firebase_key' in st.secrets:
        cred = credentials.Certificate(dict(st.secrets["firebase_key"]))
    else:
        cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {'databaseURL': 'https://racetelemetry-ea720-default-rtdb.firebaseio.com/'})


@st.cache_data(ttl=3)
def get_data_snapshot():
    data = db.reference('races').get()
    if not data: return []
    races_list = []
    for r_id, r_data in data.items():
        r_data['id'] = r_id
        r_data['type'] = r_data.get('type', 'UNKNOWN')
        if 'start_time' in r_data:
            try:
                r_data['date_display'] = pd.to_datetime(r_data['start_time']).strftime("%d/%m %H:%M")
            except:
                r_data['date_display'] = r_id
        else:
            r_data['date_display'] = r_id
        races_list.append(r_data)
    return races_list


def calculate_stats(df):
    max_s = df['speed_kph'].max()
    avg_s = df['speed_kph'].mean()
    dist = df['distance_m'].max() if 'distance_m' in df else 0  # תמיכה במרחק
    return max_s, avg_s, dist


# --- הפתרון לקפיצות! ---
# פונקציה זו מתרעננת עצמאית בלי לטעון את כל הדף מחדש
@st.fragment(run_every=1)
def live_monitor_view(race_id):
    # קריאה ישירה מהדאטה בייס למהירות מקסימלית
    race_data = db.reference(f'races/{race_id}').get()

    if not race_data or race_data.get('status') != 'LIVE':
        st.success("🏁 Session Finished!")
        time.sleep(2)
        st.rerun()  # יוצאים מהפרגמנט וחוזרים לדף הראשי
        return

    st.title(f"🔴 LIVE: {race_data['type']}")

    if 'telemetry' in race_data:
        df = pd.DataFrame.from_dict(race_data['telemetry'], orient='index')
        df['time_str'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%H:%M:%S')
        df = df.sort_values('timestamp')

        last_row = df.iloc[-1]

        # מדדים חיים
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Speed", f"{last_row['speed_kph']} km/h")
        c2.metric("Distance", f"{last_row.get('distance_m', 0):.1f} m")
        c3.metric("Throttle", f"{last_row['throttle']}%")
        c4.metric("Brake", f"{last_row['brake']}%")

        # גרף חי
        fig = px.area(df, x='time_str', y='speed_kph', title='Live Velocity', color_discrete_sequence=['#FF4B4B'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Waiting for telemetry...")


# --- לוגיקה ראשית ---
all_races = get_data_snapshot()
live_race = next((r for r in all_races if r.get('status') == 'LIVE'), None)

st.sidebar.image("https://img.icons8.com/color/96/f1-race-car-side-view.png", width=60)
st.sidebar.title("Telemetry Center")

nav_options = ["General Overview"]
if live_race: nav_options.insert(0, "🔴 LIVE MONITOR")
nav_options.extend(["SKIDPAD", "ACCELERATION", "AUTOX", "ENDURANCE", "TEST"])
selection = st.sidebar.radio("Go to:", nav_options)

# --- ניתוב דפים ---

if selection == "🔴 LIVE MONITOR" and live_race:
    # כאן הקסם קורה - אנחנו קוראים לפונקציית הפרגמנט
    live_monitor_view(live_race['id'])

elif selection == "General Overview":
    st.title("🏆 Team Overview")
    if all_races:
        c1, c2 = st.columns(2)
        c1.metric("Total Sessions", len(all_races))
        c1.metric("Active Live", "YES" if live_race else "NO")

else:
    # דפי היסטוריה רגילים (בלי פרגמנט כי הם סטטיים)
    st.title(f"🏁 Archive: {selection}")
    cat_races = [r for r in all_races if r['type'] == selection]
    cat_races.sort(key=lambda x: x['id'], reverse=True)

    race_map = {r['id']: f"{r['date_display']} ({r.get('status')})" for r in cat_races}
    sid = st.selectbox("Select Session:", list(race_map.keys()), format_func=lambda x: race_map[x])

    if sid:
        r = next(r for r in cat_races if r['id'] == sid)
        if 'telemetry' in r:
            df = pd.DataFrame.from_dict(r['telemetry'], orient='index')
            df = df.sort_values('timestamp')
            st.line_chart(df, x='timestamp', y='speed_kph')
            st.dataframe(df.tail(5))
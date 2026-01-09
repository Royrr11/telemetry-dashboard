import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import plotly.express as px
import time

# --- הגדרת עמוד ---
st.set_page_config(page_title="Race Telemetry", layout="wide")

# --- לוגיקה לחיבור לענן (נשאר זהה) ---
if not firebase_admin._apps:
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")

    firebase_admin.initialize_app(cred, {
        # שים פה את הכתובת שלך!
        'databaseURL': 'https://racetelemetry-ea720-default-rtdb.firebaseio.com/'
    })


# --- פונקציות עזר ---
def get_all_races():
    ref = db.reference('races')
    return ref.get()


# --- ממשק משתמש ---
st.title("🏎️ Racing Team Telemetry")

# 1. טעינת מידע
data = get_all_races()

if not data:
    st.warning("No race data found in Cloud.")
    st.stop()

# 2. המרה לרשימה נוחה לעבודה
# אנחנו הופכים את המילון של פיירבייס לרשימה של אובייקטים שקל לסנן
races_list = []
for r_id, r_data in data.items():
    r_data['id'] = r_id
    # אם אין סוג (מירוצים ישנים), נקרא לזה UNKNOWN
    if 'type' not in r_data:
        r_data['type'] = 'UNKNOWN'
    races_list.append(r_data)

# 3. סרגל צד - סינון
st.sidebar.header("Filter Options")
available_types = list(set([r['type'] for r in races_list]))
selected_type = st.sidebar.selectbox("Select Race Type", ["ALL"] + available_types)

# סינון הרשימה לפי מה שהמשתמש בחר
if selected_type != "ALL":
    filtered_races = [r for r in races_list if r['type'] == selected_type]
else:
    filtered_races = races_list

# בחירת מירוץ ספציפי מתוך הרשימה המסוננת (הכי חדש למעלה)
# המיון הוא לפי המזהה (שהוא התאריך)
filtered_races.sort(key=lambda x: x['id'], reverse=True)
race_options = {r['id']: f"{r['start_time']} - {r['type']} ({r['status']})" for r in filtered_races}

selected_race_id = st.sidebar.selectbox(
    "Select Session",
    options=list(race_options.keys()),
    format_func=lambda x: race_options[x]
)

# 4. הצגת הנתונים למירוץ הנבחר
if selected_race_id:
    race_data = data[selected_race_id]

    # כותרת ראשית עם פרטי המירוץ
    col_h1, col_h2, col_h3 = st.columns(3)
    col_h1.metric("Race Type", race_data.get('type', 'N/A'))
    col_h2.metric("Start Time", race_data.get('start_time', 'N/A'))
    col_h3.metric("Status", race_data.get('status', 'FINISHED'))

    st.divider()

    if 'telemetry' in race_data:
        # עיבוד נתונים לגרפים
        telemetry_dict = race_data['telemetry']
        df = pd.DataFrame.from_dict(telemetry_dict, orient='index')

        # המרת Timestamp לשעה קריאה
        df['time_str'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%H:%M:%S')

        # תצוגה חיה (השורה האחרונה)
        last_row = df.iloc[-1]

        # מדדים גדולים ("Big Numbers")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Speed", f"{last_row['speed_kph']} km/h")
        m2.metric("Throttle", f"{last_row['throttle']}%")
        m3.metric("Brake", f"{last_row['brake']}%")
        m4.metric("G-Force X", f"{last_row['g_force_x']} G")

        # גרף מהירות
        st.subheader("Velocity Trace")
        # אופציונלי: הוספת קו אדום למקסימום המותר
        max_limit = race_data.get('max_speed_limit', 120)

        fig = px.line(df, x='time_str', y='speed_kph', title=f'Speed (Limit: {max_limit} km/h)')
        fig.add_hline(y=max_limit, line_dash="dot", annotation_text="Limit", annotation_position="bottom right",
                      line_color="red")
        st.plotly_chart(fig, use_container_width=True)

        # רענון אוטומטי אם חי
        if race_data.get('status') == "LIVE":
            time.sleep(1)
            st.rerun()

    else:
        st.info("Waiting for telemetry data to start...")
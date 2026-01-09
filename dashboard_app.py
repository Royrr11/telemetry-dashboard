import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import plotly.express as px
import plotly.graph_objects as go
import time

# --- הגדרת עמוד ---
st.set_page_config(page_title="Racing Team Pro", layout="wide", page_icon="🏎️")

# --- חיבור לענן ---
if not firebase_admin._apps:
    if 'firebase_key' in st.secrets:
        key_dict = dict(st.secrets["firebase_key"])
        cred = credentials.Certificate(key_dict)
    else:
        cred = credentials.Certificate("serviceAccountKey.json")

    # !!! וודא שהכתובת כאן מעודכנת !!!
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://racetelemetry-ea720-default-rtdb.firebaseio.com/'
    })


# --- פונקציות עזר וחישובים ---
@st.cache_data(ttl=5)  # שומר בזיכרון ל-5 שניות כדי לא להעמיס
def get_data_snapshot():
    ref = db.reference('races')
    data = ref.get()
    if not data: return []

    races_list = []
    for r_id, r_data in data.items():
        r_data['id'] = r_id
        r_data['type'] = r_data.get('type', 'UNKNOWN')
        # המרת זמן לתצוגה נוחה
        if 'start_time' in r_data:
            try:
                dt_obj = pd.to_datetime(r_data['start_time'])
                r_data['date_display'] = dt_obj.strftime("%d/%m %H:%M")
            except:
                r_data['date_display'] = r_id
        else:
            r_data['date_display'] = r_id

        races_list.append(r_data)
    return races_list


def calculate_session_stats(df):
    """סטטיסטיקה למירוץ בודד"""
    max_s = df['speed_kph'].max()
    avg_s = df['speed_kph'].mean()
    duration = df['timestamp'].max() - df['timestamp'].min()
    return max_s, avg_s, duration


# --- מבנה האפליקציה ---

# 1. טעינת מידע
all_races = get_data_snapshot()

# 2. תפריט צד (ניווט ראשי)
st.sidebar.image("https://img.icons8.com/color/96/f1-race-car-side-view.png", width=60)
st.sidebar.title("Telemetry Center")

# אופציות הניווט
nav_options = ["General Overview", "SKIDPAD", "ACCELERATION", "AUTOX", "ENDURANCE", "TEST"]
selection = st.sidebar.radio("Go to:", nav_options)

st.sidebar.divider()
st.sidebar.caption(f"Total Sessions: {len(all_races)}")
if st.sidebar.button("Refresh Data 🔄"):
    st.cache_data.clear()
    st.rerun()

# --- לוגיקה לכל דף ---

# === דף ראשי: סיכום כללי ===
if selection == "General Overview":
    st.title("🏆 Team Performance Overview")

    if not all_races:
        st.warning("No data yet. Start the simulation!")
        st.stop()

    # מדדים ראשיים
    total_runs = len(all_races)

    # חישוב מהירות שיא בכל הזמנים
    global_max_speed = 0
    fastest_car_type = "-"

    for r in all_races:
        if 'telemetry' in r:
            df = pd.DataFrame.from_dict(r['telemetry'], orient='index')
            m_speed = df['speed_kph'].max()
            if m_speed > global_max_speed:
                global_max_speed = m_speed
                fastest_car_type = r['type']

    # שורה עליונה - מספרים גדולים
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Sessions", total_runs)
    col2.metric("Top Speed (Season)", f"{global_max_speed:.1f} km/h", f"in {fastest_car_type}")
    col3.metric("Active Categories", len(set([r['type'] for r in all_races])))

    st.divider()

    # גרפים מסכמים
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Sessions by Type")
        type_counts = pd.DataFrame(all_races)['type'].value_counts().reset_index()
        type_counts.columns = ['Type', 'Count']
        fig_pie = px.pie(type_counts, values='Count', names='Type', hole=0.4,
                         color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.subheader("Activity Timeline")
        # המרת זמנים לגרף
        timeline_data = []
        for r in all_races:
            timeline_data.append({'Date': r.get('start_time'), 'Type': r['type'], 'Count': 1})
        if timeline_data:
            df_time = pd.DataFrame(timeline_data)
            df_time['Date'] = pd.to_datetime(df_time['Date'])
            df_time = df_time.sort_values('Date')
            fig_hist = px.histogram(df_time, x="Date", color="Type", nbins=20)
            st.plotly_chart(fig_hist, use_container_width=True)

# === דפי קטגוריות (לכל סוג מירוץ) ===
else:
    race_type = selection
    st.title(f"🏁 {race_type} Analysis")

    # סינון המירוצים הרלוונטיים לקטגוריה
    category_races = [r for r in all_races if r['type'] == race_type]

    if not category_races:
        st.info(f"No records found for {race_type}.")
    else:
        # --- חלק א: סיכום הקטגוריה ---
        cat_avg_speeds = []
        cat_max_speeds = []

        for r in category_races:
            if 'telemetry' in r:
                df_t = pd.DataFrame.from_dict(r['telemetry'], orient='index')
                cat_avg_speeds.append(df_t['speed_kph'].mean())
                cat_max_speeds.append(df_t['speed_kph'].max())

        if cat_avg_speeds:
            avg_val = sum(cat_avg_speeds) / len(cat_avg_speeds)
            max_val = max(cat_max_speeds)

            # הצגת מטריקות של הקטגוריה
            m1, m2, m3 = st.columns(3)
            m1.metric("Category Avg Speed", f"{avg_val:.1f} km/h")
            m2.metric("Category Record", f"{max_val:.1f} km/h")
            m3.metric("Total Runs", len(category_races))

        st.divider()

        # --- חלק ב: בחירת מירוץ ספציפי ---
        st.subheader(f"Select {race_type} Session")

        # מיון מהחדש לישן
        category_races.sort(key=lambda x: x['id'], reverse=True)

        # יצירת מילון לבחירה
        race_map = {r['id']: f"{r['date_display']} (Status: {r.get('status', '?')})" for r in category_races}

        selected_id = st.selectbox("Choose from list:", list(race_map.keys()), format_func=lambda x: race_map[x])

        # --- חלק ג: תצוגת המירוץ הנבחר ---
        if selected_id:
            race = next(r for r in category_races if r['id'] == selected_id)

            # בדיקה אם יש טלמטריה
            if 'telemetry' in race:
                df = pd.DataFrame.from_dict(race['telemetry'], orient='index')
                df['time_str'] = pd.to_datetime(df['timestamp'], unit='s').dt.strftime('%H:%M:%S')
                df = df.sort_values('timestamp')

                # כרטיסיות (Tabs) לניקיון העין
                tab1, tab2 = st.tabs(["📈 Telemetry Graphs", "📋 Raw Data"])

                with tab1:
                    max_s, avg_s, dur = calculate_session_stats(df)

                    # מטריקות קטנות למירוץ הספציפי
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Max Speed", f"{max_s:.1f}")
                    c2.metric("Avg Speed", f"{avg_s:.1f}")
                    c3.metric("Duration", f"{dur:.1f}s")
                    c4.metric("Brake Usage", f"{int(df['brake'].mean())}%")

                    # גרף ראשי צבעוני
                    fig = px.area(df, x='time_str', y='speed_kph', title='Velocity Profile',
                                  color_discrete_sequence=['#00CC96'])
                    st.plotly_chart(fig, use_container_width=True)

                    # גרף משולב גז/ברקס
                    fig2 = go.Figure()
                    fig2.add_trace(
                        go.Scatter(x=df['time_str'], y=df['throttle'], name='Throttle', line=dict(color='green')))
                    fig2.add_trace(go.Scatter(x=df['time_str'], y=df['brake'], name='Brake', line=dict(color='red')))
                    fig2.update_layout(title="Pedal Inputs", hovermode="x unified")
                    st.plotly_chart(fig2, use_container_width=True)

                with tab2:
                    st.dataframe(df)

                # רענון למירוץ חי
                if race.get('status') == 'LIVE':
                    time.sleep(1)
                    st.rerun()
            else:
                st.warning("No telemetry data recorded for this session.")
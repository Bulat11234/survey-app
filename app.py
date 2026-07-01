import firebase_admin
from firebase_admin import credentials, firestore
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
import json

# --- Инициализация Firebase ---
if not firebase_admin._apps:
    try:
        # Пробуем получить ключ из Secrets (для Streamlit Cloud)
        try:
            if "FIREBASE_KEY" in st.secrets:
                creds_dict = json.loads(st.secrets["FIREBASE_KEY"])
                cred = credentials.Certificate(creds_dict)
                firebase_admin.initialize_app(cred)
        except (FileNotFoundError, KeyError, TypeError):
            # Если secrets нет, используем локальный файл
            pass
        
        # Проверяем, инициализирован ли Firebase
        if not firebase_admin._apps:
            # Локальный режим (с файла)
            KEY_PATH = os.getenv("FIREBASE_KEY", "serviceAccountKey.json")
            if os.path.exists(KEY_PATH):
                cred = credentials.Certificate(KEY_PATH)
                firebase_admin.initialize_app(cred)
            else:
                st.error("Ошибка: Файл serviceAccountKey.json не найден.")
                st.stop()
    except Exception as e:
        st.error(f"Ошибка подключения к Firebase: {e}")
        st.stop()

db = firestore.client()

# --- 2. Настройка страницы Streamlit ---
st.set_page_config(page_title="Опрос: Удалённые собеседования", layout="wide")
st.title("📊 Отношение к удалённым собеседованиям")
st.markdown("Пройдите короткий опрос. Ваши ответы анонимны и сохраняются в облачное хранилище для последующего анализа.")

# --- 3. Форма опроса (Тема 22) ---
with st.form("survey_form"):
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Демография")
        age = st.number_input("Ваш возраст", min_value=16, max_value=65, step=1)
        experience = st.radio("Ваш опыт работы/учёбы", 
                              ["Студент", "Junior (до 1 года)", "Middle (1-3 года)", "Senior (3+ года)"])
        
    with col2:
        st.subheader("Оценка процесса")
        convenience = st.slider("Насколько удобно проходить удалённые собеседования? (1-10)", 1, 10, 5)
        stress = st.slider("Уровень стресса по сравнению с очным собеседованием (1-10)", 1, 10, 5)

    st.subheader("Предпочтения и проблемы")
    format_pref = st.multiselect("Предпочитаемый формат удалённого интервью", 
                                 ["Видеосвязь (камера)", "Только аудио", "Текстовый чат", "VR/AR формат"])
    
    challenges = st.multiselect("С какими трудностями вы сталкивались?", 
                                ["Нестабильный интернет", "Отвлекающие факторы дома", 
                                 "Сложности с настройкой ПО", "Отсутствие зрительного контакта", "Нет трудностей"])
    
    comment = st.text_area("Дополнительные комментарии или предложения")
    
    submitted = st.form_submit_button("Отправить ответ", use_container_width=True)

# --- 4. Сохранение данных в Firebase Firestore ---
if submitted:
    if not format_pref:
        st.warning("Пожалуйста, выберите хотя бы один предпочитаемый формат!")
    else:
        record = {
            "age": int(age),
            "experience": experience,
            "convenience": int(convenience),
            "stress": int(stress),
            "format_pref": format_pref,
            "challenges": challenges,
            "comment": comment,
            "timestamp": datetime.utcnow()
        }
        try:
            db.collection("remote_interviews").add(record)
            st.success("✅ Спасибо! Ваш ответ успешно сохранён.")
            st.balloons()
        except Exception as e:
            st.error(f"Ошибка сохранения: {e}")

# --- 5. Аналитическая панель (Dashboard) ---
st.markdown("---")
if st.checkbox("📈 Показать аналитику (Режим аналитика)"):
    st.header("Анализ собранных данных")
    docs = db.collection("remote_interviews").stream()
    data = [doc.to_dict() for doc in docs]
    
    if not data:
        st.info("Пока нет ответов для отображения аналитики.")
    else:
        df = pd.DataFrame(data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # Таблица с сырыми данными
        st.subheader("Сырые данные")
        st.dataframe(df.sort_values(by="timestamp", ascending=False).head(20))
        
        # Визуализация 1: Удобство vs Стресс
        st.subheader("Удобство и Уровень стресса")
        fig_scatter = px.scatter(df, x="convenience", y="stress", color="experience", 
                                 title="Корреляция удобства и стресса в зависимости от опыта",
                                 labels={"convenience": "Удобство", "stress": "Стресс"})
        st.plotly_chart(fig_scatter, use_container_width=True)
        
        # Визуализация 2: Предпочитаемые форматы
        st.subheader("Предпочитаемые форматы")
        # Разбираем списки для построения графика
        formats = [item for sublist in df["format_pref"] for item in sublist]
        df_formats = pd.DataFrame(formats, columns=["format"])
        counts = df_formats["format"].value_counts().reset_index()
        counts.columns = ["Формат", "Количество"]
        
        fig_bar = px.bar(counts, x="Формат", y="Количество", title="Популярность форматов удалённого интервью", color="Формат")
        st.plotly_chart(fig_bar, use_container_width=True)

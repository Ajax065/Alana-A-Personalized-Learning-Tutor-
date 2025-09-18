import os
import streamlit as st
from dotenv import load_dotenv
import pyrebase

load_dotenv()

firebase_config = {
    "apiKey": os.environ["FIREBASE_API_KEY"],
    "authDomain": os.environ["FIREBASE_AUTH_DOMAIN"],
    "databaseURL": os.environ["FIREBASE_DATABASE_URL"],
    "projectId": os.environ["FIREBASE_PROJECT_ID"],
    "storageBucket": os.environ["FIREBASE_STORAGE_BUCKET"],
    "messagingSenderId": os.environ["FIREBASE_MESSAGING_SENDER_ID"],
    "appId": os.environ["FIREBASE_APP_ID"],
}


firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

st.title("Auth Sanity Check")

mode = st.radio("Choose", ["Login", "Sign Up"], horizontal=True)
email = st.text_input("Email")
password = st.text_input("Password", type="password")

if mode == "Sign Up":
    if st.button("Create Account"):
        try:
            auth.create_user_with_email_and_password(email, password)
            st.success("Account created! Now login.")
        except Exception as e:
            st.error(f"Sign up failed: {e}")

if mode == "Login":
    if st.button("Login"):
        try:
            user = auth.sign_in_with_email_and_password(email, password)
            st.success(f"Logged in! UID: {user['localId']}")
        except Exception as e:
            st.error(f"Login failed: {e}")

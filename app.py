import os
import streamlit as st
from dotenv import load_dotenv
import pyrebase
import firebase_admin
from firebase_admin import credentials, firestore
from openai import OpenAI

# Load environment variables
load_dotenv()

# Firebase Web config (from Firebase console → Project settings → SDK setup & config)
firebase_config = {
    "apiKey": os.environ["FIREBASE_API_KEY"],
    "authDomain": os.environ["FIREBASE_AUTH_DOMAIN"],
    "projectId": os.environ["FIREBASE_PROJECT_ID"],
    "storageBucket": os.environ["FIREBASE_STORAGE_BUCKET"],
    "messagingSenderId": os.environ["FIREBASE_MESSAGING_SENDER_ID"],
    "appId": os.environ["FIREBASE_APP_ID"],
    "databaseURL": os.environ["FIREBASE_DATABASE_URL"],
}

# Initialize Pyrebase for authentication
firebase = pyrebase.initialize_app(firebase_config)
auth = firebase.auth()

# Initialize Firebase Admin for Firestore
try:
    if not firebase_admin._apps:
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.environ["FIREBASE_PROJECT_ID"],
            "private_key_id": os.environ.get("FIREBASE_PRIVATE_KEY_ID"),
            "private_key": os.environ["FIREBASE_PRIVATE_KEY"].replace("\\n", "\n"),
            "client_email": os.environ["FIREBASE_CLIENT_EMAIL"],
            "client_id": os.environ.get("FIREBASE_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": os.environ.get("FIREBASE_CLIENT_CERT_URL")
        })
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    st.error =(f"Storage Failure: {e}")
    db = None

# Save and load chat history in Firestore
def save_message(user_id, role, content):
    if not db:
        try:
            db.collection("users").document(user_id).collection("messages").add({
             "role": role,
             "content": content
            })
        except Exception as e:
            st.error(f"Failed to save message:{e}")
    

def load_messages(user_id):
    if not db:
        return[]
    try:
        docs = db.collection("users").document(user_id).collection("messages").stream()
        return [{"role": doc.to_dict()["role"], "content": doc.to_dict()["content"]} for doc in docs]
    except Exception as e:
        st.error(f"Failed to load message : {e}")

    

# AUTHENTICATION 
def show_auth_ui():
    st.title("Login / Sign Up")

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
                st.session_state.user = user
                st.success("Logged in successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")


# CHAT ASSISTANT
def show_chat_ui(user):
    st.set_page_config(page_title="Personalized Learning Assistant")
    st.title("ALANA ")

    user_id = user["localId"]

    # Hugging Face Token input (once per session)
    if "hf_token" not in st.session_state:
        st.session_state.hf_token = ""

    if not st.session_state.hf_token:
        st.session_state.hf_token = st.text_input(
            "Enter your Hugging Face API token:",
            type="password",
            help="Get this from https://huggingface.co/settings/tokens"
        )

    if not st.session_state.hf_token:
        st.stop()

    # Model
    MODEL_NAME = "openai/gpt-oss-20b:fireworks-ai"

    # Sidebar for learning settings
    with st.sidebar:
        st.header("Learning Settings")
        name = st.text_input("Your name:")
        topic = st.text_input("Learning topic:")
        attention_span = st.selectbox(
            "Attention Span", ["Short", "Medium", "Long"]
        )

    # Style mapping
    def get_style(span):
        if span == "Short":
            return "short and concise under 3 paragraphs"
        elif span == "Medium":
            return "moderately short paragraph with examples"
        else:
            return "detailed and comprehensive summary examples"

    # Load messages from Firestore into session
    if "messages" not in st.session_state:
        st.session_state.messages = load_messages(user_id)
        if not st.session_state.messages:
            st.session_state.messages = [{"role": "system", "content": "You are a helpful learning assistant."}]
        st.session_state.intro_given = False

    # Display chat history
    for msg in st.session_state.messages:
        if msg["role"] != "system":
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Auto-generate intro lesson
    if not st.session_state.intro_given and name and topic:
        style = get_style(attention_span)
        intro_prompt = f"You are a tutor for {name}. Please give an introductory lesson on '{topic}'. The explanation should be {style}. End with an encouraging invitation to ask questions."

        client = OpenAI(
            base_url="https://router.huggingface.co/v1",
            api_key=st.session_state.hf_token,
        )

        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "You are a helpful learning assistant."},
                {"role": "user", "content": intro_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        intro_reply = completion.choices[0].message.content

        with st.chat_message("assistant"):
            st.markdown(intro_reply)

        st.session_state.messages.append({"role": "assistant", "content": intro_reply})
        save_message(user_id, "assistant", intro_reply)
        st.session_state.intro_given = True

    # User input
    if prompt := st.chat_input("Ask me something about your learning topic..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        save_message(user_id, "user", prompt)

        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            style = get_style(attention_span)
            messages_for_model = [{"role": "system", "content": f"You are a helpful learning assistant for {name} teaching '{topic}'. The explanation style should be {style}"}]

            for m in st.session_state.messages:
                if m["role"] != "system":
                    messages_for_model.append(m)

            client = OpenAI(
                base_url="https://router.huggingface.co/v1",
                api_key=st.session_state.hf_token,
            )

            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages_for_model,
                temperature=0.7,
                max_tokens=1500
            )

            reply = completion.choices[0].message.content

            with st.chat_message("assistant"):
                st.markdown(reply)
        

            st.session_state.messages.append({"role": "assistant", "content": reply})
            save_message(user_id, "assistant", reply)
        except Exception as e:
            st.error(f"Network Error")


# MAIN
if "user" not in st.session_state:
    show_auth_ui()
else:
    show_chat_ui(st.session_state.user)

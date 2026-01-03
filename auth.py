import streamlit as st
import os
import hashlib
from dotenv import load_dotenv

load_dotenv()  # loads .env into environment

PASSWORD_HASH = os.getenv("APP_PASSWORD_HASH")

def check_password():
    if "auth" not in st.session_state:
        st.session_state.auth = False

    if st.session_state.auth:
        return True

    pwd = st.text_input("Enter password to enable saving", type="password")
    if pwd:
        if hashlib.sha256(pwd.encode()).hexdigest() == PASSWORD_HASH:
            st.session_state.auth = True
            st.success("Editing unlocked")
            return True
        else:
            st.error("Incorrect password")

    return False

import streamlit as st
import hashlib

# store hash, not password
PASSWORD_HASH = hashlib.sha256("saveloan123".encode()).hexdigest()

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

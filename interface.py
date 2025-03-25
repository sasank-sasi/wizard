import streamlit as st
import requests
import json
import os
from typing import Dict, Any
import time

# Constants
API_URL = "http://localhost:8000"
OUTPUT_DIR = "output"

def init_session_state():
    """Initialize session state variables"""
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []
    if 'current_meeting_id' not in st.session_state:
        st.session_state.current_meeting_id = None
    if 'available_meetings' not in st.session_state:
        st.session_state.available_meetings = []

def load_available_meetings() -> list:
    """Load available meeting transcripts from output directory"""
    meetings = []
    if os.path.exists(OUTPUT_DIR):
        for file in os.listdir(OUTPUT_DIR):
            if file.endswith('.json'):
                meetings.append(file.split('_')[0])
    return list(set(meetings))  # Remove duplicates

def upload_and_analyze_audio(audio_file) -> Dict[str, Any]:
    """Upload and analyze audio file"""
    files = {'file': audio_file}
    response = requests.post(f"{API_URL}/analyze-audio", files=files)
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error: {response.json()['detail']}")
        return None

def ask_question(meeting_id: str, question: str) -> Dict[str, Any]:
    """Ask a question about the meeting"""
    response = requests.post(
        f"{API_URL}/ask-question",
        json={"meeting_id": meeting_id, "question": question}
    )
    if response.status_code == 200:
        return response.json()
    else:
        st.error(f"Error: {response.json()['detail']}")
        return None

def clear_context(meeting_id: str) -> bool:
    """Clear conversation context for a meeting"""
    response = requests.post(f"{API_URL}/clear-context/{meeting_id}")
    return response.status_code == 200

def main():
    st.set_page_config(
        page_title="Meeting Analyzer",
        page_icon="🎙️",
        layout="wide"
    )

    init_session_state()

    st.title("🎙️ Meeting Analyzer")

    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Choose a function:", ["Upload Meeting", "Ask Questions"])

    if page == "Upload Meeting":
        st.header("Upload Meeting Recording")
        
        uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=['wav', 'mp3', 'ogg', 'm4a']
        )

        if uploaded_file and st.button("Analyze Meeting"):
            with st.spinner("Analyzing meeting..."):
                result = upload_and_analyze_audio(uploaded_file)
                if result:
                    st.success("Meeting analyzed successfully!")
                    
                    # Display analysis
                    with st.expander("Meeting Analysis", expanded=True):
                        st.subheader("Summary")
                        st.write(result['analysis']['summary'])
                        
                        st.subheader("Key Points")
                        for point in result['analysis']['key_points']:
                            st.markdown(f"- {point}")
                        
                        st.subheader("Action Items")
                        for item in result['analysis']['action_items']:
                            st.markdown(f"- {item}")
                        
                        st.subheader("Participants")
                        st.write(", ".join(result['analysis']['participants']))
                        
                        # Save meeting ID for questions
                        meeting_id = os.path.splitext(uploaded_file.name)[0]
                        st.session_state.current_meeting_id = meeting_id
                        st.session_state.available_meetings = load_available_meetings()

    elif page == "Ask Questions":
        st.header("Ask Questions About Meetings")

        # Refresh available meetings
        st.session_state.available_meetings = load_available_meetings()

        if not st.session_state.available_meetings:
            st.warning("No analyzed meetings found. Please upload and analyze a meeting first.")
        else:
            # Meeting selector
            meeting_id = st.selectbox(
                "Select a meeting:",
                st.session_state.available_meetings
            )

            # Question input
            question = st.text_input("Ask a question about the meeting:")
            
            if st.button("Ask") and question:
                with st.spinner("Getting answer..."):
                    result = ask_question(meeting_id, question)
                    if result:
                        # Add to conversation history
                        st.session_state.conversation_history.append({
                            "question": question,
                            "answer": result["answer"],
                            "sources": result["sources"]
                        })

            # Display conversation history
            if st.session_state.conversation_history:
                st.subheader("Conversation History")
                for idx, item in enumerate(st.session_state.conversation_history):
                    with st.expander(f"Q: {item['question']}", expanded=True):
                        st.write("A:", item["answer"])
                        with st.expander("Sources"):
                            for source in item["sources"]:
                                st.markdown(f"```\n{source}\n```")

            # Clear context button
            if st.button("Clear Conversation History"):
                if clear_context(meeting_id):
                    st.session_state.conversation_history = []
                    st.success("Conversation history cleared!")

if __name__ == "__main__":
    main()
import logging
import streamlit as st
import requests
import json
import os
from typing import Dict, Any
from datetime import datetime
import pandas as pd
import plotly.express as px

# Constants - make sure this matches your FastAPI server
API_URL = "http://localhost:8000"
OUTPUT_DIR = "output"

class MeetingAnalyzer:
    def __init__(self):
        """Initialize the Streamlit app"""
        self.setup_streamlit()
        self.init_session_state()
        self.load_meetings()

    def setup_streamlit(self):
        """Configure Streamlit page settings"""
        st.set_page_config(
            page_title="Meeting Analyzer",
            page_icon="🎙️",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.title("🎙️ Meeting Analyzer & Assistant")

    def init_session_state(self):
        """Initialize session state variables"""
        for key in ['conversation_history', 'current_meeting', 'meetings_data']:
            if key not in st.session_state:
                st.session_state[key] = [] if key == 'conversation_history' else None if key == 'current_meeting' else {}

    def load_meetings(self):
        """Load available meeting data"""
        if os.path.exists(OUTPUT_DIR):
            files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.json')]
            for file in files:
                with open(os.path.join(OUTPUT_DIR, file), 'r') as f:
                    meeting_id = file.split('_')[0]
                    if meeting_id not in st.session_state.meetings_data:
                        st.session_state.meetings_data[meeting_id] = json.load(f)

    def upload_section(self):
        """Handle meeting recording upload"""
        st.header("📤 Upload Meeting Recording")
        
        uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=['wav', 'mp3', 'ogg', 'm4a'],
            help="Supported formats: WAV, MP3, OGG, M4A"
        )

        if uploaded_file and st.button("🔍 Analyze Meeting"):
            with st.spinner("Analyzing meeting recording..."):
                files = {'file': uploaded_file}
                try:
                    response = requests.post(f"{API_URL}/analyze-audio", files=files)
                    response.raise_for_status()
                    result = response.json()
                    
                    st.success("✅ Meeting analyzed successfully!")
                    self.display_analysis(result['analysis'])
                    
                    # Update session state
                    meeting_id = os.path.splitext(uploaded_file.name)[0]
                    st.session_state.current_meeting = meeting_id
                    st.session_state.meetings_data[meeting_id] = result['analysis']
                    
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Error analyzing meeting: {str(e)}")

    def display_analysis(self, analysis: Dict[str, Any]):
        """Display meeting analysis results"""
        with st.expander("📊 Meeting Analysis", expanded=True):
            # Summary
            st.subheader("📝 Summary")
            st.write(analysis['summary'])
            
            # Key Points
            st.subheader("🎯 Key Points")
            for point in analysis['key_points']:
                st.markdown(f"• {point}")
            
            # Action Items
            st.subheader("✅ Action Items")
            if analysis['action_items']:
                for item in analysis['action_items']:
                    st.checkbox(item, key=f"action_{hash(item)}")
            else:
                st.info("No action items identified")
            
            # Participants
            st.subheader("👥 Participants")
            st.write(", ".join(analysis['participants']))
            
            # Dates and Deadlines
            if analysis['dates']:
                st.subheader("📅 Important Dates")
                
                try:
                    # Create a DataFrame with properly formatted dates
                    dates_data = []
                    for date_str in analysis['dates']:
                        try:
                            # Try to parse the date
                            start_date = pd.to_datetime(date_str)
                            
                            # Create a record with both start and end dates
                            dates_data.append({
                                'Task': date_str,
                                'Start': start_date,
                                'End': start_date + pd.Timedelta(days=1),  # End date is start + 1 day
                                'Duration': '1 day'
                            })
                        except (ValueError, TypeError):
                            st.warning(f"Couldn't parse date: {date_str}")
                            continue

                    if dates_data:
                        # Create DataFrame and sort by date
                        df = pd.DataFrame(dates_data)
                        df = df.sort_values('Start')

                        # Create Gantt chart
                        fig = px.timeline(
                            df,
                            x_start='Start',
                            x_end='End',
                            y='Task',
                            title='Meeting Timeline'
                        )

                        # Customize layout
                        fig.update_layout(
                            showlegend=False,
                            xaxis_title='Date',
                            yaxis_title=None,
                            height=max(100, len(dates_data) * 40),  # Dynamic height
                            margin=dict(l=10, r=10, t=30, b=10)
                        )

                        # Display the chart
                        st.plotly_chart(fig, use_container_width=True)

                        # Also display as a table for accessibility
                        st.markdown("#### Dates Table")
                        st.dataframe(
                            df[['Task', 'Start']].rename(columns={'Start': 'Date'}),
                            hide_index=True
                        )
                    else:
                        st.info("No valid dates found to display")

                except Exception as e:
                    st.error(f"Error displaying timeline: {str(e)}")
                    logging.error(f"Timeline error: {str(e)}")

    def qa_section(self):
        """Question & Answer section"""
        st.header("💭 Ask Questions About Meetings")
        
        if not st.session_state.meetings_data:
            st.warning("⚠️ No analyzed meetings found. Please upload and analyze a meeting first.")
            return
        
        # Meeting selector
        meeting_id = st.selectbox(
            "Select a meeting:",
            options=list(st.session_state.meetings_data.keys()),
            format_func=lambda x: f"Meeting: {x}"
        )
        
        # Question input
        question = st.text_input("💬 Ask a question about the meeting:")
        
        if st.button("🤔 Ask") and question:
            with st.spinner("Getting answer..."):
                try:
                    response = requests.post(
                        f"{API_URL}/ask-question",
                        json={"meeting_id": meeting_id, "question": question}
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Add to conversation history
                    st.session_state.conversation_history.append({
                        "question": question,
                        "answer": result["answer"],
                        "sources": result["sources"],
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    })
                    
                except requests.exceptions.RequestException as e:
                    st.error(f"❌ Error: {str(e)}")
        
        # Display conversation history
        if st.session_state.conversation_history:
            st.subheader("💬 Conversation History")
            
            for idx, item in enumerate(reversed(st.session_state.conversation_history)):
                # Create a unique key for each container
                with st.container():
                    st.markdown(f"**Q:** _{item['question']}_ ({item['timestamp']})")
                    st.markdown(f"**A:** {item['answer']}")
                    
                    # Display sources in a collapsible section
                    if item['sources']:
                        with st.expander("📚 View Sources"):
                            for source in item['sources']:
                                st.code(source, language="text")
                    
                    # Add a visual separator
                    if idx < len(st.session_state.conversation_history) - 1:
                        st.divider()
            
            # Clear history button
            if st.button("🗑️ Clear History"):
                if requests.post(f"{API_URL}/clear-context/{meeting_id}").ok:
                    st.session_state.conversation_history = []
                    st.success("🧹 Conversation history cleared!")

    def run(self):
        """Main app execution"""
        with st.sidebar:
            st.header("📌 Navigation")
            page = st.radio(
                "Choose a function:",
                ["Upload & Analyze", "Questions & Answers"]
            )
        
        if page == "Upload & Analyze":
            self.upload_section()
        else:
            self.qa_section()

if __name__ == "__main__":
    # Start Streamlit app
    app = MeetingAnalyzer()
    app.run()
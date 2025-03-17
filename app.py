import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from flask import Flask, request, jsonify
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch
import librosa
from groq import Groq
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('transcript_analysis.log')
    ]
)

# Initialize Flask app
app = Flask(__name__)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not found in environment variables")

# Initialize models and clients
whisper_processor = WhisperProcessor.from_pretrained("openai/whisper-small")
whisper_model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-small")
groq_client = Groq(api_key=GROQ_API_KEY)

def transcribe_audio(file_path: str) -> str:
    """Transcribe audio file using Whisper model"""
    try:
        # Load and process audio
        audio_data, sampling_rate = librosa.load(file_path, sr=16000)
        input_features = whisper_processor(
            audio_data, 
            sampling_rate=sampling_rate, 
            return_tensors="pt"
        ).input_features

        # Generate transcription
        with torch.no_grad():
            generated_ids = whisper_model.generate(input_features)
            transcript = whisper_processor.batch_decode(
                generated_ids, 
                skip_special_tokens=True
            )[0]

        return transcript.strip()

    except Exception as e:
        logging.error(f"Transcription error: {str(e)}")
        raise

def analyze_transcript(transcript: str) -> Dict[str, Any]:
    """Analyze transcript using Groq API"""
    prompt = f"""
    Analyze this transcript and provide a JSON response with exactly this structure:
    {{
        "transcript": "full transcript text",
        "summary": "brief 2-3 sentence summary",
        "key_points": ["point 1", "point 2"],
        "dates": ["date/time reference 1", "date/time reference 2"],
        "emails": ["email1@domain.com"],
        "action_items": ["action 1", "action 2"]
    }}

    Transcript: {transcript}

    Important: Return ONLY valid JSON with the exact structure shown above.
    """

    try:
        # Get completion from Groq
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are an AI that analyzes meeting transcripts and returns structured JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            model="llama3-8b-8192",
            temperature=0.1
        )

        # Parse and validate response
        response = chat_completion.choices[0].message.content.strip()
        analysis = json.loads(response)

        # Ensure all required fields exist
        required_fields = ["transcript", "summary", "key_points", "dates", "emails", "action_items"]
        for field in required_fields:
            if field not in analysis:
                analysis[field] = [] if field not in ["transcript", "summary"] else ""

        return analysis

    except Exception as e:
        logging.error(f"Analysis error: {str(e)}")
        raise

def save_analysis(analysis: Dict[str, Any], filename: str) -> str:
    """Save analysis results to JSON file"""
    try:
        # Create output directory
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)

        # Generate output path with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(
            output_dir,
            f"{filename}_{timestamp}.json"
        )

        # Save analysis
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        return output_path

    except Exception as e:
        logging.error(f"Save error: {str(e)}")
        raise

@app.route('/analyze-audio', methods=['POST'])
def analyze_audio():
    """Handle audio file upload and analysis"""
    try:
        # Validate request
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        # Save uploaded file temporarily
        temp_path = os.path.join("/tmp", file.filename)
        file.save(temp_path)

        try:
            # Process audio file
            transcript = transcribe_audio(temp_path)
            analysis = analyze_transcript(transcript)

            # Save results
            output_path = save_analysis(
                analysis,
                os.path.splitext(file.filename)[0]
            )

            # Return results
            return jsonify({
                "success": True,
                "analysis": analysis,
                "saved_to": output_path
            })

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except Exception as e:
        logging.error(f"Request processing error: {str(e)}")
        return jsonify({
            "error": "Processing failed",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
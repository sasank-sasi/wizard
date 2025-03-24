import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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

# Initialize FastAPI app with CORS
app = FastAPI(
    title="Audio Transcript Analyzer",
    description="API for transcribing and analyzing audio files",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY not found in environment variables")

# Initialize models and clients
whisper_processor = WhisperProcessor.from_pretrained("openai/whisper-small")
whisper_model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-small")
groq_client = Groq(api_key=GROQ_API_KEY)

# Constants
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

async def transcribe_audio(file_path: str) -> str:
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
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")

async def analyze_transcript(transcript: str) -> Dict[str, Any]:
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
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

async def save_analysis(analysis: Dict[str, Any], filename: str) -> str:
    """Save analysis results to JSON file"""
    try:
        output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = os.path.join(
            output_dir,
            f"{filename}_{timestamp}.json"
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)

        return output_path

    except Exception as e:
        logging.error(f"Save error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save analysis: {str(e)}")

@app.post("/analyze-audio", response_class=JSONResponse)
async def analyze_audio(file: UploadFile = File(...)):
    """Handle audio file upload and analysis"""
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
            
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Create temp directory
        temp_dir = os.path.join(os.getcwd(), "temp")
        os.makedirs(temp_dir, exist_ok=True)

        # Save uploaded file
        temp_path = os.path.join(temp_dir, file.filename)
        content = await file.read()
        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        try:
            # Process audio file
            transcript = await transcribe_audio(temp_path)
            analysis = await analyze_transcript(transcript)
            
            # Save results
            output_path = await save_analysis(
                analysis,
                os.path.splitext(file.filename)[0]
            )

            return JSONResponse(
                content={
                    "status": "success",
                    "transcript": transcript,
                    "analysis": analysis,
                    "output_file": output_path
                },
                status_code=200
            )

        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    except HTTPException as he:
        return JSONResponse(
            content={"status": "error", "detail": he.detail},
            status_code=he.status_code
        )
    except Exception as e:
        logging.error(f"Request processing error: {str(e)}")
        return JSONResponse(
            content={"status": "error", "detail": str(e)},
            status_code=500
        )

def start():
    """Start the FastAPI server"""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    start()
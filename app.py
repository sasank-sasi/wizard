import os
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from transformers import WhisperProcessor, WhisperForConditionalGeneration, AutoProcessor, AutoModelForSpeechSeq2Seq, pipeline
import torch
import librosa
from groq import Groq
from dotenv import load_dotenv
import numpy as np
from pydub import AudioSegment
import tempfile
from vosk import Model, KaldiRecognizer
import wave
import soundfile as sf
import resampy
from rag import MeetingRAG
from pydantic import BaseModel

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

# Replace the Whisper initialization with Vosk
def initialize_vosk():
    """Initialize Vosk model"""
    model_path = "models/vosk-model-en"
    if not os.path.exists(model_path):
        raise EnvironmentError(
            "Vosk model not found. Please download it using:\n"
            "curl -L https://alphacephei.com/vosk/models/vosk-model-en-us-0.42-gigaspeech.zip -o model.zip && "
            "unzip model.zip -d models/ && "
            "mv models/vosk-model-en-us-0.42-gigaspeech models/vosk-model-en"
        )
    return Model(model_path)

# Initialize Vosk model
vosk_model = initialize_vosk()

groq_client = Groq(api_key=GROQ_API_KEY)

# Constants
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg', 'm4a'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Update the transcribe_audio function
async def transcribe_audio(file_path: str) -> str:
    """Transcribe audio file using Vosk"""
    try:
        logging.info(f"Processing audio file: {file_path}")
        
        # Convert audio to proper format for Vosk (16kHz, mono, PCM WAV)
        data, samplerate = sf.read(file_path)
        if len(data.shape) > 1:
            data = data[:, 0]  # Convert to mono
        if samplerate != 16000:
            data = resampy.resample(data, samplerate, 16000)
        
        # Save as temporary WAV file
        temp_wav = file_path + '.temp.wav'
        with wave.open(temp_wav, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes((data * 32767).astype('int16').tobytes())
        
        try:
            # Process with Vosk
            recognizer = KaldiRecognizer(vosk_model, 16000)
            transcription_parts = []
            
            with wave.open(temp_wav, 'rb') as wf:
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    if recognizer.AcceptWaveform(data):
                        result = json.loads(recognizer.Result())
                        if result.get('text'):
                            transcription_parts.append(result['text'])
                
                # Get final result
                final_result = json.loads(recognizer.FinalResult())
                if final_result.get('text'):
                    transcription_parts.append(final_result['text'])
            
            transcription = ' '.join(transcription_parts)
            
            if not transcription:
                raise ValueError("No speech detected in audio")
                
            logging.info(f"Transcription completed: {len(transcription)} characters")
            return transcription

        finally:
            # Clean up temporary WAV file
            if os.path.exists(temp_wav):
                os.remove(temp_wav)

    except Exception as e:
        logging.error(f"Transcription error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(e)}"
        )

async def analyze_transcript(transcript: str) -> Dict[str, Any]:
    """Analyze transcript using Groq API"""
    # Store original transcript unmodified
    original_transcript = transcript
    
    # Escape special characters only for the prompt
    escaped_transcript = transcript.replace('"', '\\"').replace('\n', ' ')
    
    prompt = (
        "You are an AI meeting assistant analyzing a transcript from an online meeting. "
        "Analyze this meeting transcript and return a JSON object with exactly this structure:\n\n"
        "{\n"
        f'  "transcript": {json.dumps(original_transcript)},\n'  # Store complete transcript using json.dumps
        '  "summary": "<comprehensive 5-10 sentence summary of the meeting>",\n'
        '  "key_points": [\n'
        '    "Key decisions made",\n'
        '    "Important discussion topics",\n'
        '    "Problems raised",\n'
        '    "Solutions proposed"\n'
        '  ],\n'
        '  "action_items": [\n'
        '    "Specific tasks assigned",\n'
        '    "Due dates mentioned",\n'
        '    "Responsibilities delegated"\n'
        '  ],\n'
        '  "participants": [\n'
        '    "Names of people who spoke"\n'
        '  ],\n'
        '  "follow_up": [\n'
        '    "Items requiring follow-up",\n'
        '    "Scheduled follow-up meetings"\n'
        '  ],\n'
        '  "dates": [\n'
        '    "Meeting date",\n'
        '    "Deadlines mentioned",\n'
        '    "Future meeting dates"\n'
        '  ],\n'
        '  "emails": [\n'
        '    "Email addresses mentioned"\n'
        '  ],\n'
        '  "resources": [\n'
        '    "Links shared",\n'
        '    "Documents referenced",\n'
        '    "Tools mentioned"\n'
        '  ],\n'
        '  "next_steps": "<clear description of immediate next steps>"\n'
        "}\n\n"
        f"Meeting Transcript: {escaped_transcript}\n\n"
        "Important: \n"
        "1. Focus on extracting actionable insights and key meeting outcomes\n"
        "2. Identify and highlight all assignments and responsibilities\n"
        "3. Capture all mentioned deadlines and follow-up items\n"
        "4. Include all contact information shared\n"
        "5. Respond only with the JSON object, no additional text"
    )

    # Update system message for meeting context
    system_message = {
        "role": "system",
        "content": (
            "You are a specialized meeting analysis AI that excels at:\n"
            "1. Extracting key decisions and action items from meetings\n"
            "2. Identifying participants and their responsibilities\n"
            "3. Capturing deadlines and important dates\n"
            "4. Summarizing complex discussions into clear points\n"
            "5. Preserving the complete transcript in the output\n"  # Added emphasis
            "Always respond with valid JSON matching the exact structure requested.\n"
            "Never include additional text or markdown.\n"
            "Use empty arrays [] for lists with no items.\n"
            "Use empty string \"\" for missing text fields.\n"
            "Ensure all JSON is properly escaped.\n"
            "Include the complete transcript without modifications."
        )
    }

    try:
        user_message = {
            "role": "user",
            "content": prompt
        }
        

        # Make API request with improved error handling
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[system_message, user_message],
                model="llama3-8b-8192",
                temperature=0.1,
                max_tokens=8192,
                response_format={"type": "json_object"}  # Request JSON response
            )
        except Exception as api_error:
            logging.error(f"Groq API error: {str(api_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"API request failed: {str(api_error)}"
            )

        # Extract and validate response
        try:
            response_text = chat_completion.choices[0].message.content.strip()
            # Log the raw response for debugging
            logging.debug(f"Raw API response: {response_text}")
            
            # Clean the response text
            response_text = response_text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:-3].strip()
            
            analysis = json.loads(response_text)
            
            # Validate structure immediately
            if not validate_analysis(analysis):
                raise HTTPException(
                    status_code=500,
                    detail="Invalid analysis structure from API"
                )
                
            return analysis

        except json.JSONDecodeError as json_error:
            logging.error(
                f"JSON parsing error: {str(json_error)}\n"
                f"Response text: {response_text}"
            )
            raise HTTPException(
                status_code=500,
                detail="Failed to parse API response as JSON"
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Unexpected error in analyze_transcript: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )

def validate_analysis(analysis: Dict[str, Any]) -> bool:
    """Validate the structure and content of the analysis"""
    try:
        required_fields = {
            "transcript": str,
            "summary": str,
            "key_points": list,
            "action_items": list,
            "participants": list,
            "follow_up": list,
            "dates": list,
            "emails": list,
            "resources": list,
            "next_steps": str
        }

        # Check all required fields exist and have correct types
        for field, field_type in required_fields.items():
            if field not in analysis:
                logging.error(f"Missing required field: {field}")
                return False
            if not isinstance(analysis[field], field_type):
                logging.error(f"Invalid type for field {field}: expected {field_type}, got {type(analysis[field])}")
                return False

        return True

    except Exception as e:
        logging.error(f"Validation error: {str(e)}")
        return False

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

def split_audio(audio_path: str, chunk_duration: int = 10) -> List[str]:
    """Split audio file into chunks of specified duration"""
    try:
        # Load audio file
        audio = AudioSegment.from_file(audio_path)
        
        # Calculate chunk size in milliseconds
        chunk_length_ms = chunk_duration * 1000
        
        # Create temporary directory for chunks
        temp_dir = tempfile.mkdtemp()
        chunk_paths = []
        
        # Split audio into chunks
        for i, chunk_start in enumerate(range(0, len(audio), chunk_length_ms)):
            chunk = audio[chunk_start:chunk_start + chunk_length_ms]
            chunk_path = os.path.join(temp_dir, f"chunk_{i}.wav")
            chunk.export(chunk_path, format="wav")
            chunk_paths.append(chunk_path)
        
        return chunk_paths
    
    except Exception as e:
        logging.error(f"Error splitting audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to split audio: {str(e)}")

def merge_transcripts(transcripts: List[str]) -> str:
    """Merge multiple transcripts into one"""
    return " ".join(transcripts)

def cleanup_chunks(chunk_paths: List[str]):
    """Clean up temporary chunk files"""
    for path in chunk_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logging.warning(f"Failed to remove chunk {path}: {str(e)}")
    
    # Remove temp directory
    try:
        os.rmdir(os.path.dirname(chunk_paths[0]))
    except Exception as e:
        logging.warning(f"Failed to remove temp directory: {str(e)}")

def preprocess_audio(file_path: str) -> str:
    """Preprocess audio file for better transcription"""
    try:
        # Load audio
        audio = AudioSegment.from_file(file_path)
        
        # Convert to WAV if not already
        if not file_path.lower().endswith('.wav'):
            temp_path = file_path + '.wav'
            audio.export(temp_path, format='wav')
            file_path = temp_path
        
        # Normalize audio
        normalized_audio = audio.normalize()
        
        # Export normalized audio
        norm_path = file_path + '.norm.wav'
        normalized_audio.export(norm_path, format='wav')
        
        logging.info(f"Audio preprocessed: {os.path.basename(norm_path)}")
        return norm_path
        
    except Exception as e:
        logging.error(f"Audio preprocessing error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Audio preprocessing failed: {str(e)}"
        )

# Update the analyze_audio endpointt
@app.post("/analyze-audio", response_class=JSONResponse)
async def analyze_audio(file: UploadFile = File(...)):
    """Handle audio file upload and analysis"""
    temp_files = []  # Track temporary files for cleanup
    
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
            
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        # Save uploaded file
        temp_path = os.path.join(tempfile.gettempdir(), file.filename)
        temp_files.append(temp_path)
        
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Preprocess audio
        processed_path = preprocess_audio(temp_path)
        temp_files.append(processed_path)
        
        # Process audio file
        transcript = await transcribe_audio(processed_path)
        if not transcript:
            raise HTTPException(
                status_code=500,
                detail="No transcript generated"
            )
            
        # Analyze transcript
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
        # Clean up all temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logging.warning(f"Failed to remove temporary file {temp_file}: {str(e)}")

# Add the question request model
class QuestionRequest(BaseModel):
    meeting_id: str
    question: str

# Initialize RAG system with Groq client
meeting_rag = MeetingRAG(groq_client)

# Add the question-answering endpoint
@app.post("/ask-question")
async def ask_question(request: QuestionRequest):
    """Answer questions about a specific meeting"""
    try:
        result = await meeting_rag.answer_question(
            request.meeting_id,
            request.question
        )
        
        return JSONResponse(
            content={
                "status": "success",
                "question": request.question,
                "answer": result["answer"],
                "sources": result["sources"]
            },
            status_code=200
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

@app.post("/clear-context/{meeting_id}")
async def clear_context(meeting_id: str):
    """Clear conversation history for a meeting"""
    success = await meeting_rag.clear_meeting_context(meeting_id)
    if success:
        return JSONResponse(
            content={"status": "success", "message": "Context cleared"},
            status_code=200
        )
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to clear context"
        )

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when shutting down"""
    await meeting_rag.cleanup()

def start():
    """Start the FastAPI server"""
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    start()
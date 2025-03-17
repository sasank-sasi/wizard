from flask import Flask, request, jsonify
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch
import librosa
import os
from groq import Groq

app = Flask(__name__)

# Load the Whisper model and processor from Hugging Face
processor = WhisperProcessor.from_pretrained("openai/whisper-small")
model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-small")

# Initialize Groq API client using API key directly
client = Groq(api_key="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")

def transcribe_audio(file_path):
    # Load and process the audio file
    audio_data, sampling_rate = librosa.load(file_path, sr=16000)
    audio_input = processor(audio_data, sampling_rate=sampling_rate, return_tensors="pt").input_features

    # Generate transcription
    with torch.no_grad():
        generated_ids = model.generate(audio_input)
        transcript = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    return transcript
def send_transcript_to_groq(transcript):
    # Send the transcript to Groq API and get a response using a language model
    chat_completion = client.chat.completions.create(
        messages=[
            {
                "role": "user",
                "content": transcript,
            }
        ],
        model="llama3-8b-8192",  # Using the llama3-8b-8192 model
    )
    # Extract the relevant information from the ChatCompletion object
    response_content = chat_completion.choices[0].message.content  # Use .content for attribute access
    return response_content

@app.route('/transcribe', methods=['POST'])
def transcribe():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file:
        file_path = os.path.join("/tmp", file.filename)
        file.save(file_path)
        
        transcript = transcribe_audio(file_path)
        response = send_transcript_to_groq(transcript)
        
        os.remove(file_path)
        
        return jsonify({"transcript": transcript, "response": response})

if __name__ == '__main__':
    app.run(debug=True)

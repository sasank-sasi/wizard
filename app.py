from flask import Flask, request, jsonify
from transformers import WhisperProcessor, WhisperForConditionalGeneration
import torch
import librosa
import os

app = Flask(__name__)

# Load the Whisper model and processor from Hugging Face
processor = WhisperProcessor.from_pretrained("openai/whisper-small")
model = WhisperForConditionalGeneration.from_pretrained("openai/whisper-small")

def transcribe_audio(file_path):
    # Load and process the audio file
    audio_data, sampling_rate = librosa.load(file_path, sr=16000)
    audio_input = processor(audio_data, sampling_rate=sampling_rate, return_tensors="pt").input_features

    # Generate transcription
    with torch.no_grad():
        generated_ids = model.generate(audio_input)
        transcript = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    
    return transcript

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
        
        os.remove(file_path)
        
        return jsonify({"transcript": transcript})

if __name__ == '__main__':
    app.run(debug=True)
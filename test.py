import requests
import json
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_audio_analysis():
    """Test the audio analysis endpoint"""
    # Audio file path
    audio_path = Path(__file__).parent / "audio_sample" / "harvard.wav"
    
    if not audio_path.exists():
        logger.error(f"Audio file not found at {audio_path}")
        return
    
    # API endpoint
    url = "http://localhost:8000/analyze-audio"
    logger.info(f"Testing endpoint: {url}")
    
    try:
        # Prepare and send request
        with open(audio_path, "rb") as f:
            files = {"file": (audio_path.name, f, "audio/wav")}
            logger.info("Sending request...")
            response = requests.post(url, files=files)
        
        # Process response
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ Request successful!")
            print("\nResponse:")
            print(json.dumps(result, indent=2))
            return result
        else:
            logger.error(f"Request failed with status {response.status_code}")
            print(f"\nError Response:")
            print(response.text)
            return None
            
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        return None

if __name__ == "__main__":
    test_audio_analysis()
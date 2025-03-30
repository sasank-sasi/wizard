let mediaRecorder = null;
let audioStream = null;
let ws = null;

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'startRecording') {
    console.log('Starting recording...');
    
    // Query specifically for Meet tabs
    chrome.tabs.query({
      active: true,
      currentWindow: true,
      url: ["*://meet.google.com/*"]
    }, async (tabs) => {
      try {
        // Check if we found any tabs
        if (!tabs || tabs.length === 0) {
          throw new Error('Please open and activate a Google Meet tab');
        }

        const tab = tabs[0];
        console.log('Found Meet tab:', tab.id);

        // Capture audio using chrome.tabCapture API
        const stream = await new Promise((resolve, reject) => {
          chrome.tabCapture.capture({
            audio: true,
            video: false,
            audioConstraints: {
              mandatory: {
                chromeMediaSource: 'tab'
              }
            }
          }, (captureStream) => {
            if (chrome.runtime.lastError) {
              reject(chrome.runtime.lastError);
              return;
            }
            if (!captureStream) {
              reject(new Error('Failed to capture tab audio'));
              return;
            }
            resolve(captureStream);
          });
        });

        // Create audio context to preserve system audio
        const audioContext = new AudioContext();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(audioContext.destination);

        // Setup recording
        audioStream = stream;
        mediaRecorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm;codecs=opus'
        });

        // Setup WebSocket connection
        ws = new WebSocket('ws://localhost:8000/ws/transcribe');

        ws.onopen = () => {
          mediaRecorder.start(1000);
          sendResponse({ success: true });
        };

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0 && ws?.readyState === WebSocket.OPEN) {
            ws.send(event.data);
          }
        };

      } catch (error) {
        console.error('Capture error:', error);
        sendResponse({ success: false, error: error.message });
        stopCapture();
      }
    });
    return true; // Keep message channel open
  } else if (request.action === 'stopRecording') {
    stopCapture();
    sendResponse({ status: 'success' });
  }
  return true; // Keep the message channel open for async response
});

function stopCapture() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  if (audioStream) {
    audioStream.getTracks().forEach(track => track.stop());
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
  }
  
  mediaRecorder = null;
  audioStream = null;
  ws = null;
  
  chrome.runtime.sendMessage({ status: 'Recording stopped' });
}
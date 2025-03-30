let mediaRecorder;
let recordedChunks = [];
let stream;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "startRecording") {
    chrome.tabCapture.capture({ audio: true, video: false }, (capturedStream) => {
      if (!capturedStream) {
        console.error("Error capturing tab audio");
        return;
      }
      
      stream = capturedStream;
      mediaRecorder = new MediaRecorder(capturedStream, { mimeType: "audio/webm" });
      recordedChunks = [];
      
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordedChunks.push(event.data);
      };
      mediaRecorder.onstop = () => {
        const blob = new Blob(recordedChunks, { type: "audio/webm" });
        const url = URL.createObjectURL(blob);
        chrome.runtime.sendMessage({ action: "download", url });
      };
      
      mediaRecorder.start();
    });
  } else if (message.action === "stopRecording") {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
      stream.getTracks().forEach(track => track.stop());
    }
  } else if (message.action === "download") {
    chrome.downloads.download({ url: message.url, filename: "google_meet_audio.webm" });
  }
});
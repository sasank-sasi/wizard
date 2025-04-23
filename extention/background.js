let recorder;
let audioChunks = [];

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "startRecording") {
    chrome.tabCapture.capture({ audio: true, video: false }, (stream) => {
      if (!stream) return;
      recorder = new MediaRecorder(stream);

      recorder.ondataavailable = (e) => {
        audioChunks.push(e.data);
      };
 
      recorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const url = URL.createObjectURL(blob);
        chrome.downloads.download({
          url: url,
          filename: 'meeting_audio.webm',
          saveAs: true
        });
        audioChunks = [];
      };

      recorder.start();
    });
  }

  if (message.action === "stopRecording" && recorder) {
    recorder.stop();
  }
});

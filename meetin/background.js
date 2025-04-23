let recorder = null
let recordedChunks = []
let tabId = null
let stream = null
let mediaRecorder = null
let recordingStream = null
let audioChunks = []

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handle = {
    startRecording: async () => {
      try {
        // Query for the current active tab in the active window
        const [tab] = await chrome.tabs.query({
          active: true,
          currentWindow: true
        });

        // Check if we're on a Google Meet tab
        if (!tab?.url?.includes('meet.google.com')) {
          throw new Error("Please open a Google Meet tab first");
        }

        if (!tab.id) {
          throw new Error("Invalid tab");
        }

        await startRecording(tab.id);
        sendResponse({ success: true });
      } catch (error) {
        console.error("Error starting recording:", error);
        sendResponse({ success: false, error: error.message });
      }
    },
    
    stopRecording: async () => {
      try {
        await stopRecording();
        sendResponse({ success: true });
      } catch (error) {
        console.error("Error stopping recording:", error);
        sendResponse({ success: false, error: error.message });
      }
    },
    downloadRecording: async () => {
      try {
        await downloadRecording();
        sendResponse({ success: true });
      } catch (error) {
        console.error("Error downloading recording:", error);
        sendResponse({ success: false, error: error.message });
      }
    },
    startAudioRecording: async () => {
      try {
        await startAudioRecording();
        sendResponse({ success: true });
      } catch (error) {
        console.error("Error starting audio recording:", error);
        sendResponse({ success: false, error: error.message });
      }
    },
    stopAudioRecording: async () => {
      try {
        const audioBlob = await stopAudioRecording();
        sendResponse({ success: true, audioBlob });
      } catch (error) {
        console.error("Error stopping audio recording:", error);
        sendResponse({ success: false, error: error.message });
      }
    }
  };

  if (message.action && handle[message.action]) {
    handle[message.action]();
    return true; // Keep the response channel open
  }

  return false;
});


async function startRecording(targetTabId) {
  if (recorder) {
    throw new Error("Recording already in progress");
  }

  try {
    // Capture tab audio directly using chrome.tabCapture.capture
    const stream = await new Promise((resolve, reject) => {
      chrome.tabCapture.capture(
        {
          audio: true,
          video: false,
          audioConstraints: {
            mandatory: {
              chromeMediaSource: 'tab'
            }
          }
        },
        (stream) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
            return;
          }
          if (!stream) {
            reject(new Error('Failed to capture tab audio'));
            return;
          }
          resolve(stream);
        }
      );
    });

    // Initialize recorder with the stream
    recorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm'
    });

    recordedChunks = [];

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data);
      }
    };

    recorder.onstop = () => {
      stream.getTracks().forEach(track => track.stop());
    };

    // Start recording
    recorder.start(1000);
    return true;

  } catch (error) {
    console.error("Error in startRecording:", error);
    recorder = null;
    throw error;
  }
}

async function stopRecording() {
  if (!recorder || recorder.state === "inactive") {
    throw new Error("No active recording")
  }

  return new Promise((resolve, reject) => {
    try {
      recorder.onstop = () => {
        if (stream) {
          stream.getTracks().forEach((track) => track.stop())
          stream = null
        }
        recorder = null
        resolve(true)
      }

      recorder.stop()

      // Notify content script that recording has stopped
      if (tabId) {
        chrome.tabs
          .sendMessage(tabId, { action: "recordingStopped" })
          .catch((error) => console.error("Error notifying content script:", error))
      }
    } catch (error) {
      console.error("Error in stopRecording:", error)
      reject(error)
    }
  })
}

async function downloadRecording() {
  if (recordedChunks.length === 0) {
    throw new Error("No recording available to download")
  }

  try {
    const blob = new Blob(recordedChunks, { type: "video/webm" })
    const url = URL.createObjectURL(blob)
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-")
    const filename = `google-meet-recording-${timestamp}.webm`

    await chrome.downloads.download({
      url: url,
      filename: filename,
      saveAs: true,
    })

    // Clear the recorded chunks after download
    recordedChunks = []

    return true
  } catch (error) {
    console.error("Error in downloadRecording:", error)
    throw error
  }
}

async function startAudioRecording() {
  try {
    const stream = await chrome.tabCapture.capture({
      audio: true,
      video: false
    });

    if (!stream) {
      throw new Error('Failed to capture tab audio');
    }

    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.start();
    return { success: true };

  } catch (error) {
    console.error('Error starting recording:', error);
    throw error;
  }
}

async function stopAudioRecording() {
  return new Promise((resolve, reject) => {
    if (!mediaRecorder) {
      reject(new Error('No recording in progress'));
      return;
    }

    mediaRecorder.onstop = () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      resolve(audioBlob);
    };

    mediaRecorder.stop();
  });
}

// Clean up when extension is unloaded
chrome.runtime.onSuspend.addListener(() => {
  if (recorder && recorder.state === "recording") {
    recorder.stop()
  }

  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
    stream = null
  }

  if (mediaRecorder) {
    mediaRecorder.stop()
  }
})


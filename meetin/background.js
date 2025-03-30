let recorder = null
let recordedChunks = []
let tabId = null
let stream = null

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "startRecording") {
    startRecording(message.tabId)
      .then(() => sendResponse({ success: true }))
      .catch((error) => {
        console.error("Error starting recording:", error)
        sendResponse({ success: false, error: error.message })
      })
    return true // Indicates async response
  } else if (message.action === "stopRecording") {
    stopRecording()
      .then(() => sendResponse({ success: true }))
      .catch((error) => {
        console.error("Error stopping recording:", error)
        sendResponse({ success: false, error: error.message })
      })
    return true
  } else if (message.action === "downloadRecording") {
    downloadRecording()
      .then(() => sendResponse({ success: true }))
      .catch((error) => {
        console.error("Error downloading recording:", error)
        sendResponse({ success: false, error: error.message })
      })
    return true
  }
})

async function startRecording(targetTabId) {
  if (recorder) {
    throw new Error("Recording already in progress")
  }

  tabId = targetTabId

  try {
    // Request tab capture
    stream = await chrome.tabCapture.capture({
      video: true,
      audio: true,
      videoConstraints: {
        mandatory: {
          minWidth: 1280,
          minHeight: 720,
          maxWidth: 1920,
          maxHeight: 1080,
        },
      },
    })

    if (!stream) {
      throw new Error("Failed to capture tab")
    }

    // Initialize recorder with the stream
    recorder = new MediaRecorder(stream, {
      mimeType: "video/webm;codecs=vp9,opus",
      videoBitsPerSecond: 2500000, // 2.5 Mbps
    })

    recordedChunks = []

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        recordedChunks.push(event.data)
      }
    }

    recorder.onstop = () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop())
        stream = null
      }
    }

    // Start recording
    recorder.start(1000) // Collect data in 1-second chunks

    // Inject content script to handle audio
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    })

    // Notify content script that recording has started
    await chrome.tabs.sendMessage(tabId, { action: "recordingStarted" })

    return true
  } catch (error) {
    console.error("Error in startRecording:", error)
    if (stream) {
      stream.getTracks().forEach((track) => track.stop())
      stream = null
    }
    recorder = null
    throw error
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

// Clean up when extension is unloaded
chrome.runtime.onSuspend.addListener(() => {
  if (recorder && recorder.state === "recording") {
    recorder.stop()
  }

  if (stream) {
    stream.getTracks().forEach((track) => track.stop())
    stream = null
  }
})


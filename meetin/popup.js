document.addEventListener("DOMContentLoaded", () => {
  const startBtn = document.getElementById("start-btn")
  const stopBtn = document.getElementById("stop-btn")
  const downloadBtn = document.getElementById("download-btn")
  const recordingStatus = document.getElementById("recording-status")
  const durationElement = document.getElementById("duration")
  const statusIndicator = document.getElementById("status-indicator")
  const inMeetElement = document.getElementById("in-meet")
  const notInMeetElement = document.getElementById("not-in-meet")
  const downloadContainer = document.getElementById("download-container")

  let isRecording = false
  let durationInterval
  let startTime

  // Check if we're in a Google Meet
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const currentTab = tabs[0]
    if (currentTab.url.includes("meet.google.com")) {
      inMeetElement.classList.remove("hidden")
      statusIndicator.classList.remove("bg-gray-400")
      statusIndicator.classList.add("bg-green-500")
    } else {
      notInMeetElement.classList.remove("hidden")
    }
  })

  // Get current recording state
  chrome.storage.local.get(["isRecording", "startTime"], (result) => {
    if (result.isRecording) {
      isRecording = true
      startTime = result.startTime
      updateUI(true)
      startDurationCounter()
    }
  })

  startBtn.addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      chrome.runtime.sendMessage({ action: "startRecording", tabId: tabs[0].id }, (response) => {
        if (response && response.success) {
          isRecording = true
          startTime = Date.now()
          chrome.storage.local.set({ isRecording: true, startTime: startTime })
          updateUI(true)
          startDurationCounter()
        } else {
          alert("Failed to start recording. Please try again.")
        }
      })
    })
  })

  stopBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "stopRecording" }, (response) => {
      if (response && response.success) {
        isRecording = false
        chrome.storage.local.set({ isRecording: false })
        updateUI(false)
        clearInterval(durationInterval)
        downloadContainer.classList.remove("hidden")
      } else {
        alert("Failed to stop recording. Please try again.")
      }
    })
  })

  downloadBtn.addEventListener("click", () => {
    chrome.runtime.sendMessage({ action: "downloadRecording" }, (response) => {
      if (!response || !response.success) {
        alert("Failed to download recording. Please try again.")
      }
    })
  })

  function updateUI(recording) {
    if (recording) {
      startBtn.classList.add("hidden")
      stopBtn.classList.remove("hidden")
      recordingStatus.textContent = "Recording"
      recordingStatus.classList.add("text-red-500")
      statusIndicator.classList.remove("bg-green-500")
      statusIndicator.classList.add("bg-red-500")
    } else {
      stopBtn.classList.add("hidden")
      startBtn.classList.remove("hidden")
      recordingStatus.textContent = "Not Recording"
      recordingStatus.classList.remove("text-red-500")
      statusIndicator.classList.remove("bg-red-500")
      statusIndicator.classList.add("bg-green-500")
    }
  }

  function startDurationCounter() {
    durationInterval = setInterval(() => {
      const elapsed = Date.now() - startTime
      durationElement.textContent = formatDuration(elapsed)
    }, 1000)
  }

  function formatDuration(ms) {
    const seconds = Math.floor((ms / 1000) % 60)
    const minutes = Math.floor((ms / (1000 * 60)) % 60)
    const hours = Math.floor(ms / (1000 * 60 * 60))

    return [
      hours.toString().padStart(2, "0"),
      minutes.toString().padStart(2, "0"),
      seconds.toString().padStart(2, "0"),
    ].join(":")
  }
})


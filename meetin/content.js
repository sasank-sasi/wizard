// This script runs in the context of the Google Meet page

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "recordingStarted") {
    showRecordingIndicator()
    sendResponse({ success: true })
  } else if (message.action === "recordingStopped") {
    hideRecordingIndicator()
    sendResponse({ success: true })
  }
  return true
})

// Create and show a recording indicator
function showRecordingIndicator() {
  // Remove any existing indicator first
  hideRecordingIndicator()

  // Create the indicator element
  const indicator = document.createElement("div")
  indicator.id = "meet-recorder-indicator"
  indicator.style.position = "fixed"
  indicator.style.top = "10px"
  indicator.style.right = "10px"
  indicator.style.backgroundColor = "rgba(255, 0, 0, 0.7)"
  indicator.style.color = "white"
  indicator.style.padding = "5px 10px"
  indicator.style.borderRadius = "4px"
  indicator.style.fontWeight = "bold"
  indicator.style.zIndex = "9999"
  indicator.style.display = "flex"
  indicator.style.alignItems = "center"
  indicator.style.gap = "5px"

  // Add a pulsing dot
  const dot = document.createElement("div")
  dot.style.width = "10px"
  dot.style.height = "10px"
  dot.style.borderRadius = "50%"
  dot.style.backgroundColor = "white"
  dot.style.animation = "pulse 1.5s infinite"

  // Add the animation
  const style = document.createElement("style")
  style.textContent = `
    @keyframes pulse {
      0% { opacity: 1; }
      50% { opacity: 0.3; }
      100% { opacity: 1; }
    }
  `
  document.head.appendChild(style)

  indicator.appendChild(dot)
  indicator.appendChild(document.createTextNode("Recording"))

  // Add to the page
  document.body.appendChild(indicator)
}

// Remove the recording indicator
function hideRecordingIndicator() {
  const indicator = document.getElementById("meet-recorder-indicator")
  if (indicator) {
    indicator.remove()
  }
}

// Initialize when the page loads
function initialize() {
  // Add any necessary initialization code here
  console.log("Google Meet Recorder content script initialized")
}

// Run initialization
initialize()


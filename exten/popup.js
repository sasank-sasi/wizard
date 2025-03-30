document.addEventListener("DOMContentLoaded", () => {
    document.getElementById("start").addEventListener("click", () => {
      chrome.runtime.sendMessage({ action: "startRecording" });
    });
  
    document.getElementById("stop").addEventListener("click", () => {
      chrome.runtime.sendMessage({ action: "stopRecording" });
    });
  });
  
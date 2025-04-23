document.addEventListener('DOMContentLoaded', async () => {
  const startButton = document.getElementById('startRecording');
  const stopButton = document.getElementById('stopRecording');
  const statusIndicator = document.getElementById('status-indicator');
  const recordingStatus = document.getElementById('recording-status');
  const duration = document.getElementById('duration');
  const notInMeetDiv = document.getElementById('not-in-meet');
  const inMeetDiv = document.getElementById('in-meet');
  let startTime;
  let timerInterval;

  function updateDuration() {
    const elapsed = new Date().getTime() - startTime;
    const seconds = Math.floor((elapsed / 1000) % 60);
    const minutes = Math.floor((elapsed / (1000 * 60)) % 60);
    const hours = Math.floor(elapsed / (1000 * 60 * 60));
    duration.textContent = 
      `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }

  // Check if we're in a Google Meet tab
  const [tab] = await chrome.tabs.query({
    active: true,
    currentWindow: true
  });

  const isInMeet = tab?.url?.includes('meet.google.com') || false;
  notInMeetDiv.classList.toggle('hidden', isInMeet);
  inMeetDiv.classList.toggle('hidden', !isInMeet);

  if (!isInMeet) {
    startButton.disabled = true;
    recordingStatus.textContent = 'Please open a Google Meet tab';
    recordingStatus.classList.add('text-red-500');
    return;
  }

  startButton.addEventListener('click', async () => {
    try {
      const response = await chrome.runtime.sendMessage({ action: 'startRecording' });
      if (response.success) {
        startButton.classList.add('hidden');
        stopButton.classList.remove('hidden');
        statusIndicator.classList.remove('bg-gray-400');
        statusIndicator.classList.add('bg-red-500');
        recordingStatus.textContent = 'Recording';
        recordingStatus.classList.remove('text-red-500');
        startTime = new Date().getTime();
        timerInterval = setInterval(updateDuration, 1000);
      } else {
        throw new Error(response.error || 'Failed to start recording');
      }
    } catch (error) {
      console.error('Error:', error);
      recordingStatus.textContent = error.message;
      recordingStatus.classList.add('text-red-500');
    }
  });

  stopButton.addEventListener('click', async () => {
    try {
      const response = await chrome.runtime.sendMessage({ action: 'stopRecording' });
      if (response.success) {
        stopButton.classList.add('hidden');
        startButton.classList.remove('hidden');
        statusIndicator.classList.remove('bg-red-500');
        statusIndicator.classList.add('bg-gray-400');
        recordingStatus.textContent = 'Not Recording';
        clearInterval(timerInterval);
      }
    } catch (error) {
      console.error('Error:', error);
      alert('Error stopping recording: ' + error.message);
    }
  });
});


document.addEventListener('DOMContentLoaded', () => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const status = document.getElementById('status');

    // Check if we're in a Meet
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        const currentTab = tabs[0];
        if (!currentTab.url.includes('meet.google.com')) {
            status.textContent = 'Please open a Google Meet';
            startBtn.disabled = true;
            return;
        }
    });

    startBtn.addEventListener('click', () => {
        status.textContent = 'Checking Meet tab...';
        
        chrome.runtime.sendMessage({ action: 'startRecording' }, response => {
            console.log('Start recording response:', response);
            
            if (response && response.success) {
                startBtn.disabled = true;
                stopBtn.disabled = false;
                status.textContent = 'Recording...';
            } else {
                status.textContent = response?.error || 'Failed to start recording';
            }
        });
    });

    stopBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ action: 'stopRecording' }, (response) => {
            if (chrome.runtime.lastError) {
                console.error(chrome.runtime.lastError);
                status.textContent = 'Error stopping recording';
                return;
            }
            startBtn.disabled = false;
            stopBtn.disabled = true;
            status.textContent = 'Recording stopped';
        });
    });

    // Listen for status updates from background script
    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === 'transcription') {
            status.textContent = `Latest: ${message.text}`;
        } else if (message.type === 'error') {
            status.textContent = `Error: ${message.error}`;
            startBtn.disabled = false;
            stopBtn.disabled = true;
        } else if (message.type === 'status') {
            status.textContent = message.text;
        }
    });
});
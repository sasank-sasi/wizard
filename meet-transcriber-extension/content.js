let audioProcessor = null;

// Safely inject the audio processor script
async function injectAudioProcessor() {
    try {
        const script = document.createElement('script');
        script.src = chrome.runtime.getURL('audioProcessor.js');
        script.type = 'text/javascript';
        
        // Wait for script to load
        await new Promise((resolve, reject) => {
            script.onload = resolve;
            script.onerror = reject;
            document.head.appendChild(script);
        });

        // Initialize audio processor after user interaction
        document.addEventListener('click', initializeAudioProcessor, { once: true });
        
    } catch (error) {
        console.error('Failed to inject audio processor:', error);
    }
}

async function initializeAudioProcessor() {
    if (window.AudioProcessor) {
        audioProcessor = new window.AudioProcessor();
        const initialized = await audioProcessor.initialize();
        if (initialized) {
            chrome.runtime.sendMessage({
                action: 'audioReady',
                status: 'Audio context initialized'
            });
        }
    }
}

// Listen for messages from the extension
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!chrome.runtime.id) {
        // Extension context invalidated, reload the page
        window.location.reload();
        return;
    }

    if (message.action === 'checkMeetStatus') {
        const isMeet = window.location.hostname === 'meet.google.com';
        const inMeeting = document.querySelector('[data-meeting-title]') !== null;
        
        sendResponse({
            isMeet,
            inMeeting,
            meetingId: inMeeting ? window.location.pathname.split('/').pop() : null
        });
        return true; // Keep the message channel open for async response
    }
});

// Monitor meeting status
let meetingObserver = new MutationObserver(() => {
    const meetingTitle = document.querySelector('[data-meeting-title]');
    if (meetingTitle) {
        chrome.runtime.sendMessage({
            action: 'meetingDetected',
            meetingId: window.location.pathname.split('/').pop(),
            title: meetingTitle.textContent
        });
    }
});

// Start observing DOM changes for meeting detection
meetingObserver.observe(document.body, {
    childList: true,
    subtree: true
});

// Initialize on page load
injectAudioProcessor().catch(console.error);

// Listen for audio levels
window.addEventListener('message', (event) => {
    if (event.data.type === 'audioLevel') {
        chrome.runtime.sendMessage({
            action: 'audioLevel',
            level: event.data.level
        });
    }
});

// Cleanup on unload
window.addEventListener('unload', () => {
    if (audioProcessor) {
        audioProcessor.disconnect();
    }
});
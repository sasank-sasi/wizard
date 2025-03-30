class AudioProcessor {
    constructor() {
        this.audioContext = null;
        this.processor = null;
    }

    async initialize() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            await this.audioContext.resume();
            
            this.processor = this.audioContext.createScriptProcessor(2048, 1, 1);
            this.processor.onaudioprocess = this.handleAudioProcess.bind(this);
            
            return true;
        } catch (error) {
            console.error('Audio initialization failed:', error);
            return false;
        }
    }

    handleAudioProcess(event) {
        const input = event.inputBuffer.getChannelData(0);
        let sum = 0.0;
        for (let i = 0; i < input.length; ++i) {
            sum += input[i] * input[i];
        }
        const rms = Math.sqrt(sum / input.length);
        window.postMessage({ type: 'audioLevel', level: rms }, '*');
    }

    connect(source) {
        source.connect(this.processor);
        this.processor.connect(this.audioContext.destination);
    }

    disconnect() {
        if (this.processor) {
            this.processor.disconnect();
        }
        if (this.audioContext) {
            this.audioContext.close();
        }
    }
}

window.AudioProcessor = AudioProcessor;
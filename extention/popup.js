let recorder;
let audioChunks = [];
let combinedStream = null;
let micStream = null;
let tabStream = null;

const startBtn = document.getElementById("start");
const stopBtn = document.getElementById("stop");
const statusText = document.getElementById("statusText");

startBtn.addEventListener("click", async () => {
  statusText.textContent = "🔄 Starting...";

  try {
    // Request raw mic stream
    const micRawStream = await navigator.mediaDevices.getUserMedia({ audio: true });

    // Boost mic input using Web Audio API
    const audioContext = new AudioContext();
    const micSource = audioContext.createMediaStreamSource(micRawStream);
    const gainNode = audioContext.createGain();
    gainNode.gain.value = 3.0; // 3x volume boost

    micSource.connect(gainNode);
    const boostedDestination = audioContext.createMediaStreamDestination();
    gainNode.connect(boostedDestination);

    const boostedMicStream = boostedDestination.stream;
    micStream = micRawStream; // for cleanup later

    // Capture tab audio (e.g. Google Meet)
    chrome.tabCapture.capture({ audio: true, video: false }, (tabAudio) => {
      if (!tabAudio) {
        const error = chrome.runtime.lastError?.message || "Unknown error";
        console.error("Capture error:", error);
        alert("❌ Could not capture tab audio:\n\n" + error);
        statusText.textContent = "⚠️ Tab capture failed.";
        return;
      }

      tabStream = tabAudio;

      // Merge tab + boosted mic streams
      combinedStream = new MediaStream([
        ...tabStream.getAudioTracks(),
        ...boostedMicStream.getAudioTracks()
      ]);

      recorder = new MediaRecorder(combinedStream);
      audioChunks = [];

      recorder.ondataavailable = (e) => audioChunks.push(e.data);

      recorder.onstop = async () => {
        const blob = new Blob(audioChunks, { type: "audio/webm" });
      
        // Decode audio using AudioContext
        const arrayBuffer = await blob.arrayBuffer();
        const audioContext = new AudioContext();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
      
        // Convert AudioBuffer to WAV
        const wavBlob = audioBufferToWav(audioBuffer);
      
        const url = URL.createObjectURL(wavBlob);
        chrome.downloads.download({
          url,
          filename: "meeting_and_mic_audio.wav",
          saveAs: true
        });
      
        // Clean up streams
        if (tabStream) tabStream.getTracks().forEach(track => track.stop());
        if (micStream) micStream.getTracks().forEach(track => track.stop());
      
        tabStream = micStream = combinedStream = null;
        statusText.textContent = "✅ WAV file saved!";
      };

      recorder.start();
      startBtn.disabled = true;
      stopBtn.disabled = false;
      statusText.textContent = "🎙️ Recording tab + mic...";
    });
  } catch (err) {
    alert("❌ Could not access microphone:\n\n" + err.message);
    statusText.textContent = "⚠️ Microphone access failed.";
  }
});

stopBtn.addEventListener("click", () => {
  if (recorder) {
    recorder.stop();
    startBtn.disabled = false;
    stopBtn.disabled = true;
    statusText.textContent = "⏹️ Stopping...";
  }
});

function audioBufferToWav(buffer) {
    const numOfChannels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;
  
    let result;
    let length = buffer.length * numOfChannels * (bitDepth / 8);
    let bufferArray = new ArrayBuffer(44 + length);
    let view = new DataView(bufferArray);
  
    let offset = 0;
  
    function writeString(str) {
      for (let i = 0; i < str.length; i++) {
        view.setUint8(offset++, str.charCodeAt(i));
      }
    }
  
    function writeInt16(value) {
      view.setInt16(offset, value, true);
      offset += 2;
    }
  
    function writeInt32(value) {
      view.setInt32(offset, value, true);
      offset += 4;
    }
  
    writeString("RIFF");
    writeInt32(36 + length);
    writeString("WAVE");
    writeString("fmt ");
    writeInt32(16);
    writeInt16(format);
    writeInt16(numOfChannels);
    writeInt32(sampleRate);
    writeInt32(sampleRate * numOfChannels * (bitDepth / 8));
    writeInt16(numOfChannels * (bitDepth / 8));
    writeInt16(bitDepth);
    writeString("data");
    writeInt32(length);
  
    const interleaved = interleaveChannels(buffer);
    const volume = 1;
    for (let i = 0; i < interleaved.length; i++) {
      view.setInt16(offset, interleaved[i] * (0x7FFF * volume), true);
      offset += 2;
    }
  
    return new Blob([bufferArray], { type: "audio/wav" });
  }
  
  function interleaveChannels(buffer) {
    const channelData = [];
    const length = buffer.length;
    const numChannels = buffer.numberOfChannels;
  
    for (let i = 0; i < numChannels; i++) {
      channelData.push(buffer.getChannelData(i));
    }
  
    const result = new Float32Array(length * numChannels);
    let index = 0;
  
    for (let i = 0; i < length; i++) {
      for (let j = 0; j < numChannels; j++) {
        result[index++] = channelData[j][i];
      }
    }
  
    return result;
  }
  
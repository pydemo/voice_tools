import pyaudio
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import numpy as np

# Set up the Whisper speech-to-text model
device = "cuda:0" if torch.cuda.is_available() else "cpu"
torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32

model_id = "openai/whisper-large-v3"
model = AutoModelForSpeechSeq2Seq.from_pretrained(
    model_id, torch_dtype=torch_dtype, low_cpu_mem_usage=True, use_safetensors=True
)
model.to(device)
processor = AutoProcessor.from_pretrained(model_id)

# Set up the speech recognition pipeline
pipe = pipeline(
    "automatic-speech-recognition",
    model=model,
    tokenizer=processor.tokenizer,
    feature_extractor=processor.feature_extractor,
    torch_dtype=torch_dtype,
    device=device
)

# Audio capture settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
DURATION = 5  # Duration of each chunk to process (in seconds)
SILENCE_THRESHOLD = 500  # Threshold to filter out quiet sounds

# Function to detect if audio chunk is silent
def is_silent(audio_data):
    audio_amplitude = np.abs(audio_data)
    max_amplitude = np.max(audio_amplitude)
    return max_amplitude < SILENCE_THRESHOLD

# Function to stream and convert voice to text
def stream_voice_to_text():
    audio_interface = pyaudio.PyAudio()
    
    # Open the stream for the default microphone (or WASAPI loopback for system sound)
    stream = audio_interface.open(format=FORMAT, channels=CHANNELS,
                                  rate=RATE, input=True, frames_per_buffer=CHUNK)
    
    print("Recording and transcribing...")

    while True:
        frames = []
        # Capture audio for the specified duration
        for _ in range(0, int(RATE / CHUNK * DURATION)):
            data = stream.read(CHUNK)
            audio_data = np.frombuffer(data, dtype=np.int16)

            # Filter out silent audio
            if not is_silent(audio_data):
                frames.append(audio_data)
        
        # If no valid audio was captured, skip processing
        if not frames:
            continue
        
        # Convert frames to numpy array for processing
        audio_data = np.concatenate(frames, axis=0).astype(np.float32)
        
        # Process the raw audio data with Whisper, specifying the language as English
        result = pipe(audio_data, return_tensors="pt", language="en")
        transcription = result["text"]
        
        # Print the transcription
        print(f"Transcription: {transcription}")

# Start streaming voice to text
if __name__ == "__main__":
    try:
        stream_voice_to_text()
    except KeyboardInterrupt:
        print("Stopped by user.")

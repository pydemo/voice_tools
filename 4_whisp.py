import whisper
import sounddevice as sd
import numpy as np
import torch

def record_audio(duration, samplerate=16000):
    print(f"Recording for {duration} seconds...")
    audio = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1, dtype='float32')
    sd.wait()
    return audio.flatten()

def transcribe_audio(audio, model):
    # Ensure audio is in float32 format and scale to [-1, 1]
    audio = audio.astype(np.float32)
    audio = np.clip(audio, -1, 1)
    
    # Convert to PyTorch tensor
    audio_tensor = torch.from_numpy(audio)
    
    result = model.transcribe(audio_tensor)
    return result["text"]

def main():
    # Load the Whisper model
    model = whisper.load_model("base")
    
    while True:
        input("Press Enter to start recording...")
        audio = record_audio(10)  # Record for 10 seconds
        
        print("Transcribing...")
        transcription = transcribe_audio(audio, model)
        
        print(f"Transcription: {transcription}")
        
        if input("Press Enter to continue or type 'q' to quit: ").lower() == 'q':
            break

if __name__ == "__main__":
    main()
import tekore as tk
import time
import sys
import pyaudiowpatch
import wave
from datetime import datetime

def capture_audio(trackName, CHUNK_SIZE=512):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{trackName}_{timestamp}.wav"
    #filename = trackName + ".wav"
    
    with pyaudiowpatch.PyAudio() as p:
        try:
            # Get default WASAPI info
            wasapi_info = p.get_host_api_info_by_type(pyaudiowpatch.paWASAPI)
        except OSError:
            print("WASAPI not available on the system. Exiting...")
            exit()

        # Get default WASAPI speakers
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])

        if not default_speakers["isLoopbackDevice"]:
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                print("Default loopback output device not found.\nExiting...\n")
                exit()

        print(f"Recording from: ({default_speakers['index']}) {default_speakers['name']}")
        
        wave_file = wave.open(filename, 'wb')
        wave_file.setnchannels(default_speakers["maxInputChannels"])
        wave_file.setsampwidth(pyaudiowpatch.get_sample_size(pyaudiowpatch.paInt16))
        wave_file.setframerate(int(default_speakers["defaultSampleRate"]))

        def callback(in_data, frame_count, time_info, status):
            """Write frames and return PA flag"""
            wave_file.writeframes(in_data)
            return (in_data, pyaudiowpatch.paContinue)
        
        with p.open(format=pyaudiowpatch.paInt16,
                    channels=default_speakers["maxInputChannels"],
                    rate=int(default_speakers["defaultSampleRate"]),
                    frames_per_buffer=CHUNK_SIZE,
                    input=True,
                    input_device_index=default_speakers["index"],
                    stream_callback=callback
        ) as stream:
            print(f"Recording continuously to {filename}. Press Ctrl+C to stop.")
            try:
                while True:
                    time.sleep(0.1)  # Sleep briefly to keep loop responsive
            except KeyboardInterrupt:
                print("\nRecording stopped.")
            
        wave_file.close()

if __name__ == "__main__":
    track_name = "example_audio"
    capture_audio(track_name)

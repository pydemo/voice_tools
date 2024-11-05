import pyaudiowpatch as pyaudio
import wave
import time
import threading
import speech_recognition as sr
import numpy as np
import queue
import sys
import os
from google.cloud import speech

def capture_audio(track_name, duration, chunk_size=1024):
    filename = f"{track_name}.wav"
    audio_queue = queue.Queue()
    stop_flag = threading.Event()
    
    # Set up the Google Cloud Speech-to-Text client
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(config=config, interim_results=True)
    
    with pyaudio.PyAudio() as p:
        try:
            wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            print("WASAPI is not available on the system. Exiting...")
            sys.exit(1)
        
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        
        if not default_speakers["isLoopbackDevice"]:
            for loopback in p.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    default_speakers = loopback
                    break
            else:
                print("Default loopback output device not found. Run `python -m pyaudiowpatch` to check available devices. Exiting...")
                sys.exit(1)
                
        print(f"Recording from: ({default_speakers['index']}) {default_speakers['name']}")
        
        wave_file = wave.open(filename, 'wb')
        wave_file.setnchannels(default_speakers["maxInputChannels"])
        wave_file.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wave_file.setframerate(int(default_speakers["defaultSampleRate"]))

        def audio_callback(in_data, frame_count, time_info, status):
            wave_file.writeframes(in_data)
            audio_queue.put(in_data)
            return (in_data, pyaudio.paContinue)

        def transcription_thread():
            requests = (speech.StreamingRecognizeRequest(audio_content=content)
                        for content in iter(lambda: audio_queue.get(), None))
            responses = client.streaming_recognize(streaming_config, requests)

            for response in responses:
                if stop_flag.is_set():
                    break
                for result in response.results:
                    if result.is_final:
                        print("Transcription:", result.alternatives[0].transcript)

        with p.open(format=pyaudio.paInt16,
                    channels=default_speakers["maxInputChannels"],
                    rate=int(default_speakers["defaultSampleRate"]),
                    frames_per_buffer=chunk_size,
                    input=True,
                    input_device_index=default_speakers["index"],
                    stream_callback=audio_callback) as stream:
            
            print(f"Recording for {duration} seconds. Audio will be saved to {filename} and transcribed in real-time.")
            print("Press Ctrl+C to stop recording early.")
            
            # Start the transcription thread
            thread = threading.Thread(target=transcription_thread)
            thread.start()
            
            try:
                time.sleep(duration)
            except KeyboardInterrupt:
                print("\nRecording stopped early by user.")
            
            # Stop the stream and wait for the transcription thread to finish
            stream.stop_stream()
            stop_flag.set()
            audio_queue.put(None)  # Signal to exit the transcription thread
            thread.join()
        
        wave_file.close()

if __name__ == "__main__":
    # Set your Google Cloud credentials
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "<path-to-your-credentials-file.json>"
    
    track_name = "example_audio"
    duration = 30  # Record audio for 30 seconds
    capture_audio(track_name, duration)
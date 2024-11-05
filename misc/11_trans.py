import pyaudiowpatch as pyaudio
import wave
import time
import threading
import speech_recognition as sr
import numpy as np
import queue
import sys

def capture_audio(track_name, duration, chunk_size=1024):
    filename = f"{track_name}.wav"
    recognizer = sr.Recognizer()
    audio_queue = queue.Queue()
    stop_flag = threading.Event()
    
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

        def transcription_thread(recognizer):
            buffer = np.array([], dtype=np.int16)
            while not stop_flag.is_set():
                try:
                    data = audio_queue.get(timeout=1)
                    buffer = np.append(buffer, np.frombuffer(data, dtype=np.int16))
                    
                    # Process every 5 seconds of audio
                    if len(buffer) > int(default_speakers["defaultSampleRate"]) * 5:
                        audio_data = sr.AudioData(buffer.tobytes(), 
                                                  default_speakers["defaultSampleRate"],
                                                  sample_width=p.get_sample_size(pyaudio.paInt16))
                        try:
                            text = recognizer.recognize_google(audio_data)
                            print("Transcription:", text)
                        except sr.UnknownValueError:
                            print("Google Speech Recognition could not understand audio")
                        except sr.RequestError as e:
                            print(f"Could not request results from Google Speech Recognition service; {e}")
                            raise
                        
                        buffer = np.array([], dtype=np.int16)
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"An error occurred in transcription: {e}")
                    raise

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
            thread = threading.Thread(target=transcription_thread, args=(recognizer,))
            thread.start()
            
            try:
                time.sleep(duration)
            except KeyboardInterrupt:
                print("\nRecording stopped early by user.")
            
            # Stop the stream and wait for the transcription thread to finish
            stream.stop_stream()
            stop_flag.set()
            thread.join()
        
        wave_file.close()

if __name__ == "__main__":
    track_name = "example_audio"
    duration = 30  # Record audio for 30 seconds
    capture_audio(track_name, duration)
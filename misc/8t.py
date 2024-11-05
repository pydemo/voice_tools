import tekore as tk
import time
import sys
import pyaudiowpatch as pyaudio
import wave
import speech_recognition as sr


def capture_audio_and_transcribe(trackName, DURATION, CHUNK_SIZE=1024):
    filename = trackName + ".wav"
    
    recognizer = sr.Recognizer()
    
    with pyaudio.PyAudio() as p:
        try:
            for i in range(p.get_device_count()):
                device_info = p.get_device_info_by_index(i)
                if "Loopback" in device_info['name'] and device_info['maxInputChannels'] > 0:
                    print(f"Using device: {device_info['name']} (Index: {i})")
                    selected_device = device_info
                    break
            else:
                print("No valid loopback device found.")
                exit()
        except OSError:
            print("WASAPI not available.")
            exit()
        
        supported_sample_rate = int(selected_device["defaultSampleRate"])
        print(f"Using sample rate: {supported_sample_rate}")
        
        wave_file = wave.open(filename, 'wb')
        wave_file.setnchannels(1)  # Mono
        wave_file.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
        wave_file.setframerate(supported_sample_rate)
        
        def callback(in_data, frame_count, time_info, status):
            wave_file.writeframes(in_data)
            try:
                audio_data = sr.AudioData(in_data, supported_sample_rate, 2)
                text = recognizer.recognize_google(audio_data)
                print("Transcription:", text)
            except sr.UnknownValueError:
                print("Google Speech Recognition could not understand audio")
            except sr.RequestError as e:
                print(f"Request failed; {e}")
            return (in_data, pyaudio.paContinue)
        
        with p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=supported_sample_rate,
                    frames_per_buffer=CHUNK_SIZE,
                    input=True,
                    input_device_index=selected_device["index"],
                    stream_callback=callback
        ) as stream:
            print(f"Recording and transcribing for {DURATION} seconds.")
            time.sleep(DURATION)
        
        wave_file.close()



if __name__ == "__main__":
    track_name = "example_audio"
    duration = 10  # Record audio for 10 seconds
    capture_audio_and_transcribe(track_name, duration)

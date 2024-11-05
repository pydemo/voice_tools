import pyaudiowpatch as pyaudio

def list_audio_devices():
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        print(f"Device Index: {i}")
        print(f"Name: {device_info['name']}")
        print(f"Sample Rate: {device_info['defaultSampleRate']}")
        print(f"Max Input Channels: {device_info['maxInputChannels']}")
        print("--------")
    p.terminate()

if __name__ == "__main__":
    list_audio_devices()

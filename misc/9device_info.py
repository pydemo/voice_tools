import pyaudiowpatch as pyaudio

def print_device_info():
    p = pyaudio.PyAudio()
    try:
        wasapi_info = p.get_host_api_info_by_type(pyaudio.paWASAPI)
        default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
        print("Default Output Device Information:")
        print(f"Name: {default_speakers['name']}")
        print(f"Sample Rate: {default_speakers['defaultSampleRate']}")
        print(f"Max Input Channels: {default_speakers['maxInputChannels']}")
    except OSError:
        print("WASAPI not available.")
    finally:
        p.terminate()

if __name__ == "__main__":
    print_device_info()

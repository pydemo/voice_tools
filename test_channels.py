import pyaudio
import wave
from pprint import pprint as pp

CHUNK = 1024
FORMAT = pyaudio.paInt16
RATE = 44100
RECORD_SECONDS = 5

p = pyaudio.PyAudio()

# List device information to verify device index
for i in range(p.get_device_count()):
    dev = p.get_device_info_by_index(i)
    print(f"Device Index: {i}, Name: {dev['name']}, Max Input Channels: {dev['maxInputChannels']}")

# Try opening the stream and print a debug statement
for did in range(p.get_device_count()):
    print(f"\nDevice Index: {did}")
    dev = p.get_device_info_by_index(did)
    pp(dev)
    chan = dev['maxInputChannels']  # Use maxInputChannels for recording

    if chan > 0:  # Proceed only if the device has input channels
        fn = f"output_{did}.wav"
        try:
            print(f"Trying to record from device index {did} with {chan} input channels'")
            stream = p.open(format=FORMAT,
                            channels=chan,  # Use input channels count
                            rate=RATE,
                            input=True,
                            input_device_index=did,
                            frames_per_buffer=CHUNK)
            print("* recording")

            frames = []

            for i in range(0, int(RATE / CHUNK * RECORD_SECONDS)):
                data = stream.read(CHUNK)
                frames.append(data)

            print("* done recording")

            stream.stop_stream()
            stream.close()

            wf = wave.open(fn, 'wb')
            wf.setnchannels(chan)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

            print(f"Recording saved to {fn}")

        except Exception as e:
            print(f"Failed to record from device index {did}: {e}")

p.terminate()

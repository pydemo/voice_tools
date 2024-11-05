import pyaudio
import wave
import click 

@click.command()
@click.option('--out', 'output_filename', default='test.wav', type=str, help="Path to the output WAV file")
@click.option('--device_index', default=0, type=int, help="Device index for recording audio")
@click.option('--record_seconds', default=10, type=int, help="Duration to record in seconds")
def main(output_filename, device_index, record_seconds):
    # Set parameters
    FORMAT = pyaudio.paInt16  # 16-bit resolution
    CHANNELS = 2              # 2 channels for stereo
    RATE = 44100              # 44.1kHz sampling rate
    CHUNK = 1024              # 2^10 samples for buffer size

    # Initialize PyAudio
    audio = pyaudio.PyAudio()

    # Open stream
    stream = audio.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        input_device_index=device_index,
                        frames_per_buffer=CHUNK)

    print(f"Recording from device index {device_index} for {record_seconds} seconds...")

    # Initialize array to store frames
    frames = []

    # Store data in chunks for the given record_seconds
    for _ in range(0, int(RATE / CHUNK * record_seconds)):
        data = stream.read(CHUNK)
        frames.append(data)

    print("Recording finished.")

    # Stop and close the stream
    stream.stop_stream()
    stream.close()

    # Terminate PyAudio object
    audio.terminate()

    # Save the recorded data as a WAV file
    wf = wave.open(output_filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(audio.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()

    print(f"Audio saved to {output_filename}")

if __name__ == "__main__":
    main()

import pyaudio
import wave
import click
from datetime import datetime
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
@click.command()
@click.option('--out', 'output_filename', default=f'test_{timestamp}.wav', type=str, help="Path to the output WAV file")
@click.option('--device_index', default=0, type=int, help="Device index for recording audio")
@click.option('--record_seconds', default=10, type=int, help="Duration to record in seconds (used as max limit)")
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

    print(f"Recording from device index {device_index}. Press Ctrl+C to stop recording...")

    # Initialize array to store frames
    frames = []

    try:
        # Store data in chunks until interrupted
        while True:
            data = stream.read(CHUNK)
            frames.append(data)
    except KeyboardInterrupt:
        print("\nRecording stopped by user.")

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

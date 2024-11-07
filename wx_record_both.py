import wx
import pyaudio
import pyaudiowpatch
import wave
from os.path import join
from datetime import datetime
import threading
import time
import os
import subprocess   
import platform
from pprint import pprint as pp 
import traceback
import pyaudio

out_dir = 'output'
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
file_prefix=f'call_{timestamp}'
os.makedirs(join(out_dir,file_prefix), exist_ok=True)
from pydub import AudioSegment
import noisereduce as nr
import numpy as np
from scipy.io import wavfile
import os
from datetime import datetime
class AudioEnhancer:
    def __init__(self, output_dir='output'):
        self.output_dir = output_dir
        self._callback = None
        
    def set_callback(self, callback):
        self._callback = callback
    
    def _log(self, message):
        if self._callback:
            self._callback(message)        
        
    def enhance_recording(self, input_file, prefix=None):
        """Apply audio enhancements to recording with dynamic parameters"""
        try:
            self._log(f"Loading audio file: {input_file}")
            # Load audio file
            rate, data = wavfile.read(input_file)
            
            # Convert to float32 for processing
            data = data.astype(np.float32, order='C') / 32768.0

            # Calculate appropriate FFT size based on data length
            data_length = len(data)
            if data_length < 2:
                self._log("Audio file too short to process")
                return None
                
            # Choose FFT size that's power of 2 and less than data length
            n_fft = min(2048, 2**int(np.log2(data_length)))
            
            # Normalize audio levels first
            self._log("Normalizing audio levels...")
            abs_max = np.abs(data).max()
            if abs_max > 0:
                normalized = data / abs_max * 0.9  # Leave some headroom
            else:
                normalized = data

            # Only apply noise reduction if we have enough samples
            if data_length > n_fft:
                self._log(f"Reducing background noise (FFT size: {n_fft})...")
                try:
                    reduced_noise = nr.reduce_noise(
                        y=normalized,
                        sr=rate,
                        stationary=True,
                        prop_decrease=0.75,
                        n_fft=n_fft,
                        n_std_thresh_stationary=1.5
                    )
                except Exception as e:
                    self._log(f"Noise reduction failed: {str(e)}, using normalized audio")
                    reduced_noise = normalized
            else:
                self._log("Audio too short for noise reduction, using normalized audio")
                reduced_noise = normalized
                
            # Save enhanced audio
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if prefix is None:
                prefix = os.path.splitext(os.path.basename(input_file))[0]
                
            output_file = os.path.join(
                self.output_dir,
                f'{prefix}_enhanced_{timestamp}.wav'
            )
            
            # Convert back to int16
            output_data = (reduced_noise * 32768.0).astype(np.int16)
            
            self._log("Saving enhanced audio...")
            wavfile.write(output_file, rate, output_data)
            
            return output_file
            
        except Exception as e:
            self._log(f"Error during audio enhancement: {str(e)}")
            import traceback
            self._log(f"Stack trace !!!!: {traceback.format_exc()}")
            
            
    def enhance_conversation(self, mic_file, speaker_file):
        """Enhance both sides of a conversation"""
        try:
            # Create enhanced conversation directory
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            conv_dir = os.path.join(self.output_dir, f'enhanced_{timestamp}')
            os.makedirs(conv_dir, exist_ok=True)
            
            results = {
                'mic': None,
                'speaker': None
            }
            
            if mic_file and os.path.exists(mic_file) and os.path.getsize(mic_file) > 0:
                self._log("Enhancing your side of conversation...")
                results['mic'] = self.enhance_recording(
                    mic_file,
                    f'mic_{timestamp}'
                )
                
            if speaker_file and os.path.exists(speaker_file) and os.path.getsize(speaker_file) > 0:
                self._log("Enhancing other side of conversation...")
                results['speaker'] = self.enhance_recording(
                    speaker_file,
                    f'speaker_{timestamp}'
                )
                
            return results
            
        except Exception as e:
            self._log(f"Error enhancing conversation: {str(e)}")
            return None
class AudioRecorder:
    def __init__(self):
        self.FORMAT = pyaudio.paInt16
        self.RATE = 44100
        self.CHUNK = 1024
        self.recording = False
        self.frames = []
        self.audio = None
        self._callback = None
        self.current_channels = None
        self.stream = None
        self.wave_file = None
        self.current_filename = None
        
    def get_microphones(self):
        """Get list of available microphone devices"""
        self.audio = pyaudio.PyAudio()
        microphones = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            channels = int(device_info['maxInputChannels'])
            if channels > 0 and (
                'mic' in device_info['name'].lower() or
                'microphone' in device_info['name'].lower() or
                device_info['name'].lower().startswith('input') or
                'audio input' in device_info['name'].lower()
            ):
                microphones.append((i, device_info['name'], channels))
                
        if not microphones:
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                channels = int(device_info['maxInputChannels'])
                if channels > 0:
                    microphones.append((i, device_info['name'], channels))
        return microphones

    def get_speakers(self):
        """Get list of available speaker devices"""
        speakers = []
        with pyaudiowpatch.PyAudio() as p:
            try:
                wasapi_info = p.get_host_api_info_by_type(pyaudiowpatch.paWASAPI)
                for loopback in p.get_loopback_device_info_generator():
                    speakers.append({
                        'index': loopback['index'],
                        'name': loopback['name'],
                        'channels': loopback['maxInputChannels'],
                        'rate': int(loopback['defaultSampleRate'])
                    })
            except OSError:
                if self._callback:
                    self._callback("WASAPI not available on the system")
        return speakers
    
    def set_callback(self, callback):
        self._callback = callback
    
    def _log(self, message):
        if self._callback:
            self._callback(message)
    
    def start_recording_mic(self, device_index, channels):
        """Start recording from microphone"""
        if self.recording:
            return False
            
        self.recording = True
        self.frames = []
        self.current_channels = channels
        self.audio = pyaudio.PyAudio()
        
        def record_thread():
            try:
                stream = self.audio.open(
                    format=self.FORMAT,
                    channels=channels,
                    rate=self.RATE,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=self.CHUNK
                )
                
                self._log(f"Microphone recording started with {channels} channel(s)")
                
                while self.recording:
                    try:
                        data = stream.read(self.CHUNK)
                        self.frames.append(data)
                    except Exception as e:
                        self._log(f"Error during recording: {str(e)}")
                        break
                
                stream.stop_stream()
                stream.close()
                
            except Exception as e:
                self._log(f"Error setting up audio stream: {str(e)}")
                self.recording = False
        
        threading.Thread(target=record_thread, daemon=True).start()
        return True

    def start_recording_speaker(self, device_info):
        global file_prefix
        """Start recording from speaker"""
        if self.recording:
            return False
            
        self.recording = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(join(out_dir,file_prefix), exist_ok=True)
        self.current_filename = join(out_dir,file_prefix, f'speaker_recording_{timestamp}.wav')
        
        def record_thread():
            try:
                self.audio = pyaudiowpatch.PyAudio()
                self.wave_file = wave.open(self.current_filename, 'wb')
                self.wave_file.setnchannels(device_info['channels'])
                self.wave_file.setsampwidth(pyaudiowpatch.get_sample_size(pyaudiowpatch.paInt16))
                self.wave_file.setframerate(device_info['rate'])

                def callback(in_data, frame_count, time_info, status):
                    if self.recording:
                        self.wave_file.writeframes(in_data)
                        return (in_data, pyaudiowpatch.paContinue)
                    return (None, pyaudiowpatch.paComplete)

                self.stream = self.audio.open(
                    format=pyaudiowpatch.paInt16,
                    channels=device_info['channels'],
                    rate=device_info['rate'],
                    frames_per_buffer=self.CHUNK,
                    input=True,
                    input_device_index=device_info['index'],
                    stream_callback=callback
                )

                self._log(f"Speaker recording started from: {device_info['name']}")

                while self.recording:
                    time.sleep(0.1)

            except Exception as e:
                self._log(f"Recording error: {str(e)}")
                self.stop_recording()

        threading.Thread(target=record_thread, daemon=True).start()
        return self.current_filename

    def start_both_recordings(self, mic_info, speaker_info):
        global file_prefix
        """Start both microphone and speaker recordings"""
        if self.recording:
            return False
            
        self.recording = True
        # Start microphone recording
        self.frames = []
        self.current_channels = mic_info[2]
        self.audio_mic = pyaudio.PyAudio()
        
        # Start speaker recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs(join(out_dir,file_prefix), exist_ok=True)
        self.current_filename = join(out_dir,file_prefix, f'speaker_recording_{timestamp}.wav')
        
        def mic_thread():
            try:
                stream = self.audio_mic.open(
                    format=self.FORMAT,
                    channels=mic_info[2],
                    rate=self.RATE,
                    input=True,
                    input_device_index=mic_info[0],
                    frames_per_buffer=self.CHUNK
                )
                
                self._log(f"Microphone recording started with {mic_info[2]} channel(s)")
                
                while self.recording:
                    try:
                        data = stream.read(self.CHUNK)
                        self.frames.append(data)
                    except Exception as e:
                        self._log(f"Error during mic recording: {str(e)}")
                        break
                
                stream.stop_stream()
                stream.close()
                
            except Exception as e:
                self._log(f"Error setting up mic stream: {str(e)}")
        
        def speaker_thread():
            try:
                self.audio_speaker = pyaudiowpatch.PyAudio()
                self.wave_file = wave.open(self.current_filename, 'wb')
                self.wave_file.setnchannels(speaker_info['channels'])
                self.wave_file.setsampwidth(pyaudiowpatch.get_sample_size(pyaudiowpatch.paInt16))
                self.wave_file.setframerate(speaker_info['rate'])

                def callback(in_data, frame_count, time_info, status):
                    if self.recording:
                        self.wave_file.writeframes(in_data)
                        return (in_data, pyaudiowpatch.paContinue)
                    return (None, pyaudiowpatch.paComplete)

                self.stream = self.audio_speaker.open(
                    format=pyaudiowpatch.paInt16,
                    channels=speaker_info['channels'],
                    rate=speaker_info['rate'],
                    frames_per_buffer=self.CHUNK,
                    input=True,
                    input_device_index=speaker_info['index'],
                    stream_callback=callback
                )

                self._log(f"Speaker recording started from: {speaker_info['name']}")

                while self.recording:
                    time.sleep(0.1)

            except Exception as e:
                self._log(f"Recording error: {str(e)}")
        
        # Start both threads
        threading.Thread(target=mic_thread, daemon=True).start()
        threading.Thread(target=speaker_thread, daemon=True).start()
        return True
    
    def stop_recording(self, recording_type="mic"):
        global out_dir, file_prefix
        """Stop recording and save the file"""
        if not self.recording:
            return None
            
        self.recording = False
        
        if recording_type == "mic":
            if not self.frames:
                return None
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(join(out_dir,file_prefix), exist_ok=True)
            filename = join(out_dir, file_prefix, f'mic_recording_{timestamp}.wav')
            
            try:
                wf = wave.open(filename, 'wb')
                wf.setnchannels(self.current_channels)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.frames))
                wf.close()
                return filename
            except Exception as e:
                self._log(f"Error saving recording: {str(e)}")
                return None
        else:  # speaker
            try:
                if self.stream:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.stream = None
                    
                if self.wave_file:
                    self.wave_file.close()
                    self.wave_file = None
                    
                if self.audio:
                    self.audio.terminate()
                    self.audio = None
                    
                return self.current_filename
            except Exception as e:
                self._log(f"Error stopping recording: {str(e)}")
                return None

    def stop_both_recordings(self):
        global out_dir, file_prefix
        """Stop both recordings and save files"""
        if not self.recording:
            return None, None
            
        self.recording = False
        speaker_file = self.current_filename
        
        try:
            # Save microphone recording
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            os.makedirs(join(out_dir,file_prefix), exist_ok=True)
            mic_filename = join(out_dir,file_prefix, f'mic_recording_{timestamp}.wav')
            
            # Properly close streams first
            try:
                if self.stream:
                    self.stream.stop_stream()
                    time.sleep(0.1)  # Give a small delay for cleanup
                    self.stream.close()
                    self.stream = None
            except Exception as e:
                self._log(f"Error closing speaker stream: {str(e)}")

            # Close wave file
            try:
                if self.wave_file:
                    self.wave_file.close()
                    self.wave_file = None
            except Exception as e:
                self._log(f"Error closing wave file: {str(e)}")

            # Save microphone recording
            if self.frames:
                try:
                    wf = wave.open(mic_filename, 'wb')
                    wf.setnchannels(self.current_channels)
                    wf.setsampwidth(self.audio_mic.get_sample_size(self.FORMAT))
                    wf.setframerate(self.RATE)
                    wf.writeframes(b''.join(self.frames))
                    wf.close()
                except Exception as e:
                    self._log(f"Error saving microphone recording: {str(e)}")
                    mic_filename = None
            else:
                mic_filename = None

            # Clean up audio instances
            try:
                if hasattr(self, 'audio_speaker'):
                    self.audio_speaker.terminate()
                    delattr(self, 'audio_speaker')
            except Exception as e:
                self._log(f"Error terminating speaker audio: {str(e)}")

            try:
                if hasattr(self, 'audio_mic'):
                    self.audio_mic.terminate()
                    delattr(self, 'audio_mic')
            except Exception as e:
                self._log(f"Error terminating microphone audio: {str(e)}")

            return mic_filename, speaker_file
            
        except Exception as e:
            self._log(f"Error in stop_both_recordings: {str(e)}")
            return None, None
    
    def __del__(self):
        """Cleanup"""
        if self.audio:
            self.audio.terminate()

class AudioRecorderFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Audio Recorder', size=(800, 500))
        
        # Initialize recorder
        self.recorder = AudioRecorder()
        self.recorder.set_callback(self.log_message)
        self.enhancer=AudioEnhancer('enhanced')
        self.recorder.set_callback(self.log_message)
        self.last_mic_file = None
        self.last_speaker_file = None        
        wx.CallAfter(self.Raise)
        wx.CallLater(500, self.Raise)        
        self.init_ui()
        self.populate_devices()
        wx.CallAfter(self.Raise)
        wx.CallLater(500, self.Raise)        
        self.log_message("Application started")
        
    def init_ui(self):
        global file_prefix
        """Initialize the user interface"""
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create ListCtrl for logging
        self.log_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.BORDER_SUNKEN
        )
        self.log_list.InsertColumn(0, 'Timestamp', width=150)
        self.log_list.InsertColumn(1, 'Message', width=600)
        
        # Microphone controls
        mic_box = wx.StaticBox(panel, label="Microphone Recording")
        mic_sizer = wx.StaticBoxSizer(mic_box, wx.VERTICAL)
        
        mic_device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mic_label = wx.StaticText(panel, label='Microphone:')
        self.mic_choice = wx.Choice(panel)
        self.mic_record_btn = wx.Button(panel, label='Record Microphone')
        self.play_mic_btn = wx.Button(panel, label='Play Mic')
        self.transcribe_mic_btn = wx.Button(panel, label='Transcribe')
        
        mic_device_sizer.Add(mic_label, 0, wx.ALL | wx.CENTER, 5)
        mic_device_sizer.Add(self.mic_choice, 1, wx.ALL | wx.EXPAND, 5)
        mic_device_sizer.Add(self.mic_record_btn, 0, wx.ALL, 5)
        mic_device_sizer.Add(self.play_mic_btn, 0, wx.ALL, 5)
        mic_device_sizer.Add(self.transcribe_mic_btn, 0, wx.ALL, 5)
        self.transcribe_mic_btn.SetForegroundColour(wx.Colour(0, 128, 0))  # Green border color
        self.transcribe_mic_btn.SetBackgroundColour(wx.Colour(255, 255, 255))  # White background color

        
        mic_sizer.Add(mic_device_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Speaker controls
        speaker_box = wx.StaticBox(panel, label="Speaker Recording")
        speaker_sizer = wx.StaticBoxSizer(speaker_box, wx.VERTICAL)
        
        speaker_device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        speaker_label = wx.StaticText(panel, label='Speaker:')
        self.speaker_choice = wx.Choice(panel)
        self.speaker_record_btn = wx.Button(panel, label='Record Speaker')
        self.play_speaker_btn = wx.Button(panel, label='Play Speaker')
        self.transcribe_speaker_btn = wx.Button(panel, label='Transcribe')
        speaker_device_sizer.Add(speaker_label, 0, wx.ALL | wx.CENTER, 5)
        speaker_device_sizer.Add(self.speaker_choice, 1, wx.ALL | wx.EXPAND, 5)
        speaker_device_sizer.Add(self.speaker_record_btn, 0, wx.ALL, 5)
        speaker_device_sizer.Add(self.play_speaker_btn, 0, wx.ALL, 5)
        speaker_device_sizer.Add(self.transcribe_speaker_btn, 0, wx.ALL, 5)
        self.transcribe_speaker_btn.SetForegroundColour(wx.Colour(0, 128, 0))  # Green border color
        self.transcribe_speaker_btn.SetBackgroundColour(wx.Colour(255, 255, 255))  # White background color

        
        speaker_sizer.Add(speaker_device_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Refresh and Record Both buttons in horizontal layout
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(panel, label='Refresh Devices')
        # add text ctrl for file prefix
        
        self.file_prefix= wx.TextCtrl(panel, value=file_prefix)
        self.update_prefix_btn = wx.Button(panel, label='Update Prefix')
        self.both_btn = wx.Button(panel, label='Record Both')
        self.both_btn.SetForegroundColour(wx.Colour(200, 100, 100))  # Green border color
        self.both_btn.SetBackgroundColour(wx.Colour(255, 255, 255)) 
        

        
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.file_prefix, 0, wx.ALL, 5)
        button_sizer.Add(self.update_prefix_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.both_btn, 0, wx.ALL, 5)
        if 1:
            enhance_sizer = wx.BoxSizer(wx.HORIZONTAL)
            self.enhance_last_btn = wx.Button(panel, label='Enhance Last Recording')
            self.enhance_both_btn = wx.Button(panel, label='Enhance Conversation')
            
            enhance_sizer.Add(self.enhance_last_btn, 0, wx.ALL, 5)
            enhance_sizer.Add(self.enhance_both_btn, 0, wx.ALL, 5)
            
            main_sizer.Add(enhance_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
            
            # Bind enhancement events
            self.enhance_last_btn.Bind(wx.EVT_BUTTON, self.on_enhance_last)
            self.enhance_both_btn.Bind(wx.EVT_BUTTON, self.on_enhance_conversation)

        
        # Bind events
        self.mic_choice.Bind(wx.EVT_CHOICE, self.on_mic_change)
        self.speaker_choice.Bind(wx.EVT_CHOICE, self.on_speaker_change)
        self.mic_record_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_record(evt, "mic"))
        self.speaker_record_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_record(evt, "speaker"))
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.play_mic_btn.Bind(wx.EVT_BUTTON, self.on_play_mic)
        self.play_speaker_btn.Bind(wx.EVT_BUTTON, self.on_play_speaker)
        self.update_prefix_btn.Bind(wx.EVT_BUTTON, self.on_update_prefix) 
        self.both_btn.Bind(wx.EVT_BUTTON, self.on_both)
        self.file_prefix.Bind(wx.EVT_TEXT, self.on_file_prefix)
        self.transcribe_mic_btn.Bind(wx.EVT_BUTTON, self.on_transcribe_mic)
        self.transcribe_speaker_btn.Bind(wx.EVT_BUTTON, self.on_transcribe_speaker)

        
        # Add everything to main sizer
        main_sizer.Add(self.log_list, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(mic_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(speaker_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        self.last_recording = None
        
        # Add status bar
        self.CreateStatusBar()
        self.SetStatusText('Ready')
        wx.CallAfter(self.Raise)
        wx.CallLater(500, self.Raise)
    def on_enhance_last(self, event):
        """Enhance the most recent recording"""
        if not hasattr(self, 'last_recording'):
            self.log_message("No recent recording to enhance")
            return
            
        if not os.path.exists(self.last_recording):
            self.log_message("Recording file not found")
            return
            
        if os.path.getsize(self.last_recording) == 0:
            self.log_message("Recording file is empty")
            return
            
        def enhance_thread():
            try:
                self.SetStatusText('Enhancing audio...')
                enhanced_file = self.enhancer.enhance_recording(self.last_recording)
                
                if enhanced_file:
                    wx.CallAfter(self.log_message, f"Enhanced audio saved to: {enhanced_file}")
                else:
                    wx.CallAfter(self.log_message, "Enhancement failed")
            except Exception as e:
                wx.CallAfter(self.log_message, f"Enhancement error: {str(e)}")
            finally:
                wx.CallAfter(self.SetStatusText, 'Ready')
        
        threading.Thread(target=enhance_thread, daemon=True).start()

    def on_enhance_conversation(self, event):
        """Enhance both sides of the conversation"""
        if not (hasattr(self, 'last_mic_file') and hasattr(self, 'last_speaker_file')):
            self.log_message("No conversation recordings available")
            return
            
        def enhance_thread():
            self.SetStatusText('Enhancing conversation...')
            results = self.enhancer.enhance_conversation(
                self.last_mic_file,
                self.last_speaker_file
            )
            
            if results:
                wx.CallAfter(self.log_message, "Conversation enhancement complete")
                if results['mic']:
                    wx.CallAfter(self.log_message, f"Enhanced mic audio: {results['mic']}")
                if results['speaker']:
                    wx.CallAfter(self.log_message, f"Enhanced speaker audio: {results['speaker']}")
            else:
                wx.CallAfter(self.log_message, "Enhancement failed")
            wx.CallAfter(self.SetStatusText, 'Ready')
        
        threading.Thread(target=enhance_thread).start()


    # Inside the AudioRecorderFrame class
    def on_transcribe_mic(self, event):
        if self.last_mic_file:
            file_name = self.last_mic_file
            
            def transcribe_in_background():
                try:
                    pp(['python', 'wx_async_transcribe.py', file_name])
                    subprocess.run(['python', 'wx_async_transcribe.py', file_name], check=True, shell=True)
                    wx.CallAfter(self.log_message, f"Transcription completed for: {file_name}")
                except Exception as e:
                    wx.CallAfter(self.log_message, f"Error during transcription: {str(e)}")

            # Start transcription in a new thread
            threading.Thread(target=transcribe_in_background, daemon=True).start()
            self.log_message(f"Transcription started for: {file_name}")
        else:
            self.log_message("No microphone recording available to transcribe.")
    def on_transcribe_speaker(self, event):
        if self.last_speaker_file:
            file_name = self.last_speaker_file
            
            def transcribe_in_background():
                try:
                    pp(['python', 'wx_async_transcribe.py', file_name])
                    subprocess.run(['python', 'wx_async_transcribe.py', file_name], check=True, shell=True)
                    wx.CallAfter(self.log_message, f"Transcription completed for: {file_name}")
                except Exception as e:
                    wx.CallAfter(self.log_message, f"Error during transcription: {str(e)}")

            # Start transcription in a new thread
            threading.Thread(target=transcribe_in_background, daemon=True).start()
            self.log_message(f"Transcription started for: {file_name}")
        else:
            self.log_message("No microphone recording available to transcribe.")

    def _on_transcribe(self, event):
        if self.last_mic_file:
            file_name = self.last_mic_file

            def transcribe_in_background():
                try:
                    command = ['python', 'wx_async_transcribe.py', file_name]
                    
                    # Platform-specific settings to bring window to the top
                    if platform.system() == 'Windows':
                        command = ['start', 'cmd', '/c'] + command  # Uses start command to launch with focus
                    elif platform.system() == 'Darwin':  # macOS
                        command = ['open', '-a', 'Terminal'] + command
                    elif platform.system() == 'Linux':
                        command = ['gnome-terminal', '--'] + command  # Or 'xterm -hold -e' based on your terminal
                    subprocess.run(command, check=True, shell=True)
                    
                    wx.CallAfter(self.log_message, f"Transcription completed for: {file_name}")
                except Exception as e:
                    wx.CallAfter(self.log_message, f"Error during transcription: {str(e)}")

            # Start transcription in a new thread
            threading.Thread(target=transcribe_in_background, daemon=True).start()
            self.log_message(f"Transcription started for: {file_name}")
        else:
            self.log_message("No microphone recording available to transcribe.")

    def on_update_prefix(self, event):
        global file_prefix
        file_prefix = self.file_prefix.GetValue()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_prefix=f'call_{timestamp}'
        self.file_prefix.SetValue(file_prefix)
    def play_audio(self, file_name):
        """Plays an audio file using the default system media player."""
        try:
            if platform.system() == "Darwin":  # macOS
                subprocess.run(['open', file_name], check=True)
            elif platform.system() == "Windows":  # Windows
                subprocess.run(['start', file_name], shell=True, check=True)
            elif platform.system() == "Linux":  # Linux
                subprocess.run(['xdg-open', file_name], check=True)
            else:
                self.log_message("Unsupported OS for automatic playback.")
        except Exception as e:
            self.log_message(f"Error playing audio: {str(e)}")

    def on_play_mic(self, event):
        if self.last_mic_file:
            self.play_audio(self.last_mic_file)
            self.log_message(f"Playing microphone recording: {self.last_mic_file}")
        else:
            self.log_message("No microphone recording available to play.")  
    def on_play_speaker(self, event):
        if self.last_speaker_file:
            self.play_audio(self.last_speaker_file)
            self.log_message(f"Playing speaker recording: {self.last_speaker_file}")
        else:
            self.log_message("No speaker recording available to play.")                  
    def on_file_prefix(self, event):
        global file_prefix
        file_prefix = self.file_prefix.GetValue()
    def on_mic_change(self, event):
        selection = self.mic_choice.GetSelection()
        if selection >= 0:
            device_info = self.microphones[selection]
            self.log_message(f"Selected microphone: {device_info[1]} ({device_info[2]} channels)")
    
    def on_speaker_change(self, event):
        selection = self.speaker_choice.GetSelection()
        if selection >= 0:
            device_info = self.speakers[selection]
            self.log_message(f"Selected speaker: {device_info['name']}")
    
    def populate_devices(self):
        """Populate both device choices with the default system speaker selected if available."""
        # Microphones
        self.mic_choice.Clear()
        self.microphones = self.recorder.get_microphones()
        
        if not self.microphones:
            self.log_message("No microphone devices found!")
            self.mic_record_btn.Disable()
            self.both_btn.Disable()
        else:
            for i, name, channels in self.microphones:
                self.mic_choice.Append(f'{name} ({channels}ch)')
            self.mic_choice.SetSelection(0)
            self.mic_record_btn.Enable()
        
        # Speakers
        self.speaker_choice.Clear()
        self.speakers = self.recorder.get_speakers()
        
        default_speaker_index = 0
        with pyaudiowpatch.PyAudio() as p:
            try:
                # Get default WASAPI output device info
                wasapi_info = p.get_host_api_info_by_type(pyaudiowpatch.paWASAPI)
                default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                
                # Find corresponding loopback device if the default device is not a loopback
                if not default_speakers["isLoopbackDevice"]:
                    for index, loopback in enumerate(self.speakers):
                        if default_speakers["name"] in loopback["name"]:
                            default_speaker_index = index
                            break
                    else:
                        self.log_message("Default loopback output device not found.")
            except OSError:
                self.log_message("WASAPI not available on the system")

        # Populate the speaker dropdown with available devices and set the default selection
        if not self.speakers:
            self.log_message("No speaker devices found!")
            self.speaker_record_btn.Disable()
            self.both_btn.Disable()
        else:
            for speaker in self.speakers:
                self.speaker_choice.Append(speaker['name'])
            self.speaker_choice.SetSelection(default_speaker_index)
            self.speaker_record_btn.Enable()
        
        # Enable "Record Both" only if both device types are available
        if self.microphones and self.speakers:
            self.both_btn.Enable()
        else:
            self.both_btn.Disable()


    
    def on_refresh(self, event):
        self.log_message("Refreshing device list...")
        self.populate_devices()
        self.log_message("Device list updated")
    
    def log_message(self, message):
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        index = self.log_list.GetItemCount()
        self.log_list.InsertItem(index, timestamp)
        self.log_list.SetItem(index, 1, message)
        self.log_list.EnsureVisible(index)
    
    def on_record(self, event, source):
        if not self.recorder.recording:
            if source == "mic":
                selection = self.mic_choice.GetSelection()
                if selection >= 0:
                    device_info = self.microphones[selection]
                    if self.recorder.start_recording_mic(device_info[0], device_info[2]):
                        self.mic_record_btn.SetLabel('Stop Recording')
                        self.speaker_record_btn.Disable()
                        self.both_btn.Disable()
                        self.SetStatusText('Recording from microphone...')
                        
            else:  # speaker
                selection = self.speaker_choice.GetSelection()
                if selection >= 0:
                    device_info = self.speakers[selection]
                    filename = self.recorder.start_recording_speaker(device_info)
                    if filename:
                        self.speaker_record_btn.SetLabel('Stop Recording')
                        self.mic_record_btn.Disable()
                        self.both_btn.Disable()
                        self.SetStatusText('Recording from speaker...')
                        self.last_speaker_file = filename
        else:
            self.SetStatusText('Stopping...')
            filename = self.recorder.stop_recording(source)
            if filename:
                self.log_message(f"Recording saved to: {filename}")
            
            if source == "mic":
                self.mic_record_btn.SetLabel('Record Microphone')
                self.speaker_record_btn.Enable()
                self.last_mic_file = filename
                self.last_recording=filename
            else:
                self.speaker_record_btn.SetLabel('Record Speaker')
                self.mic_record_btn.Enable()
                self.last_speaker_file = filename
                self.last_recording=filename
            
            self.both_btn.Enable()
            self.SetStatusText('Ready')
    
    def on_both(self, event):
        if not self.recorder.recording:
            # Start both recordings
            selection_mic = self.mic_choice.GetSelection()
            selection_speaker = self.speaker_choice.GetSelection()
            
            if selection_mic >= 0 and selection_speaker >= 0:
                mic_info = self.microphones[selection_mic]
                speaker_info = self.speakers[selection_speaker]
                
                if self.recorder.start_both_recordings(mic_info, speaker_info):
                    self.both_btn.SetLabel('Stop Recording')
                    self.mic_record_btn.Disable()
                    self.speaker_record_btn.Disable()
                    self.SetStatusText('Recording from both devices...')
        else:
            # Stop both recordings
            self.SetStatusText('Stopping...')
            mic_file, speaker_file = self.recorder.stop_both_recordings()
            self.last_mic_file = mic_file
            self.last_speaker_file = speaker_file
            self.last_recording=speaker_file
            if mic_file:
                self.log_message(f"Microphone recording saved to: {mic_file}")
            if speaker_file:
                self.log_message(f"Speaker recording saved to: {speaker_file}")
                
            self.both_btn.SetLabel('Record Both')
            self.mic_record_btn.Enable()
            self.speaker_record_btn.Enable()
            self.SetStatusText('Ready')


if __name__ == '__main__':
    app = wx.App()
    frame = AudioRecorderFrame()
    frame.Show()
    frame.Raise()
    app.MainLoop()
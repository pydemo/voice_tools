import wx
import pyaudio
import pyaudiowpatch
import wave
from os.path import join
from datetime import datetime
import threading
import time
import os

out_dir = 'output'
os.makedirs(out_dir, exist_ok=True)

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
        """Start recording from speaker"""
        if self.recording:
            return False
            
        self.recording = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_filename = join(out_dir, f'speaker_recording_{timestamp}.wav')
        
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
        self.current_filename = join(out_dir, f'speaker_recording_{timestamp}.wav')
        
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
        """Stop recording and save the file"""
        if not self.recording:
            return None
            
        self.recording = False
        
        if recording_type == "mic":
            if not self.frames:
                return None
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = join(out_dir, f'mic_recording_{timestamp}.wav')
            
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
        """Stop both recordings and save files"""
        if not self.recording:
            return None, None
            
        self.recording = False
        speaker_file = self.current_filename
        
        # Save microphone recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mic_filename = join(out_dir, f'mic_recording_{timestamp}.wav')
        
        try:
            # Close speaker recording
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
                
            if self.wave_file:
                self.wave_file.close()
                self.wave_file = None
                
            if hasattr(self, 'audio_speaker'):
                self.audio_speaker.terminate()
                
            # Save microphone recording
            if self.frames:
                wf = wave.open(mic_filename, 'wb')
                wf.setnchannels(self.current_channels)
                wf.setsampwidth(self.audio_mic.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.frames))
                wf.close()
                
            if hasattr(self, 'audio_mic'):
                self.audio_mic.terminate()
                
            return mic_filename, speaker_file
            
        except Exception as e:
            self._log(f"Error stopping recordings: {str(e)}")
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
        
        self.init_ui()
        self.populate_devices()
        self.log_message("Application started")
        
    def init_ui(self):
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
        
        mic_device_sizer.Add(mic_label, 0, wx.ALL | wx.CENTER, 5)
        mic_device_sizer.Add(self.mic_choice, 1, wx.ALL | wx.EXPAND, 5)
        mic_device_sizer.Add(self.mic_record_btn, 0, wx.ALL, 5)
        
        mic_sizer.Add(mic_device_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Speaker controls
        speaker_box = wx.StaticBox(panel, label="Speaker Recording")
        speaker_sizer = wx.StaticBoxSizer(speaker_box, wx.VERTICAL)
        
        speaker_device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        speaker_label = wx.StaticText(panel, label='Speaker:')
        self.speaker_choice = wx.Choice(panel)
        self.speaker_record_btn = wx.Button(panel, label='Record Speaker')
        
        speaker_device_sizer.Add(speaker_label, 0, wx.ALL | wx.CENTER, 5)
        speaker_device_sizer.Add(self.speaker_choice, 1, wx.ALL | wx.EXPAND, 5)
        speaker_device_sizer.Add(self.speaker_record_btn, 0, wx.ALL, 5)
        
        speaker_sizer.Add(speaker_device_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        # Refresh and Record Both buttons in horizontal layout
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.refresh_btn = wx.Button(panel, label='Refresh Devices')
        self.both_btn = wx.Button(panel, label='Record Both')
        
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.both_btn, 0, wx.ALL, 5)
        
        # Bind events
        self.mic_choice.Bind(wx.EVT_CHOICE, self.on_mic_change)
        self.speaker_choice.Bind(wx.EVT_CHOICE, self.on_speaker_change)
        self.mic_record_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_record(evt, "mic"))
        self.speaker_record_btn.Bind(wx.EVT_BUTTON, lambda evt: self.on_record(evt, "speaker"))
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        self.both_btn.Bind(wx.EVT_BUTTON, self.on_both)
        
        # Add everything to main sizer
        main_sizer.Add(self.log_list, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(mic_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(speaker_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_CENTER | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        
        # Add status bar
        self.CreateStatusBar()
        self.SetStatusText('Ready')
        
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
        """Populate both device choices"""
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
        
        if not self.speakers:
            self.log_message("No speaker devices found!")
            self.speaker_record_btn.Disable()
            self.both_btn.Disable()
        else:
            for speaker in self.speakers:
                self.speaker_choice.Append(speaker['name'])
            self.speaker_choice.SetSelection(0)
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
        else:
            self.SetStatusText('Stopping...')
            filename = self.recorder.stop_recording(source)
            if filename:
                self.log_message(f"Recording saved to: {filename}")
            
            if source == "mic":
                self.mic_record_btn.SetLabel('Record Microphone')
                self.speaker_record_btn.Enable()
            else:
                self.speaker_record_btn.SetLabel('Record Speaker')
                self.mic_record_btn.Enable()
            
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
    app.MainLoop()
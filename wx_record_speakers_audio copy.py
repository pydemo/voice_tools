import wx
import pyaudiowpatch as pyaudio
import wave
from datetime import datetime
import threading
import time

class AudioRecorder:
    def __init__(self):
        self.FORMAT = pyaudio.paInt16
        self.RATE = 44100
        self.CHUNK = 1024
        self.recording = False
        self.frames = []
        self.audio = pyaudio.PyAudio()
        self._callback = None
        
    def get_microphones(self):
        """Get list of available microphone devices"""
        microphones = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            channels = int(device_info['maxInputChannels'])
            if channels > 0 and not device_info.get('isLoopbackDevice', False):
                microphones.append((i, device_info['name'], channels))
        return microphones

    def get_speakers(self):
        """Get list of available speaker devices for loopback recording"""
        speakers = []
        try:
            # Get WASAPI info
            wasapi_info = self.audio.get_host_api_info_by_type(pyaudio.paWASAPI)
            # Get default speakers
            default_speakers = self.audio.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            
            # Get all loopback devices
            for loopback in self.audio.get_loopback_device_info_generator():
                if default_speakers["name"] in loopback["name"]:
                    speakers.append((
                        loopback["index"],
                        loopback["name"],
                        loopback["maxInputChannels"],
                        int(loopback["defaultSampleRate"])
                    ))
                    break
            
            # Get all other loopback devices
            for loopback in self.audio.get_loopback_device_info_generator():
                if default_speakers["name"] not in loopback["name"]:
                    speakers.append((
                        loopback["index"],
                        loopback["name"],
                        loopback["maxInputChannels"],
                        int(loopback["defaultSampleRate"])
                    ))
            
            return speakers
        except OSError as e:
            self._log(f"WASAPI error: {str(e)}")
            return []
    
    def set_callback(self, callback):
        self._callback = callback
    
    def _log(self, message):
        if self._callback:
            self._callback(message)

    def start_recording_speakers(self, device_index, channels, sample_rate):
        """Start recording from speakers"""
        if self.recording:
            return False
            
        self.recording = True
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"speakers_{timestamp}.wav"
        
        def record_thread():
            wave_file = None
            stream = None
            
            try:
                wave_file = wave.open(filename, 'wb')
                wave_file.setnchannels(channels)
                wave_file.setsampwidth(pyaudio.get_sample_size(pyaudio.paInt16))
                wave_file.setframerate(sample_rate)

                def callback(in_data, frame_count, time_info, status):
                    if status:
                        self._log(f"Stream status: {status}")
                    wave_file.writeframes(in_data)
                    return (in_data, pyaudio.paContinue)
                
                stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=channels,
                    rate=sample_rate,
                    frames_per_buffer=self.CHUNK,
                    input=True,
                    input_device_index=device_index,
                    stream_callback=callback
                )
                
                self._log(f"Recording system audio to {filename}")
                
                while self.recording:
                    time.sleep(0.1)
                
            except Exception as e:
                self._log(f"Error recording speakers: {str(e)}")
                self.recording = False
            finally:
                if stream:
                    stream.stop_stream()
                    stream.close()
                if wave_file:
                    wave_file.close()
                    if not self.recording:  # If recording was stopped due to error
                        try:
                            os.remove(filename)
                        except:
                            pass
                    else:
                        self._log(f"Recording saved to: {filename}")
        
        threading.Thread(target=record_thread).start()
        return True
    
    def start_recording_microphone(self, device_index, channels):
        """Start recording from microphone"""
        if self.recording:
            return False
            
        self.recording = True
        self.frames = []
        self.current_channels = channels
        
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
                
                self._log(f"Recording started with {channels} channel(s) at {self.RATE}Hz")
                
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
        
        threading.Thread(target=record_thread).start()
        return True
    
    def stop_recording(self):
        if not self.recording:
            return False
        self.recording = False
        return True
    
    def save_microphone_recording(self):
        if not self.frames:
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f'mic_recording_{timestamp}.wav'
        
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
    
    def __del__(self):
        self.audio.terminate()

# ... rest of the code (AudioRecorderFrame and AudioRecorderApp) remains the same ...

# ... rest of the code (AudioRecorderFrame and AudioRecorderApp) remains the same ...

# ... rest of the code (AudioRecorderFrame and AudioRecorderApp) remains the same ...

class AudioRecorderFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Audio Recorder', size=(800, 500))
        
        self.recorder = AudioRecorder()
        self.recorder.set_callback(self.log_message)
        
        self.init_ui()
        self.populate_devices()
        self.log_message("Application started")
        
    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create ListCtrl for logging
        self.log_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.BORDER_SUNKEN
        )
        self.log_list.InsertColumn(0, 'Timestamp', width=150)
        self.log_list.InsertColumn(1, 'Message', width=600)
        
        # Microphone device selection
        mic_sizer = wx.BoxSizer(wx.HORIZONTAL)
        mic_label = wx.StaticText(panel, label='Microphone:')
        self.mic_choice = wx.Choice(panel)
        mic_sizer.Add(mic_label, 0, wx.ALL | wx.CENTER, 5)
        mic_sizer.Add(self.mic_choice, 1, wx.ALL | wx.EXPAND, 5)
        
        # Speaker device selection
        speaker_sizer = wx.BoxSizer(wx.HORIZONTAL)
        speaker_label = wx.StaticText(panel, label='Speaker:')
        self.speaker_choice = wx.Choice(panel)
        speaker_sizer.Add(speaker_label, 0, wx.ALL | wx.CENTER, 5)
        speaker_sizer.Add(self.speaker_choice, 1, wx.ALL | wx.EXPAND, 5)
        
        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.record_mic_btn = wx.Button(panel, label='Record Microphone')
        self.record_speakers_btn = wx.Button(panel, label='Record Speakers')
        self.refresh_btn = wx.Button(panel, label='Refresh Devices')
        
        self.record_mic_btn.Bind(wx.EVT_BUTTON, self.on_record_mic)
        self.record_speakers_btn.Bind(wx.EVT_BUTTON, self.on_record_speakers)
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        
        button_sizer.Add(self.record_mic_btn, 1, wx.ALL | wx.EXPAND, 5)
        button_sizer.Add(self.record_speakers_btn, 1, wx.ALL | wx.EXPAND, 5)
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        
        # Add all to main sizer
        main_sizer.Add(self.log_list, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(mic_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(speaker_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        panel.SetSizer(main_sizer)
        
        self.CreateStatusBar()
        self.SetStatusText('Ready')
    
    def populate_devices(self):
        # Populate microphones
        self.mic_choice.Clear()
        self.microphones = self.recorder.get_microphones()
        
        if not self.microphones:
            self.log_message("No microphone devices found!")
            self.record_mic_btn.Disable()
        else:
            for i, name, channels in self.microphones:
                self.mic_choice.Append(f'{i}:{name} ({channels}ch)')
            self.mic_choice.SetSelection(0)
            self.record_mic_btn.Enable()
        
        # Populate speakers
        self.speaker_choice.Clear()
        self.speakers = self.recorder.get_speakers()
        
        if not self.speakers:
            self.log_message("No speaker devices found!")
            self.record_speakers_btn.Disable()
        else:
            for i, name, channels, rate in self.speakers:
                self.speaker_choice.Append(f'{i}:{name} ({channels}ch, {rate}Hz)')
            self.speaker_choice.SetSelection(0)
            self.record_speakers_btn.Enable()
    
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
    
    def on_record_mic(self, event):
        if not self.recorder.recording:
            device_info = self.microphones[self.mic_choice.GetSelection()]
            if self.recorder.start_recording_microphone(device_info[0], device_info[2]):
                self.record_mic_btn.SetLabel('Stop Recording')
                self.record_speakers_btn.Disable()
                self.SetStatusText('Recording from microphone...')
                self.log_message(f"Started recording from: {device_info[1]}")
        else:
            self.recorder.stop_recording()
            filename = self.recorder.save_microphone_recording()
            if filename:
                self.log_message(f"Recording saved to: {filename}")
            self.record_mic_btn.SetLabel('Record Microphone')
            self.record_speakers_btn.Enable()
            self.SetStatusText('Ready')
    
    def on_record_speakers(self, event):
        if not self.recorder.recording:
            device_info = self.speakers[self.speaker_choice.GetSelection()]
            if self.recorder.start_recording_speakers(device_info[0], device_info[2], device_info[3]):
                self.record_speakers_btn.SetLabel('Stop Recording')
                self.record_mic_btn.Disable()
                self.SetStatusText('Recording system audio...')
                self.log_message(f"Started recording from: {device_info[1]}")
        else:
            self.recorder.stop_recording()
            self.record_speakers_btn.SetLabel('Record Speakers')
            self.record_mic_btn.Enable()
            self.SetStatusText('Ready')

class AudioRecorderApp(wx.App):
    def OnInit(self):
        frame = AudioRecorderFrame()
        frame.Show()
        return True

if __name__ == '__main__':
    app = AudioRecorderApp()
    app.MainLoop()
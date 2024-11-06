import wx
import pyaudio
import wave
from os.path import join
from datetime import datetime
import threading
import os
out_dir='output'
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
        """Get list of available microphone devices with their channel info"""
        microphones = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            channels = int(device_info['maxInputChannels'])
            # Filter for microphone devices
            if (channels > 0 and 
                ('mic' in device_info['name'].lower() or
                 'microphone' in device_info['name'].lower() or
                 device_info['name'].lower().startswith('input') or
                 'audio input' in device_info['name'].lower())):
                microphones.append((i, device_info['name'], channels))
                
        if not microphones:  # If no specific microphones found, return all input devices
            for i in range(self.audio.get_device_count()):
                device_info = self.audio.get_device_info_by_index(i)
                channels = int(device_info['maxInputChannels'])
                if channels > 0:
                    microphones.append((i, device_info['name'], channels))
                    
        return microphones
    
    def set_callback(self, callback):
        """Set callback function for logging"""
        self._callback = callback
    
    def _log(self, message):
        """Internal logging method"""
        if self._callback:
            self._callback(message)
    
    def start_recording(self, device_index, channels):
        """Start recording from specified device with correct channel count"""
        if self.recording:
            return False
            
        self.recording = True
        self.frames = []
        self.current_channels = channels  # Store for saving
        
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
        global out_dir
        """Stop recording and save the file"""
        if not self.recording:
            return None
            
        self.recording = False
        
        if not self.frames:
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = join(out_dir,   f'micrecording_{timestamp}.wav')
        
        try:
            wf = wave.open(filename, 'wb')
            wf.setnchannels(self.current_channels)  # Use detected channels
            wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
            wf.setframerate(self.RATE)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            return filename
        except Exception as e:
            self._log(f"Error saving recording: {str(e)}")
            return None
    
    def __del__(self):
        """Cleanup"""
        self.audio.terminate()

class AudioRecorderFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Audio Recorder', size=(600, 400))
        
        # Initialize recorder
        self.recorder = AudioRecorder()
        self.recorder.set_callback(self.log_message)
        
        self.init_ui()
        self.populate_devices()
        self.log_message("Application started")
        
    def init_ui(self):
        """Initialize the user interface"""
        # Create main panel
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create ListCtrl for logging
        self.log_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.BORDER_SUNKEN
        )
        self.log_list.InsertColumn(0, 'Timestamp', width=150)
        self.log_list.InsertColumn(1, 'Message', width=400)
        
        # Add device selection
        device_sizer = wx.BoxSizer(wx.HORIZONTAL)
        device_label = wx.StaticText(panel, label='Microphone:')
        self.device_choice = wx.Choice(panel)
        device_sizer.Add(device_label, 0, wx.ALL | wx.CENTER, 5)
        device_sizer.Add(self.device_choice, 1, wx.ALL | wx.EXPAND, 5)
        self.device_choice.Bind(wx.EVT_CHOICE, self.on_device_change)
        
        # Create record button
        self.record_btn = wx.Button(panel, label='Record Microphone')
        self.record_btn.Bind(wx.EVT_BUTTON, self.on_record)
        
        # Add refresh button for devices
        self.refresh_btn = wx.Button(panel, label='Refresh Devices')
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        
        # Add buttons to horizontal sizer
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.Add(self.record_btn, 1, wx.ALL | wx.EXPAND, 5)
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        
        # Add widgets to main sizer
        main_sizer.Add(self.log_list, 1, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(device_sizer, 0, wx.ALL | wx.EXPAND, 5)
        main_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 5)
        
        panel.SetSizer(main_sizer)
        
        # Add status bar
        self.CreateStatusBar()
        self.SetStatusText('Ready')
        
    def on_device_change(self, event):
        """Handle device choice change"""
        selection = self.device_choice.GetSelection()
        if selection >= 0:
            device_info = self.devices[selection]
            self.log_message(f"Selected device: {device_info[1]} ({device_info[2]} channels)")
    
    def populate_devices(self):
        """Populate the device choice with available microphones"""
        self.device_choice.Clear()
        self.devices = self.recorder.get_microphones()
        
        if not self.devices:
            self.log_message("No microphone devices found!")
            self.record_btn.Disable()
            return
            
        for i, name, channels in self.devices:
            self.device_choice.Append(f'{i}:{name} ({channels}ch)')
        
        self.device_choice.SetSelection(0)
        self.record_btn.Enable()
    
    def on_refresh(self, event):
        """Handle refresh button click"""
        self.log_message("Refreshing device list...")
        self.populate_devices()
        self.log_message("Device list updated")
    
    def log_message(self, message):
        """Add a message to the log list"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        index = self.log_list.GetItemCount()
        self.log_list.InsertItem(index, timestamp)
        self.log_list.SetItem(index, 1, message)
        self.log_list.EnsureVisible(index)
    
    def on_record(self, event):
        """Handle record button click"""
        if not self.recorder.recording:
            selection = self.device_choice.GetSelection()
            device_info = self.devices[selection]
            device_index = device_info[0]
            channels = device_info[2]
            
            if self.recorder.start_recording(device_index, channels):
                self.record_btn.SetLabel('Stop Recording')
                self.SetStatusText('Recording...')
                self.log_message(f"Started recording from: {device_info[1]} ({channels} channels)")
        else:
            self.SetStatusText('Stopping...')
            filename = self.recorder.stop_recording()
            if filename:
                self.log_message(f"Recording saved to: {filename}")
            self.record_btn.SetLabel('Record Microphone')
            self.SetStatusText('Ready')

class AudioRecorderApp(wx.App):
    def OnInit(self):
        frame = AudioRecorderFrame()
        frame.Show()
        return True

if __name__ == '__main__':
    app = AudioRecorderApp()
    app.MainLoop()
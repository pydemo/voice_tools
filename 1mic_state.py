import wx
import threading
import time
import sounddevice as sd

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Microphone Monitor', size=(400, 200))
        self.panel = wx.Panel(self)
        
        # Create vertical sizer
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create device selection dropdown
        self.device_label = wx.StaticText(self.panel, label="Select Microphone:")
        sizer.Add(self.device_label, 0, wx.ALL, 5)
        
        # Get input devices (microphones)
        devices = sd.query_devices()
        self.input_devices = [(i, dev) for i, dev in enumerate(devices) 
                            if dev['max_input_channels'] > 0]
        
        device_names = [f"{dev['name']} (Ch: {dev['max_input_channels']})" 
                       for _, dev in self.input_devices]
        
        self.device_choice = wx.Choice(self.panel, choices=device_names)
        if device_names:
            self.device_choice.SetSelection(0)
        self.device_choice.Bind(wx.EVT_CHOICE, self.on_device_change)
        sizer.Add(self.device_choice, 0, wx.EXPAND | wx.ALL, 5)
        
        # Add status displays
        self.volume_text = wx.StaticText(self.panel, label="Volume: ---")
        self.mute_indicator = wx.StaticText(self.panel, label="State: Unknown")
        self.mute_indicator.SetForegroundColour(wx.RED)
        
        sizer.Add(self.volume_text, 0, wx.ALL, 5)
        sizer.Add(self.mute_indicator, 0, wx.ALL, 5)
        
        self.panel.SetSizer(sizer)
        
        # Initialize monitoring flag and current device
        self.is_monitoring = True
        self.current_device_id = self.input_devices[0][0] if self.input_devices else None
        
        # Start monitoring thread if we have devices
        if self.current_device_id is not None:
            self.monitor_thread = threading.Thread(target=self.monitor_microphone, daemon=True)
            self.monitor_thread.start()
        else:
            self.volume_text.SetLabel("No microphone devices found")
            self.mute_indicator.SetLabel("Please check your audio settings")
        
        # Center the window
        self.Center()
        
        # Bind close event
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Show the frame
        self.Show()
    
    def monitor_microphone(self):
        CHUNK_SIZE = 1024
        while self.is_monitoring:
            try:
                with sd.InputStream(device=self.current_device_id, 
                                  channels=1, 
                                  samplerate=44100,
                                  blocksize=CHUNK_SIZE) as stream:
                    while self.is_monitoring:
                        data, overflowed = stream.read(CHUNK_SIZE)
                        volume_norm = float(abs(data).mean())
                        
                        # Check if there's any signal (arbitrary threshold)
                        is_active = volume_norm > 0.001
                        
                        wx.CallAfter(self.update_display, volume_norm, is_active)
                        
                        time.sleep(0.1)  # Update 10 times per second
                        
            except Exception as e:
                print(f"Error monitoring device: {e}")
                wx.CallAfter(self.update_error, str(e))
                time.sleep(1)  # Wait before retrying
    
    def update_display(self, volume, is_active):
        # Update volume level (convert to dB for better representation)
        volume_db = 20 * (volume + 1e-10)  # Add small number to avoid log(0)
        volume_percent = min(100, max(0, int(volume_db * 100)))
        self.volume_text.SetLabel(f"Volume: {volume_percent}%")
        
        # Update activity state
        if is_active:
            self.mute_indicator.SetLabel("State: ACTIVE")
            self.mute_indicator.SetForegroundColour(wx.GREEN)
        else:
            self.mute_indicator.SetLabel("State: SILENT")
            self.mute_indicator.SetForegroundColour(wx.RED)
    
    def update_error(self, error_msg):
        self.volume_text.SetLabel("Error")
        self.mute_indicator.SetLabel(f"Error: {error_msg}")
        self.mute_indicator.SetForegroundColour(wx.RED)
    
    def on_device_change(self, event):
        selected_idx = self.device_choice.GetSelection()
        if selected_idx != wx.NOT_FOUND:
            self.current_device_id = self.input_devices[selected_idx][0]
            print(f"Selected device id: {self.current_device_id}")
    
    def on_close(self, event):
        self.is_monitoring = False
        time.sleep(0.6)  # Give thread time to clean up
        self.Destroy()

if __name__ == '__main__':
    app = wx.App()
    frame = MainFrame()
    app.MainLoop()
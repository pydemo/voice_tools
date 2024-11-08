import wx
import win32gui
import win32con
import threading
import time

class MainFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='PhoneLink Monitor', size=(300, 200))
        self.panel = wx.Panel(self)
        
        # Create status text
        self.status_text = wx.StaticText(self.panel, label="Monitoring for PhoneLink...", pos=(20, 20))
        
        # Create toggle button
        self.toggle_btn = wx.Button(self.panel, label="Stop Monitoring", pos=(20, 50))
        self.toggle_btn.Bind(wx.EVT_BUTTON, self.on_toggle)
        
        # Initialize monitoring flag
        self.is_monitoring = True
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_windows, daemon=True)
        self.monitor_thread.start()
        
        # Center the window
        self.Center()
        
        # Show the frame
        self.Show()
        
    def on_toggle(self, event):
        self.is_monitoring = not self.is_monitoring
        if self.is_monitoring:
            self.toggle_btn.SetLabel("Stop Monitoring")
            self.status_text.SetLabel("Monitoring for PhoneLink...")
        else:
            self.toggle_btn.SetLabel("Start Monitoring")
            self.status_text.SetLabel("Monitoring stopped")
    
    def bring_to_front(self):
        # Bring this window to front
        if self.IsIconized():
            self.Iconize(False)
        self.Raise()
        self.SetFocus()
    
    def monitor_windows(self):
        while True:
            if self.is_monitoring:
                try:
                    # Get the foreground window
                    hwnd = win32gui.GetForegroundWindow()
                    title = win32gui.GetWindowText(hwnd)
                    
                    # Check if PhoneLink is in the title
                    if 'Phone Link' in title:
                        # Use CallAfter to safely update GUI from another thread
                        wx.CallAfter(self.bring_to_front)
                        wx.CallAfter(self.status_text.SetLabel, f"PhoneLink detected: {title}")
                    
                except Exception as e:
                    print(f"Error: {e}")
            
            # Sleep to prevent high CPU usage
            time.sleep(0.5)

if __name__ == '__main__':
    app = wx.App()
    frame = MainFrame()
    app.MainLoop()
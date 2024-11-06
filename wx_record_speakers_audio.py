import wx
import pyaudiowpatch
import wave
import time
from datetime import datetime
import threading

class AudioRecorder:
    def __init__(self, callback=None):
        self.is_recording = False
        self.wave_file = None
        self.stream = None
        self.audio = None
        self.callback = callback
        self.current_device = None

    def get_available_speakers(self):
        speakers = []
        with pyaudiowpatch.PyAudio() as p:
            try:
                wasapi_info = p.get_host_api_info_by_type(pyaudiowpatch.paWASAPI)
                default_speakers = p.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
                
                # Get all loopback devices
                for loopback in p.get_loopback_device_info_generator():
                    speakers.append({
                        'name': loopback['name'],
                        'index': loopback['index'],
                        'channels': loopback['maxInputChannels'],
                        'rate': int(loopback['defaultSampleRate'])
                    })
            except OSError:
                if self.callback:
                    self.callback("WASAPI not available on the system")
        return speakers

    def start_recording(self, device_info, filename):
        if self.is_recording:
            return

        self.is_recording = True
        self.current_device = device_info
        
        def record_thread():
            try:
                self.audio = pyaudiowpatch.PyAudio()
                self.wave_file = wave.open(filename, 'wb')
                self.wave_file.setnchannels(device_info['channels'])
                self.wave_file.setsampwidth(pyaudiowpatch.get_sample_size(pyaudiowpatch.paInt16))
                self.wave_file.setframerate(device_info['rate'])

                def callback(in_data, frame_count, time_info, status):
                    if self.is_recording:
                        self.wave_file.writeframes(in_data)
                        return (in_data, pyaudiowpatch.paContinue)
                    return (None, pyaudiowpatch.paComplete)

                self.stream = self.audio.open(
                    format=pyaudiowpatch.paInt16,
                    channels=device_info['channels'],
                    rate=device_info['rate'],
                    frames_per_buffer=512,
                    input=True,
                    input_device_index=device_info['index'],
                    stream_callback=callback
                )

                if self.callback:
                    self.callback(f"Started recording from: {device_info['name']}")

                while self.is_recording:
                    time.sleep(0.1)

            except Exception as e:
                if self.callback:
                    self.callback(f"Recording error: {str(e)}")
                self.stop_recording()

        threading.Thread(target=record_thread, daemon=True).start()

    def stop_recording(self):
        if not self.is_recording:
            return

        self.is_recording = False
        
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
            
        if self.callback:
            self.callback("Recording stopped")

class AudioRecorderFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Audio Recorder', size=(600, 400))
        self.recorder = AudioRecorder(callback=self.log_message)
        self.init_ui()
        
    def init_ui(self):
        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        # Speakers dropdown
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        speaker_label = wx.StaticText(panel, label="Select Speaker:")
        self.speaker_choice = wx.Choice(panel)
        hbox1.Add(speaker_label, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        hbox1.Add(self.speaker_choice, 1)
        vbox.Add(hbox1, 0, wx.ALL | wx.EXPAND, 5)
        
        # Record button
        self.record_btn = wx.Button(panel, label="Start Recording")
        self.record_btn.Bind(wx.EVT_BUTTON, self.on_record)
        vbox.Add(self.record_btn, 0, wx.ALL | wx.EXPAND, 5)
        
        # Log list
        self.log_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
        self.log_list.InsertColumn(0, "Time", width=100)
        self.log_list.InsertColumn(1, "Message", width=450)
        vbox.Add(self.log_list, 1, wx.ALL | wx.EXPAND, 5)
        
        panel.SetSizer(vbox)
        
        # Populate speakers
        self.populate_speakers()
        
    def populate_speakers(self):
        self.speakers = self.recorder.get_available_speakers()
        self.speaker_choice.Clear()
        for speaker in self.speakers:
            self.speaker_choice.Append(speaker['name'])
        if self.speaker_choice.GetCount() > 0:
            self.speaker_choice.SetSelection(0)
            
    def log_message(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        index = self.log_list.GetItemCount()
        self.log_list.InsertItem(index, timestamp)
        self.log_list.SetItem(index, 1, message)
        self.log_list.EnsureVisible(index)
        
    def on_record(self, event):
        if not self.recorder.is_recording:
            if self.speaker_choice.GetSelection() < 0:
                self.log_message("Please select a speaker first")
                return
                
            selected_speaker = self.speakers[self.speaker_choice.GetSelection()]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
            
            self.recorder.start_recording(selected_speaker, filename)
            self.record_btn.SetLabel("Stop Recording")
        else:
            self.recorder.stop_recording()
            self.record_btn.SetLabel("Start Recording")

def main():
    app = wx.App()
    frame = AudioRecorderFrame()
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()
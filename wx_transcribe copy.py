import wx
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import threading
import os
import sys
from datetime import datetime

class AudioTranscriber:
    def __init__(self):
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model = None
        self.processor = None
        self.pipe = None
        
    def initialize_model(self, model_id="openai/whisper-large-v3"):
        """Initialize the transcription model"""
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id, 
            torch_dtype=self.torch_dtype, 
            low_cpu_mem_usage=True, 
            use_safetensors=True, 
            cache_dir="cache"
        )
        self.model.to(self.device)
        
        self.processor = AutoProcessor.from_pretrained(model_id)
        
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            torch_dtype=self.torch_dtype,
            device=self.device
        )
    
    def transcribe(self, audio_file, progress_callback=None):
        """Transcribe the audio file"""
        if self.pipe is None:
            raise RuntimeError("Model not initialized. Call initialize_model first.")
            
        if progress_callback:
            progress_callback(0, "Starting transcription...")
            
        result = self.pipe(audio_file)
        
        if progress_callback:
            progress_callback(100, "Transcription complete!")
            
        return result["text"]

class TranscriptionFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Audio Transcription Tool', size=(800, 600))
        self.transcriber = AudioTranscriber()
        
        # Get the directory where the script is located
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        # Create base transcriptions directory
        self.transcriptions_dir = os.path.join(self.script_dir, "transcriptions")
        os.makedirs(self.transcriptions_dir, exist_ok=True)
        
        self.init_ui()
        
        # Start model initialization in a separate thread
        self.init_model_thread = threading.Thread(target=self.init_model)
        self.init_model_thread.start()

    def init_ui(self):
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # File picker section
        file_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.file_picker = wx.FilePickerCtrl(
            panel, 
            message="Choose an audio file",
            wildcard="Audio files (*.mp3;*.wav)|*.mp3;*.wav",
            style=wx.FLP_DEFAULT_STYLE | wx.FLP_USE_TEXTCTRL,
            path=os.path.join(self.script_dir, "")
        )
        file_sizer.Add(self.file_picker, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        
        # Model selection dropdown
        model_sizer = wx.BoxSizer(wx.HORIZONTAL)
        model_label = wx.StaticText(panel, label="Model:")
        self.model_choice = wx.Choice(panel, choices=["whisper-large-v3"])
        self.model_choice.SetSelection(0)
        model_sizer.Add(model_label, flag=wx.ALL|wx.CENTER, border=5)
        model_sizer.Add(self.model_choice, flag=wx.ALL, border=5)
        
        # Transcribe button
        self.transcribe_btn = wx.Button(panel, label='Transcribe')
        self.transcribe_btn.Bind(wx.EVT_BUTTON, self.on_transcribe)
        
        # Progress bar
        self.progress = wx.Gauge(panel, range=100, size=(250, 25))
        
        # Status text
        self.status_text = wx.StaticText(panel, label="Ready")
        
        # Transcription output
        self.output_ctrl = wx.TextCtrl(
            panel, 
            style=wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL,
            size=(-1, 200)
        )
        
        # Add everything to the main sizer
        main_sizer.Add(file_sizer, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(model_sizer, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.transcribe_btn, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.progress, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.status_text, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.output_ctrl, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        
        panel.SetSizer(main_sizer)
        
        # Initially disable the transcribe button until model is loaded
        self.transcribe_btn.Enable(False)

    def get_relative_path(self, full_path):
        """Get path relative to script directory"""
        try:
            rel_path = os.path.relpath(full_path, self.script_dir)
            # If the path starts with '..' it means it's outside script_dir
            if rel_path.startswith('..'):
                return None
            return rel_path
        except ValueError:
            # This happens when paths are on different drives
            return None

    def save_transcription(self, audio_file, transcription):
        """Save transcription to file maintaining directory structure"""
        # Get relative path of audio file
        rel_path = self.get_relative_path(audio_file)
        
        if rel_path:
            # Get the directory structure from the relative path
            rel_dir = os.path.dirname(rel_path)
            
            # Create the same directory structure in transcriptions
            if rel_dir:
                save_dir = os.path.join(self.transcriptions_dir, rel_dir)
                os.makedirs(save_dir, exist_ok=True)
            else:
                save_dir = self.transcriptions_dir
        else:
            # If file is outside script directory, just use base transcriptions dir
            save_dir = self.transcriptions_dir
            
        # Get the audio filename without extension
        audio_basename = os.path.splitext(os.path.basename(audio_file))[0]
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{audio_basename}_{timestamp}.txt"
        
        # Full path to save file
        save_path = os.path.join(save_dir, filename)
        
        # Save transcription
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(f"Source: {audio_file}\n\n")  # Add source file info
            f.write(transcription)
            
        return save_path
        
    def init_model(self):
        """Initialize the model in a separate thread"""
        try:
            wx.CallAfter(self.status_text.SetLabel, "Initializing model...")
            self.transcriber.initialize_model()
            wx.CallAfter(self.on_model_loaded)
        except Exception as e:
            wx.CallAfter(self.status_text.SetLabel, f"Error loading model: {str(e)}")
            
    def on_model_loaded(self):
        """Called when model is finished loading"""
        self.status_text.SetLabel("Model loaded - ready to transcribe")
        self.transcribe_btn.Enable(True)
        
    def update_progress(self, progress, message):
        """Update the progress bar and status message"""
        wx.CallAfter(self.progress.SetValue, progress)
        wx.CallAfter(self.status_text.SetLabel, message)
        
    def on_transcribe(self, event):
        """Handle transcribe button click"""
        audio_file = self.file_picker.GetPath()
        if not audio_file:
            wx.MessageBox("Please select an audio file first", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        self.transcribe_btn.Enable(False)
        self.output_ctrl.SetValue("")
        
        # Start transcription in a separate thread
        thread = threading.Thread(
            target=self.run_transcription,
            args=(audio_file,)
        )
        thread.start()
        
    def run_transcription(self, audio_file):
        """Run the transcription in a separate thread"""
        try:
            transcription = self.transcriber.transcribe(
                audio_file,
                progress_callback=self.update_progress
            )
            
            # Save transcription to file
            save_path = self.save_transcription(audio_file, transcription)
            
            # Create relative path for display
            try:
                display_path = os.path.relpath(save_path, self.script_dir)
            except ValueError:
                display_path = save_path
            
            # Update UI with transcription and save location
            def update_ui():
                self.output_ctrl.SetValue(transcription)
                self.status_text.SetLabel(f"Transcription saved to: {display_path}")
            
            wx.CallAfter(update_ui)
            
        except Exception as e:
            wx.CallAfter(
                wx.MessageBox,
                f"Transcription error: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
        finally:
            wx.CallAfter(self.transcribe_btn.Enable, True)

def main():
    app = wx.App()
    frame = TranscriptionFrame()
    frame.Show()
    app.MainLoop()

if __name__ == '__main__':
    main()
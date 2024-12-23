import wx
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
import threading
import os
import sys
from datetime import datetime
from abc import ABC, abstractmethod

class BaseTranscriber(ABC):
    """Abstract base class for transcribers"""
    @abstractmethod
    def initialize_model(self, model_id):
        pass
    
    @abstractmethod
    def transcribe(self, audio_file, progress_callback=None):
        pass
    
    @abstractmethod
    def get_available_models(self):
        pass
        
    @property
    @abstractmethod
    def name(self):
        pass

class HuggingFaceTranscriber(BaseTranscriber):
    def __init__(self):
        self.device = "cuda:0" if torch.cuda.is_available() else "cpu"
        self.torch_dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model = None
        self.processor = None
        self.pipe = None
        
    @property
    def name(self):
        return "HuggingFace Transformers"
        
    def get_available_models(self):
        return [
            "openai/whisper-large-v3",
            "openai/whisper-medium",
            "openai/whisper-small",
            "openai/whisper-base"
        ]
        
    def initialize_model(self, model_id):
        self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_id, 
            torch_dtype=self.torch_dtype, 
            low_cpu_mem_usage=True, 
            use_safetensors=True, 
            cache_dir="cache"
        )
        self.model.to(self.device)
        
        self.processor = AutoProcessor.from_pretrained(model_id)
        forced_decoder_ids = self.processor.get_decoder_prompt_ids(language="en", task="transcribe")
        
        
        self.pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model,
            tokenizer=self.processor.tokenizer,
            feature_extractor=self.processor.feature_extractor,
            torch_dtype=self.torch_dtype,
            device=self.device,
            generate_kwargs={
                "forced_decoder_ids": forced_decoder_ids,
                "task": "transcribe"
            },
            return_timestamps=True
        )
    
    def transcribe(self, audio_file, progress_callback=None):
        if self.pipe is None:
            raise RuntimeError("Model not initialized. Call initialize_model first.")
            
        if progress_callback:
            progress_callback(0, "Starting transcription...")
            
        result = self.pipe(audio_file)
        
        if progress_callback:
            progress_callback(100, "Transcription complete!")
            
        return result["text"]

class TranscriberRegistry:
    """Registry for available transcriber types"""
    def __init__(self):
        self.transcribers = {}
        
    def register(self, transcriber_class):
        instance = transcriber_class()
        self.transcribers[instance.name] = transcriber_class
        
    def get_transcriber(self, name):
        if name not in self.transcribers:
            raise ValueError(f"Unknown transcriber type: {name}")
        return self.transcribers[name]()
        
    def get_available_transcribers(self):
        return list(self.transcribers.keys())

class TranscriptionFrame(wx.Frame):
    def __init__(self):
        super().__init__(parent=None, title='Audio Transcription Tool', size=(800, 600))
        
        # Initialize transcriber registry
        self.registry = TranscriberRegistry()
        self.registry.register(HuggingFaceTranscriber)
        
        # Initial transcriber
        self.transcriber = None
        
        # Get the directory where the script is located
        if getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
            
        # Create base transcriptions directory
        self.transcriptions_dir = os.path.join(self.script_dir, "transcriptions")
        os.makedirs(self.transcriptions_dir, exist_ok=True)
        
        self.init_ui()

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
        
        # Transcriber and model selection
        selector_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Transcriber type dropdown
        transcriber_label = wx.StaticText(panel, label="Transcriber:")
        self.transcriber_choice = wx.Choice(panel, choices=self.registry.get_available_transcribers())
        self.transcriber_choice.SetSelection(0)
        self.transcriber_choice.Bind(wx.EVT_CHOICE, self.on_transcriber_changed)
        
        # Model selection dropdown
        model_label = wx.StaticText(panel, label="Model:")
        self.model_choice = wx.Choice(panel, choices=[])
        self.model_choice.Bind(wx.EVT_CHOICE, self.on_model_changed)
        
        selector_sizer.Add(transcriber_label, flag=wx.ALL|wx.CENTER, border=5)
        selector_sizer.Add(self.transcriber_choice, flag=wx.ALL, border=5)
        selector_sizer.Add(model_label, flag=wx.ALL|wx.CENTER, border=5)
        selector_sizer.Add(self.model_choice, flag=wx.ALL, border=5)
        
        # Transcribe button
        self.transcribe_btn = wx.Button(panel, label='Transcribe')
        self.transcribe_btn.Bind(wx.EVT_BUTTON, self.on_transcribe)
        self.transcribe_btn.Enable(False)
        
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
        main_sizer.Add(selector_sizer, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.transcribe_btn, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.progress, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.status_text, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.output_ctrl, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)
        
        panel.SetSizer(main_sizer)
        
        # Initialize first transcriber
        self.on_transcriber_changed(None)

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
            f.write(f"Source: {audio_file}\n")
            f.write(f"Model: {self.model_choice.GetString(self.model_choice.GetSelection())}\n\n")
            f.write(transcription)
            
        return save_path

    def on_transcriber_changed(self, event):
        """Handle transcriber type selection"""
        transcriber_name = self.transcriber_choice.GetString(self.transcriber_choice.GetSelection())
        
        # Create new transcriber instance
        self.transcriber = self.registry.get_transcriber(transcriber_name)
        
        # Update model choices
        self.model_choice.SetItems(self.transcriber.get_available_models())
        self.model_choice.SetSelection(0)
        
        # Initialize model in background
        self.transcribe_btn.Enable(False)
        self.status_text.SetLabel("Initializing model...")
        
        thread = threading.Thread(target=self.init_model)
        thread.start()

    def on_model_changed(self, event):
        """Handle model selection change"""
        self.transcribe_btn.Enable(False)
        self.status_text.SetLabel("Initializing model...")
        
        thread = threading.Thread(target=self.init_model)
        thread.start()

    def init_model(self):
        """Initialize the model in a separate thread"""
        try:
            wx.CallAfter(self.status_text.SetLabel, "Initializing model...")
            model_id = self.model_choice.GetString(self.model_choice.GetSelection())
            self.transcriber.initialize_model(model_id)
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
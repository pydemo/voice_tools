import wx
import os
import sys
import threading
from datetime import datetime
from abc import ABC, abstractmethod
args=sys.argv
DEFAULT_FILE_NAME = None
if args[1]:
    DEFAULT_FILE_NAME = args[1]
    assert os.path.exists(DEFAULT_FILE_NAME), "Speech File not found"

def show_import_progress():
    """Function to show a progress dialog during imports and run imports sequentially in the main thread."""
    app = wx.App()

    # Create the progress dialog in the main thread
    progress_dialog = wx.ProgressDialog(
        "Loading Modules", "Initializing imports...",
        maximum=100, parent=None, style=wx.PD_APP_MODAL | wx.PD_AUTO_HIDE
    )



    progress_dialog.Update(20, "Loading torch...")
    import torch

    progress_dialog.Update(30, "Loading transformers...")
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline

    progress_dialog.Update(40, "Loading threading...")
    import threading

    progress_dialog.Update(50, "Loading OS...")
    import os

    progress_dialog.Update(60, "Loading sys...")
    import sys

    progress_dialog.Update(70, "Loading datetime...")
    from datetime import datetime

    progress_dialog.Update(80, "Loading abstract base class...")
    from abc import ABC, abstractmethod

    progress_dialog.Update(90, "Loading torchaudio...")
    import torchaudio

    progress_dialog.Update(100, "Finalizing imports...")
    import subprocess
    import platform

    # Close the progress dialog
    progress_dialog.Destroy()
    
    app.MainLoop()


class BaseTranscriber(ABC):
    """Abstract base class for transcribers"""
    @abstractmethod
    def initialize_model(self, model_id):
        pass

    @abstractmethod
    def transcribe(self, audio_streamer, progress_callback=None):
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
            }
        )

    def transcribe(self, audio_streamer, progress_callback=None):
        if self.pipe is None:
            raise RuntimeError("Model not initialized. Call initialize_model first.")

        transcription = ""
        processed_chunks = 0

        if progress_callback:
            progress_callback(0, "Starting transcription...")

        # Load audio to get total chunks
        audio_streamer.load_audio()
        total_chunks = audio_streamer.get_total_chunks()

        for chunk in audio_streamer.stream():
            # Ensure chunk is single-channel and resampled to 16 kHz
            chunk = audio_streamer.to_mono_and_resample(chunk, target_sample_rate=16000)

            # Transcribe the chunk without sampling_rate argument
            result = self.pipe(chunk.squeeze().numpy())

            # Append the text
            transcription += result["text"] + " "
            processed_chunks += 1

            # Update progress
            progress = int((processed_chunks / total_chunks) * 100)
            if progress_callback:
                progress_callback(progress, "Transcribing...")

            # Yield the transcription so far
            yield transcription.strip()

        if progress_callback:
            progress_callback(100, "Transcription complete!")

class AudioStreamer:
    """Class to stream audio in chunks"""
    def __init__(self, audio_file, chunk_length_s=10.0):
        self.audio_file = audio_file
        self.chunk_length_s = chunk_length_s  # in seconds
        self.sample_rate = None
        self.audio_data = None

    def load_audio(self):
        self.audio_data, self.sample_rate = torchaudio.load(self.audio_file)

    def to_mono_and_resample(self, chunk, target_sample_rate=16000):
        """Convert audio chunk to mono and resample if necessary."""
        # Convert to mono by averaging channels if multi-channel
        if chunk.shape[0] > 1:
            chunk = torch.mean(chunk, dim=0, keepdim=True)
        # Resample if the sample rate does not match the target
        if self.sample_rate != target_sample_rate:
            resampler = torchaudio.transforms.Resample(
                orig_freq=self.sample_rate, new_freq=target_sample_rate
            )
            chunk = resampler(chunk)
        return chunk

    def get_total_chunks(self):
        num_samples = self.audio_data.shape[1]
        chunk_size = int(self.sample_rate * self.chunk_length_s)
        total_chunks = (num_samples + chunk_size - 1) // chunk_size
        return total_chunks

    def stream(self):
        if self.audio_data is None:
            self.load_audio()
        num_samples = self.audio_data.shape[1]
        chunk_size = int(self.sample_rate * self.chunk_length_s)
        for start in range(0, num_samples, chunk_size):
            end = min(start + chunk_size, num_samples)
            chunk = self.audio_data[:, start:end]
            yield chunk


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
        super().__init__(parent=None, title='Audio Transcription Tool', size=(800, 600),
                         style=wx.DEFAULT_FRAME_STYLE | wx.STAY_ON_TOP)

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
        self.file_picker.SetPath(DEFAULT_FILE_NAME)
        self.play_audio_btn = wx.Button(panel, label='Play Audio')
        self.play_audio_btn.Bind(wx.EVT_BUTTON, self.on_play_audio)
        file_sizer.Add(self.play_audio_btn, flag=wx.ALL, border=5)

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

        self.copy_btn = wx.Button(panel, label='Copy')
        self.copy_btn.Bind(wx.EVT_BUTTON, self.on_copy)
        self.copy_btn.Enable(False)  # Initially disabled until transcription is available


        # Progress bar
        self.progress = wx.Gauge(panel, range=100, size=(250, 25))

        # Status text
        self.status_text = wx.StaticText(panel, label="Ready")

        # Transcription output
        self.output_ctrl = wx.TextCtrl(
            panel,
            style=wx.TE_MULTILINE|wx.TE_READONLY|wx.TE_WORDWRAP,
            size=(-1, 200)
        )

        # Add everything to the main sizer
        main_sizer.Add(file_sizer, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(selector_sizer, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.transcribe_btn, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.copy_btn, flag=wx.EXPAND | wx.ALL, border=5)
        main_sizer.Add(self.progress, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.status_text, flag=wx.EXPAND|wx.ALL, border=5)
        main_sizer.Add(self.output_ctrl, proportion=1, flag=wx.EXPAND|wx.ALL, border=5)

        panel.SetSizer(main_sizer)

        # Initialize first transcriber
        self.on_transcriber_changed(None)
    def on_play_audio(self, event):
        """Handle play audio button click"""
        audio_file = self.file_picker.GetPath()
        if not audio_file:
            wx.MessageBox("Please select an audio file first", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.play_audio(audio_file) 
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
    def on_copy(self, event):
            """Copy transcription text to the system clipboard"""
            transcription_text = self.output_ctrl.GetValue()
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(transcription_text))
                wx.TheClipboard.Close()
                wx.MessageBox("Transcription copied to clipboard", "Info", wx.OK | wx.ICON_INFORMATION)
        
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

    def _save_transcription(self, audio_file, transcription):
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

    def save_transcription(self, audio_file, transcription):
        """Save transcription to the same directory as the source audio file with the same base name and .txt extension."""
        # Get the directory and base name of the audio file
        audio_dir = os.path.dirname(audio_file)
        audio_basename = os.path.splitext(os.path.basename(audio_file))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create the transcription filename with .txt extension
        filename = f"{audio_basename}_{timestamp}.txt"

        # Full path to save the transcription file in the same directory as the audio file
        save_path = os.path.join(audio_dir, filename)

        # Save transcription to the specified path
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
        wx.CallAfter(self.on_transcribe, None)

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
        self.progress.SetValue(0)
        self.status_text.SetLabel("Starting transcription...")

        # Start transcription in a separate thread
        thread = threading.Thread(
            target=self.run_transcription,
            args=(audio_file,)
        )
        thread.start()

    def run_transcription(self, audio_file):
        """Run the transcription in a separate thread"""
        try:
            audio_streamer = AudioStreamer(audio_file)
            transcription = ""

            # Start transcribing
            for partial_transcription in self.transcriber.transcribe(
                audio_streamer,
                progress_callback=self.update_progress
            ):
                # Update the transcription text
                transcription = partial_transcription
                # Update the output control
                def update_ui():
                    self.output_ctrl.SetValue(transcription)
                    self.copy_btn.Enable(True)
                wx.CallAfter(update_ui)

            # Save transcription to file
            save_path = self.save_transcription(audio_file, transcription)

            # Create relative path for display
            try:
                display_path = os.path.relpath(save_path, self.script_dir)
            except ValueError:
                display_path = save_path

            # Update UI with transcription and save location
            def update_ui_final():
                self.output_ctrl.SetValue(transcription)
                self.status_text.SetLabel(f"Transcription saved to: {display_path}")
                self.progress.SetValue(100)

            wx.CallAfter(update_ui_final)

        except Exception as e:
            wx.CallAfter(
                wx.MessageBox,
                f"Transcription error: {str(e)}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )
            print(e)
        finally:
            wx.CallAfter(self.transcribe_btn.Enable, True)

def main():
    app = wx.App()

    # Initialize the main frame after progress is done
    frame = TranscriptionFrame()
    frame.Show()
    app.MainLoop()




if __name__ == "__main__":
    show_import_progress()  # Show progress and import modules
    import torch
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    import torchaudio
    import subprocess
    import platform
    import os
    import sys
    from datetime import datetime
    from abc import ABC, abstractmethod    
    main() 

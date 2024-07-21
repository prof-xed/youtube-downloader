import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import yt_dlp as youtube_dl
import imageio_ffmpeg as ffmpeg

class VideoComponent(tk.Frame):
    def __init__(self, master, video_info, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.video_info = video_info
        self.create_widgets()

    def create_widgets(self):
        self.quality_var = tk.StringVar(self)
        qualities = sorted(set(self.video_info['qualities']), reverse=True)
        default_quality = next((q for q in qualities if q >= 1080), qualities[-1] if qualities else "N/A")
        self.quality_var.set(default_quality)
        quality_menu = tk.OptionMenu(self, self.quality_var, default_quality, *qualities)
        quality_menu.grid(row=0, column=0, padx=10, pady=5)

        self.extension_var = tk.StringVar(self)
        extensions = sorted(set(self.video_info['extensions']))
        default_extension = "mp4" if "mp4" in extensions else (extensions[0] if extensions else "N/A")
        self.extension_var.set(default_extension)
        extension_menu = tk.OptionMenu(self, self.extension_var, default_extension, *extensions)
        extension_menu.grid(row=0, column=1, padx=10, pady=5)

        tk.Label(self, text=self.video_info['title']).grid(row=0, column=2, padx=10, pady=5)

class YouTubeDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Video Downloader")
        self.geometry("800x600")  # Make the window wider
        self.create_widgets()

    def create_widgets(self):
        tk.Label(self, text="YouTube URL:").grid(row=0, column=0, padx=10, pady=10)
        self.url_entry = tk.Entry(self, width=50)
        self.url_entry.grid(row=0, column=1, padx=10, pady=10)
        self.url_entry.bind('<Return>', self.update_dropdowns)

        self.fetch_button = tk.Button(self, text="Fetch Formats", command=self.update_dropdowns)
        self.fetch_button.grid(row=1, column=0, columnspan=2, pady=10)

        self.canvas = tk.Canvas(self)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=2, column=0, columnspan=2, sticky="nsew")
        self.scrollbar.grid(row=2, column=2, sticky="ns")

        self.download_button = tk.Button(self, text="Download", command=self.download_video)
        self.download_button.grid(row=3, column=0, columnspan=2, pady=20)

        self.progress = ttk.Progressbar(self, orient="horizontal", length=400, mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=2, pady=10)

    def fetch_formats(self, url):
        ydl_opts = {'quiet': True}
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            formats = info_dict.get('formats', [])
            video_qualities = sorted(set(f['height'] for f in formats if f.get('height')), reverse=True)
            extensions = sorted(set(f['ext'] for f in formats if f.get('ext')))
            return video_qualities, extensions, info_dict

    def update_dropdowns(self, event=None):
        url = self.url_entry.get()
        if url:
            ydl_opts = {'quiet': True}
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                for widget in self.scrollable_frame.winfo_children():
                    widget.destroy()
                if 'entries' in info_dict:  # It's a playlist
                    for index, entry in enumerate(info_dict['entries']):
                        entry_formats = entry.get('formats', [])
                        video_qualities = sorted(set(f['height'] for f in entry_formats if f.get('height')), reverse=True)
                        extensions = sorted(set(f['ext'] for f in entry_formats if f.get('ext')))
                        video_info = {
                            'title': entry.get('title', f'Video {index + 1}'),
                            'qualities': video_qualities,
                            'extensions': extensions
                        }
                        video_component = VideoComponent(self.scrollable_frame, video_info)
                        video_component.grid(row=index, column=0, padx=10, pady=5)
                else:  # It's a single video
                    formats = info_dict.get('formats', [])
                    video_qualities = sorted(set(f['height'] for f in formats if f.get('height')), reverse=True)
                    extensions = sorted(set(f['ext'] for f in formats if f.get('ext')))
                    video_info = {
                        'title': info_dict.get('title', 'Video'),
                        'qualities': video_qualities,
                        'extensions': extensions
                    }
                    video_component = VideoComponent(self.scrollable_frame, video_info)
                    video_component.grid(row=0, column=0, padx=10, pady=5)

    def download_video(self, event=None):
        url = self.url_entry.get()
        if not url:
            messagebox.showwarning("Warning", "Please enter a URL.")
            return

        save_path = filedialog.askdirectory()
        if not save_path:
            messagebox.showwarning("Warning", "Please select a save location.")
            return

        ffmpeg_path = ffmpeg.get_ffmpeg_exe()
        ydl_opts = {
            'ffmpeg_location': ffmpeg_path,
            'noplaylist': False  # Set to False to download the entire playlist
        }

        total_videos = len(self.scrollable_frame.winfo_children())
        self.progress["maximum"] = total_videos
        self.progress["value"] = 0

        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, VideoComponent):
                quality = widget.quality_var.get()
                extension = widget.extension_var.get()
                title = widget.video_info['title']
                if quality == "N/A" or extension == "N/A":
                    messagebox.showwarning("Warning", f"Invalid quality or extension for {title}.")
                    continue
                ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[ext={extension}]'
                ydl_opts['outtmpl'] = f'{save_path}/{title}.%(ext)s'
                try:
                    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                    self.progress["value"] += 1
                    self.update_idletasks()
                except Exception as e:
                    messagebox.showerror("Error", str(e))
                    return

        messagebox.showinfo("Success", "Download completed!")

if __name__ == "__main__":
    app = YouTubeDownloader()
    app.mainloop()

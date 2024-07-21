import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import yt_dlp as youtube_dl
import imageio_ffmpeg as ffmpeg
import os
import sys
import re
import requests
from io import BytesIO
import webbrowser
import threading

class VideoComponent(tk.Frame):
    def __init__(self, master, video_info, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.video_info = video_info
        self.create_widgets()

    def create_widgets(self):
        self.download_var = tk.BooleanVar(value=True)
        self.download_check = tk.Checkbutton(self, variable=self.download_var)
        self.download_check.grid(row=0, column=0, padx=10, pady=5, sticky="w")

        self.quality_var = tk.StringVar(self)
        qualities = sorted(set(self.video_info['qualities']), reverse=True)
        default_quality = next((q for q in qualities if q >= 1080), qualities[-1] if qualities else "N/A")
        self.quality_var.set(default_quality)
        quality_menu = tk.OptionMenu(self, self.quality_var, default_quality, *qualities)
        quality_menu.grid(row=0, column=1, padx=10, pady=5, sticky="w")

        self.extension_var = tk.StringVar(self)
        extensions = sorted(set(self.video_info['extensions']))
        default_extension = "mp4" if "mp4" in extensions else (extensions[0] if extensions else "N/A")
        self.extension_var.set(default_extension)
        extension_menu = tk.OptionMenu(self, self.extension_var, default_extension, *extensions)
        extension_menu.grid(row=0, column=2, padx=10, pady=5, sticky="w")

        self.thumbnail_label = tk.Label(self)
        self.thumbnail_label.grid(row=0, column=3, padx=10, pady=5, sticky="w")
        self.load_thumbnail()

        self.title_label = tk.Label(self, text=self.video_info['title']+"                     ")
        self.title_label.grid(row=0, column=4, padx=10, pady=5, sticky="ew")

    def load_thumbnail(self):
        thumbnail_url = self.video_info.get('thumbnail')
        if thumbnail_url:
            response = requests.get(thumbnail_url)
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            img.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(img)
            self.thumbnail_label.config(image=photo)
            self.thumbnail_label.image = photo

        self.after(0, self.animate_text)

    def animate_text(self):
        text = self.title_label.cget("text")
        if len(text) > 20:  # Adjust the length as needed
            def scroll_text():
                current_text = self.title_label.cget("text")
                new_text = current_text[1:] + current_text[0]
                self.title_label.config(text=new_text)
                self.after(500, scroll_text)  # Adjust the speed as needed
            scroll_text()

class YouTubeDownloader(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Video Downloader")
        self.geometry("800x600")
        self.create_widgets()

        # # Add the icon
        # self.icon_image = tk.PhotoImage(file=f"{os.path.dirname(os.path.abspath(__file__))}\icon.ico")
        # self.iconphoto(False, self.icon_image)

    def create_widgets(self):
        tk.Label(self, text="YouTube URL:").grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.url_entry = tk.Entry(self, width=50)
        self.url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        self.url_entry.bind('<Return>', self.start_fetch_formats_thread)

        self.toggle_all_var = tk.BooleanVar(value=True)
        self.toggle_all_check = tk.Checkbutton(self, text="Toggle All", variable=self.toggle_all_var, command=self.toggle_all_checkboxes)
        self.toggle_all_check.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.reverse_selection_button = tk.Button(self, text="Reverse Selection", command=self.reverse_selection)
        self.reverse_selection_button.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.fetch_button = tk.Button(self, text="Fetch Formats", command=self.start_fetch_formats_thread)
        self.fetch_button.grid(row=1, column=3, pady=10, padx=10, sticky="e")

        self.audio_only_var = tk.BooleanVar()
        self.audio_only_check = tk.Checkbutton(self, text="Download Audio Only", variable=self.audio_only_var)
        self.audio_only_check.grid(row=1, column=2, padx=10, pady=10, sticky="e")

        self.about_me_button = tk.Button(self, text="Prof-xed", command=self.open_github)
        self.about_me_button.grid(row=1, column=4, padx=10, pady=10, sticky="e")

        self.loading_label = tk.Label(self, text="Loading...", fg="red")
        self.loading_label.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        self.loading_label.grid_remove()

        self.canvas = tk.Canvas(self)
        self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas)

        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=2, column=0, columnspan=5, sticky="nsew")
        self.scrollbar.grid(row=2, column=5, sticky="ns")

        self.download_button = tk.Button(self, text="Download", command=self.start_download_thread)
        self.download_button.grid(row=3, column=0, columnspan=5, pady=20, padx=10, sticky="ew")

        self.progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress.grid(row=4, column=0, columnspan=5, pady=10, padx=10, sticky="ew")

        self.columnconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        self.bind("<Button-1>", self.unfocus_text)

    def start_fetch_formats_thread(self, event=None):
        self.loading_label.grid()
        fetch_thread = threading.Thread(target=self.update_dropdowns)
        fetch_thread.start()

    def fetch_formats(self, url):
        ydl_opts = {'quiet': True}
        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=False)
                formats = info_dict.get('formats', [])
                video_qualities = sorted(set(f['height'] for f in formats if f.get('height')), reverse=True)
                extensions = sorted(set(f['ext'] for f in formats if f.get('ext')))
                return video_qualities, extensions, info_dict
        except Exception as e:
            messagebox.showerror("Error", f"Failed to fetch formats: {e}")
            return [], [], {}

    def update_dropdowns(self, event=None):
        url = self.url_entry.get()
        if url:
            video_qualities, extensions, info_dict = self.fetch_formats(url)
            self.after(0, self.update_dropdowns_ui, video_qualities, extensions, info_dict)

    def update_dropdowns_ui(self, video_qualities, extensions, info_dict):
        self.loading_label.grid_remove()
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        if 'entries' in info_dict:  # It's a playlist
            for index, entry in enumerate(info_dict['entries']):
                entry_formats = entry.get('formats', [])
                video_qualities = sorted(set(f['height'] for f in entry_formats if f.get('height')), reverse=True)
                extensions = sorted(set(f['ext'] for f in entry_formats if f.get('ext')))
                video_info = { 'title': entry.get('title', f'Video {index + 1}'), 'qualities': video_qualities, 'extensions': extensions, 'thumbnail': entry.get('thumbnail') }
                video_component = VideoComponent(self.scrollable_frame, video_info)
                video_component.grid(row=index, column=0, padx=10, pady=5, sticky="w")
        else:  # It's a single video
            video_info = { 'title': info_dict.get('title', 'Video'), 'qualities': video_qualities, 'extensions': extensions, 'thumbnail': info_dict.get('thumbnail') }
            video_component = VideoComponent(self.scrollable_frame, video_info)
            video_component.grid(row=0, column=0, padx=10, pady=5, sticky="w")

    def sanitize_filename(self, filename):
        return re.sub(r'[<>:"/\\|?*]', '_', filename)

    def toggle_all_checkboxes(self):
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, VideoComponent):
                widget.download_var.set(self.toggle_all_var.get())

    def reverse_selection(self):
        for widget in self.scrollable_frame.winfo_children():
            if isinstance(widget, VideoComponent):
                widget.download_var.set(not widget.download_var.get())

    def start_download_thread(self):
        download_thread = threading.Thread(target=self.download_video)
        download_thread.start()

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
        ydl_opts = { 'ffmpeg_location': ffmpeg_path, 'noplaylist': False }

        with youtube_dl.YoutubeDL({'quiet': True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            
            if 'entries' in info_dict:  # It's a playlist
                self.download_playlist(info_dict, save_path, ydl_opts)
            else:  # It's a single video
                self.download_single_video(info_dict, save_path, ydl_opts)

    def download_single_video(self, info_dict, save_path, ydl_opts):
        video_info = { 'title': info_dict.get('title', 'Video'), 'qualities': sorted(set(f['height'] for f in info_dict['formats'] if f.get('height')), reverse=True), 'extensions': sorted(set(f['ext'] for f in info_dict['formats'] if f.get('ext')))}
        quality = video_info['qualities'][0] if video_info['qualities'] else "N/A"
        extension = video_info['extensions'][0] if video_info['extensions'] else "N/A"
        title = video_info['title']
        if quality == "N/A" or extension == "N/A":
            messagebox.showwarning("Warning", f"Invalid quality or extension for {title}.")
            return
        if self.audio_only_var.get():
            ydl_opts['format'] = 'bestaudio/best'
        else:
            ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[ext={extension}]'
        ydl_opts['outtmpl'] = f'{save_path}/{self.sanitize_filename(title)}.{extension}'

        try:
            with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                ydl.download([info_dict['webpage_url']])
            messagebox.showinfo("Success", "Download completed!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def download_playlist(self, info_dict, save_path, ydl_opts):
        playlist_name = info_dict.get('title', 'Playlist')
        sanitized_playlist_name = self.sanitize_filename(playlist_name)
        playlist_path = os.path.join(save_path, sanitized_playlist_name)
        os.makedirs(playlist_path, exist_ok=True)

        selected_videos = [widget for widget in self.scrollable_frame.winfo_children() if isinstance(widget, VideoComponent) and widget.download_var.get()]
        total_videos = len(selected_videos)
        self.progress["maximum"] = total_videos
        self.progress["value"] = 0

        for i, widget in enumerate(selected_videos):
            quality = widget.quality_var.get()
            extension = widget.extension_var.get()
            title = widget.video_info['title']
            if quality == "N/A" or extension == "N/A":
                messagebox.showwarning("Warning", f"Invalid quality or extension for {title}.")
                continue
            if self.audio_only_var.get():
                ydl_opts['format'] = 'bestaudio/best'
            else:
                ydl_opts['format'] = f'bestvideo[height<={quality}]+bestaudio/best[ext={extension}]'
            ydl_opts['outtmpl'] = f'{playlist_path}/{self.sanitize_filename(title)}.{extension}'

            try:
                with youtube_dl.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([info_dict['entries'][i]['webpage_url']])

                self.progress["value"] += 1
                self.update_idletasks()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

        messagebox.showinfo("Success", "Download completed!")

    def open_github(self):
        webbrowser.open("https://github.com/prof-xed")

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def unfocus_text(self, event):
        if event.widget != self.url_entry:
            self.url_entry.selection_clear()
            self.focus()

if __name__ == "__main__":
    app = YouTubeDownloader()

    app.mainloop()

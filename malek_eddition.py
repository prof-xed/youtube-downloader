import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import yt_dlp as youtube_dl
import imageio_ffmpeg as ffmpeg
import os
import re
import requests
from io import BytesIO
import webbrowser
import threading
import queue  # Import the queue module

# Set the theme
ctk.set_appearance_mode("Dark")  # Set to dark mode
ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue"

class VideoComponent(ctk.CTkFrame):
    def __init__(self, master, video_info, audio_only_var, sanitize_filename, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.video_info = video_info
        self.audio_only_var = audio_only_var
        self.sanitize_filename = sanitize_filename
        self.configure(fg_color="black", width=800)  # Set frame background color and fixed width
        self.create_widgets()

    def create_widgets(self):
        # Components
        self.download_var = ctk.BooleanVar(value=True)
        self.download_check = ctk.CTkCheckBox(self, variable=self.download_var, text="")
        self.download_check.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        self.quality_var = ctk.StringVar(self)
        qualities = sorted(set(self.video_info['qualities']), reverse=True)
        default_quality = next((q for q in qualities if q >= 1080), qualities[-1] if qualities else "N/A")
        self.quality_var.set(default_quality)
        quality_menu = ctk.CTkOptionMenu(self, variable=self.quality_var, values=[str(q) for q in qualities])
        quality_menu.grid(row=1, column=1, padx=10, pady=5, sticky="ew")

        self.extension_var = ctk.StringVar(self)
        extensions = sorted(set(self.video_info['extensions']))
        default_extension = "mp4" if "mp4" in extensions else (extensions[0] if extensions else "N/A")
        self.extension_var.set(default_extension)
        extension_menu = ctk.CTkOptionMenu(self, variable=self.extension_var, values=extensions)
        extension_menu.grid(row=1, column=2, padx=10, pady=5, sticky="ew")

        self.thumbnail_label = ctk.CTkLabel(self, text=None)
        self.thumbnail_label.grid(row=1, column=3, padx=10, pady=5, sticky="ew")
        self.load_thumbnail()

        # Directly add the title Label to the grid
        self.title_label = ctk.CTkLabel(self, text=str(self.video_info['title']).ljust(30), font=("Helvetica", 12), text_color="white")
        self.title_label.grid(row=1, column=4, padx=10, pady=5, sticky="ew")

        self.size_label = ctk.CTkLabel(self, text=self.get_file_size(), font=("Helvetica", 10), text_color="green")
        self.size_label.grid(row=1, column=5, padx=10, pady=5, sticky="ew")

        self.download_button = ctk.CTkButton(self, text="Download", command=self.download_video, font=("Helvetica", 10), fg_color="#3192F9", hover_color="lightblue")
        self.download_button.grid(row=1, column=6, padx=10, pady=5, sticky="ew")

        # Configure column widths
        self.columnconfigure(0, weight=1, minsize=50)  # Select
        self.columnconfigure(1, weight=1, minsize=80)  # Quality
        self.columnconfigure(2, weight=1, minsize=80)  # Extension
        self.columnconfigure(3, weight=1, minsize=100) # Thumbnail
        self.columnconfigure(4, weight=3, minsize=200) # Title
        self.columnconfigure(5, weight=1, minsize=80)  # Size
        self.columnconfigure(6, weight=1, minsize=100) # Download

    def load_thumbnail(self):
        thumbnail_url = self.video_info.get('thumbnail')
        if thumbnail_url:
            response = requests.get(thumbnail_url)
            img_data = response.content
            img = Image.open(BytesIO(img_data))
            img.thumbnail((100, 100))
            photo = ImageTk.PhotoImage(img)
            self.thumbnail_label.configure(image=photo)
            self.thumbnail_label.image = photo

        self.after(0, self.animate_text)

    def animate_text(self):
        text = self.title_label.cget("text")
        if len(text) > 30:  # Adjust the length as needed
            def scroll_text():
                current_text = self.title_label.cget("text")
                new_text = current_text[1:] + current_text[0]
                self.title_label.configure(text=new_text)
                self.after(500, scroll_text)  # Adjust the speed as needed
            scroll_text()

    def get_file_size(self):
        selected_quality = int(self.quality_var.get())
        selected_extension = self.extension_var.get()
        formats = self.video_info.get('formats', [])

        for f in formats:
            if f.get('height') == selected_quality and f.get('ext') == selected_extension:
                size = f.get('filesize', 0)
                if size:
                    return f"{size / (1024 * 1024):.2f} MB"
        return "N/A"

    def download_video(self):
        url = self.video_info['webpage_url']
        save_path = filedialog.askdirectory()
        if not save_path:
            messagebox.showwarning("Warning", "Please select a save location.")
            return

        ffmpeg_path = ffmpeg.get_ffmpeg_exe()
        ydl_opts = {'ffmpeg_location': ffmpeg_path, 'noplaylist': True}

        quality = self.quality_var.get()
        extension = self.extension_var.get()
        title = self.video_info['title']
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
                ydl.download([url])
            messagebox.showinfo("Success", "Download completed!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

class YouTubeDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Video Downloader")
        self.geometry("1100x600")
        self.configure(fg_color="black")  # Set main window background color
        self.progress_queue = queue.Queue()  # Initialize the progress_queue
        self.create_widgets()
        self.process_queue()  # Start processing the queue

    def create_widgets(self):
        ctk.CTkLabel(self, text="YouTube URL:", font=("Helvetica", 12)).grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.url_entry = ctk.CTkEntry(self, width=50, font=("Helvetica", 12))
        self.url_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.fetch_button = ctk.CTkButton(self, text="Fetch Formats", command=self.start_fetch_formats_thread, font=("Helvetica", 12), fg_color="#3192F9", hover_color="lightblue")
        self.fetch_button.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        self.toggle_all_var = ctk.BooleanVar(value=True)
        self.toggle_all_check = ctk.CTkCheckBox(self, text="Toggle All", variable=self.toggle_all_var, command=self.toggle_all_checkboxes, font=("Helvetica", 12))
        self.toggle_all_check.grid(row=1, column=0, padx=10, pady=10, sticky="w")

        self.reverse_selection_button = ctk.CTkButton(self, text="Reverse Selection", command=self.reverse_selection, font=("Helvetica", 12), fg_color="#3192F9", hover_color="lightblue")
        self.reverse_selection_button.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        self.audio_only_var = ctk.BooleanVar()
        self.audio_only_check = ctk.CTkCheckBox(self, text="Download Audio Only", variable=self.audio_only_var, font=("Helvetica", 12))
        self.audio_only_check.grid(row=1, column=2, padx=10, pady=10, sticky="e")

        self.about_me_button = ctk.CTkButton(self, text="Prof-xed", command=self.open_github, font=("Helvetica", 12), fg_color="#3192F9", hover_color="lightblue")
        self.about_me_button.grid(row=1, column=3, padx=10, pady=10, sticky="e")

        self.loading_label = ctk.CTkLabel(self, text="Loading...", text_color="red", font=("Helvetica", 12))
        self.loading_label.grid(row=1, column=1, padx=10, pady=10, sticky="w")
        self.loading_label.grid_remove()

        # Labels for each component
        headers = ["Select", "Quality", "Extension", "Thumbnail", "Title", "Size", "Download"]
        for col, header in enumerate(headers):
            ctk.CTkLabel(self, text=header, font=("Helvetica", 10), text_color="white").grid(row=2, column=col, padx=10, pady=5, sticky="w")

        self.canvas = ctk.CTkCanvas(self, bg="black")  # Set canvas background color
        self.scrollbar = ctk.CTkScrollbar(self, command=self.canvas.yview)
        self.scrollable_frame = ctk.CTkFrame(self.canvas, fg_color="black")  # Set scrollable frame background color
        self.scrollable_frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=3, column=0, columnspan=7, sticky="nsew")
        self.scrollbar.grid(row=3, column=7, sticky="ns")

        self.download_button = ctk.CTkButton(self, text="Download All", command=self.start_download_thread, font=("Helvetica", 12), fg_color="#3192F9", hover_color="lightblue")
        self.download_button.grid(row=4, column=3, pady=20, padx=10, sticky="ew")
        self.progress = ctk.CTkProgressBar(self, orientation="horizontal", mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=7, pady=10, padx=10, sticky="ew")
        self.progress.set(0)

        self.columnconfigure(0, weight=1, minsize=50)  # Select
        self.columnconfigure(1, weight=1, minsize=80)  # Quality
        self.columnconfigure(2, weight=1, minsize=80)  # Extension
        self.columnconfigure(3, weight=1, minsize=100) # Thumbnail
        self.columnconfigure(4, weight=3, minsize=200) # Title
        self.columnconfigure(5, weight=1, minsize=80)  # Size
        self.columnconfigure(6, weight=1, minsize=100) # Download

        self.process_queue()  # Start processing the queue

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
                video_info = { 'title': entry.get('title', f'Video {index + 1}'), 'qualities': video_qualities, 'extensions': extensions, 'thumbnail': entry.get('thumbnail'), 'webpage_url': entry.get('webpage_url'), 'formats': entry_formats }
                video_component = VideoComponent(self.scrollable_frame, video_info, self.audio_only_var, self.sanitize_filename)
                video_component.grid(row=index + 1, column=0, padx=10, pady=5, sticky="ew")
        else:  # It's a single video
            video_info = { 'title': info_dict.get('title', 'Video'), 'qualities': video_qualities, 'extensions': extensions, 'thumbnail': info_dict.get('thumbnail'), 'webpage_url': info_dict.get('webpage_url'), 'formats': info_dict.get('formats', []) }
            video_component = VideoComponent(self.scrollable_frame, video_info, self.audio_only_var, self.sanitize_filename)
            video_component.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

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
        selected_videos = [widget for widget in self.scrollable_frame.winfo_children() if isinstance(widget, VideoComponent) and widget.download_var.get()]
        total_videos = len(selected_videos)

        if total_videos == 0:
            messagebox.showwarning("Warning", "Please make a selection of download.")
            return

        download_thread = threading.Thread(target=self.download_all_videos)
        download_thread.start()

    def download_all_videos(self, event=None):
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
        video_info = { 'title': info_dict.get('title', 'Video'), 'qualities': sorted(set(str(f['height']) for f in info_dict['formats'] if f.get('height')), reverse=True), 'extensions': sorted(set(f['ext'] for f in info_dict['formats'] if f.get('ext'))) }
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
            self.progress_queue.put(1)  # Put progress update in the queue
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
        self.progress.set(0)

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
                self.progress_queue.put(1 / total_videos)  # Put progress update in the queue
            except Exception as e:
                messagebox.showerror("Error", str(e))
                self.progress_queue.put(1 / total_videos)  # Put progress update in the queue

        messagebox.showinfo("Success", "Download completed!")

    def open_github(self):
        webbrowser.open("https://github.com/prof-xed")

    def on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def unfocus_text(self, event):
        if event.widget != self.url_entry:
            self.url_entry.selection_clear()
            self.focus()

    def process_queue(self):
        try:
            while True:
                progress_update = self.progress_queue.get_nowait()
                self.progress.set(self.progress.get() + progress_update)
                self.update_idletasks()
        except queue.Empty:
            pass
        self.after(100, self.process_queue)  # Check the queue every 100 ms

if __name__ == "__main__":
    app = YouTubeDownloader()
    app.mainloop()

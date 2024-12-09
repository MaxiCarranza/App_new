import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path


class FolderComparisonApp:

    DEFAULT_TEXT_1 = "Malla 1: "
    DEFAULT_TEXT_2 = "Malla 2: "

    def __init__(self, root_app: tk.Tk):
        self.root = root_app
        self.root.title("Comparador de mallas")
        self.root.geometry("400x250")

        self.path_foder1 = None
        self.path_foder2 = None

        # Labels to show selected files
        self.label_file1 = tk.Label(self.root, text=self.DEFAULT_TEXT_1 + "Sin seleccionar", wraplength=300)
        self.label_file1.pack(pady=10)

        self.label_file2 = tk.Label(self.root, text=self.DEFAULT_TEXT_2 + "Sin seleccionar", wraplength=300)
        self.label_file2.pack(pady=10)

        # Buttons for selecting files
        self.button_file1 = tk.Button(self.root, text="Seleccionar malla 1", command=self.select_file1)
        self.button_file1.pack(pady=5)

        self.button_file2 = tk.Button(self.root, text="Seleccionar malla 2", command=self.select_file2)
        self.button_file2.pack(pady=5)

        # Button to compare files
        self.button_compare = tk.Button(self.root, text="Comparar", command=self.compare_files, bg="#414bb2", fg="white", font=("Arial", 12, "bold"), width=15, height=2)
        self.button_compare.pack(pady=10)

        # Footer label
        self.footer_label = tk.Label(self.root, text="By Reliability Argentina", font=("Arial", 10, "italic"))
        self.footer_label.pack(side="bottom", anchor="se", padx=10, pady=5)

    def _selecion_complete(self):
        return False if (self.path_foder1 is None or self.path_foder2 is None) else True

    def select_file1(self):
        """Open file dialog to select the first file."""
        file1 = filedialog.askopenfilename(title="Seleccionar malla 1")
        if file1:
            self.path_foder1 = Path(file1)
            self.label_file1.config(text=self.DEFAULT_TEXT_1 + self.path_foder1.name)

    def select_file2(self):
        """Open file dialog to select the second file."""
        file2 = filedialog.askopenfilename(title="Seleccionar malla 2")
        if file2:
            self.path_foder2 = Path(file2)
            self.label_file2.config(text=self.DEFAULT_TEXT_2 + self.path_foder2.name)

    def compare_files(self):
        """Compare the selected files. Raise an error if not both files are selected."""

        if not self._selecion_complete():
            # Show error if any file is not selected
            messagebox.showerror("Error", "Se deben seleccionar ambas mallas para comparar")
            return

        file1 = self.label_file1.cget("text")
        file2 = self.label_file2.cget("text")

        msg = f"Se comparará:\nMalla 1: {self.path_foder1.name} \ncontra la Malla 2: {self.path_foder2.name}"
        return_option = messagebox.askyesno(title="Confirme accion", message=msg)

        # Proceed with the comparison (for now, just print a message)
        print("Comparando", file1, file2, return_option)


# Create the main window
root = tk.Tk()

# Create and run the application
app = FolderComparisonApp(root)

# Run the Tkinter event loop
root.mainloop()

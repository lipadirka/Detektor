'''

Приложение для детекции dxf рамок чертежей

'''

# Библиотеки
import os # Работа с системой 
import subprocess # Для запуска приложения конвертера ODAFileConverter 
import tkinter as tk # Создание интерфейса приложения
from tkinter import filedialog, messagebox # Для добавления всплывающих окон
import ezdxf # Работает с dxf файлами
import ttkbootstrap as tb # Для добавления разных стилей приложения
import itertools # перебор элементов по одному
import threading # для выполнение фоновых задач
from concurrent.futures import ThreadPoolExecutor # Пул потоков для параллельного выполнения задач 

# Импорт файла py, который обнаруживает рамки листов
from Proccess_detekt import layout_sheet

# Поиск приложения ODA file converter на пк
def foda_converter():
    possible_dirs = ["C:\\"]
    for root_dir in possible_dirs:
        for root, _, files in os.walk(root_dir):
            if "ODAFileConverter.exe" in files:
                return os.path.join(root, "ODAFileConverter.exe")
    return None



# Создание интерфейса и основных функций
class DXFdetekt:
    def __init__(self, master):
        # Создание окна приложения и кнопок
        self.master = master
        self.master.title("DWG Converter")
        self.master.geometry("300x300")
        self.master.resizable(False, False)  
       
        self.style = tb.Style("darkly")
        self.frame = tb.Frame(self.master, style="Dark.TFrame")
        self.frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.progress = tb.Progressbar(self.frame, mode="determinate", bootstyle="info")
        self.progress.pack(fill=tk.X, pady=5)
        
        self.btn_convert = tb.Button(self.frame, text="Конвертировать DWG в DXF", command=self.convert_dwg_dxf, bootstyle="primary")
        self.btn_convert.pack(fill=tk.X, pady=5)
    
        self.btn_detect_sheets = tb.Button(self.frame, text="Детекция листов", command=self.start_detection_thread, bootstyle="info")
        self.btn_detect_sheets.pack(fill=tk.X, pady=5)
    
    # Функция конвертации из dwg в dxf 
    def convert_dwg_dxf(self):
        oda_converter = foda_converter()
        if not oda_converter:
            messagebox.showerror("Ошибка", "ODA File Converter не найден!")
            return

        input_folder = filedialog.askdirectory(title="Выберите папку с DWG файлами")
        if not input_folder:
            return
    
        # Получение списка доступных dwg файлов
        dwg_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".dwg")]

        if not dwg_files:
            messagebox.showwarning("Не найдено", "В выбранной папке нет DWG файлов!")
            return

        # Визуализация полученных файлов
        file_list = "\n".join(dwg_files)
        messagebox.showinfo("Найденные файлы", f"Обнаружены следующие файлы:\n{file_list}")

        output_folder = filedialog.askdirectory(title="Выберите папку для сохранения DXF")
        
        # Авто настройка для приложения oda converter
        if not output_folder:
            return
        try:
            command = [
                f'"{oda_converter}"',
                f'"{input_folder}"',
                f'"{output_folder}"',
                "", "", "ACAD2010", "DXF", "0", "1"
            ]
            subprocess.run(" ".join(command), shell=True, check=True)
            messagebox.showinfo("Успешное выполнение", f"Файлы DWG сконвертированы в DXF в: {output_folder}")
        except subprocess.CalledProcessError as e:
            messagebox.showerror("Error", f"Не удалось конвертировать: {e}")
    
    # Функция запуски детекции в отдельном потоке
    def start_detection_thread(self):
        threading.Thread(target=self.detect_sheets, daemon=True).start()
    
    #  Функция детекции рамок листов 
    def detect_sheets(self):
        self.progress["value"] = 0
        self.progress.update()
        dxf_path = filedialog.askopenfilename(filetypes=[("DXF files", "*.dxf")])
        if not dxf_path:
            return

        try:
            doc = ezdxf.readfile(dxf_path)
        except ezdxf.DXFError as e:
            messagebox.showerror("Ошибка", f"Ошибка при загрузке DXF файла: {e}")
            return  

        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка при обработке DXF: {e}")
            return  

      
        layout_sheets = {}

        with ThreadPoolExecutor(max_workers=os.cpu_count()) as executor:
            results = executor.map(layout_sheet, doc.layouts)

        for layout, found_sheets in zip(doc.layouts, results):
            if found_sheets:
                layout_sheets[layout.name] = found_sheets

        self.progress["value"] = 100
        self.progress.update()
        self.master.after(0, self.show_results, layout_sheets, doc)

        
    # Вывод результатов детекции dxf файлов
    def show_results(self, layout_sheets, doc):
       
        if layout_sheets:
            message = "Обнаружены листы:\n\n"
            for layout_name, sheets in layout_sheets.items():
                message += f"Вкладка '{layout_name}': {len(sheets)} лист(ов)\n"
                for i, (fmt, w, h, _) in enumerate(sheets, start=1):
                    message += f"  {i}: {fmt} ({w:.2f} x {h:.2f}) мм\n"
                message += "\n"

            if messagebox.askyesno("Обнаружены листы", message + "\nСохранить в  формате (Не работает!) PDF?"):
                folder = filedialog.askdirectory(title="Выберите папку для сохранения в PDF формат")
                if folder:
                    self.save_to_pdf(doc, folder, layout_sheets)  
                else:
                    messagebox.showwarning("Отмена", "Сохранение PDF отменено.")
        else:
            messagebox.showwarning("Результат", "Листы не найдены.")
            
    
  
root = tb.Window(themename="darkly")
app = DXFdetekt(root)
root.mainloop()
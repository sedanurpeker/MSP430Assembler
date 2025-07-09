#!/usr/bin/env python3
import os
import struct
from typing import Tuple, Optional

try:
    import matplotlib.pyplot as plt
    from matplotlib.table import Table
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Matplotlib bulunamadı, metin tabanlı görselleştirme kullanılacak.")

class MSP430VirtualMemory:
    def __init__(self):
        self.memory = {
            'SFR': bytearray(0x200),    # 0x0000-0x01FF
            'PERIPH': bytearray(0x1A00), # 0x0200-0x1BFF
            'RAM': bytearray(0x800),    # 0x1C00-0x23FF
            'FLASH': bytearray(0xBBC0), # 0x4400-0xFFBF
            'VECTORS': bytearray(0x40)  # 0xFFC0-0xFFFF
        }
        self.region_ranges = {
            'SFR': (0x0000, 0x01FF),
            'PERIPH': (0x0200, 0x1BFF),
            'RAM': (0x1C00, 0x23FF),
            'FLASH': (0x4400, 0xFFBF),
            'VECTORS': (0xFFC0, 0xFFFF)
        }

    def get_memory_region(self, address: int) -> Tuple[str, int]:
        for region, (start, end) in self.region_ranges.items():
            if start <= address <= end:
                return region, address - start
        raise ValueError(f"Geçersiz adres: 0x{address:04X}")

    def write_memory(self, address: int, data: bytes) -> bool:
        try:
            region, offset = self.get_memory_region(address)
            end_offset = offset + len(data)
            if end_offset > len(self.memory[region]):
                print(f"HATA: {region} bölgesinde taşma, adres: 0x{address:04X}")
                return False
            self.memory[region][offset:end_offset] = data
            return True
        except ValueError as e:
            print(f"HATA: Bellek yazma: {e}")
            return False

    def read_memory(self, address: int, size: int) -> Optional[bytes]:
        try:
            region, offset = self.get_memory_region(address)
            return bytes(self.memory[region][offset:offset + size])
        except ValueError as e:
            print(f"HATA: Bellek okuma: {e}")
            return None

class MSP430ELFLoader:
    def __init__(self, memory: MSP430VirtualMemory):
        self.memory = memory

    def load_linked_elf(self, filename: str, text_base: int = 0x4400, data_base: int = 0x1C00) -> bool:
        if not os.path.exists(filename):
            print(f"HATA: '{filename}' dosyası bulunamadı.")
            return False

        print(f"ELF dosyası yükleniyor: {filename}")
        mode = None
        text_count = 0
        data_count = 0
        data_section_found = False

        with open(filename, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(".text Section"):
                    mode = 'text'
                    print(".text bölümü okunuyor")
                    continue
                elif line.startswith(".data Section"):
                    mode = 'data'
                    data_section_found = True
                    print(".data bölümü okunuyor")
                    continue
                elif line.startswith((".symtab", ".relocations")):
                    mode = None
                    continue
                if not line or line.startswith(("---", "Address", "Value", "Symbol", "Offset")):
                    continue

                if mode in ['text', 'data']:
                    if "|" in line:
                        parts = line.split("|")
                        if len(parts) >= 2:
                            try:
                                addr = int(parts[0].strip(), 16)
                                value = int(parts[1].strip(), 16)
                                target_addr = addr + (text_base if mode == 'text' else data_base)
                                data = struct.pack('<H', value)
                                if self.memory.write_memory(target_addr, data):
                                    print(f"{mode.upper()} girişi: 0x{target_addr:04X} -> 0x{value:04X}")
                                    if mode == 'text':
                                        text_count += 1
                                    else:
                                        data_count += 1
                                else:
                                    print(f"HATA: Adres 0x{target_addr:04X} yüklenemedi")
                            except ValueError:
                                print(f"UYARI: Satır işlenemedi: '{line}'")
                        else:
                            print(f"UYARI: Geçersiz satır formatı: '{line}'")

        if data_section_found and data_count == 0:
            print("UYARI: .data bölümü bulundu ama veri girişi yok!")

        print(f"Yükleme tamam: {text_count} .text, {data_count} .data girişi")
        return text_count > 0 or data_count > 0

class MSP430SimpleVisualizer:
    def __init__(self, memory: MSP430VirtualMemory):
        self.memory = memory
        self.colors = {
            'TEXT': '#d4edda',  # Yeşil
            'DATA': '#cce5ff',  # Mavi
            'VECTORS': '#f8d7da',  # Kırmızı
            'EMPTY': '#f0f0f0'  # Gri
        }

    def draw_memory(self, filename: str, text_start: int = 0x4400, text_end: int = 0x447F, 
                    data_start: int = 0x1C00, data_end: int = 0x23FF, filename_output: str = "memory_map.png"):
        if text_end < text_start or data_end < data_start:
            print("HATA: Geçersiz adres aralığı")
            return

        if not MATPLOTLIB_AVAILABLE:
            self._show_text_map(text_start, text_end, data_start, data_end)
            return

        print("Tablo görselleştiriliyor...")
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_title("MSP430 Bellek Haritası")
        ax.set_axis_off()

        table_data = []
        text_addresses = list(range(text_start, text_end + 1, 2))
        data_addresses = list(range(data_start, data_end + 1, 2))

        # Bellekten veri oku
        for addr in text_addresses:
            data = self.memory.read_memory(addr, 2)
            if data and data != b'\x00\x00':
                value = struct.unpack('<H', data)[0]
                table_data.append([f"0x{addr:04X}", f"0x{value:04X}", 'text', 'FLASH'])
                print(f"TEXT: 0x{addr:04X} -> 0x{value:04X}")

        for addr in data_addresses:
            data = self.memory.read_memory(addr, 2)
            if data and data != b'\x00\x00':
                value = struct.unpack('<H', data)[0]
                table_data.append([f"0x{addr:04X}", f"0x{value:04X}", 'data', 'RAM'])
                print(f"DATA: 0x{addr:04X} -> 0x{value:04X}")

        if not table_data:
            print("UYARI: Görselleştirilecek veri bulunamadı!")
            return

        table = Table(ax, bbox=[0.1, 0.1, 0.8, 0.8])
        table.set_fontsize(10)

        # Başlık
        table.add_cell(0, 0, 0.2, 0.1, text="Adres", loc='center', facecolor=self.colors['EMPTY'])
        table.add_cell(0, 1, 0.2, 0.1, text="Değer", loc='center', facecolor=self.colors['EMPTY'])
        table.add_cell(0, 2, 0.2, 0.1, text="Bölge", loc='center', facecolor=self.colors['EMPTY'])

        # Veriler
        for i, (addr, value, mode, region) in enumerate(table_data, 1):
            table.add_cell(i, 0, 0.2, 0.1, text=addr, loc='center')
            table.add_cell(i, 1, 0.2, 0.1, text=value, loc='center', facecolor=self.colors[mode.upper()])
            table.add_cell(i, 2, 0.2, 0.1, text=region, loc='center', facecolor=self.colors[mode.upper()])

        ax.add_table(table)
        plt.tight_layout()
        plt.savefig(filename_output, dpi=300)
        plt.close()
        print(f"Bellek görseli kaydedildi: {filename_output}")

    def _show_text_map(self, text_start: int, text_end: int, data_start: int, data_end: int):
        print("\nMSP430 BELLEK HARİTASI")
        addresses = list(range(text_start, text_end + 1, 2)) + list(range(data_start, data_end + 1, 2))
        found = False
        for addr in addresses:
            data = self.memory.read_memory(addr, 2)
            if data and data != b'\x00\x00':
                value = struct.unpack('<H', data)[0]
                region, _ = self.memory.get_memory_region(addr)
                print(f"Adres: 0x{addr:04X} | Değer: 0x{value:04X} | Bölge: {region}")
                found = True
        if not found:
            print("Veri bulunamadı.")

def main():
    elf_file = r"C:\Users\sedan\OneDrive\Masaüstü\Sistem\linked_output.elf"
    memory = MSP430VirtualMemory()
    loader = MSP430ELFLoader(memory)
    if loader.load_linked_elf(elf_file):
        visualizer = MSP430SimpleVisualizer(memory)
        visualizer.draw_memory(elf_file)
    else:
        print("HATA: Program yüklenemedi!")

if __name__ == "__main__":
    main()
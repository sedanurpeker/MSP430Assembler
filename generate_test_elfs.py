import os
import sys
os.chdir(r"C:\Users\sedan\OneDrive\Masaüstü\Sistem")
print(f"Çalışma dizini: {os.getcwd()}")
from test4 import assemble, create_object_file, pass1, pass2, opcode_table  # Gerekli fonksiyonları import et

# Debug fonksiyonu
def debug_create_object_file(machine_code, symbol_table, literals, relocation_entries, relocation_data, filename):
    """Debug amaçlı ELF oluşturucu"""
    print(f"🔍 Debug: ELF dosyası oluşturuluyor: {filename}")
    print(f"  Machine code: {len(machine_code)} entries")
    print(f"  Symbol table: {len(symbol_table)} entries")
    print(f"  Literals: {len(literals)} entries")
    print(f"  Relocation entries: {len(relocation_entries)} entries")
    
    # Orijinal create_object_file fonksiyonunu çağır
    try:
        result = create_object_file(machine_code, symbol_table, literals, relocation_entries, relocation_data, filename)
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"✅ {filename} oluşturuldu ({size} bytes)")
            return True
        else:
            print(f"❌ {filename} oluşturulamadı")
            return False
    except Exception as e:
        print(f"❌ create_object_file hatası: {e}")
        return False

# Özel assemble fonksiyonu
def debug_assemble(assembly_code, filename="input.asm"):
    """Debug amaçlı assemble fonksiyonu"""
    print(f"\n🔧 Debug Assemble: {filename}")
    
    lines = assembly_code.strip().split('\n')
    print(f"  Toplam satır: {len(lines)}")
    
    # Pass 1
    try:
        symbol_table = pass1(lines)
        print(f"  Pass1 tamamlandı - Symbol table: {symbol_table}")
    except Exception as e:
        print(f"  ❌ Pass1 hatası: {e}")
        return None
    
    # Pass 2
    try:
        machine_code, literals, relocation_entries, relocation_data = pass2(lines, symbol_table, opcode_table)
        print(f"  Pass2 tamamlandı - Machine code: {len(machine_code)} entries")
    except Exception as e:
        print(f"  ❌ Pass2 hatası: {e}")
        return None
    
    # ELF oluştur
    base_name = filename.replace('.asm', '')
    elf_filename = f"{base_name}.elf"
    
    success = debug_create_object_file(
        machine_code, symbol_table, literals, 
        relocation_entries, relocation_data, elf_filename
    )
    
    if success:
        # ELF dosyasını oku
        try:
            with open(elf_filename, 'rb') as f:
                elf_data = f.read()
            print(f"  ELF verisi okundu: {len(elf_data)} bytes")
            return machine_code, symbol_table, literals, relocation_entries, relocation_data, elf_data
        except Exception as e:
            print(f"  ❌ ELF okuma hatası: {e}")
            return machine_code, symbol_table, literals, relocation_entries, relocation_data, None
    else:
        return machine_code, symbol_table, literals, relocation_entries, relocation_data, None

# main.asm içeriği
main_code = """
.ref FUNC_MUL

.text
main:
    MOV #0x1234, R4        ; Immediate -> Register (literal test)
    MOV R4, &0x0200        ; Register -> Memory (direct adresleme)
    CMP &0x0200, R4        ; Memory -> Register karşılaştırması
    JZ EQUAL
    CALL #FUNC_MUL         ; Fonksiyon çağrısı (relocation)
EQUAL:
    BR EQUAL               ; Sonsuz döngü



"""

# utils.asm içeriği
utils_code = """
.text
FUNC_MUL:
    PUSH R5                ; Register yedekle
    MOV R4, R5             ; R4'ü R5'e kopyala
    ADD R4, R5             ; R5 = R4 + R4
    POP R5                 ; R5 restore
    RET                    ; Fonksiyondan dön


"""

# Kodları diske yaz
with open("main.asm", "w",encoding="utf-8") as f:
    f.write(main_code.strip())

with open("utils.asm", "w", encoding="utf-8") as f:
    f.write(utils_code.strip())

print("Debug ELF Oluşturucu Başlatılıyor...")

try:
    # Mevcut ELF dosyalarını temizle
    for elf_file in ["main.elf", "utils.elf", "output.elf"]:
        if os.path.exists(elf_file):
            os.remove(elf_file)
            print(f" Eski {elf_file} dosyası silindi")
    
    # Debug assemble
    print("\n" + "="*50)
    main_result = debug_assemble(main_code, filename="main.asm")
    
    print("\n" + "="*50)
    utils_result = debug_assemble(utils_code, filename="utils.asm")
    
    print("\n" + "="*50)
    print(" Sonuçlar:")
    
    # Sonuçları kontrol et
    if main_result and len(main_result) >= 6:
        if main_result[5] and len(main_result[5]) > 0:
            print(f" main.asm işlendi - ELF: {len(main_result[5])} bytes")
        else:
            print(" main.asm işlendi ama ELF verisi yok")
    else:
        print(" main.asm işlenemedi")
    
    if utils_result and len(utils_result) >= 6:
        if utils_result[5] and len(utils_result[5]) > 0:
            print(f" utils.asm işlendi - ELF: {len(utils_result[5])} bytes")
        else:
            print(" utils.asm işlendi ama ELF verisi yok")
    else:
        print(" utils.asm işlenemedi")
    
    # Dosya durumunu kontrol et
    print("\ Dosya Durumu:")
    for filename in ["main.elf", "utils.elf"]:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            print(f"  {filename}: {size} bytes")
            
            # ELF magic number kontrolü
            if size > 0:
                with open(filename, "rb") as f:
                    header = f.read(16)
                    if len(header) >= 4:
                        magic = header[:4]
                        if magic == b'\x7fELF':
                            print(f"     Geçerli ELF dosyası")
                        else:
                            print(f"     ELF magic number yok: {magic.hex()}")
                    else:
                        print(f"     Header çok küçük")
        else:
            print(f"  {filename}: dosya bulunamadı")

except Exception as e:
    print(f" Genel hata: {e}")
    import traceback
    traceback.print_exc()
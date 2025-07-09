# linker.py
# MSP430 assembler çıktılarını (.elf benzeri) birleştirerek çalıştırılabilir tek bir çıktı dosyası oluşturur

import os
import re

def read_elf(filename):
    print(f"\n=== {filename} dosyası okunuyor ===")
    
    with open(filename, 'r') as f:
        lines = f.readlines()

    text_section = []
    data_section = []
    symbol_table = {}
    relocation_entries = []

    mode = None
    for i, line in enumerate(lines):
        line = line.strip()

        if line.startswith('.text Section'):
            mode = 'text'
            print(f"  Text section başladı (satır {i+1})")
            continue
        elif line.startswith('.data Section'):
            mode = 'data'
            print(f"  Data section başladı (satır {i+1})")
            continue
        elif line.startswith('.symtab Section'):
            mode = 'symtab'
            print(f"  Symbol table başladı (satır {i+1})")
            continue
        elif line.startswith('.rel.text Section') or (line.startswith('.rel') and 'Section' in line):
            mode = 'relocation'
            print(f"  Relocation section başladı (satır {i+1})")
            continue

        if not line or line.startswith(('---', 'Address', 'Value', 'Symbol', 'Offset')):
            continue

        if mode == 'text':
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    try:
                        addr = int(parts[0].strip(), 16)
                        code = int(parts[1].strip(), 16)
                        text_section.append((addr, code))
                    except ValueError:
                        continue

        elif mode == 'data':
            if '|' in line:
                parts = line.split('|')
                if len(parts) >= 2:
                    try:
                        addr = int(parts[0].strip(), 16)
                        val = int(parts[1].strip(), 16)
                        data_section.append((addr, val))
                    except ValueError:
                        continue

        elif mode == 'symtab':
            if '|' in line:
                parts = [x.strip() for x in line.split('|')]
                if len(parts) >= 6:
                    try:
                        sym = parts[0]
                        val = parts[1]
                        typ = parts[2]
                        sect = parts[3]
                        defined = parts[4].lower() == 'true'
                        global_flag = parts[5].lower() == 'true'
                        symbol_table[sym] = {
                            'value': int(val, 16),
                            'type': typ,
                            'section': sect,
                            'defined': defined,
                            'is_global': global_flag
                        }
                    except ValueError:
                        continue

        elif mode == 'relocation':
            if '|' in line:
                parts = [x.strip() for x in line.split('|')]
                if len(parts) >= 4:
                    try:
                        offset = int(parts[0], 16)
                        symbol = parts[1]
                        typ = parts[2]
                        sect = parts[3]
                        relocation_entries.append({
                            'offset': offset,
                            'symbol': symbol,
                            'type': typ,
                            'section': sect
                        })
                    except ValueError:
                        continue

    return {
        'text': text_section,
        'data': data_section,
        'symbols': symbol_table,
        'relocations': relocation_entries
    }

def link(elf_files, output_file='linked_output.elf'):
    linked_text = []
    linked_data = []
    global_symbol_table = {}
    all_relocations = []

    current_text_offset = 0x0000
    current_data_offset = 0x0200

    for filename in elf_files:
        obj = read_elf(filename)
        file_text_start = current_text_offset
        file_data_start = current_data_offset

        # Sembolleri güncelle
        for sym, info in obj['symbols'].items():
            updated_info = info.copy()
            if info['section'] == 'text':
                updated_info['value'] += file_text_start
            elif info['section'] == 'data':
                updated_info['value'] += file_data_start
            updated_info['source_file'] = filename

            if sym in global_symbol_table:
                if info['defined'] and global_symbol_table[sym]['defined']:
                    raise ValueError(f"Sembol çakışması: '{sym}'")
                elif info['defined']:
                    global_symbol_table[sym] = updated_info
            else:
                global_symbol_table[sym] = updated_info

        # Text ve Data adreslerini güncelle
        for addr, code in obj['text']:
            linked_text.append((addr + file_text_start, code))
        for addr, val in obj['data']:
            linked_data.append((addr + file_data_start, val))

        for rel in obj['relocations']:
            updated_rel = rel.copy()
            if rel['section'] == 'text':
                updated_rel['offset'] += file_text_start
            elif rel['section'] == 'data':
                updated_rel['offset'] += file_data_start
            updated_rel['source_file'] = filename
            all_relocations.append(updated_rel)

        current_text_offset += len(obj['text']) * 2
        current_data_offset += len(obj['data']) * 2

    # Relocation çözümlemesi
    for rel in all_relocations:
        offset = rel['offset']
        symbol = rel['symbol']
        target_symbol = symbol.lstrip('#@')
        if target_symbol not in global_symbol_table or not global_symbol_table[target_symbol]['defined']:
            raise ValueError(f"Tanımsız sembol: {symbol}")

        symbol_address = global_symbol_table[target_symbol]['value']
        if rel['section'] == 'text':
            for i, (addr, code) in enumerate(linked_text):
                if addr == offset:
                    linked_text[i] = (addr, symbol_address)
                    break
        elif rel['section'] == 'data':
            for i, (addr, val) in enumerate(linked_data):
                if addr == offset:
                    linked_data[i] = (addr, symbol_address)
                    break

    # Çıktı dosyası oluştur
    with open(output_file, 'w') as f:
        f.write("MSP430 Linked Executable\n")
        f.write("========================\n\n")

        f.write(".text Section (Machine Code):\n")
        f.write("Address | Code\n")
        f.write("--------+------\n")
        for addr, code in sorted(linked_text):
            f.write(f"{addr:04X}    | {code:04X}\n")

        if linked_data:
            f.write("\n.data Section (Literals):\n")
            f.write("Address | Value\n")
            f.write("--------+-------\n")
            for addr, val in sorted(linked_data):
                f.write(f"{addr:04X}    | {val:04X}\n")

        f.write("\n.symtab Section (Symbol Table):\n")
        f.write("Symbol      | Value | Type      | Section | Defined | Global | File\n")
        f.write("------------+-------+-----------+---------+---------+--------+----------\n")
        for sym, info in sorted(global_symbol_table.items()):
            f.write(f"{sym:<11} | {info['value']:04X}  | {info['type']:<9} | {info['section']:<7} | {str(info['defined']):<7} | {str(info.get('is_global', False)):<6} | {info.get('source_file', 'N/A')}\n")

        if all_relocations:
            f.write("\n.relocations (Processed):\n")
            f.write("Offset | Symbol      | Type        | Section | Status   | File\n")
            f.write("-------+-------------+-------------+---------+----------+----------\n")
            for rel in all_relocations:
                symbol = rel['symbol']
                status = "RESOLVED" if symbol in global_symbol_table and global_symbol_table[symbol]['defined'] else "UNRESOLVED"
                f.write(f"{rel['offset']:04X}   | {symbol:<11} | {rel['type']:<11} | {rel['section']:<7} | {status:<8} | {rel['source_file']}\n")

        f.write(f"\n--- Linking Summary ---\n")
        f.write(f"Total text instructions: {len(linked_text)}\n")
        f.write(f"Total data entries: {len(linked_data)}\n")
        f.write(f"Total symbols: {len(global_symbol_table)}\n")
        f.write(f"Total relocations: {len(all_relocations)}\n")
        f.write(f"Files linked: {', '.join(elf_files)}\n")

    print(f"✓ Linking tamamlandı! Çıktı: {output_file}")

if __name__ == '__main__':
    import sys
    args = sys.argv[1:]
    output = "linked_output.elf"
    files = []

    if "-o" in args:
        o_index = args.index("-o")
        output = args[o_index + 1]
        files = args[:o_index] + args[o_index + 2:]
    else:
        files = args

    if not files:
        print("Kullanım: python linker.py file1.elf [file2.elf ...] [-o output.elf]")
        sys.exit(1)

    try:
        link(files, output_file=output)
    except Exception as e:
        print(f"\n❌ Hata: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
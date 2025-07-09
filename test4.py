import re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import json

# MSP430 Opcode Tablosu: Çift, tek operandlı ve atlama talimatları için opcode'lar
opcode_table = {
    "double_operand": {
        "MOV":  0x4,
        "ADD":  0x5,
        "ADDC": 0x6,
        "SUBC": 0x7,
        "SUB":  0x8,
        "CMP":  0x9,
        "DADD": 0xA,
        "BIT":  0xB,
        "BIC":  0xC,
        "BIS":  0xD,
        "XOR":  0xE,
        "AND":  0xF,
    },
    "single_operand": {
        "RRC":  0x10,
        "SWPB": 0x10,
        "RRA":  0x10,
        "SXT":  0x10,
        "PUSH": 0x12,
        "CALL": 0x12,
        "RETI": 0x13,
    },
    "jump": {
        "JNE":  0x2000,
        "JEQ":  0x2400,
        "JNC":  0x2800,
        "JC":   0x2C00,
        "JN":   0x3000,
        "JGE":  0x3400,
        "JL":   0x3800,
        "JMP":  0x3C00,
    }
}

# Makro tablosu ve genişletme sayacı
macro_table = {}  # Makro tanımlarını saklar
macro_expansion_counter = 0  # Unique etiketler için sayaç

class Macro:
    def __init__(self, name, params, body):
        # Makro sınıfı: Makro adı, parametreler ve gövdeyi saklar
        self.name = name
        self.params = params
        self.body = body

def parse_macros(lines):
    """Makro tanımlarını ayrıştırır ve macro_table'a ekler"""
    global macro_table
    i = 0
    new_lines = []  # Makro olmayan satırları saklar
    
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith(".macro"):
            # .macro direktifi: Makro tanımını başlatır
            macro_line = line[6:].strip()  # .macro kısmını çıkar
            parts = [p.strip() for p in macro_line.replace(',', ' ').split()]
            
            if len(parts) < 1:
                raise ValueError(f"Geçersiz makro tanımı: {line}")
            
            name = parts[0]  # Makro adı
            params = parts[1:] if len(parts) > 1 else []  # Parametreler
            body = []  # Makro gövdesi
            i += 1
            
            # Makro gövdesini .endm'ye kadar topla
            while i < len(lines) and not lines[i].strip().startswith(".endm"):
                body_line = lines[i].strip()
                if body_line:
                    body.append(body_line)
                i += 1
            
            if i >= len(lines):
                raise ValueError(f"Makro '{name}' için .endm bulunamadı")
            
            macro_table[name] = Macro(name, params, body)  # Makroyu kaydet
            print(f"DEBUG: Makro tanımlandı: {name} parametreler: {params}")
            print(f"DEBUG: Makro gövdesi: {body}")
        else:
            # Makro değilse, satırı koru
            if not line.startswith(".endm"):
                new_lines.append(lines[i])
        i += 1
    
    lines[:] = new_lines  # Orijinal listeyi güncelle

def expand_macros(lines):
    """Makro çağrılarını genişletir"""
    global macro_table, macro_expansion_counter
    expanded_lines = []
    
    for line_num, line in enumerate(lines):
        original_line = line.strip()
        
        # Yorumları ayır
        comment_pos = original_line.find(';')
        if comment_pos != -1:
            code_part = original_line[:comment_pos].strip()
            comment_part = original_line[comment_pos:]
        else:
            code_part = original_line
            comment_part = ""
        
        tokens = code_part.split()
        
        if not tokens:
            expanded_lines.append(line)  # Boş satırı koru
            continue
        
        if tokens[0] in macro_table:
            # Makro çağrısı bulundu
            macro = macro_table[tokens[0]]
            
            # Argümanları ayrıştır
            arg_string = ' '.join(tokens[1:])
            args = [arg.strip() for arg in arg_string.replace(',', ' ').split() if arg.strip()]
            
            print(f"DEBUG: Makro çağrısı bulundu: {tokens[0]} args: {args}")
            
            if len(args) != len(macro.params):
                raise ValueError(f"Makro '{macro.name}' {len(macro.params)} parametre bekliyor, {len(args)} verildi")
            
            mapping = dict(zip(macro.params, args))  # Parametre-argüman eşleşmesi
            macro_expansion_counter += 1
            
            print(f"DEBUG: Parametre eşleştirmesi: {mapping}")
            
            for m_line in macro.body:
                expanded = m_line
                
                # Parametreleri argümanlarla değiştir
                for param, arg in mapping.items():
                    expanded = re.sub(rf'#{re.escape(param)}\b', f'#{arg}', expanded)
                    expanded = re.sub(rf':{re.escape(param)}:', arg, expanded)
                    expanded = re.sub(rf'\b{re.escape(param)}\b', arg, expanded)
                
                # Unique etiketler için sayacı kullan
                expanded = re.sub(r'(\w+)\?', rf'\1.{macro_expansion_counter}', expanded)
                
                if comment_part and not expanded.strip().startswith('.'):
                    expanded = expanded + " " + comment_part  # Yorumu ekle
                
                print(f"DEBUG: Genişletilmiş satır: '{m_line}' -> '{expanded}'")
                expanded_lines.append(expanded)
        else:
            expanded_lines.append(line)  # Normal satırı koru
    
    return expanded_lines

def parse_operand(operand, symbol_table=None, bw_bit=0):
    """Operandları ayrıştırır ve adresleme modunu belirler"""
    operand = operand.strip()

    debug_mode = False
    if operand == "#ext_var":
        print(f"\nDEBUG: parse_operand çağrıldı - operand: '{operand}'")
        debug_mode = True
        
    if operand.startswith('#'):
        # Immediate mod
        value_str = operand[1:].strip()
        
        if re.match(r"^'.'$", value_str):
            char = value_str[1]
            result = {'mode': 'immediate', 'value': ord(char), 'As': 0x3, 'register': 'R0'}
        elif value_str == "''":
            raise ValueError("Bos karakter literali gecersiz: #''")
        elif re.match(r'^0b[01]+$', value_str) or re.match(r'^[01]+b$', value_str):
            bin_val = value_str[2:] if value_str.startswith('0b') else value_str[:-1]
            result = {'mode': 'immediate', 'value': int(bin_val, 2), 'As': 0x3, 'register': 'R0'}
        elif re.match(r'^0x[0-9a-fA-F]+$', value_str) or re.match(r'^[0-9a-fA-F]+h$', value_str):
            hex_val = value_str[2:] if value_str.startswith('0x') else value_str[:-1]
            result = {'mode': 'immediate', 'value': int(hex_val, 16), 'As': 0x3, 'register': 'R0'}
        elif value_str.isdigit():
            result = {'mode': 'immediate', 'value': int(value_str), 'As': 0x3, 'register': 'R0'}
        else:
            if symbol_table and value_str in symbol_table:
                if isinstance(symbol_table[value_str], dict) and 'value' in symbol_table[value_str]:
                    result = {
                        'mode': 'immediate',
                        'value': int(symbol_table[value_str]['value']),
                        'As': 0x3,
                        'register': 'R0',
                        'label': value_str
                    }
                else:
                    result = {'mode': 'immediate', 'value': int(symbol_table[value_str]), 'As': 0x3, 'register': 'R0'}

    elif operand.startswith('&'):
        # Absolute mod
        label = operand[1:]
        if symbol_table and label in symbol_table:
            if isinstance(symbol_table[label], dict):
                result = {'mode': 'absolute', 'label': label, 'As': 0x1, 'register': 'R2'}
            else:
                result = {'mode': 'absolute', 'value': int(symbol_table[label]), 'As': 0x1, 'register': 'R2'}
        try:
            addr = int(label, 0)
            result = {'mode': 'absolute', 'value': addr, 'As': 0x1, 'register': 'R2'}
        except ValueError:
            result = {'mode': 'absolute', 'label': label, 'As': 0x1, 'register': 'R2'}
        
    elif re.match(r'^-?\d+\(R\d+\)$', operand):
        # Indexed mod
        offset, reg = operand[:-1].split('(')
        result = {
            'mode': 'indexed',
            'offset': int(offset),
            'register': reg,
            'As': 0x1
        }
    
    elif re.match(r'^@R\d+\+$', operand):
        # Indirect auto-increment mod
        reg = operand[1:-1]
        result = {'mode': 'indirect_autoinc', 'register': reg, 'As': 0x3}
    
    elif re.match(r'^@R\d+$', operand):
        # Indirect mod
        reg = operand[1:]
        result = {'mode': 'indirect', 'register': reg, 'As': 0x2}
    
    elif re.match(r'^R\d+$', operand):
        # Register mod
        result = {'mode': 'register', 'register': operand, 'As': 0x0}
    
    elif re.match(r'^[A-Za-z_]\w*$', operand):
        # Symbolic mod
        result = {'mode': 'symbolic', 'label': operand, 'As': 0x1, 'register': 'R0'}
    
    else:
        raise ValueError(f"Gecersiz operand: {operand}")

    if debug_mode:
        print(f"  Operand: {operand}")
        print(f"  Sonuç: {result}")
        print(f"  Symbol tablosunda 'ext_var' var mı? {'ext_var' in symbol_table if symbol_table else 'symbol_table None'}")
        if symbol_table and 'ext_var' in symbol_table:
            print(f"  Symbol tablosu girişi: {symbol_table['ext_var']}")
            print(f"  Tipi: {type(symbol_table['ext_var'])}")
    
    return result

def resolve_forward_references(symbol_table):
    """İleri referansları çözer"""
    for label in list(symbol_table.keys()):
        entry = symbol_table[label]
        if not entry.get('defined', False) and 'forward_references' in entry:
            for ref_label in entry['forward_references']:
                if ref_label in symbol_table and symbol_table[ref_label].get('is_constant', False):
                    try:
                        symbol_table[label]['value'] = symbol_table[ref_label]['value']
                        symbol_table[label]['defined'] = True
                    except KeyError:
                        pass

def pass1(lines):
    """Birinci geçiş: Sembol tablosunu oluşturur"""
    symbol_table = {}
    current_section = 'text'  # Varsayılan bölüm
    section_addresses = {
        'text': 0,
        'data': 0x0200, 
        'bss': 0x0400
    }
    location_counter = section_addresses[current_section]  # Adres sayacı

    placeholder_base = 0xFF00  # Geçici değerler için taban adres
    placeholder_counter = 0

    for line_num, line in enumerate(lines, 1):
        line = line.split(';', 1)[0].strip()  # Yorumları çıkar
        if not line:
            continue

        label = None

        if line.lower().startswith('.org'):
            # .org: Başlangıç adresini belirler
            try:
                addr = line[len('.org'):].strip()
                location_counter = int(addr, 16) if addr.lower().startswith('0x') else int(addr, 0)
                continue
            except ValueError:
                raise ValueError(f"Line {line_num}: Gecersiz .org adresi: '{addr}'")

        if line.lower().startswith('.usect'):
            # .usect: Özel bölüm tanımlar
            match = re.match(r'\.usect\s+\"([^\"]+)\"\s*,\s*(\d+)', line, re.IGNORECASE)
            if match:
                sect_name = match.group(1)
                size = int(match.group(2))
                if sect_name not in section_addresses:
                    section_addresses[sect_name] = 0
                section_addresses[sect_name] += size
            continue

        elif line.lower().startswith('.sect'):
            # .sect: Yeni bir bölümü başlatır
            match = re.match(r'\.sect\s+\"([^\"]+)\"', line, re.IGNORECASE)
            if match:
                sect_name = match.group(1)
                current_section = sect_name
                if sect_name not in section_addresses:
                    section_addresses[sect_name] = 0
                location_counter = section_addresses[sect_name]
            continue

        elif line.lower().startswith('.text'):
            # .text: Kod bölümü
            current_section = 'text'
            location_counter = section_addresses.get(current_section, 0)
            continue
        elif line.lower().startswith('.data'):
            # .data: Veri bölümü
            current_section = 'data'
            location_counter = section_addresses.get(current_section, 0x0200)
            continue
        elif line.lower().startswith('.bss'):
            # .bss: Rezerve alan
            current_section = 'bss'
            location_counter = section_addresses.get(current_section, 0x0400)
            continue

        elif line.lower().startswith('.global'):
            # .global: Global semboller tanımlar
            symbols = [s.strip() for s in line[len('.global'):].split(',') if s.strip()]
            for sym in symbols:
                symbol_table.setdefault(sym, {
                    'value': 0,
                    'type': 'external',
                    'defined': False,
                    'section': 'none',
                    'is_constant': False
                })
                symbol_table[sym]['is_global'] = True
            continue

        elif line.lower().startswith('.def'):
            # .def: Sembol tanımlar
            symbols = [s.strip() for s in line[len('.def'):].split(',') if s.strip()]
            for sym in symbols:
                symbol_table[sym] = {
                    'value': 0,
                    'type': 'code',
                    'defined': True,
                    'section': current_section,
                    'is_constant': False
                }
            continue

        elif line.lower().startswith('.ref'):
            # .ref: Dış sembol referansları
            symbols = [s.strip() for s in line[len('.ref'):].split(',') if s.strip()]
            for sym in symbols:
                symbol_table[sym] = {
                    'value': 0,
                    'type': 'external',
                    'defined': False,
                    'section': 'none',
                    'is_constant': False
                }
            continue

        if line.lower() == ".end":
            break  # Kod sonu

        if '.equ' in line.lower() or '.set' in line.lower():
            # .equ/.set: Sabit değer tanımlar
            parts = re.split(r'\s+', line, maxsplit=2)
            if len(parts) >= 3 and parts[1].lower() in ['.equ', '.set']:
                label = parts[0].strip()
                value_expr = parts[2].strip()
                value_expr = value_expr.replace('$', f'(0x{location_counter:X})')
                
                symbols_in_expr = re.findall(r'\b[A-Za-z_]\w*\b', value_expr)
                operand_types = []
                unresolved = False

                for sym in symbols_in_expr:
                    if sym not in symbol_table or not symbol_table[sym].get("defined", False):
                        if sym not in symbol_table:
                            placeholder_value = placeholder_base + placeholder_counter
                            placeholder_counter += 1
                            symbol_table[sym] = {
                                'value': placeholder_value,
                                'type': 'absolute',
                                'defined': False,
                                'placeholder': True,
                                'forward_references': [label]
                            }
                        else:
                            symbol_table[sym].setdefault('forward_references', []).append(label)
                        unresolved = True
                        operand_types.append('absolute')
                    else:
                        operand_types.append(symbol_table[sym]['type'])

                expr_ops = re.findall(r'[\+\-\*/]', value_expr)
                unique_types = set(operand_types)

                try:
                    if len(unique_types) == 1 and 'absolute' in unique_types:
                        symbol_type = 'absolute'
                    elif unique_types == {'relative'}:
                        if expr_ops == ['-'] and len(operand_types) == 2:
                            symbol_type = 'absolute'
                        else:
                            raise ValueError(f"Line {line_num}: Gecersiz islem.")
                    elif 'relative' in unique_types and 'absolute' in unique_types:
                        raise ValueError(f"Line {line_num}: Gecersiz islem.")
                    elif not operand_types:
                        symbol_type = 'absolute'
                    else:
                        raise ValueError(f"Line {line_num}: Gecersiz islem.")
                except ValueError as ve:
                    raise ValueError(f"Line {line_num}: .equ/.set ifadesi hatali: {ve}")

                try:
                    value = eval_value_expression(value_expr, symbol_table)
                    if not (0 <= value <= 0xFFFF):
                        raise ValueError(f"Line {line_num}: .equ sonucu 16-bit sinirini asiyor: {value}")
                except Exception as e:
                    print(f"DEBUG: Line{line_num} - Expression '{value_expr}' failed: {str(e)}")
                    value = placeholder_base + 0x7F

                symbol_table[label] = {
                    'value': value,
                    'type': symbol_type,
                    'defined': not unresolved,
                    'section': 'const',
                    'is_constant': True,
                    'depends_on': symbols_in_expr if unresolved else []
                }
                continue

        if ':' in line:
            # Etiket tanımı
            label_part, rest = line.split(':', 1)
            label = label_part.strip()
            line = rest.strip()

        if label:
            if label in symbol_table and not (symbol_table[label].get('is_global', False) or symbol_table[label].get('defined', False)):
                raise ValueError(f"Line {line_num}: Tekrarlanan etiket '{label}'")
            symbol_table[label] = {
                'value': location_counter,
                'type': 'relative',
                'defined': True,
                'section': current_section,
                'is_constant': False
            }

        parts = re.split(r'\s+', line, maxsplit=1)
        mnemonic = parts[0].upper() if parts else ""
        operands = parts[1] if len(parts) > 1 else ""

        if mnemonic in ['MOV', 'ADD', 'SUB', 'CMP']:
            # Çift operandlı talimatlar
            location_counter += 2
            ops = [op.strip() for op in operands.split(',')] if operands else []
            for op in ops:
                if '@' in op or '&' in op or '#' in op:
                    location_counter += 2

        elif mnemonic in ['JMP', 'JZ', 'JNZ']:
            # Atlama talimatları
            location_counter += 2
        else:
            location_counter += 2

        section_addresses[current_section] = location_counter

    resolve_forward_references(symbol_table)
    return symbol_table

def eval_value_expression(expr, symbol_table):
    """İfadeleri değerlendirir"""
    try:
        expr = expr.strip()
        hex_matches = re.findall(r'\b0x[0-9A-Fa-f]+\b', expr)
        for h in hex_matches:
            expr = expr.replace(h, str(int(h, 16)))
        
        bin_matches = re.findall(r'\b0b[01]+\b', expr)
        for b in bin_matches:
            expr = expr.replace(b, str(int(b[2:], 2)))
        
        symbols_in_expr = re.findall(r'\b[A-Za-z_]\w*\b', expr)
        for sym in symbols_in_expr:
            if sym in symbol_table:
                sym_entry = symbol_table[sym]
                if isinstance(sym_entry, dict):
                    if not sym_entry.get('defined', False):
                        raise ValueError(f"Tanımsız sembol: {sym}")
                    expr = expr.replace(sym, str(sym_entry['value']))
                else:
                    expr = expr.replace(sym, str(sym_entry))
            else:
                raise ValueError(f"Bilinmeyen sembol: {sym}")
        
        allowed_chars = set("0123456789+-*/()&|^~<> ")
        if not all(c in allowed_chars for c in expr):
            raise ValueError(f"Geçersiz karakterler: {expr}")
        
        result = eval(expr, {"_builtins_": None}, {})
        
        if -32768 <= result <= 65535:
            return result & 0xFFFF
        else:
            raise ValueError(f"16-bit sınırı aşıldı: {result}")
            
    except Exception as e:
        raise ValueError(f"İfade hatası '{expr}': {str(e)}")

def needs_relocation(operand_info, symbol_table):
    """Relocation gerekip gerekmediğini kontrol eder"""
    if 'label' in operand_info:
        label = operand_info['label']
        if label in symbol_table:
            if isinstance(symbol_table[label], dict):
                return not symbol_table[label].get('defined', False) or symbol_table[label].get('type') == 'external'
            else:
                return True
        else:
            return True
    return False

def pass2(lines, symbol_table, opcode_table):
    """İkinci geçiş: Makine kodunu üretir"""
    machine_code = []
    literals_table = []
    relocation_entries = []
    relocation_data = {}
    location_counter = 0
    start_address = None
    current_section = 'text'
    section_addresses = {
        'text': 0,
        'data': 0x0200,
        'bss': 0x0400
    }

    location_counter = section_addresses[current_section]

    for line in lines:
        line = line.split(';', 1)[0].strip()
        if not line:
            continue

        if line.lower().startswith('.org'):
            addr = line[len('.org'):].strip()
            location_counter = int(addr, 16) if addr.lower().startswith('0x') else int(addr, 0)
            continue

        if line.lower().startswith('.text'):
            current_section = 'text'
            location_counter = section_addresses.get(current_section, 0)
            continue
        elif line.lower().startswith('.data'):
            current_section = 'data'
            location_counter = section_addresses.get(current_section, 0x0200)
            continue
        elif line.lower().startswith('.bss'):
            current_section = 'bss'
            location_counter = section_addresses.get(current_section, 0x0400)
            continue

        if line.lower() == ".end":
            break

        if line.startswith('.word'):
            # .word: Veri kelimeleri ekler
            if ':' in line:
                label_part, rest = line.split(':', 1)
                label = label_part.strip()
                values = [v.strip() for v in re.split(r'\s*,\s*', rest.strip())]
            else:
                label = None
                values = [v.strip() for v in re.split(r'\s*,\s*', line[len('.word'):].strip())]
            for value in values:
                int_value = int(value, 16) if value.lower().startswith('0x') else int(value, 0)
                if label:
                    symbol_table[label] = {'value': location_counter, 'type': 'data', 'defined': True, 'section': current_section, 'is_constant': False}
                machine_code.append((location_counter, int_value))
                location_counter += 2
            continue

        label = None
        if ':' in line:
            label_part, rest = line.split(':', 1)
            label = label_part.strip()
            line = rest.strip()

        parts = re.split(r'\s+', line, maxsplit=1)
        mnemonic = parts[0].upper() if parts else ""
        operands = parts[1] if len(parts) > 1 else ""

        if not mnemonic:
            continue

        if mnemonic == "NOP":
            word = 0x4303
            machine_code.append((location_counter, int(word)))
            location_counter += 2
            continue
        
        bw_bit = 1 if mnemonic.endswith(".B") else 0
        mnemonic_clean = mnemonic.replace(".B", "").replace(".W", "")

        if mnemonic_clean in opcode_table["double_operand"]:
            # Çift operandlı talimatlar için makine kodu üret
            ops = [op.strip() for op in operands.split(',')]
            src_info = parse_operand(ops[0], symbol_table, bw_bit)
            dst_info = parse_operand(ops[1], symbol_table, bw_bit)

            if ops[0] == "#ext_var":
                print("\nDEBUG: pass2 içinde - MOV.W #ext_var, R6 satırı")
                print(f"  Kaynak operand bilgisi: {src_info}")
                print(f"  'label' alanı var mı? {'label' in src_info}")
                print(f"  Hedef operand bilgisi: {dst_info}")
                print(f"  Symbol tablosunda 'ext_var': {symbol_table.get('ext_var', 'YOK')}")
                print(f"  Tipi: {type(symbol_table.get('ext_var', None))}")
                print(f"  Relocation gerekli mi? {needs_relocation(src_info, symbol_table)}")

            src_reg = int(src_info['register'][1:]) if 'register' in src_info else 0
            dst_reg = int(dst_info['register'][1:]) if 'register' in dst_info else 0

            As = src_info['As']
            Ad = 1 if dst_info['mode'] in ['indexed', 'symbolic', 'absolute'] else 0

            opcode = opcode_table["double_operand"][mnemonic_clean]
            word = (opcode << 12) | (src_reg << 8) | (Ad << 7) | (bw_bit << 6) | (As << 4) | dst_reg
            machine_code.append((location_counter, int(word)))
            location_counter += 2

            if src_info['mode'] in ['immediate', 'indexed', 'absolute', 'symbolic']:
                if needs_relocation(src_info, symbol_table):
                    # Relocation girişi ekle
                    relocation_entries.append({
                        "section": current_section,
                        "offset": location_counter,
                        "symbol": src_info['label'],
                        "type": "ABSOLUTE_16"
                    })
                    print(f"Added relocation entry: section={current_section}, offset={location_counter}, symbol={src_info['label']}")
                    extra_word = 0
                else:
                    if 'label' in src_info:
                        if src_info['label'] not in symbol_table:
                            raise ValueError(f"Etiket bulunamadi: {src_info['label']}")
                        if isinstance(symbol_table[src_info['label']], dict) and 'value' in symbol_table[src_info['label']]:
                            extra_word = int(symbol_table[src_info['label']]['value'])
                        else:
                            extra_word = int(symbol_table[src_info['label']])
                    elif 'value' in src_info:
                        extra_word = int(src_info['value'])
                    else:
                        extra_word = 0
                
                machine_code.append((location_counter, int(extra_word)))
                literals_table.append({'address': location_counter, 'value': int(extra_word), 'type': 'src'})
                location_counter += 2

            if dst_info['mode'] in ['indexed', 'absolute', 'symbolic']:
                if needs_relocation(dst_info, symbol_table):
                    # Relocation girişi ekle
                    relocation_entries.append({
                        "section": current_section,
                        "offset": location_counter,
                        "symbol": dst_info['label'],
                        "type": "ABSOLUTE_16"
                    })
                    print(f"Added relocation entry: section={current_section}, offset={location_counter}, symbol={dst_info['label']}")
                    extra_word = 0
                else:
                    if 'label' in dst_info:
                        if dst_info['label'] not in symbol_table:
                            raise ValueError(f"Etiket bulunamadi: {dst_info['label']}")
                        if isinstance(symbol_table[dst_info['label']], dict) and 'value' in symbol_table[dst_info['label']]:
                            extra_word = int(symbol_table[dst_info['label']]['value'])
                        else:
                            extra_word = int(symbol_table[dst_info['label']])
                    elif 'value' in dst_info:
                        extra_word = int(dst_info['value'])
                    elif 'offset' in dst_info:
                        extra_word = int(dst_info['offset'])
                    else:
                        extra_word = 0
                
                machine_code.append((location_counter, int(extra_word)))
                literals_table.append({'address': location_counter, 'value': int(extra_word), 'type': 'dst'})
                location_counter += 2

        elif mnemonic_clean in opcode_table["single_operand"]:
            if mnemonic_clean == "RETI":
                word = 0x1300
                machine_code.append((location_counter, int(word)))
                location_counter += 2
            else:
                operand_info = parse_operand(operands, symbol_table, bw_bit)
                reg = int(operand_info['register'][1:]) if 'register' in operand_info else 0
                As = operand_info['As']
                
                if mnemonic_clean == "PUSH":
                    word = (4 << 12) | (reg << 8) | (As << 4) | 0
                    machine_code.append((location_counter, int(word)))
                    location_counter += 2
                    
                    if operand_info['mode'] in ['immediate', 'indexed', 'absolute', 'symbolic']:
                        if needs_relocation(operand_info, symbol_table):
                            relocation_entries.append({
                                "section": current_section,
                                "offset": location_counter,
                                "symbol": operand_info['label'],
                                "type": "ABSOLUTE_16"
                            })
                            print(f"Added relocation entry: section={current_section}, offset={location_counter}, symbol={operand_info['label']}")
                            extra_word = 0
                        else:
                            if 'label' in operand_info:
                                if operand_info['label'] not in symbol_table:
                                    raise ValueError(f"Etiket bulunamadi: {operand_info['label']}")
                                if isinstance(symbol_table[operand_info['label']], dict) and 'value' in symbol_table[operand_info['label']]:
                                    extra_word = int(symbol_table[operand_info['label']]['value'])
                                else:
                                    extra_word = int(symbol_table[operand_info['label']])
                            elif 'value' in operand_info:
                                extra_word = int(operand_info['value'])
                            elif 'offset' in operand_info:
                                extra_word = int(operand_info['offset'])
                            else:
                                extra_word = 0
                        
                        machine_code.append((location_counter, int(extra_word)))
                        location_counter += 2

                elif mnemonic_clean == "CALL":
                    word = 0x1280
                    machine_code.append((location_counter, int(word)))
                    location_counter += 2
                    
                    target = operands.strip().lstrip('#')
                    op_info = {'label': target, 'mode': 'immediate'}
                    print(f"CALL target: {target}, defined: {target in symbol_table and symbol_table[target].get('defined', False)}")
                    
                    if needs_relocation(op_info, symbol_table):
                        relocation_entries.append({
                            "section": current_section,
                            "offset": location_counter,
                            "symbol": target,
                            "type": "ABSOLUTE_16"
                        })
                        print(f"Added relocation entry: section={current_section}, offset={location_counter}, symbol={target}")
                        target_value = 0
                    else:
                        if target not in symbol_table:
                            raise ValueError(f"Etiket bulunamadi: {target}")
                        if isinstance(symbol_table[target], dict) and 'value' in symbol_table[target]:
                            target_value = int(symbol_table[target]['value'])
                        else:
                            target_value = int(symbol_table[target])
                    
                    machine_code.append((location_counter, int(target_value)))
                    location_counter += 2
                else:
                    mod = {'RRC': 0, 'SWPB': 1, 'RRA': 2, 'SXT': 3}.get(mnemonic_clean, 0)
                    word = (1 << 15) | (0 << 13) | (mod << 7) | (bw_bit << 6) | (As << 4) | reg
                    machine_code.append((location_counter, int(word)))
                    location_counter += 2
                    
                    if operand_info['mode'] in ['immediate', 'indexed', 'absolute', 'symbolic']:
                        if needs_relocation(operand_info, symbol_table):
                            relocation_entries.append({
                                "section": current_section,
                                "offset": location_counter,
                                "symbol": operand_info['label'],
                                "type": "ABSOLUTE_16"
                            })
                            print(f"Added relocation entry: section={current_section}, offset={location_counter}, symbol={operand_info['label']}")
                            extra_word = 0
                        else:
                            if 'label' in operand_info:
                                if operand_info['label'] not in symbol_table:
                                    raise ValueError(f"Etiket bulunamadi: {operand_info['label']}")
                                if isinstance(symbol_table[operand_info['label']], dict) and 'value' in symbol_table[operand_info['label']]:
                                    extra_word = int(symbol_table[operand_info['label']]['value'])
                                else:
                                    extra_word = int(symbol_table[operand_info['label']])
                            elif 'value' in operand_info:
                                extra_word = int(operand_info['value'])
                            elif 'offset' in operand_info:
                                extra_word = int(operand_info['offset'])
                            else:
                                extra_word = 0
                        
                        machine_code.append((location_counter, int(extra_word)))
                        location_counter += 2

        elif mnemonic_clean in opcode_table["jump"]:
            # Atlama talimatları için makine kodu üret
            offset_label = operands.strip()
            if offset_label not in symbol_table:
                raise ValueError(f"Etiket bulunamadi: {offset_label}")
            
            if not symbol_table[offset_label]['defined'] or symbol_table[offset_label].get('type') == 'external':
                relocation_entries.append({
                    "section": current_section,
                    "offset": location_counter,
                    "symbol": offset_label,
                    "type": "PC_RELATIVE"
                })
                print(f"Added relocation entry: section={current_section}, offset={location_counter}, symbol={offset_label}")
                offset = 0
            else:
                if isinstance(symbol_table[offset_label], dict) and 'value' in symbol_table[offset_label]:
                    target_address = int(symbol_table[offset_label]['value'])
                else:
                    target_address = int(symbol_table[offset_label])
                
                offset = (target_address - (location_counter + 2)) // 2
                
                if not -1024 <= offset <= 1023:
                    raise ValueError(f"Atlama mesafesi cok uzak: {offset_label}, offset: {offset}")
            
            opcode_base = opcode_table["jump"][mnemonic_clean]
            word = opcode_base | (offset & 0x03FF)
            machine_code.append((location_counter, int(word)))
            location_counter += 2

        else:
            continue

    if start_address is not None:
        machine_code.append((0xFFFE, int(start_address)))

    relocation_data = {
        'entries': relocation_entries,
        'symbol_table': symbol_table,
        'section_info': {
            'text': {
                'start': 0, 
                'size': len([mc for mc in machine_code if mc[0] < 0x0200]) * 2
            },
            'data': {
                'start': 0x0200, 
                'size': len([mc for mc in machine_code if 0x0200 <= mc[0] < 0x0400]) * 2
            },
            'bss': {
                'start': 0x0400, 
                'size': 0
            }
        }
    }

    print(f"pass2'dan dönen relocation_entries: {relocation_entries}")
    return machine_code, literals_table, relocation_entries, relocation_data

def assemble(assembly_code):
    """Assembly kodunu derler"""
    lines = assembly_code.strip().split('\n')
    
    # Makroları ayrıştır ve genişlet
    parse_macros(lines)
    lines = expand_macros(lines)
    
    # Sembol tablosunu oluştur
    symbol_table = pass1(lines)
    # Makine kodunu üret
    machine_code, literals, relocation_entries, relocation_data = pass2(lines, symbol_table, opcode_table)
    
    formatted_machine_code = []
    for addr, code in machine_code:
        formatted_machine_code.append((addr, code))
    
    # ELF nesne dosyasını oluştur
    create_object_file(
        machine_code,
        symbol_table,
        literals,
        relocation_entries=relocation_entries,
        relocation_data=relocation_data,
        filename="output.elf"
    )

    return formatted_machine_code, symbol_table, literals, relocation_entries, relocation_data

def create_object_file(machine_code, symbol_table, literals, relocation_entries=None, relocation_data=None, filename="output.o"):
    """ELF nesne dosyası oluşturur"""
    with open(filename, 'w') as f:
        f.write("ELF Object File\n")
        f.write("=================\n\n")
        f.write("ELF Header:\n")
        f.write("  Magic:   7F 45 4C 46 (ELF)\n")
        f.write("  Class:   ELF32\n")
        f.write("  Data:    2's complement, little endian\n")
        f.write("  Version: 1 (current)\n")
        f.write("  OS/ABI:  System V ABI\n")
        f.write("  Type:    REL (Relocatable file)\n")
        f.write("  Machine: MSP430\n")
        f.write("  Entry:   0x0000\n")
        f.write("\n")

        section_count = 5 + (1 if relocation_entries else 0)
        
        f.write("Section Headers:\n")
        f.write("  [Nr] Name       Type            Addr   Size\n")
        f.write("  [ 0]            NULL            000000 000000\n")
        f.write("  [ 1] .text      PROGBITS        000000 %06X\n" % (len(machine_code) * 2))
        f.write("  [ 2] .data      PROGBITS        020000 %06X\n" % (len(literals) * 2))
        f.write("  [ 3] .symtab    SYMTAB          000000 %06X\n" % (len(symbol_table) * 16))
        f.write("  [ 4] .shstrtab  STRTAB          000000 000100\n")
        if relocation_entries:
            f.write("  [ 5] .rel.text  REL             000000 %06X\n" % (len(relocation_entries) * 8))
        f.write("\n")

        f.write(".text Section (Machine Code):\n")
        f.write("Address | Code\n")
        f.write("---------------\n")
        for addr, code in machine_code:
            f.write(f"{addr:04X}    | {code:04X}\n")
        f.write("\n")

        f.write(".data Section (Literals):\n")
        f.write("Address | Value   | Type\n")
        f.write("-----------------------\n")
        for lit in literals:
            addr = lit['address']
            val = lit['value']
            f.write(f"{addr:04X}    | {val:04X} | {lit['type']}\n")
        f.write("\n")

        f.write(".symtab Section (Symbol Table):\n")
        f.write("Symbol    | Value | Type      | Section | Defined | Global\n")
        f.write("-------------------------------------------------------\n")
        for symbol, info in symbol_table.items():
            if isinstance(info, dict) and 'value' in info:
                value = info['value']
                f.write(f"{symbol:<10} | {value:04X} | {info['type']:<9} | {info['section']:<7} | {str(info['defined']):<7} | {str(info.get('is_global', False))}\n")
            else:
                value = int(info) if isinstance(info, (int, str)) else 0
                f.write(f"{symbol:<10} | {value:04X} | external   | none    | False   | False\n")
        f.write("\n")

        if relocation_entries:
            f.write(".relocation Section:\n")
            f.write("Offset | Symbol | Type | Section\n")
            f.write("---------------------------------------------\n")
            for entry in relocation_entries:
                f.write(f"{entry['offset']:04X} | {entry['symbol']:<10} | {entry['type']:<12} | {entry['section']}\n")
            f.write("\n")

        if relocation_entries:
            f.write(".rel.text Section (Relocation Entries):\n")
            f.write("Offset  | Symbol     | Type        | Section\n")
            f.write("-------------------------------------------\n")
            for entry in relocation_entries:
                f.write(f"{entry['offset']:04X}    | {entry['symbol']:<10} | {entry['type']:<11} | {entry['section']}\n")
            f.write("\n")

        if relocation_data:
            f.write("Section Information:\n")
            f.write("Section | Start  | Size\n")
            f.write("-------------------\n")
            for section, info in relocation_data['section_info'].items():
                f.write(f"{section:<7} | {info['start']:04X} | {info['size']:04X}\n")
            f.write("\n")

    return filename

class AssemblerGUI:
    def __init__(self, root):
        """GUI arayüzünü başlatır"""
        self.root = root
        self.root.title("MSP430 Assembler")
        self.root.geometry("1000x700")
        
        self.relocation_data = None

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TButton', font=('Helvetica', 10), padding=10, background='#4CAF50', foreground='white')
        self.style.map('TButton', background=[('active', '#45A049')])
        self.style.configure('TLabel', font=('Helvetica', 12), padding=5)
        self.style.configure('TNotebook', background='#f0f0f0')
        self.style.configure('TNotebook.Tab', font=('Helvetica', 10, 'bold'), padding=[10, 5])

        self.main_frame = ttk.Frame(root, padding="10", style='Main.TFrame')
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        self.style.configure('Main.TFrame', background='#e0e0e0')

        self.title_label = ttk.Label(self.main_frame, text="MSP430 Assembler", font=("Helvetica", 20, "bold"), foreground='#333333')
        self.title_label.pack(pady=10)

        self.top_frame = ttk.Frame(self.main_frame, style='Top.TFrame')
        self.top_frame.pack(fill=tk.X, pady=5)
        self.style.configure('Top.TFrame', background='#e0e0e0')

        self.input_label = ttk.Label(self.top_frame, text="Assembly Kodu:", font=("Helvetica", 12, "bold"), foreground='#333333')
        self.input_label.pack(anchor="nw", padx=5, pady=5)

        self.input_text = scrolledtext.ScrolledText(self.top_frame, height=10, width=100, font=("Consolas", 10), bg='#ffffff', fg='#333333', insertbackground='black')
        self.input_text.pack(fill=tk.X, padx=5, pady=5)

        self.button_frame = ttk.Frame(self.top_frame)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)

        self.assemble_button = ttk.Button(self.button_frame, text="Derle", command=self.assemble_code, style='TButton')
        self.assemble_button.pack(side=tk.LEFT, padx=5)

        self.save_object_button = ttk.Button(self.button_frame, text="Obje Dosyasını Kaydet", command=self.save_object_file, style='TButton')
        self.save_object_button.pack(side=tk.LEFT, padx=5)

        self.output_notebook = ttk.Notebook(self.main_frame)
        self.output_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.symbol_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.symbol_frame, text="Sembol Tablosu")

        self.symbol_text = scrolledtext.ScrolledText(self.symbol_frame, height=15, width=100, font=("Consolas", 10), bg='#ffffff', fg='#333333')
        self.symbol_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.literals_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.literals_frame, text="Literals Tablosu")

        self.literals_text = scrolledtext.ScrolledText(self.literals_frame, height=15, width=100, font=("Consolas", 10), bg='#ffffff', fg='#333333')
        self.literals_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.machine_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.machine_frame, text="Makine Kodu")

        self.machine_text = scrolledtext.ScrolledText(self.machine_frame, height=15, width=100, font=("Consolas", 10), bg='#ffffff', fg='#333333')
        self.machine_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.relocation_frame = ttk.Frame(self.output_notebook)
        self.output_notebook.add(self.relocation_frame, text="Relocation Bilgileri")

        self.relocation_text = scrolledtext.ScrolledText(self.relocation_frame, height=15, width=100, font=("Consolas", 10), bg='#ffffff', fg='#333333')
        self.relocation_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.status_var = tk.StringVar()
        self.status_var.set("Hazir")
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=5, background='#d0d0d0', foreground='#333333')
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.input_text.insert(tk.END, """
        ;-------------------------------------------------------------------------------
; MSP430 Assembler Code Template for use with TI Code Composer Studio
;
;
;-------------------------------------------------------------------------------
            
            
;-------------------------------------------------------------------------------
            .def    RESET                   ; Export program entry-point to
                                            ; make it known to linker.
;-------------------------------------------------------------------------------
            .text                           ; Assemble into program memory.
            
;-------------------------------------------------------------------------------
RESET       mov.w   #__STACK_END,SP         ; Initialize stackpointer
StopWDT     mov.w   #WDTPW|WDTHOLD,&WDTCTL  ; Stop watchdog timer


;-------------------------------------------------------------------------------
; Main loop here
;-------------------------------------------------------------------------------
; Blink led
.def PADIR,PAOUT
			bis.b #0x01, &PADIR
outer
			xor.b #1, &PAOUT
			mov.w #0xFFFF, r5

inner
			dec.w r5
			tst.w r5
			jne inner
			jmp outer

;-------------------------------------------------------------------------------
; Stack Pointer definition
;-------------------------------------------------------------------------------
            .global __STACK_END
            .sect   .stack
            
;-------------------------------------------------------------------------------
; Interrupt Vectors
;-------------------------------------------------------------------------------
            .sect   ".reset"                ; MSP430 RESET Vector
            
            

        """)

    def assemble_code(self):
        """Kodu derler ve sonuçları GUI'de gösterir"""
        try:
            self.status_var.set("Derleniyor...")
            self.status_bar.configure(background='#FF9800', foreground='white')
            assembly_code = self.input_text.get("1.0", tk.END)
            machine_code, symbol_table, literals, relocation_entries, relocation_data = assemble(assembly_code)

            print(f"GUI'de alınan relocation_entries: {relocation_entries}")
            print(f"GUI Literals Before Display: {literals}, types: {[type(lit['value']) for lit in literals]}")
            print(f"Machine Code Before Display: {machine_code}, types: {[(type(addr), type(code)) for addr, code in machine_code]}")

            self.symbol_text.delete("1.0", tk.END)
            self.literals_text.delete("1.0", tk.END)
            self.machine_text.delete("1.0", tk.END)
            self.relocation_text.delete("1.0", tk.END)

            self.symbol_text.insert(tk.END, "Sembol    | Deger | Tur       | Bolum   | Tanimli | Global\n")
            self.symbol_text.insert(tk.END, "-------------------------------------------------------\n")
            for symbol, info in symbol_table.items():
                if isinstance(info, dict) and 'value' in info:
                    value = info['value']
                    print(f"Symbol Table Entry: {symbol}, value={value}, type={type(value)}")
                    self.symbol_text.insert(tk.END, f"{symbol:<10} | {value:04X} | {info['type']:<9} | {info['section']:<7} | {str(info['defined']):<7} | {str(info.get('is_global', False))}\n")
                else:
                    value = int(info) if isinstance(info, (int, str)) else 0
                    self.symbol_text.insert(tk.END, f"{symbol:<10} | {value:04X} | external   | none    | False   | False\n")

            self.literals_text.insert(tk.END, "Adres   | Deger   | Tur\n")
            self.literals_text.insert(tk.END, "-----------------------\n")
            for lit in literals:
                addr = lit['address']
                val = lit['value']
                print(f"Displaying Literal: addr={addr}, val={val}, type(val)={type(val)}")
                self.literals_text.insert(tk.END, f"{addr:04X}    | {val:04X} | {lit['type']}\n")

            self.machine_text.insert(tk.END, "Adres   | Kod\n")
            self.machine_text.insert(tk.END, "---------------\n")
            for addr, code in machine_code:
                print(f"Displaying Machine Code: addr={addr}, code={code}, types={(type(addr), type(code))}")
                self.machine_text.insert(tk.END, f"{addr:04X}    | {code:04X}\n")
            
            self.relocation_text.insert(tk.END, "Offset  | Symbol     | Type         | Section\n")
            self.relocation_text.insert(tk.END, "---------------------------------------------\n")
            if relocation_entries:
                for entry in relocation_entries:
                    self.relocation_text.insert(
                        tk.END,
                        f"{entry['offset']:04X}    | {entry['symbol']:<10} | {entry['type']:<12} | {entry['section']}\n"
                    )
            else:
                self.relocation_text.insert(tk.END, "(Relocation kaydı yok)\n")
        
            self.object_filename = create_object_file(machine_code, symbol_table, literals, relocation_entries, relocation_data)
            self.status_var.set(f"Derleme basarili! ELF Obje dosyasi olusturuldu: {self.object_filename}")
            self.status_bar.configure(background='#4CAF50', foreground='white')

        except Exception as e:
            messagebox.showerror("Derleme Hatasi", f"Kod derlenemedi:\n{str(e)}")
            self.status_var.set("Derleme basarisiz")
            self.status_bar.configure(background='#F44336', foreground='white')
            print(f"Exception Details: {str(e)}")

    def save_object_file(self):
        """ELF dosyasını kaydeder"""
        if not hasattr(self, 'object_filename'):
            messagebox.showwarning("Uyari", "Lutfen once kodu derleyin.")
            self.status_var.set("Once derleme yapin")
            self.status_bar.configure(background='#FF9800', foreground='white')
            return

        try:
            with open(self.object_filename, 'r') as f:
                content = f.read()
            with open(self.object_filename, 'w') as f:
                f.write(content)
            self.status_var.set(f"ELF Obje dosyasi kaydedildi: {self.object_filename}")
            self.status_bar.configure(background='#4CAF50', foreground='white')
        except Exception as e:
            messagebox.showerror("Hata", f"ELF Obje dosyasi kaydedilemedi: {str(e)}")
            self.status_var.set("ELF Obje dosyasi kaydetme hatasi")
            self.status_bar.configure(background='#F44336', foreground='white')

if __name__ == "__main__":
    root = tk.Tk()
    app = AssemblerGUI(root)
    root.mainloop()
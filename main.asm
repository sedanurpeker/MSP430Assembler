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
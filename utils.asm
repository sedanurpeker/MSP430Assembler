.text
FUNC_MUL:
    PUSH R5                ; Register yedekle
    MOV R4, R5             ; R4'ü R5'e kopyala
    ADD R4, R5             ; R5 = R4 + R4
    POP R5                 ; R5 restore
    RET                    ; Fonksiyondan dön
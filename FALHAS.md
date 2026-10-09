# FALHAS

| data | o que quebrou | menor correção | prompt \| infra |
|---|---|---|---|
| 09/10/2026 | conferência da voz reprovava fala com número (Whisper escreve "529", texto diz "quinhentas e vinte e nove": 78%) | `norm()` passa dígitos para extenso e iguala feminino/variantes | infra |

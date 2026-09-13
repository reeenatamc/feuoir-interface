#ifndef RELOJ_MAESTRO_H
#define RELOJ_MAESTRO_H

// Reloj maestro del PCM1808: 12.288 MHz = 256 fS a 48 kHz, por GPIO21 (CLOCK GPOUT0).
// Por qué esta solución y no la del PIO: docs/reloj.md.
#define RELOJ_MAESTRO_GPIO 21
#define RELOJ_MAESTRO_HZ 12288000

// 1 cuando el firmware se compila para tomar SCKI del oscilador externo (opción FEUOIR_RELOJ_EXTERNO
// de CMake). Entonces GPOUT0 queda apagado; ver la sección del oscilador externo en docs/reloj.md.
#ifndef RELOJ_EXTERNO
#define RELOJ_EXTERNO 0
#endif

// Pone clk_sys en 61.44 MHz y, salvo con RELOJ_EXTERNO, saca clk_sys / 5 por GPIO21 con el ciclo de
// trabajo corregido. Cambia clk_sys, así que va antes de configurar cualquier cosa que calcule
// divisores a partir de clk_sys, como las máquinas de estados del PIO.
void reloj_maestro_iniciar(void);

#endif

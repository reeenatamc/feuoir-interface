#ifndef INFORME_H
#define INFORME_H

// Informe del firmware de verificación del reloj maestro (pasos 1 y 2 de docs/reloj.md).
// Esta parte no toca hardware: recibe los valores ya leídos de los registros y del contador de
// frecuencia, los decodifica y escribe una línea por chequeo. Por eso se puede probar en la Mac
// con tests/verificacion_sin_placa.py.

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    bool reloj_externo;             // firmware compilado para el oscilador externo: GPOUT0 apagado
    uint32_t pll_cs;                // PLL_SYS CS
    uint32_t pll_fbdiv_int;         // PLL_SYS FBDIV_INT
    uint32_t pll_prim;              // PLL_SYS PRIM
    uint32_t gpout0_ctrl;           // CLK_GPOUT0_CTRL
    uint32_t gpout0_div;            // CLK_GPOUT0_DIV
    bool fc_pll_terminado;          // el contador de frecuencia terminó a tiempo
    uint32_t fc_pll_estado;         // FC0_STATUS al medir la salida del PLL
    uint32_t fc_pll_resultado;      // FC0_RESULT al medir la salida del PLL
    bool fc_gpio20_terminado;
    uint32_t fc_gpio20_estado;      // FC0_STATUS al medir GPIO20 (CLOCK GPIN0)
    uint32_t fc_gpio20_resultado;   // FC0_RESULT al medir GPIO20
} lecturas_t;

// Campos de los registros. Tienen los mismos valores que las macros del SDK 2.3.1;
// verificar_reloj.c lo comprueba con static_assert al compilar para el Pico.
#define INF_PLL_CS_LOCK              0x80000000u
#define INF_PLL_CS_REFDIV_MASK       0x3fu
#define INF_PLL_FBDIV_INT_MASK       0xfffu
#define INF_PLL_PRIM_POSTDIV1_LSB    16
#define INF_PLL_PRIM_POSTDIV2_LSB    12
#define INF_PLL_PRIM_POSTDIV_MASK    0x7u
#define INF_GPOUT_CTRL_ENABLE        0x00000800u
#define INF_GPOUT_CTRL_DC50          0x00001000u
#define INF_GPOUT_CTRL_AUXSRC_LSB    5
#define INF_GPOUT_CTRL_AUXSRC_MASK   0xfu
#define INF_GPOUT_AUXSRC_CLK_SYS     6u
#define INF_GPOUT_DIV_INT_LSB        8
#define INF_GPOUT_DIV_FRAC_MASK      0xffu
#define INF_FC0_STATUS_DIED          0x10000000u
#define INF_FC0_RESULT_KHZ_LSB       5
#define INF_FC0_RESULT_KHZ_MASK      0x1ffffffu
#define INF_FC0_RESULT_FRAC_MASK     0x1fu

// Intervalo del contador: 15 son 32 ms, con exactitud de 62.5 Hz (tabla 206 de la hoja del RP2040).
#define INF_FC0_INTERVALO            15u
#define INF_FC0_EXACTITUD_HZ         62.5

// Escribe el informe número n llamando a linea() una vez por línea, sin salto de línea al final.
// Devuelve la cantidad de chequeos que fallaron.
int informe_escribir(const lecturas_t *l, unsigned n, void (*linea)(const char *texto));

#endif

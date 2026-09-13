#include <stdio.h>

#include "informe.h"

// Lo que tiene que dar la configuración de reloj_maestro.c.
#define PLL_REFDIV 1u
#define PLL_FBDIV 128u
#define PLL_POSTDIV1 5u
#define PLL_POSTDIV2 5u
#define GPOUT_DIVISOR 5u
#define PLL_HZ 61440000.0
#define MCLK_HZ 12288000.0

// GPOUT0 sale del mismo cristal que usa el contador, así que una diferencia solo puede venir del
// contador: se acepta el doble de su exactitud. El oscilador externo tiene su propio cristal: los
// 1000 ppm detectan un oscilador equivocado, no juzgan su error, que depende de la pieza.
#define TOLERANCIA_HZ (2*INF_FC0_EXACTITUD_HZ)
#define TOLERANCIA_EXTERNO_HZ (MCLK_HZ*1000e-6)

typedef void (*escritor_t)(const char *texto);

static int chequeo_entero(escritor_t linea, const char *nombre, uint32_t valor, uint32_t esperado) {
    char texto[160];
    int falla = valor != esperado;
    snprintf(texto, sizeof texto, "%s=%lu esperado=%lu resultado=%s",
             nombre, (unsigned long)valor, (unsigned long)esperado, falla ? "FALLA" : "ok");
    linea(texto);
    return falla;
}

static double frecuencia_hz(uint32_t resultado) {
    uint32_t khz = (resultado >> INF_FC0_RESULT_KHZ_LSB) & INF_FC0_RESULT_KHZ_MASK;
    uint32_t fraccion = resultado & INF_FC0_RESULT_FRAC_MASK;      // en 1/32 de kHz
    return khz*1000.0 + fraccion*1000.0/32;
}

static int chequeo_frecuencia(escritor_t linea, const char *nombre, bool terminado, uint32_t estado,
                              uint32_t resultado, double esperado, double tolerancia, const char *sin_senal) {
    char texto[240];
    if (!terminado) {
        snprintf(texto, sizeof texto, "%s=sin_medicion esperado=%.0f resultado=FALLA "
                 "nota=el contador de frecuencia no terminó", nombre, esperado);
        linea(texto);
        return 1;
    }
    double medido = frecuencia_hz(resultado);
    if ((estado & INF_FC0_STATUS_DIED) || medido < 1000.0) {
        snprintf(texto, sizeof texto, "%s=0 esperado=%.0f resultado=FALLA nota=%s", nombre, esperado, sin_senal);
        linea(texto);
        return 1;
    }
    double diferencia = medido - esperado;
    int falla = (diferencia < 0 ? -diferencia : diferencia) > tolerancia;
    snprintf(texto, sizeof texto, "%s=%.2f esperado=%.0f diferencia_ppm=%.1f tolerancia_hz=%.1f resultado=%s",
             nombre, medido, esperado, diferencia/esperado*1e6, tolerancia, falla ? "FALLA" : "ok");
    linea(texto);
    return falla;
}

int informe_escribir(const lecturas_t *l, unsigned n, escritor_t linea) {
    char texto[160];
    int fallas = 0;
    snprintf(texto, sizeof texto, "inicio_informe=%u modo=%s", n, l->reloj_externo ? "oscilador_externo" : "gpout0");
    linea(texto);

    // Paso 1: la configuración leída de vuelta y la salida del PLL medida contra el cristal.
    fallas += chequeo_entero(linea, "pll_refdiv", l->pll_cs & INF_PLL_CS_REFDIV_MASK, PLL_REFDIV);
    fallas += chequeo_entero(linea, "pll_enganchado", (l->pll_cs & INF_PLL_CS_LOCK) != 0, 1);
    fallas += chequeo_entero(linea, "pll_fbdiv", l->pll_fbdiv_int & INF_PLL_FBDIV_INT_MASK, PLL_FBDIV);
    fallas += chequeo_entero(linea, "pll_postdiv1",
                             (l->pll_prim >> INF_PLL_PRIM_POSTDIV1_LSB) & INF_PLL_PRIM_POSTDIV_MASK, PLL_POSTDIV1);
    fallas += chequeo_entero(linea, "pll_postdiv2",
                             (l->pll_prim >> INF_PLL_PRIM_POSTDIV2_LSB) & INF_PLL_PRIM_POSTDIV_MASK, PLL_POSTDIV2);
    fallas += chequeo_entero(linea, "gpout0_enable", (l->gpout0_ctrl & INF_GPOUT_CTRL_ENABLE) != 0, !l->reloj_externo);
    if (!l->reloj_externo) {
        fallas += chequeo_entero(linea, "gpout0_dc50", (l->gpout0_ctrl & INF_GPOUT_CTRL_DC50) != 0, 1);
        fallas += chequeo_entero(linea, "gpout0_fuente",
                                 (l->gpout0_ctrl >> INF_GPOUT_CTRL_AUXSRC_LSB) & INF_GPOUT_CTRL_AUXSRC_MASK,
                                 INF_GPOUT_AUXSRC_CLK_SYS);
        fallas += chequeo_entero(linea, "gpout0_divisor_entero", l->gpout0_div >> INF_GPOUT_DIV_INT_LSB, GPOUT_DIVISOR);
        fallas += chequeo_entero(linea, "gpout0_divisor_fraccion", l->gpout0_div & INF_GPOUT_DIV_FRAC_MASK, 0);
    }
    fallas += chequeo_frecuencia(linea, "pll_hz", l->fc_pll_terminado, l->fc_pll_estado, l->fc_pll_resultado,
                                 PLL_HZ, TOLERANCIA_HZ, "el contador no ve la salida del PLL");

    // Paso 2: la frecuencia que entra por GPIO20.
    if (l->reloj_externo) {
        fallas += chequeo_frecuencia(linea, "gpio20_hz", l->fc_gpio20_terminado, l->fc_gpio20_estado,
                                     l->fc_gpio20_resultado, MCLK_HZ, TOLERANCIA_EXTERNO_HZ,
                                     "sin señal en GPIO20: falta el cable desde la salida del oscilador externo");
    } else {
        fallas += chequeo_frecuencia(linea, "gpio20_hz", l->fc_gpio20_terminado, l->fc_gpio20_estado,
                                     l->fc_gpio20_resultado, MCLK_HZ, TOLERANCIA_HZ,
                                     "sin señal en GPIO20: falta el puente con GPIO21");
    }

    snprintf(texto, sizeof texto, "fin_informe=%u fallas=%d resultado=%s", n, fallas, fallas ? "FALLA" : "ok");
    linea(texto);
    return fallas;
}

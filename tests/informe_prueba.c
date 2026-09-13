// Casos para la parte del firmware de verificación que no toca hardware (firmware/informe.c).
// Se compila y se corre en la Mac con tests/verificacion_sin_placa.py.

#include <stdio.h>
#include <string.h>

#include "informe.h"

static char salida[4096];
static int casos_fallidos = 0;

static void guardar(const char *texto) {
    strncat(salida, texto, sizeof salida - strlen(salida) - 2);
    strcat(salida, "\n");
}

// Registro FC0_RESULT: kHz enteros y fracción en 1/32 de kHz.
static uint32_t fc0(uint32_t khz, uint32_t fraccion) {
    return (khz << INF_FC0_RESULT_KHZ_LSB) | fraccion;
}

// Lo que leería el firmware con todo configurado como en reloj_maestro.c y el puente puesto.
static lecturas_t en_orden(void) {
    lecturas_t l = {0};
    l.pll_cs = INF_PLL_CS_LOCK | 1u;
    l.pll_fbdiv_int = 128;
    l.pll_prim = (5u << INF_PLL_PRIM_POSTDIV1_LSB) | (5u << INF_PLL_PRIM_POSTDIV2_LSB);
    l.gpout0_ctrl = INF_GPOUT_CTRL_ENABLE | INF_GPOUT_CTRL_DC50 | (INF_GPOUT_AUXSRC_CLK_SYS << INF_GPOUT_CTRL_AUXSRC_LSB);
    l.gpout0_div = 5u << INF_GPOUT_DIV_INT_LSB;
    l.fc_pll_terminado = true;
    l.fc_pll_resultado = fc0(61440, 0);
    l.fc_gpio20_terminado = true;
    l.fc_gpio20_resultado = fc0(12288, 0);
    return l;
}

static void comprobar(const char *nombre, lecturas_t l, int fallas_esperadas, const char *debe_decir[]) {
    salida[0] = '\0';
    int fallas = informe_escribir(&l, 1, guardar);
    int bien = fallas == fallas_esperadas;
    for (int i = 0; debe_decir[i]; i++) {
        if (!strstr(salida, debe_decir[i])) {
            printf("       falta en el informe: %s\n", debe_decir[i]);
            bien = 0;
        }
    }
    printf("%s %s\n", bien ? "ok    " : "FALLA ", nombre);
    if (!bien) {
        printf("       fallas del informe: %d, esperadas: %d\n%s", fallas, fallas_esperadas, salida);
        casos_fallidos++;
    }
}

static void imprimir(const char *texto) {
    printf("%s\n", texto);
}

int main(int argc, char **argv) {
    // Con una opción imprime un informe con el formato del firmware, para tests/lectura_sin_placa.py.
    if (argc > 1) {
        lecturas_t l = en_orden();
        if (strcmp(argv[1], "--imprimir-sin-dc50") == 0) {
            l.gpout0_ctrl &= ~INF_GPOUT_CTRL_DC50;
        } else if (strcmp(argv[1], "--imprimir") != 0) {
            fprintf(stderr, "opción desconocida: %s\n", argv[1]);
            return 2;
        }
        informe_escribir(&l, 7, imprimir);
        return 0;
    }

    comprobar("todo en orden", en_orden(), 0, (const char *[]){
        "inicio_informe=1 modo=gpout0",
        "pll_fbdiv=128 esperado=128 resultado=ok",
        "gpout0_dc50=1 esperado=1 resultado=ok",
        "gpout0_fuente=6 esperado=6 resultado=ok",
        "gpout0_divisor_entero=5 esperado=5 resultado=ok",
        "pll_hz=61440000.00 esperado=61440000 diferencia_ppm=0.0",
        "gpio20_hz=12288000.00 esperado=12288000 diferencia_ppm=0.0",
        "fin_informe=1 fallas=0 resultado=ok", NULL});

    lecturas_t l = en_orden();
    l.gpout0_ctrl &= ~INF_GPOUT_CTRL_DC50;
    comprobar("DC50 sin activar", l, 1, (const char *[]){"gpout0_dc50=0 esperado=1 resultado=FALLA", NULL});

    l = en_orden();                                  // clk_sys en los 125 MHz con que arranca el SDK
    l.pll_fbdiv_int = 125;
    l.pll_prim = (6u << INF_PLL_PRIM_POSTDIV1_LSB) | (2u << INF_PLL_PRIM_POSTDIV2_LSB);
    l.fc_pll_resultado = fc0(125000, 0);
    l.fc_gpio20_resultado = fc0(25000, 0);
    comprobar("PLL sin configurar", l, 5, (const char *[]){
        "pll_fbdiv=125 esperado=128 resultado=FALLA", "pll_postdiv1=6 esperado=5 resultado=FALLA",
        "pll_postdiv2=2 esperado=5 resultado=FALLA", "gpio20_hz=25000000.00", NULL});

    l = en_orden();
    l.gpout0_div = (5u << INF_GPOUT_DIV_INT_LSB) | 128u;
    comprobar("divisor de GPOUT0 con fracción", l, 1, (const char *[]){"gpout0_divisor_fraccion=128 esperado=0 resultado=FALLA", NULL});

    l = en_orden();
    l.fc_gpio20_resultado = 0;
    l.fc_gpio20_estado = INF_FC0_STATUS_DIED;
    comprobar("sin puente entre GPIO21 y GPIO20", l, 1, (const char *[]){"falta el puente con GPIO21", NULL});

    l = en_orden();
    l.fc_gpio20_resultado = fc0(12288, 3);           // +93.75 Hz: dentro de los 125 Hz
    comprobar("GPIO20 dentro de la exactitud del contador", l, 0, (const char *[]){"gpio20_hz=12288093.75", NULL});

    l = en_orden();
    l.fc_gpio20_resultado = fc0(12288, 5);           // +156.25 Hz: fuera de los 125 Hz
    comprobar("GPIO20 fuera de la exactitud del contador", l, 1, (const char *[]){"gpio20_hz=12288156.25", NULL});

    l = en_orden();
    l.fc_pll_terminado = false;
    comprobar("contador que no termina", l, 1, (const char *[]){"pll_hz=sin_medicion", NULL});

    l = en_orden();                                  // oscilador externo: GPOUT0 apagado
    l.reloj_externo = true;
    l.gpout0_ctrl = 0;
    l.gpout0_div = 0;
    l.fc_gpio20_resultado = fc0(12288, 13);          // +406.25 Hz, +33.1 ppm
    comprobar("oscilador externo a +33 ppm", l, 0, (const char *[]){
        "modo=oscilador_externo", "gpout0_enable=0 esperado=0 resultado=ok", "diferencia_ppm=33.1", NULL});

    l.fc_gpio20_resultado = fc0(12000, 0);
    comprobar("oscilador externo de 12 MHz en vez de 12.288 MHz", l, 1, (const char *[]){"gpio20_hz=12000000.00", NULL});

    l = en_orden();
    l.reloj_externo = true;
    comprobar("GPOUT0 encendido con el oscilador externo", l, 1,
              (const char *[]){"gpout0_enable=1 esperado=0 resultado=FALLA", NULL});

    return casos_fallidos != 0;
}

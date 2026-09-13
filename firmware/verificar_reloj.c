// Firmware de verificación del reloj maestro: pasos 1 y 2 de docs/reloj.md. Sin probar en placa.
//
// Configura el reloj igual que el firmware principal y cada 2 s imprime por USB un informe con los
// registros del PLL y de GPOUT0 leídos de vuelta, la salida del PLL medida con el contador de
// frecuencia del RP2040 y la frecuencia que entra por GPIO20. Para el paso 2, GPIO20 va puenteado a
// GPIO21 (o a la salida del oscilador externo si se compiló con FEUOIR_RELOJ_EXTERNO).

#include <assert.h>
#include <stdio.h>

#include "hardware/clocks.h"
#include "hardware/gpio.h"
#include "hardware/regs/clocks.h"
#include "hardware/regs/pll.h"
#include "hardware/structs/clocks.h"
#include "hardware/structs/pll.h"
#include "pico/stdlib.h"

#include "informe.h"
#include "reloj_maestro.h"

#define GPIO_GPIN0 20       // CLOCK GPIN0 en la tabla de funciones del RP2040

// Las constantes de informe.h tienen que coincidir con las del SDK.
static_assert(INF_PLL_CS_LOCK == PLL_CS_LOCK_BITS, "PLL CS LOCK");
static_assert(INF_PLL_CS_REFDIV_MASK << PLL_CS_REFDIV_LSB == PLL_CS_REFDIV_BITS, "PLL CS REFDIV");
static_assert(INF_PLL_FBDIV_INT_MASK == PLL_FBDIV_INT_BITS, "PLL FBDIV_INT");
static_assert(INF_PLL_PRIM_POSTDIV1_LSB == PLL_PRIM_POSTDIV1_LSB, "PLL PRIM POSTDIV1");
static_assert(INF_PLL_PRIM_POSTDIV_MASK << INF_PLL_PRIM_POSTDIV1_LSB == PLL_PRIM_POSTDIV1_BITS, "PLL PRIM POSTDIV1");
static_assert(INF_PLL_PRIM_POSTDIV2_LSB == PLL_PRIM_POSTDIV2_LSB, "PLL PRIM POSTDIV2");
static_assert(INF_PLL_PRIM_POSTDIV_MASK << INF_PLL_PRIM_POSTDIV2_LSB == PLL_PRIM_POSTDIV2_BITS, "PLL PRIM POSTDIV2");
static_assert(INF_GPOUT_CTRL_ENABLE == CLOCKS_CLK_GPOUT0_CTRL_ENABLE_BITS, "GPOUT0 CTRL ENABLE");
static_assert(INF_GPOUT_CTRL_DC50 == CLOCKS_CLK_GPOUT0_CTRL_DC50_BITS, "GPOUT0 CTRL DC50");
static_assert(INF_GPOUT_CTRL_AUXSRC_LSB == CLOCKS_CLK_GPOUT0_CTRL_AUXSRC_LSB, "GPOUT0 CTRL AUXSRC");
static_assert(INF_GPOUT_CTRL_AUXSRC_MASK << INF_GPOUT_CTRL_AUXSRC_LSB == CLOCKS_CLK_GPOUT0_CTRL_AUXSRC_BITS,
              "GPOUT0 CTRL AUXSRC");
static_assert(INF_GPOUT_AUXSRC_CLK_SYS == CLOCKS_CLK_GPOUT0_CTRL_AUXSRC_VALUE_CLK_SYS, "GPOUT0 AUXSRC clk_sys");
static_assert(INF_GPOUT_DIV_INT_LSB == CLOCKS_CLK_GPOUT0_DIV_INT_LSB, "GPOUT0 DIV INT");
static_assert(INF_GPOUT_DIV_FRAC_MASK == CLOCKS_CLK_GPOUT0_DIV_FRAC_BITS, "GPOUT0 DIV FRAC");
static_assert(INF_FC0_STATUS_DIED == CLOCKS_FC0_STATUS_DIED_BITS, "FC0 STATUS DIED");
static_assert(INF_FC0_RESULT_KHZ_LSB == CLOCKS_FC0_RESULT_KHZ_LSB, "FC0 RESULT KHZ");
static_assert(INF_FC0_RESULT_KHZ_MASK << INF_FC0_RESULT_KHZ_LSB == CLOCKS_FC0_RESULT_KHZ_BITS, "FC0 RESULT KHZ");
static_assert(INF_FC0_RESULT_FRAC_MASK == CLOCKS_FC0_RESULT_FRAC_BITS, "FC0 RESULT FRAC");
static_assert(INF_FC0_INTERVALO <= CLOCKS_FC0_INTERVAL_BITS, "FC0 INTERVAL");

// Mide con el contador de frecuencia (FC0, sección 2.15.4 de la hoja del RP2040), igual que
// frequency_count_khz del SDK pero con otro intervalo y sin perder la fracción: frequency_count_khz
// usa 1 ms, con exactitud de 2 kHz, y devuelve solo kHz enteros. Devuelve false si no termina en 1 s.
static bool medir(uint32_t fuente, uint32_t *estado, uint32_t *resultado) {
    fc_hw_t *fc = &clocks_hw->fc0;
    absolute_time_t limite = make_timeout_time_ms(1000);
    while (fc->status & CLOCKS_FC0_STATUS_RUNNING_BITS) {
        if (time_reached(limite)) {
            return false;
        }
    }
    fc->ref_khz = clock_get_hz(clk_ref) / 1000;     // clk_ref viene del cristal de 12 MHz
    fc->interval = INF_FC0_INTERVALO;
    fc->min_khz = 0;
    fc->max_khz = 0xffffffff;
    fc->src = fuente;                               // escribir la fuente arranca la medición
    limite = make_timeout_time_ms(1000);
    while (!(fc->status & CLOCKS_FC0_STATUS_DONE_BITS)) {
        if (time_reached(limite)) {
            return false;
        }
    }
    *estado = fc->status;
    *resultado = fc->result;
    return true;
}

static void escribir_linea(const char *texto) {
    printf("%s\n", texto);
}

int main(void) {
    reloj_maestro_iniciar();        // primero: cambia clk_sys
    stdio_init_all();

    gpio_set_function(GPIO_GPIN0, GPIO_FUNC_GPCK);  // GPIO20 como entrada de reloj para el paso 2
    gpio_pull_down(GPIO_GPIN0);                     // sin puente lee cero en vez de ruido

    for (unsigned n = 1;; n++) {
        lecturas_t l = {.reloj_externo = RELOJ_EXTERNO};
        l.pll_cs = pll_sys_hw->cs;
        l.pll_fbdiv_int = pll_sys_hw->fbdiv_int;
        l.pll_prim = pll_sys_hw->prim;
        l.gpout0_ctrl = clocks_hw->clk[clk_gpout0].ctrl;
        l.gpout0_div = clocks_hw->clk[clk_gpout0].div;
        l.fc_pll_terminado = medir(CLOCKS_FC0_SRC_VALUE_PLL_SYS_CLKSRC_PRIMARY, &l.fc_pll_estado, &l.fc_pll_resultado);
        l.fc_gpio20_terminado = medir(CLOCKS_FC0_SRC_VALUE_CLKSRC_GPIN0, &l.fc_gpio20_estado, &l.fc_gpio20_resultado);
        informe_escribir(&l, n, escribir_linea);
        sleep_ms(2000);
    }
}

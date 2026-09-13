#include <assert.h>

#include "hardware/clocks.h"
#include "hardware/structs/clocks.h"
#include "reloj_maestro.h"

// PLL del sistema: 12 MHz / REFDIV 1 x FBDIV 128 = VCO de 1536 MHz, y 1536 / (5 x 5) = 61.44 MHz.
// set_sys_clock_pll usa REFDIV 1 (PLL_SYS_REFDIV en el SDK 2.3.1) y calcula FBDIV a partir del VCO.
#define VCO_HZ 1536000000
#define POSTDIV1 5
#define POSTDIV2 5
#define SYSCLK_HZ 61440000
#define DIVISOR_GPOUT 5

static_assert(VCO_HZ / (POSTDIV1 * POSTDIV2) == SYSCLK_HZ, "el PLL no da 61.44 MHz");
static_assert(SYSCLK_HZ == DIVISOR_GPOUT * RELOJ_MAESTRO_HZ, "el divisor no da 12.288 MHz exactos");
static_assert(RELOJ_MAESTRO_HZ == 256 * 48000, "el reloj maestro no es 256 fS a 48 kHz");
static_assert(RELOJ_MAESTRO_GPIO == 21, "clk_gpout0 solo sale por GPIO21");

void reloj_maestro_iniciar(void) {
    set_sys_clock_pll(VCO_HZ, POSTDIV1, POSTDIV2);

    clock_gpio_init_int_frac8(RELOJ_MAESTRO_GPIO, CLOCKS_CLK_GPOUT0_CTRL_AUXSRC_VALUE_CLK_SYS, DIVISOR_GPOUT, 0);

    // DC50 se escribe a mano. El divisor de reloj del RP2040 trabaja con los flancos de subida de la
    // fuente, así que con un divisor impar no da 50 %: dividir por 5 deja el ciclo de trabajo en 40 %,
    // justo el mínimo que acepta el PCM1808 (40 % a 60 %). DC50 mueve el flanco de bajada de la salida
    // al flanco de bajada de la fuente y devuelve el 50 % (hoja del RP2040, sección 2.15.3.4).
    // clock_gpio_init_int_frac8 del SDK 2.3.1 escribe CTRL con solo la fuente y ENABLE, así que el bit
    // va después de la llamada: si se pusiera antes, la llamada lo borraría. La hoja permite activar
    // DC50 con el reloj corriendo, y los ciclos que salen antes de esta línea quedan en 40 %, todavía
    // dentro de lo que acepta el PCM1808.
    hw_set_bits(&clocks_hw->clk[clk_gpout0].ctrl, CLOCKS_CLK_GPOUT0_CTRL_DC50_BITS);
}

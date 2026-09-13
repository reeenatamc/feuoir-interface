#include "pico/stdlib.h"
#include "reloj_maestro.h"

int main(void) {
    reloj_maestro_iniciar();    // primero: cambia clk_sys

    // El LED parpadea cada medio segundo para mostrar que el firmware sigue corriendo después
    // de cambiar el reloj.
    gpio_init(PICO_DEFAULT_LED_PIN);
    gpio_set_dir(PICO_DEFAULT_LED_PIN, GPIO_OUT);
    bool encendido = false;
    while (true) {
        encendido = !encendido;
        gpio_put(PICO_DEFAULT_LED_PIN, encendido);
        sleep_ms(500);
    }
}

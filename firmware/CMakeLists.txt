cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico CACHE STRING "Placa")

include(pico_sdk_import.cmake)

project(feuoir_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

# SCKI del PCM1808 desde el oscilador externo en vez de GPOUT0 (docs/reloj.md, oscilador externo).
option(FEUOIR_RELOJ_EXTERNO "Tomar SCKI del oscilador externo y dejar GPOUT0 apagado" OFF)

add_executable(feuoir
    main.c
    reloj_maestro.c
)

target_link_libraries(feuoir pico_stdlib hardware_clocks)
target_compile_definitions(feuoir PRIVATE RELOJ_EXTERNO=$<BOOL:${FEUOIR_RELOJ_EXTERNO}>)

pico_add_extra_outputs(feuoir)

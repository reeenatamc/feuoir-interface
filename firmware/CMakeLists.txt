cmake_minimum_required(VERSION 3.13)

set(PICO_BOARD pico CACHE STRING "Placa")

include(pico_sdk_import.cmake)

project(feuoir_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)

pico_sdk_init()

add_executable(feuoir
    main.c
    reloj_maestro.c
)

target_link_libraries(feuoir pico_stdlib hardware_clocks)

pico_add_extra_outputs(feuoir)

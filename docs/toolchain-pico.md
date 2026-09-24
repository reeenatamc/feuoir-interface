# Toolchain del Pico

Procedimiento que funcionó el 2026-09-13 en macOS 26.5.2 (MacBook Pro 2019, Intel), sin la placa conectada. Todo queda en ~/pico, fuera de este repo.

| Componente | Versión |
|---|---|
| pico-sdk | 2.3.1 (commit 079c6f3), con el submódulo lib/tinyusb (86ad6e5) |
| pico-examples | sdk-2.3.1 (commit 0d62f75) |
| Arm GNU Toolchain | 14.2.rel1, arm-none-eabi-gcc 14.2.1 20241119 |
| picotool | 2.3.1 (commit 2041936), con libusb 1.0.30 de Homebrew |
| CMake | 4.4.3 de Homebrew |
| make | /usr/bin/make de macOS |
| Compilador para picotool | AppleClang 21.0.0 |
| Python que encontró el SDK | 3.14.7 de Homebrew |

### 1. CMake

```
brew install cmake
```

### 2. Toolchain de Arm

Arm dejó de publicar builds para Mac Intel después de la 14.2.rel1: la 14.3.rel1 y la 15.2.rel1 solo salen para darwin-arm64. El tar.xz se descarga en una carpeta temporal y no necesita sudo.

```
cd "$(mktemp -d)"
URL=https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz
curl -fLO "$URL"
curl -fLO "$URL.sha256asc"
cat arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz.sha256asc
shasum -a 256 arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz
mkdir -p ~/pico/toolchain
tar -xJf arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi.tar.xz -C ~/pico/toolchain
```

Los dos hashes tienen que coincidir: 2d9e717dd4f7751d18936ae1365d25916534105ebcb7583039eff1092b824505. Extraído ocupa 996 MB.

### 3. pico-sdk y pico-examples

Del SDK solo se inicializa el submódulo lib/tinyusb, que es el que da soporte USB. Los demás no hicieron falta para compilar.

```
cd ~/pico
git clone --depth 1 --branch 2.3.1 https://github.com/raspberrypi/pico-sdk.git
git -C pico-sdk submodule update --init --depth 1 lib/tinyusb
git clone --depth 1 --branch sdk-2.3.1 https://github.com/raspberrypi/pico-examples.git
```

### 4. picotool

Desde el SDK 2.0 la conversión de ELF a UF2 la hace picotool. Si el SDK no lo encuentra, lo baja y lo compila dentro de cada proyecto, así que se instala una vez aparte. Usa libusb y pkgconf de Homebrew.

```
cd ~/pico
git clone --depth 1 --branch 2.3.1 https://github.com/raspberrypi/picotool.git
cd picotool && mkdir build && cd build
export PICO_SDK_PATH=$HOME/pico/pico-sdk
cmake .. -DCMAKE_INSTALL_PREFIX=$HOME/pico/picotool-install -DPICOTOOL_FLAT_INSTALL=1
make -j4
make install
~/pico/picotool-install/picotool/picotool version
```

Tiene que responder picotool v2.3.1. Se compila con -j4 y no con todos los núcleos para no llenar la memoria.

### 5. Compilar el blink

Las tres variables se exportan en la terminal donde se compila.

```
export PICO_SDK_PATH=$HOME/pico/pico-sdk
export PICO_TOOLCHAIN_PATH=$HOME/pico/toolchain/arm-gnu-toolchain-14.2.rel1-darwin-x86_64-arm-none-eabi
export picotool_DIR=$HOME/pico/picotool-install/picotool
cd ~/pico/pico-examples && mkdir build && cd build
cmake .. -DPICO_BOARD=pico
cd blink
make -j4
```

Resultado: ~/pico/pico-examples/build/blink/blink.uf2, de 13312 bytes, 26 bloques UF2 para RP2040 en 0x10000000. La configuración tardó 16 s y la compilación 5 s, sin avisos. CMake avisa que se salta ejemplos de RP2350 y los que necesitan Mbed TLS, que no afectan al blink. En CMakeCache.txt, CMAKE_C_COMPILER apunta al gcc de ~/pico/toolchain. No se probó en una placa.

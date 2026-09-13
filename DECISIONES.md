# Decisiones

Lo que ya está decidido, para no volver a discutirlo.

## Entrada para la guitarra: tarjeta de sonido USB (2026-09-13)

El jack de 3.5 mm de la Mac (MacBook Pro 16", 2019) es combinado de audífonos y micrófono, así que un adaptador simple de 6.35 a 3.5 mm conectado ahí no funciona como entrada.

No se compra iRig ni cable en Y. Se usa una tarjeta de sonido USB de $6 a $10 con entrada de micrófono de tres contactos real, no combinada. Con esa entrada, un adaptador simple de 6.35 a 3.5 mm de $2 sí funciona.

## El micrófono interno solo valida el script (2026-09-13)

El micrófono interno de la Mac entrega un solo canal ya procesado, y ese procesamiento no se puede desactivar. Por eso no sirve para caracterizar la guitarra. Se usa solo para validar que medir.py funciona. La caracterización real se hace cuando llegue la tarjeta USB.

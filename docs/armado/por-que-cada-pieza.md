# Por qué va cada pieza

Este documento no dice dónde meter los cables, eso está en las imágenes de `pasos/` y en `mapa_de_agujeritos.md`.
Este dice para qué sirve cada cosa. El dibujo resumido es `por_que_cada_pieza.png`.

## Qué estamos armando y por qué

La guitarra no se puede enchufar directo a la tarjeta de sonido USB y esperar que suene bien. Lo que sale de las
pastillas de la guitarra es una señal muy pequeña y muy delicada: unas pocas decenas de milivoltios, y además sale de
una bobina de muchas vueltas, que se comporta como una fuente muy débil. Si le cuelgas algo que le pide corriente, la
señal se cae y el sonido se apaga y pierde agudos.

La entrada de micrófono de la tarjeta es justo eso, algo que pide corriente. Así que entre la guitarra y la tarjeta
hace falta una etapa que reciba la señal sin cargarla, la haga más grande y la entregue con fuerza. Eso es lo que
estás armando en la protoboard.

Además, los módulos de audio del proyecto todavía no llegan. Mientras tanto la tarjeta USB hace de sustituto, y así se
puede medir esta etapa de verdad, con la guitarra, antes de tener el resto.

## Pieza por pieza

### La piecita negra de ocho patitas

Es un amplificador operacional doble, un TL072. Dentro trae dos amplificadores independientes, y por eso la usamos
dos veces: una mitad para agrandar la señal y la otra para darle fuerza. Las ocho patitas son las entradas y salidas
de esas dos mitades más las dos de alimentación.

### Las dos cajitas con pilas

La señal de la guitarra sube y baja alrededor del cero. Para que el amplificador pueda seguirla en los dos sentidos
necesita electricidad por arriba y por abajo del cero. Por eso van dos pilas de 9 V en fila: una punta queda en +9 V,
la otra en -9 V, y el punto donde se juntan es el cero, lo que llamamos tierra. Todo el circuito mide sus voltajes
respecto de ese punto del medio.

### La lentejita 104 de la entrada, 100 nF

Deja pasar el temblor de la señal y frena cualquier voltaje quieto. Así, venga lo que venga por el cable de la
guitarra, a la etapa solo le entra la música.

### El tubito de 1 MΩ

Le da al circuito una referencia al cero. Sin él la entrada del amplificador queda al aire y se va sola a un extremo,
y la etapa no sirve. Es de 1 MΩ, un valor muy alto, justamente para no pedirle corriente a la guitarra: es lo que
hace que la pastilla no se sienta cargada y no pierda agudos.

### La perilla de 10 kΩ y el tubito de 1 kΩ

Estos dos deciden cuánto crece la señal. La cuenta es 1 más lo que marque la perilla dividido entre 1 kΩ. Con la
perilla en cero queda 1, es decir sale igual que entra. Con la perilla al máximo, 10 kΩ entre 1 kΩ da 10, más 1, o sea
11 veces. Por eso la ganancia va de 1 a 11.

### El tubito de 4.7 kΩ y la lentejita 102, 1 nF

Los dos juntos son un colador de agudos. Dejan pasar lo que es guitarra y cortan lo muy agudo, que ahí arriba ya no
es música sino ruido y radio colada por los cables. Van entre las dos mitades de la piecita negra.

### La segunda mitad de la piecita negra

No agranda nada: copia la señal tal cual y la entrega con fuerza. Sirve para que el cable hasta la tarjeta y la propia
entrada de la tarjeta no le quiten nada. Es lo que se llama un seguidor.

### El barrilito, el condensador de acoplo de salida

Otra vez lo mismo que la lentejita de la entrada, pero al revés: deja pasar el temblor hacia la tarjeta y frena los
voltajes quietos. Hace falta porque la entrada de micrófono de la tarjeta tiene su propio voltaje de reposo y no hay
que pelearse con él. Este es el único que tiene lado: la raya impresa es el negativo y va hacia la piecita negra, que
está centrada en cero, y el positivo hacia la tarjeta.

### Las otras dos lentejitas 104, las de los rieles

Son un depósito de electricidad pegado a la piecita negra. Cuando la señal da un golpe seco, la piecita pide corriente
de golpe, y las pilas y sus cables no son infinitamente rápidos. Estas dos tapan ese hueco.

## Por qué los cables van donde van

En la protoboard los cinco agujeritos de una fila, de un mismo lado de la zanja, están unidos por dentro con una
lámina de metal. Son un solo punto eléctrico. Entre una fila y otra no hay nada. Las cuatro tiras de los bordes son
cuatro puntos largos, uno cada una.

Entonces armar consiste en esto: cada vez que dos cosas del circuito tienen que tocarse, se meten en la misma fila. Y
cuando están en filas distintas, se junta con un cable. El cable no hace nada más que eso, unir dos puntos.

La piecita negra va montada a caballo sobre la zanja precisamente para que sus patitas de la izquierda y las de la
derecha caigan en filas separadas, y cada una pueda recibir lo suyo sin tocarse entre ellas.

## Cómo sabemos que está bien

El trazado de la protoboard no se dibujó a ojo. `draw_input_stage_breadboard.py` deriva los puntos del propio dibujo y
los compara contra `input_stage_split`, el circuito que está simulado en `spice/netlists/input_stage.cir`. Si un cable
estuviera en la fila equivocada, el guion falla al dibujar, no en la mesa.

Lo que la simulación no puede ver es si un pincho quedó a medias o si una pieza se metió corrida. Para eso es la
revisión con el multímetro de `prueba_pitido.png`, que se hace antes de poner las pilas.

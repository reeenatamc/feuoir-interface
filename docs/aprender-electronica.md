# Un camino para entender la electrónica de este proyecto

Esto no es una lista de todo lo que existe. Es el orden más corto para que la etapa de entrada que estás armando deje
de ser una receta y pase a ser algo que puedes leer y modificar sola. Cada paso trae qué concepto es, dónde aparece en
este repositorio, y con qué estudiarlo.

## Con qué estudiar

Lo mínimo, si solo vas a usar una cosa:

- Charles Platt, *Make: Electronics*. Se aprende armando y rompiendo cosas, con experimentos cortos. Hay traducción al
  español publicada por Anaya, *Electrónica: aprende haciendo*. Es el que más se parece a cómo estamos trabajando.

Gratis y muy útiles:

- El simulador de Paul Falstad, en falstad.com/circuit. Se abre en el navegador, no instala nada y dibuja la corriente
  moviéndose por los cables. Puedes armar ahí la etapa de entrada y ver qué pasa al girar la perilla. Para una máquina
  con poca memoria es lo mejor que hay.
- El libro de texto de allaboutcircuits.com, en su sección Textbook. Está en inglés, es gratis y cubre desde la ley de
  Ohm hasta amplificadores operacionales.

Para tener a mano cuando ya sepas buscar:

- Forrest Mims, *Getting Started in Electronics*. Es un cuaderno dibujado a mano, barato y sorprendentemente denso.
- Paul Scherz y Simon Monk, *Practical Electronics for Inventors*. Referencia gorda, para consultar, no para leer de
  corrido.
- Horowitz y Hill, *The Art of Electronics*. El libro serio del área. Déjalo para después, pero existe y está bien
  saber que ahí está la respuesta buena a casi todo.

## El orden

### 1. Voltaje, corriente y resistencia

Qué es cada una y cómo se relacionan con la ley de Ohm. Y de ahí, el divisor de tensión, que es el circuito más usado
del mundo.

En este repositorio: el divisor de la prueba de 750 Hz contra la tarjeta USB, con las resistencias de 100 kΩ y 1 kΩ,
en `docs/reloj.md`.

### 2. Condensadores

La idea clave: un condensador deja pasar lo que cambia y frena lo que está quieto. Cuanto más rápido cambia algo, más
fácil le resulta pasar.

En este repositorio: la lentejita 104 de la entrada y el barrilito de la salida están ahí exactamente por eso, para
dejar pasar la música y frenar los voltajes de reposo.

### 3. Filtros RC

Una resistencia y un condensador juntos deciden a partir de qué frecuencia una señal empieza a pasar o a cortarse. Ahí
aparece la frecuencia de corte y la fórmula 1 partido por 2 pi R C.

En este repositorio: el tubito de 4.7 kΩ con la lentejita 102 es un filtro que corta lo agudo. Y el cálculo de por qué
el barrilito de 2.2 µF da 1.21 Hz de corte, y uno de 10 µF da 0.27 Hz, sale de esa misma fórmula. Está en
`docs/entrada-analogica.md` y en `docs/compras.md`.

### 4. Impedancia

Por qué una fuente débil se cae cuando le cuelgas una carga. Es lo que explica todo el proyecto: la guitarra es una
fuente de impedancia alta y la entrada de la tarjeta es de impedancia baja, y por eso hace falta algo en medio.

En este repositorio: el tubito de 1 MΩ es grande justamente para no cargar la pastilla de la guitarra.

### 5. El amplificador operacional

El TL072. Las dos configuraciones que usamos: el amplificador no inversor, donde la ganancia sale de dos resistencias,
y el seguidor, que no amplifica pero entrega fuerza. Con eso entiendes por qué la perilla y el tubito de 1 kΩ dan de 1
a 11 veces.

En este repositorio: `docs/entrada-analogica.md` y la netlist `spice/netlists/input_stage.cir`.

### 6. Alimentación partida y desacoplo

Por qué dos pilas con el punto medio como cero, y por qué se pone un condensador pequeño pegado a cada patita de
alimentación.

En este repositorio: `docs/bitacora.md`, entrada 24, donde se decidió pasar de una sola pila a la alimentación
partida.

## Cómo comprobar que lo entendiste

Sin tocar la protoboard, y sin gastar nada:

1. Arma la etapa de entrada en falstad.com/circuit y mira la señal en cada punto.
2. Cambia el tubito de 1 kΩ por uno de 2 kΩ y predice la ganancia antes de mirarla.
3. Corre las simulaciones que ya están en `simulaciones/` y compara lo que salga con tu predicción.

Si los tres te salen, la etapa ya no es una receta.

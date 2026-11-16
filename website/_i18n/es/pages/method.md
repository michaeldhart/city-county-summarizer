---
title: Cómo se escribe esto
es_source_hash: 32f57a0ca494b441
es_model: claude-sonnet-4-5
es_translated_at: '2026-11-16T12:11:17+00:00'
---

# Cómo se escribe esto

**Ningún reportero humano asiste a estas reuniones.** Cada despacho en The Belvidere
Wire es escrito por Claude, un modelo de IA creado por Anthropic, a partir de los documentos primarios que un gobierno publica por sí mismo. Nada aquí es reporteado, y nada aquí es editado por una persona antes de ser publicado.

**Tampoco una persona elige la portada.** Los resúmenes en ella son escritos por el
mismo modelo y clasificados entre sí por él. Decidir qué encabeza una portada
es el acto más editorial que realiza una publicación, y aquí una máquina lo realiza.

Esas son cosas inusuales para que diga una publicación, así que esta página las dice
claramente y establece exactamente qué ve la máquina, qué se le dice que haga, y
dónde se sabe que está equivocada.

## De qué se escribe un despacho

Para una **reunión de la junta del condado o Committee of the Whole**: la agenda completa según
publicada en el portal Diligent del condado, y la transcripción automática
completa del video de la reunión donde la reunión fue transmitida — aproximadamente
trece mil palabras para una reunión de noventa minutos.

Para una **reunión de un organismo subordinado** — zonificación, planificación, salud, servidumbres agrícolas:
los mismos materiales de la agenda. Estas reuniones no se graban, así que no hay
registro de lo que se dijo, solo de lo que estaba programado.

Para una **reunión de la ciudad, distrito escolar, distrito de parques o distrito de conservación**: el PDF de la agenda, y el PDF de las actas una vez que el organismo las publica —
lo cual es usualmente en la reunión siguiente, un mes después. Los documentos escaneados se
pasan primero por reconocimiento óptico de caracteres.

La columna de Recursos en cada despacho enumera exactamente cuáles de estos existieron para
esa reunión. Los documentos listados bajo *Also linked from the agenda* **no** fueron
leídos — son material de apoyo al que la agenda apunta, publicado por
exhaustividad.

## Qué se le dice a la máquina que haga

Reportar, no caracterizar. Registrar el recuento de votos, no una teoría de por qué alguien
votó de esa manera. Corregir los errores obvios en una transcripción automática —
los nombres propios salen mal, los números y cifras en dólares salen
limpiamente — y citar con moderación. No inventar nada que no esté en la fuente.

Donde solo existe una agenda y no hay registro de lo que realmente sucedió,
el despacho se etiqueta como **adelanto de la agenda** y describe solo lo que un organismo
estaba programado para tratar. No le dirá que se decidió nada,
porque nada en sus fuentes lo dice.

Los materiales suelen llegar después de que se publica el primer despacho — las actas un mes
después, un video al día siguiente, subtítulos un día después de eso. Cada semana el periódico
vuelve a revisar cada reunión del último año. Cuando las actas, un video o sus
subtítulos han aparecido desde entonces, el despacho es **escrito nuevamente a partir del conjunto más completo** y reemplaza el primero, y su firma dice la fecha en que fue reescrito.
Nada se agrega al texto anterior: el nuevo despacho es un resumen nuevo de
todo lo ahora disponible.

## Qué es la portada

La portada se ensambla a partir de **resúmenes** — artículos cortos de un párrafo cada uno,
escritos a partir de un despacho en lugar de la reunión detrás de él. Un resumen es un
resumen de un resumen, lo cual vale la pena saber: está a dos pasos del
registro oficial, y el despacho al que enlaza siempre está más cerca de la verdad que
él.

Entre uno y tres se escriben por reunión, ordenados en tres tipos:

- **Cívico** — algo que un residente de este condado querría saber y sobre lo cual aún podría
  actuar. Los residentes presentándose, hablando u objetando cuentan más
  aquí que cualquier otra cosa, seguido de decisiones aún abiertas a influencia: una votación
  por venir, un período de comentarios, una audiencia con una fecha, una vacante recibiendo
  solicitudes.
- **Significativo** — decisiones reales y gastos reales que no alcanzan eso.
- **Resumen** — un relato sencillo de una reunión de rutina, escrito solo cuando nada
  de lo anterior aplica, de modo que una reunión aburrida produzca algo honesto en lugar de
  algo inflado.

Los resúmenes nunca son citas textuales, por la misma razón que los despachos no lo son: la mayoría de lo que
se extrae de ellos comenzó como un subtítulo automático.

## Cómo se elige la portada

Cada resumen de los últimos treinta días es un candidato. Se ordenan por tipo,
luego por una puntuación que el modelo asignó cuando los escribió, luego por recencia — y
luego la lista corta se entrega de nuevo al modelo, que la pone en orden final,
juzgando cada resumen contra los otros en lugar de en aislamiento.

Ese último pase existe porque cada resumen se escribe sin saber que existe ningún otro
resumen. Solo algo mirándolos juntos puede notar que un
comité tomando un asunto y la junta decidiéndolo son una historia y una
ranura en la página.

Los criterios en los que clasifica son los de arriba: asistencia, si una decisión aún está
abierta, si cambia lo que un residente paga, posee o se le permite hacer,
la escala de dinero público involucrado, y si un residente podría enterarse de otra manera.
Las aprobaciones de rutina, los informes recibidos y las mociones de procedimiento clasifican hacia abajo.

**Hay una palanca humana.** Un resumen puede ser *fijado*, lo cual lo fuerza a aparecer en la
página independientemente de dónde clasificó. Fijar no puede promover un resumen — mantiene
su posición clasificada — y cada fijación se registra en
[un archivo en el repositorio público](https://github.com/michaeldhart/city-county-summarizer/blob/main/docs/PINS.md).
Nada más en este sitio es elegido por una persona.

## La edición en español

Los despachos, números de portada, los documentos de contexto y esta página también se publican en español, bajo
[/es/]({{ '/es/beats/' | loc | relative_url }}). **El español es una traducción automática
de la página en inglés**, realizada por el mismo modelo después de que se publica el inglés — nada en ella es re-reporteado, y el original en inglés
gobierna donde quiera que los dos difieran. Cada página traducida lo dice y
enlaza al original.

Se le dice al modelo que traduzca fiel y completamente, que deje cada cifra,
recuento de votos y nombre tal como está escrito, y que mantenga los nombres de gobiernos, organismos y
personas en inglés. Una traducción se rechaza y se rehace si omite un encabezado o
una viñeta, o si sus números no coinciden con el inglés. Lo que eso no puede detectar es
el fraseo: una oración puede ser precisa y aún leerse extrañamente. Hasta que un hablante de español
haya revisado una página, dice que no lo ha sido.

Un despacho que aún no ha sido traducido no tiene página en español, y los enlaces a él
desde el sitio en español van al inglés en su lugar.

## Ediciones

Una nueva edición se publica cada lunes por la mañana. Lleva lo que había sido publicado para entonces,
lo cual no es lo mismo que todo lo que se reunió la semana anterior: una reunión cuya
agenda llega tarde aparece en una edición posterior en su lugar. Un despacho que es
reescrito cuando llegan las actas o subtítulos reemplaza el anterior en su ronda,
pero no se publica en la portada nuevamente.

Cada vez que se reconstruye la portada se publica como un número numerado y se mantiene
en [/issues/]({{ '/issues/' | loc | relative_url }}). Nada se sobrescribe, así que lo que
esta publicación encabezó en cualquier día dado queda en el registro — incluyendo los
días que encabezó con lo incorrecto.

Los números anteriores quedan congelados tal como se publicaron. Si un despacho es corregido posteriormente, el resumen
impreso en un número que ya ha salido **no** se actualiza, y puede que ya no
coincida con el despacho al que enlaza. El despacho es el que hay que confiar.

## Dónde se sabe que esto está equivocado

- **Las agendas no siempre se publican con anticipación.** El condado a veces publica
  una cerca de, o después de, la reunión. Una reunión puede aparecer en video días
  antes de que exista un despacho para ella.
- **No se garantiza que se recojan materiales tardíos.** La verificación semanal
  cubre solo el último año. Un documento que no se puede leer — un escaneo que el
  reconocimiento de caracteres no logra — se intenta cuatro veces, luego se deja solo y
  se lista como no leído. Un video cuyos subtítulos no han aparecido después de cuatro verificaciones
  permanece como un enlace y no se lee. El Park District y la City mantienen solo un año
  o dos en sus páginas públicas, así que lo que eliminan ya no se verifica.
- **Dos organismos nunca aparecen.** El Local Emergency Planning Committee y la
  Veteran's Assistance Commission no publican en ningún portal que podamos leer.
  Están en la lista de rondas y nunca han producido un despacho.
- **Los registros antiguos desaparecen.** Algunos gobiernos mantienen solo uno o dos años de
  documentos en su sitio público. Donde el material ha desaparecido desde entonces, un
  despacho puede enlazar a menos de lo que fue escrito.
- **Las transcripciones automáticas distorsionan nombres.** La mayoría de los errores obvios se corrigen.
  Algunos no lo serán.
- **Un resumen no es un registro.** Donde un despacho y un documento oficial
  discrepan, el documento oficial está en lo correcto. Cada uno de ellos está enlazado.
- **Un despacho puede ser publicado en la ronda incorrecta.** Qué organismo se reunió se lee de
  la etiqueta que el portal de reuniones pone en él. Cuando el condado cambió de plataformas en
  mayo de 2026, cada reunión transferida del sistema anterior fue reetiquetada como una
  reunión del County Board, y diecinueve despachos — zonificación, salud, planificación,
  los Committees of the Whole — estuvieron en la ronda del County Board hasta que se detectó el 17 de septiembre de 2026. Han sido rearchivados, lo que movió sus
  direcciones web. Los despachos mismos no fueron afectados: cada uno fue escrito desde
  la agenda de su propia reunión y nombra al organismo correctamente.
- **La misma reunión puede aparecer dos veces.** Un gobierno ocasionalmente lista una
  reunión bajo dos entradas con diferentes documentos adjuntos. Ambas se leen,
  y ambas se publican, así que una ronda puede llevar dos despachos de una fecha.
- **Los resúmenes no saben de los demás.** Cada uno se escribe de una reunión en
  aislamiento. Se le pide al pase de clasificación que detecte la misma historia apareciendo dos veces,
  pero es lo único que puede, y a veces lo pasará por alto.
- **Un resumen puede describir una reunión de la cual nadie tiene registro.** Donde un despacho
  fue escrito solo a partir de una agenda, sus resúmenes describen lo que un organismo estaba
  programado para tratar — no lo que hizo. El despacho lo dice; el resumen tiene
  un párrafo y puede que no lo diga.
- **El periódico se queda en silencio.** Cuando muy pocas reuniones caen dentro de la ventana, se
  amplía hasta que la página se llena, y la línea de folio dice qué tan atrás llegó.

## Qué registra este sitio sobre usted

{% if site.goatcounter_code -%}
Este sitio cuenta las vistas de página, usando [GoatCounter](https://www.goatcounter.com),
un servicio de análisis de código abierto. No establece cookies y no recopila datos personales, que es por qué no se le pidió que descartara un banner para leer esto. Lo que
registra es la página, de dónde llegó, su país, su navegador y
sistema operativo, y el tamaño de su pantalla — contado en agregado, nunca
vinculado a una persona, nunca vendido y nunca compartido.

No tiene que tomar eso por confianza: los números están
[publicados en su totalidad](https://{{ site.goatcounter_code }}.goatcounter.com), la misma vista que tiene quien publica.
Una publicación que le pide que crea que una máquina la escribió no debería mantener
su audiencia en secreto.

{% else -%}
No se cuenta nada. Este sitio no ejecuta análisis, no establece cookies, y no tiene
registro de que usted estuvo aquí.

{% endif -%}
Tres cosas no están cubiertas por eso, y todas vale la pena decirlas claramente.

**Leer por feed es invisible aquí.** [El periódico]({{ '/feed/meetings.xml' | loc | relative_url }}) y
[la edición]({{ '/feed/issues.xml' | loc | relative_url }}) son obtenidos por su lector en lugar de cargados como
una página, y nada en este sitio cuenta esos. Quien sirve los archivos puede ver
la solicitud, como con cualquier dirección web.

**La búsqueda permanece en su navegador.** El índice de búsqueda se descarga y se consulta
en su máquina en lugar de en un servidor, así que lo que escribe no se envía a ninguna parte
como una búsqueda.

**Su idioma se recuerda, en su navegador.** Si su navegador está configurado para
preferir español, la primera página en inglés que abra lo envía a su versión en español, cuando existe una. Elegir un idioma con el enlace en el pie de página guarda
esa elección en el almacenamiento local de su navegador para que no se cuestione de nuevo.
Nunca sale de su máquina y nada en este sitio lo lee excepto esa única
línea de código.

El único lugar donde este sitio pide algo sobre usted es el formulario de contacto, que
es un Google Form. El nombre y el correo electrónico son opcionales allí — si los proporciona, van
a Google junto con lo que sea que escriba, y una corrección no los necesita.

## Correcciones

Si un despacho comete un error, los documentos subyacentes están enlazados en la
parte superior de la página — comience allí, luego
[envíe una corrección](https://docs.google.com/forms/d/e/1FAIpQLScxpZW5UnwwEPaKGP5ls7szdGotiMh_0GA6FJIaHnRAG2WJiQ/viewform). Lo mismo aplica para un resumen, y para que la portada
haya encabezado con lo incorrecto: la clasificación es un juicio, y los juicios pueden
ser discutidos.

Las correcciones se hacen reescribiendo el despacho desde la fuente, no editando la
oración que estaba mal — el despacho tiene que seguir coincidiendo con el registro del que vino.

Ese formulario también es la forma de comunicarse con una persona sobre cualquier otra cosa. Donde la
falla está en la maquinaria en lugar de en un despacho, el código que produce
todo esto es público y puede ser [presentado como un problema](https://github.com/michaeldhart/city-county-summarizer/issues) en su lugar.

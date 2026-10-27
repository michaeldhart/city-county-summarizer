---
title: Cómo se escribe esto
es_source_hash: 9d0d4552143afc96
es_model: claude-sonnet-4-5
es_translated_at: '2026-10-27T00:26:01+00:00'
---

# Cómo se escribe esto

**Ningún reportero humano asiste a estas reuniones.** Cada despacho en The Belvidere
Wire es escrito por Claude, un modelo de IA creado por Anthropic, a partir de los documentos primarios que un gobierno publica por sí mismo. Nada aquí es reportado, y nada aquí es editado por una persona antes de ser publicado.

**Tampoco una persona elige la portada.** Los resúmenes en ella son escritos por el
mismo modelo y clasificados entre sí por él. Decidir qué encabeza una portada
es el acto más editorial que realiza una publicación, y aquí una máquina lo realiza.

Estas son cosas inusuales para que las diga una publicación, así que esta página las dice
claramente y establece exactamente qué ve la máquina, qué se le dice que haga, y
dónde se sabe que está equivocada.

## De qué se escribe un despacho

Para una **reunión del County Board o Committee of the Whole**: la agenda completa según
publicada en el portal Diligent del condado, y la transcripción automática
completa del video de la reunión donde se transmitió la reunión — aproximadamente
trece mil palabras para una reunión de noventa minutos.

Para una **reunión de sub-organismo** — zonificación, planeación, salud, servidumbre agrícola:
los mismos materiales de la agenda. Estas reuniones no se graban, así que no hay
registro de lo que se dijo, solo de lo que estaba programado.

Para una **reunión de ciudad, distrito escolar, distrito de parques o distrito de conservación**: el PDF de la agenda, y el PDF de las actas una vez que el organismo las publica —
lo cual es usualmente en la siguiente reunión, un mes después. Los documentos escaneados son
procesados primero mediante reconocimiento óptico de caracteres.

La columna Resources en cada despacho enumera exactamente cuáles de estos existieron para
esa reunión. Los documentos enumerados bajo *Also linked from the agenda* **no** fueron
leídos — son material de respaldo al que señala la agenda, publicado por
completitud.

## Qué se le dice a la máquina que haga

Reportar, no caracterizar. Registrar el conteo de votos, no una teoría de por qué alguien
votó de esa manera. Corregir los errores obvios en una transcripción automática —
los nombres propios salen mal, los números y cifras en dólares salen
limpiamente — y citar con moderación. No inventar nada que no esté en la fuente.

Donde solo existe una agenda y no hay registro de lo que realmente sucedió,
el despacho está etiquetado como **adelanto de la agenda** y describe solo lo que un organismo
estaba programado para tratar. No le dirá que se decidió nada,
porque nada en sus fuentes lo dice.

## Qué es la portada

La portada se ensambla a partir de **resúmenes** — artículos cortos de un párrafo cada uno,
escritos a partir de un despacho en lugar del evento detrás de él. Un resumen es un
resumen de un resumen, lo cual vale la pena saber: está a dos pasos del
registro oficial, y el despacho al que enlaza siempre está más cerca de la verdad que
él.

Entre uno y tres se escriben por reunión, ordenados en tres tipos:

- **Civic** — algo que un residente de este condado querría saber y aún podría
  actuar sobre ello. Residentes presentándose, hablando u objetando cuenta más
  aquí que cualquier otra cosa, seguido de decisiones aún abiertas a influencia: un voto
  por venir, un período de comentarios, una audiencia con fecha, una vacante que acepta
  solicitudes.
- **Significant** — decisiones reales y gasto real que no llegan a eso.
- **Summary** — un relato simple de una reunión rutinaria, escrito solo cuando nada
  de lo anterior aplica, para que una reunión aburrida produzca algo honesto en lugar de
  algo inflado.

Los resúmenes nunca son citas, por la misma razón que los despachos no lo son: la mayoría de lo que
se extrae de ellos comenzó como un subtítulo automático.

## Cómo se elige la portada

Cada resumen de los últimos treinta días es candidato. Se ordenan por tipo,
luego por un puntaje que el modelo asignó cuando los escribió, luego por actualidad — y
luego la lista corta se devuelve al modelo, que la pone en orden final,
juzgando cada resumen contra los otros en lugar de aisladamente.

Ese último pase existe porque cada resumen se escribe sin saber que existe ningún otro
resumen. Solo algo que los mire juntos puede notar que un
comité que toma un asunto y la junta que lo decide son una historia y una
posición en la página.

Los criterios en los que se clasifica son los anteriores: asistencia, si una decisión aún está
abierta, si cambia lo que un residente paga, posee o se le permite hacer,
la escala de dinero público involucrado, y si un residente podría aprenderlo de otra
manera. Aprobaciones rutinarias, informes recibidos y mociones procesales se clasifican abajo.

**Hay una palanca humana.** Un resumen puede ser *fijado*, lo que lo fuerza a la
página independientemente de dónde se clasificó. Fijar no puede promover un resumen — mantiene
su posición clasificada — y cada fijación se registra en
[un archivo en el repositorio público](https://github.com/michaeldhart/city-county-summarizer/blob/main/docs/PINS.md).
Nada más en este sitio es elegido por una persona.

## La edición en español

Los despachos, los contextos y esta página también se publican en español, bajo
[/es/]({{ '/es/beats/' | loc | relative_url }}). **El español es una traducción automática
de la página en inglés**, hecha por el mismo modelo después de que el inglés se publica — nada en ella se re-reporta, y el inglés
original gobierna dondequiera que los dos difieran. Cada página traducida lo dice y
enlaza al original.

Se le dice al modelo que traduzca fiel y completamente, que deje cada cifra,
conteo de votos y nombre como está escrito, y que mantenga los nombres de gobiernos, organismos y
personas en inglés. Una traducción se rechaza y se rehace si omite un encabezado o
una viñeta, o si sus números no coinciden con el inglés. Lo que eso no puede captar es
la redacción: una oración puede ser precisa y aún leerse extrañamente. Hasta que una persona
de habla hispana haya revisado una página, dice que no lo ha sido.

Un despacho que aún no ha sido traducido no tiene página en español, y los enlaces a él
desde el sitio en español van al inglés en su lugar.

## Ediciones

Una nueva edición se publica cada lunes por la mañana. Lleva lo que se había publicado para entonces,
lo cual no es lo mismo que todo lo que se reunió la semana anterior: una reunión cuya
agenda o actas llegan tarde aparece en una edición posterior en su lugar.

Cada vez que se reconstruye la portada se publica como un número numerado y se mantiene
en [/issues/]({{ '/issues/' | loc | relative_url }}). Nada se sobrescribe, así que con lo que
esta publicación encabezó en cualquier día dado permanece en el registro — incluyendo los
días que encabezó con lo incorrecto.

Los números anteriores están congelados según publicados. Si un despacho se corrige posteriormente, el resumen
impreso en un número que ya se publicó **no** se actualiza, y puede ya no
coincidir con el despacho al que enlaza. El despacho es en el que hay que confiar.

## Dónde se sabe que esto está equivocado

- **Las agendas no siempre se publican con anticipación.** El condado a veces publica
  una cerca de, o después de, la reunión. Una reunión puede aparecer en video días
  antes de que exista un despacho para ella.
- **Dos organismos nunca aparecen.** El Local Emergency Planning Committee y la
  Veteran's Assistance Commission no publican en ningún portal que podamos leer.
  Están en la lista de cobertura y nunca han producido un despacho.
- **Los registros antiguos desaparecen.** Algunos gobiernos mantienen solo uno o dos años de
  documentos en su sitio público. Donde el material ha desaparecido desde entonces, un
  despacho puede enlazar a menos de lo que se escribió.
- **Las transcripciones automáticas distorsionan los nombres.** La mayoría de los errores obvios se corrigen.
  Algunos no lo serán.
- **Un resumen no es un registro.** Donde un despacho y un documento oficial
  difieren, el documento oficial es correcto. Cada uno de ellos está enlazado.
- **Un despacho puede ser publicado en la cobertura equivocada.** Qué organismo se reunió se lee de
  la etiqueta que el portal de reuniones le pone. Cuando el condado cambió de plataforma en
  mayo de 2026, cada reunión transferida del sistema antiguo fue reetiquetada como una
  reunión del County Board, y diecinueve despachos — zonificación, salud, planeación,
  los Committees of the Whole — permanecieron en la cobertura del County Board hasta que se
  detectó el 17 de septiembre de 2026. Han sido rearchivados, lo que movió sus
  direcciones web. Los despachos mismos no fueron afectados: cada uno se escribió desde
  la agenda de su propia reunión y nombra al organismo correctamente.
- **La misma reunión puede aparecer dos veces.** Un gobierno ocasionalmente enumera una
  reunión bajo dos entradas con diferentes documentos adjuntos. Ambas se leen,
  y ambas se publican, así que una cobertura puede llevar dos despachos de una fecha.
- **Los resúmenes no saben unos de otros.** Cada uno se escribe de una reunión en
  aislamiento. El pase de clasificación se le pide que detecte la misma historia apareciendo dos veces,
  pero es lo único que puede, y a veces lo pasará por alto.
- **Un resumen puede describir una reunión de la que nadie tiene registro.** Donde un despacho
  se escribió solo de una agenda, sus resúmenes describen lo que un organismo estaba
  programado para tratar — no lo que hizo. El despacho lo dice; el resumen tiene
  un párrafo y puede no hacerlo.
- **El wire se queda en silencio.** Cuando muy pocas reuniones caen dentro de la ventana, se
  amplía hasta que la página se llena, y la línea de folio dice qué tan atrás llegó.

## Qué registra este sitio sobre usted

{% if site.goatcounter_code -%}
Este sitio cuenta vistas de página, usando [GoatCounter](https://www.goatcounter.com),
un servicio de analíticas de código abierto. No establece cookies y no recopila datos personales, por eso no se le pidió que descartara un banner para leer esto. Lo que
registra es la página, de dónde llegó, su país, su navegador y
sistema operativo, y el tamaño de su pantalla — contado en conjunto, nunca
vinculado a una persona, nunca vendido y nunca compartido.

No tiene que tomar eso por confianza: los números están
[publicados en su totalidad](https://{{ site.goatcounter_code }}.goatcounter.com), la misma vista que tiene quien publica.
Una publicación que le pide que crea que una máquina la escribió no debería mantener
su lectoría en secreto.

{% else -%}
Nada se cuenta. Este sitio no ejecuta analíticas, no establece cookies, y no tiene
registro de que usted estuvo aquí.

{% endif -%}
Tres cosas no están cubiertas por eso, y todas valen la pena decirlas claramente.

**Leer por feed es invisible aquí.** [El wire]({{ '/feed/meetings.xml' | loc | relative_url }}) y
[la edición]({{ '/feed/issues.xml' | loc | relative_url }}) son obtenidos por su lector en lugar de cargarse como
una página, y nada en este sitio cuenta esos. Quien sea que sirva los archivos puede ver
la solicitud, como con cualquier dirección web.

**La búsqueda permanece en su navegador.** El índice de búsqueda se descarga y consulta
en su máquina en lugar de en un servidor, así que lo que escribe no se envía a ningún lado
como búsqueda.

**Su idioma se recuerda, en su navegador.** Si su navegador está configurado para
preferir español, la primera página en inglés que abra lo envía a su versión en español, cuando exista una. Elegir un idioma con el enlace en el pie de página guarda
esa elección en el almacenamiento local de su navegador para que no se vuelva a adivinar.
Nunca sale de su máquina y nada en este sitio lo lee excepto esa única
línea de código.

El único lugar donde este sitio pide algo sobre usted es el formulario de contacto, que
es un Google Form. Nombre y correo electrónico son opcionales allí — si los da, van
a Google junto con lo que escriba, y una corrección no los necesita.

## Correcciones

Si un despacho comete un error, los documentos subyacentes están enlazados en la
parte superior de la página — comience allí, luego
[envíe una corrección](https://docs.google.com/forms/d/e/1FAIpQLScxpZW5UnwwEPaKGP5ls7szdGotiMh_0GA6FJIaHnRAG2WJiQ/viewform). Lo mismo aplica para un resumen, y para que la portada
haya encabezado con lo incorrecto: la clasificación es un juicio, y los juicios pueden
ser discutidos.

Las correcciones se hacen re-escribiendo el despacho desde la fuente, no editando la
oración que estaba equivocada — el despacho tiene que seguir coincidiendo con el registro del que
vino.

Ese formulario es también la manera de contactar a una persona sobre cualquier otra cosa. Donde la
falla está en la maquinaria en lugar de en un despacho, el código que produce
todo esto es público y puede ser [planteado como un issue](https://github.com/michaeldhart/city-county-summarizer/issues) en su lugar.

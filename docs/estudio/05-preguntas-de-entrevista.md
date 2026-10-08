# 05 — Preguntas de entrevista

Preguntas típicas sobre este proyecto y cómo responderlas con seguridad.
Practica diciéndolas en voz alta en inglés también.

## Sobre el modelo de consentimiento

**¿Por qué no modelar el consentimiento como un simple sí/no?**
Porque el consentimiento en salud tiene cuatro dimensiones: quién, a quién, para
qué propósito y qué categorías de datos (más hasta cuándo). Un solo booleano no
puede expresar "mi cardiólogo puede ver mis análisis para tratarme, pero nadie
puede usar mi genética para investigar". Si no puedes expresar el matiz, filtras
datos.

**¿Cómo compruebas que un consentimiento cubre una petición?**
Con una operación de bits: `concedido & solicitado == solicitado`. Las categorías
son una máscara de 16 bits, así que cubrir todo lo pedido es un solo `AND`.
Además se comprueba que el propósito coincida (clave distinta) y que no haya
caducado.

**¿Por qué una máscara de bits?**
Porque es exacta, rápida y encaja en la EVM, que trabaja con enteros. Todo el
alcance de un consentimiento cabe en un número. El límite es 16 categorías, de
sobra para el dominio.

## Sobre el clasificador

**¿Por qué un modelo lineal y no un LLM?**
Porque la decisión afecta a datos sensibles y tiene que ser **auditable**. Un
modelo lineal (TF-IDF + regresión logística) es una suma ponderada de palabras,
así que la explicación son los términos con más peso, directamente. Además es
determinista y funciona offline, sin claves ni red. La interfaz permite cambiar a
un modelo más potente después sin tocar las reglas.

**¿Cómo manejas que una petición pida varias categorías a la vez?**
Es un problema multi-etiqueta: uso un clasificador *uno-contra-el-resto*
(one-vs-rest), un binario por categoría, y combino las que superan el umbral en
una máscara.

**¿Cómo das explicabilidad?**
Multiplico el vector TF-IDF de la petición por los coeficientes de la clase
elegida y me quedo con los términos de mayor contribución. Son las palabras que
empujaron la decisión.

**¿Y si el modelo no está seguro?**
La política convierte una confianza baja en **revisión humana**, no en una
adivinanza. La autoridad de la decisión está en las reglas, no en el modelo.

## Sobre la cadena

**¿No es exagerado usar blockchain para esto?**
La cadena no se usa para pagar, sino como un **registro de consentimiento
auditable e inmutable** que varias partes que no se fían del todo entre sí pueden
compartir. Ese es el caso de uso legítimo: una fuente de verdad que nadie puede
reescribir en secreto.

**¿Cómo proteges la privacidad si la cadena es permanente?**
No escribo nada personal ni clínico. Paciente y solicitante son `bytes32` (hash
de un identificador que vive fuera de la cadena); las categorías son bits y el
propósito un entero. Así la cadena es auditable pero no revela quién ni qué, y el
derecho al olvido sigue siendo posible borrando la correspondencia off-chain.

**¿Quién puede escribir en el contrato y por qué?**
Solo el operador (`onlyOperator`), que es el servicio de gestión de
consentimiento actuando por instrucción del paciente. Impide que alguien
falsifique consentimiento. Hay guardas con errores personalizados (`ZeroParty`,
`EmptyScope`, `PastExpiry`), más baratos en gas.

## Sobre el diseño y las pruebas

**¿Por qué separar el clasificador de la política?**
Porque son dos preguntas distintas: una de lenguaje (qué pide) y otra de
gobernanza (si se permite). Separarlas hace las reglas auditables, el modelo
reemplazable y la incertidumbre explícita (va a revisión). Y cada parte se prueba
en aislamiento.

**¿Por qué un `Protocol` para el registro y un fake en memoria?**
Para desacoplar el servicio de web3. La API funciona con o sin cadena, las
pruebas son rápidas, y una prueba de equivalencia comprueba que el fake y el
contrato real coinciden, para que el fake no se desvíe.

**¿Qué cubren las pruebas?**
El vocabulario de consentimiento, el clasificador (con una prueba de precisión en
datos no vistos), todos los caminos de la política (permitir, denegar, revisar,
caducidad, sensible), la API y el contrato (en una EVM en memoria, con las
guardas de operador y de entrada). Cobertura mínima en CI del 80 %.

## Pregunta trampa

**¿Qué cambiarías para llevarlo a producción?**
Cuatro cosas: (1) identidades autenticadas de verdad para pacientes y
solicitantes; (2) una gestión seria de la clave del operador (HSM o firma
delegada); (3) una auditoría formal del contrato antes de desplegarlo; y (4) un
clasificador más robusto ante lenguaje muy variado, midiendo siempre contra la
línea base actual. Y dejaría claro que es una implementación de referencia, no un
dispositivo médico certificado.

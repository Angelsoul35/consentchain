# 02 — El clasificador de IA

## Qué hace

El clasificador (`classifier.py`) recibe una petición de acceso en **lenguaje
natural** y la convierte en una afirmación estructurada:

- un **propósito** (tratamiento, pago, operaciones o investigación),
- un conjunto de **categorías de datos**,
- una **confianza** (probabilidad),
- y una **explicación** (las palabras que más pesaron en la decisión).

Ejemplo:

> "The treating physician needs the recent lab results and the current medication
> list to adjust therapy."

→ propósito = **TREATMENT**, categorías = **{lab_results, medications}**.

## Cómo está hecho

Dos piezas, las dos lineales y explicables:

1. **Vectorizador TF-IDF.** Convierte el texto en números. TF-IDF da más peso a
   las palabras distintivas (las que aparecen en pocas peticiones) y menos a las
   comunes. Usamos unigramas y bigramas (palabras sueltas y pares), así "billing
   department" cuenta como señal.
2. **Regresión logística.**
   - Para el **propósito**: un modelo multiclase (elige 1 de 4).
   - Para las **categorías**: un modelo *uno-contra-el-resto* (one-vs-rest), es
     decir, un clasificador binario por categoría, porque una petición puede
     pedir **varias** categorías a la vez (problema *multi-etiqueta*).

## ¿Por qué un modelo lineal y no un LLM grande?

Porque una decisión de consentimiento afecta a si se liberan datos sensibles de
salud. Si la petición se clasifica mal, el sistema o filtra datos o bloquea una
atención. Así que el modelo tiene que ser **auditable**: un revisor debe poder
ver **por qué** se leyó la petición de esa forma.

- Un modelo lineal es una **suma ponderada** de palabras. La explicación son
  literalmente los términos con más peso: no hace falta una aproximación posterior.
- Es **determinista y offline**: entrena con un conjunto sintético fijo, corre en
  local y no necesita ninguna clave ni red.

Además del TF-IDF de palabras, usamos **n-gramas de caracteres** (`char_wb`, 3-5)
combinados con `FeatureUnion`. Los n-gramas de carácter capturan raíces que se
repiten (*diagnos-*, *imaging*, *genom-*), lo que permite reconocer frases que el
modelo **no** vio en el entrenamiento. Esto es clave para una evaluación rigurosa
y sin fugas de información (ver abajo).

Un LLM grande sería más robusto ante frases muy distintas, pero perderíamos la
explicabilidad directa y añadiríamos dependencia externa. La interfaz `classify`
está pensada para poder cambiar el modelo más adelante sin tocar el resto.

## Evaluación rigurosa y sin fugas: ni 1.0 ni autoengaño (over/underfitting)

Con datos sintéticos de plantillas, un split aleatorio daría ~1.0 de exactitud, y
sería **mentira**: train y test compartirían las mismas frases y mediríamos
memorización, no generalización. Por eso `evaluation.py` hace un **split por
frases disjuntas**: las aperturas de propósito, las frases de categoría y las
cláusulas de contexto se parten, y las frases de prueba se construyen **solo con
las partes retiradas** del entrenamiento. Así, el fraseo de prueba nunca se vio.

```
$ python -m consentchain.evaluation
Phrase-disjoint evaluation (test wording never seen in training):
  train / test size    : 1600 / 533
  purpose accuracy     : 0.895     # 4 clases; el azar es 0.25
  purpose train acc    : 1.0
  purpose train-test gap: 0.105     # pequeña -> aprende señal, no plantillas
  category micro-F1    : 0.481      # multi-etiqueta, con vocabulario clínico NO visto
```

**El propósito generaliza de verdad:** en peticiones escritas a mano que **no**
están en el generador —"el fellow de cardiología quiere el ecocardiograma y la
troponina", "un estudio de cohorte con aprobación del IRB necesita las variantes
genómicas"— clasifica bien el propósito, y la brecha pequeña confirma que no hay
under ni overfitting.

**La extracción de categorías es más difícil, y el ~0.48 es una medición rigurosa
y sin fugas, no inflada.** Esto salió de **probar a mano** (no solo del eval automático): la
primera versión usaba un vocabulario de juguete y etiquetaba mal términos reales
como "ecocardiograma" (lo ponía como *demographics*). Ahora el vocabulario incluye
terminología clínica real (troponina, HbA1c, CBC, MRI, BRCA, PHQ-9, códigos CPT),
así que reconoce términos comunes — pero etiquetar un término sin **ningún
pariente** en el vocabulario de entrenamiento es genuinamente difícil, y el F1 de
frases disjuntas de ~0.48 lo refleja. En producción, la extracción de categorías de
calidad necesita un NER clínico / una ontología médica o datos reales; aquí el
modelo demuestra el pipeline y deja ese límite explícito y verificable. El
propósito y el modelo de consentimiento on-chain son las partes robustas, y la
generalización del pipeline queda confirmada además en un conjunto de datos
público y real (ver la sección "Validación en datos reales" más abajo).

Lección (la que pedía el usuario): un número automático (0.88) **escondía** un
fallo real que solo se vio **validando a mano** con términos clínicos de verdad.

## Validación en datos reales (benchmark)

La evaluación anterior usa datos **sintéticos** del propio proyecto. Para
demostrar que el pipeline generaliza con lenguaje clínico **de verdad** —y no
solo con nuestras plantillas— lo medimos también sobre un conjunto de datos
**público y real**. El código está en `consentchain/real_data.py` (la carga) y
`consentchain/real_benchmark.py` (la evaluación), y se ejecuta con:

```
python -m consentchain.real_benchmark
```

### La tarea y el mapeo de etiquetas

- **Dataset:** `gretelai/symptom_to_diagnosis` (Hugging Face, licencia Apache-2.0).
- **Qué es:** 1065 descripciones de síntomas en lenguaje natural, escritas en
  primera persona por pacientes, cada una etiquetada con **1 de 22 diagnósticos**
  clínicos (p. ej. *impetigo*, *malaria*, *migraine*, *diabetes*).
- **Por qué encaja con nuestra tarea:** el clasificador de ConsentChain lee texto
  de salud libre y lo mapea a una **categoría de datos**. Este dataset es ese
  mismo problema llevado al extremo real: en vez de un único bit `diagnoses`, hay
  que decidir **cuál de 22 condiciones reales** describe una narración genuina.
- **El mapeo:** cada una de las 22 etiquetas es una instancia de la categoría
  `DIAGNOSES` del proyecto (`DataCategory.DIAGNOSES`). Es decir, estamos
  estresando la *vía de reconocimiento de diagnósticos* del clasificador con 22
  condiciones reales. Ninguna de las 22 cae en las categorías extra-sensibles
  (`genetic`, `mental_health`), así que este benchmark ejercita la vía de
  diagnóstico general; lo sensible lo cubren las pruebas de la política.
- **Reutilizamos el pipeline del proyecto, no un modelo de usar y tirar:** el
  mismo `FeatureUnion` de TF-IDF (palabras + caracteres `char_wb`) y los mismos
  hiperparámetros de la regresión logística del propósito (`C=2.0`,
  `max_iter=2000`). Solo la cabeza es de una sola etiqueta, porque la tarea del
  dataset es de una sola etiqueta.
- **Subconjunto vendido:** se guarda bajo `datasets/` un subconjunto **balanceado**
  de 770 filas (35 por clase × 22 clases) en JSONL. Así el benchmark y las
  pruebas corren sin red y de forma determinista. Detalles y cómo regenerarlo:
  `datasets/README.md`.

### Las métricas: exactitud y macro-F1

Para una clase `c`, con verdaderos positivos `VP`, falsos positivos `FP` y falsos
negativos `FN`:

```
precisión(c)      P_c  = VP_c / (VP_c + FP_c)      # de lo que predije como c, ¿cuánto acerté?
exhaustividad(c)  R_c  = VP_c / (VP_c + FN_c)      # de los c reales, ¿cuántos encontré?
F1(c)                  = 2 · P_c · R_c / (P_c + R_c)  # media armónica de P y R
```

Y las dos métricas globales:

```
exactitud (accuracy) = aciertos / total
macro-F1             = (1/C) · Σ_c F1(c)           # promedio SIMPLE sobre las C clases
```

La clave del **macro**-F1 es que promedia por clase **sin** ponderar por tamaño:
trata a las 22 clases por igual. Eso importa porque la *exactitud* se puede
inflar si el modelo solo acierta la clase mayoritaria. En nuestro caso las clases
están balanceadas (35 cada una), así que exactitud y macro-F1 salen casi iguales
—señal sana de que no hay una clase dominando el número.

**Mini-ejemplo de F1.** Supón una clase con 10 casos reales. El modelo predice
esa clase 12 veces y acierta 9 (`VP=9`, `FP=3`, `FN=1`). Entonces `P = 9/12 =
0.75`, `R = 9/10 = 0.90`, y `F1 = 2·0.75·0.90 / (0.75+0.90) = 0.818`. El macro-F1
es el promedio de ese 0.818 con el F1 de las otras 21 clases.

### Validación cruzada (CV) y partición held-out

Medimos de **dos** formas complementarias, para no fiarnos de una sola partición:

1. **Validación cruzada estratificada de k=5 pliegues.** Se parte el conjunto en
   5 bloques manteniendo la proporción de clases ("estratificada"); se entrena con
   4 bloques y se evalúa con el que queda, rotando las 5 veces, y se promedian los
   resultados. La **desviación estándar** entre pliegues mide la **estabilidad**:
   si varía poco, el número no depende de la suerte del corte.
2. **Partición held-out 75/25 (estratificada y fija).** Entrenamos con el 75 % y
   evaluamos con el 25 % apartado. Esto nos deja comparar la puntuación en
   *train* contra la de *test* y calcular la **brecha**.

### Sobreajuste y subajuste: la brecha train/test

```
brecha = F1_train − F1_test
```

- **Sobreajuste (overfitting):** `F1_train` alto pero `F1_test` bajo → brecha
  grande. El modelo memorizó en vez de aprender.
- **Subajuste (underfitting):** `F1_train` y `F1_test` **ambos** bajos (cerca del
  baseline). El modelo es demasiado simple o no hay señal; ni siquiera aprende el
  entrenamiento.
- **Matiz importante (no "lisiar" el modelo):** un modelo lineal con n-gramas de
  carácter **satura** el entrenamiento (train ≈ 1.0). Eso **por sí solo no es
  sobreajuste**. Lo que decide es si la **CV** y el **held-out** coinciden y se
  mantienen altos. Si coinciden, la saturación del train es esperable y sana.

### El control de etiquetas barajadas

Es la prueba que distingue una señal real de un espejismo. Barajamos las
etiquetas (rompemos la relación texto→diagnóstico) y repetimos la CV con el
**mismo** pipeline. Si el modelo *siguiera* puntuando alto, habría una **fuga**
(leakage) o un artefacto. Lo correcto es que **colapse al baseline**. En nuestro
caso cae a macro-F1 ≈ 0.026 (≈ azar), lo que prueba que el 0.925 real viene del
**texto**, no de un truco.

### Ejemplo trabajado con los números reales

```
$ python -m consentchain.real_benchmark
  majority baseline    : acc 0.041  macro-F1 0.004  (chance acc 0.045)
  5-fold stratified CV : acc 0.945 +/- 0.010  macro-F1 0.946 +/- 0.010
  held-out train       : acc 0.998  macro-F1 0.998
  held-out test        : acc 0.927  macro-F1 0.925
  train/test gap       : 0.073  (macro-F1)
  shuffled-label ctrl  : acc 0.027  macro-F1 0.026
  regularisation path  : C=0.25:0.908  C=1:0.925  C=4:0.932
  VERDICT              : WELL-FIT
```

Cómo se lee, número a número:

- **Baseline (lo que hay que superar):** la clase mayoritaria da 0.041 de
  exactitud (azar = 1/22 ≈ 0.045) y 0.004 de macro-F1. Cualquier resultado real
  tiene que dejar esto muy atrás.
- **CV:** 0.946 ± 0.010 de macro-F1. Alto y **estable** (desviación de solo
  0.010 entre pliegues).
- **Held-out:** train 0.998, test 0.925 → brecha 0.073. El train satura (lineal +
  n-gramas), pero el test sigue alto y la brecha es **acotada**.
- **CV vs held-out:** 0.946 frente a 0.925, |diferencia| = 0.021. **Coinciden**,
  que es la prueba de generalización.
- **Control barajado:** 0.026 → colapsa al baseline. La señal es real.
- **Camino de regularización:** de `C=0.25` a `C=4` el test se mueve solo entre
  0.908 y 0.932. El resultado **no** depende de un hiperparámetro afortunado.
- **Por debajo de 1.0:** 0.925 en texto real de 22 clases es lo correcto; un 1.0
  sería sospechoso (indicaría fuga).

### El veredicto, cómo se decide

El veredicto **se deriva** de los números (en `_decide_verdict`), no se afirma:

1. Si la CV apenas supera el baseline → **underfit**.
2. Si el held-out es débil o **no** coincide con la CV (|diferencia| > 0.10) →
   **overfit**.
3. Si la CV es inestable entre pliegues (desviación > 0.05) → **overfit**.
4. Si la CV y el held-out coinciden, son altos y estables → **well-fit** (ajuste
   correcto), aunque el train esté saturado.

Con nuestros números: CV alta y estable, held-out alto y de acuerdo con la CV,
brecha acotada → **WELL-FIT**.

## La explicabilidad, paso a paso

Para la predicción de propósito:

1. Toma los coeficientes del modelo para la clase elegida.
2. Multiplícalos por el vector TF-IDF de la petición.
3. Ordena y quédate con los términos de mayor contribución positiva.

Eso da algo como `[('treating physician', 0.60), ('physician', 0.60), ...]`: las
palabras que empujaron la decisión hacia "tratamiento".

## El umbral de categorías y el respaldo

Una categoría se incluye si su probabilidad supera un umbral (0,5). Si **ninguna**
lo supera, el clasificador devuelve igualmente la **más probable**, para que la
política siempre tenga algo con lo que razonar. Es mejor devolver la mejor
estimación que no devolver nada.

## Importante: el modelo no decide solo

El clasificador solo responde a la pregunta de lenguaje ("¿qué pide esto?"). La
decisión de permitir o denegar es de la **política** (guía 03). Si la confianza
es baja, la política manda la petición a **revisión humana** en vez de adivinar.
Así, la autoridad de la decisión está en las reglas, no en el modelo.

## Para fijar la idea

- TF-IDF + regresión logística = fuerte **y** explicable.
- Propósito = multiclase; categorías = multi-etiqueta (one-vs-rest).
- La explicación son las palabras con más peso, sin trucos.
- El modelo propone; la política dispone. La confianza baja va a revisión.

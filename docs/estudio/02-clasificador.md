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
- Es **fuerte en esta tarea**: en datos de validación (que el modelo no vio), la
  precisión de propósito y el F1 de categorías son muy altos, porque el lenguaje
  de estas peticiones es muy distintivo.

Un LLM grande sería más robusto ante frases muy distintas, pero perderíamos la
explicabilidad directa y añadiríamos dependencia externa. La interfaz `classify`
está pensada para poder cambiar el modelo más adelante sin tocar el resto.

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

# 03 — La política y la decisión

## Dos preguntas muy distintas

En una decisión de acceso hay dos preguntas que conviene no mezclar:

1. **Pregunta de lenguaje:** ¿qué está pidiendo esta petición? → la responde el
   **clasificador**.
2. **Pregunta de gobernanza:** dado lo que pide, ¿está permitido ahora mismo? →
   la responde la **política**.

Es tentador juntarlo todo en un componente (que el modelo lea la petición *y*
diga sí o no). Pero eso acopla un modelo probabilístico a una decisión con peso
legal, esconde las reglas dentro del comportamiento del modelo y hace que todo
sea difícil de auditar y de cambiar. Por eso las separamos.

## Qué hace la política

`policy.py` es una **función pura**: recibe la petición ya clasificada y el
consentimiento leído del registro, y devuelve una de tres decisiones:

- **ALLOW** (permitir),
- **DENY** (denegar),
- **REVIEW** (a revisión humana),

junto con **razones** legibles.

## El algoritmo de decisión

En orden:

1. **¿Confianza baja?** Si la confianza del clasificador está por debajo del
   umbral (`CC_MIN_CONFIDENCE`, por defecto 0,55) → **REVIEW**. No adivinamos: lo
   ve una persona.
2. **¿Hay consentimiento válido que cubra todo?** Se pregunta al registro
   `has_consent(paciente, solicitante, propósito, máscara_solicitada)`. Si
   responde que sí (cubre todas las categorías y no está caducado) → **ALLOW**.
3. **Si no**, se explica por qué y se **DENY**:
   - no hay consentimiento registrado para ese propósito, o
   - el consentimiento no cubre ciertas categorías (se listan), o
   - el consentimiento ha caducado.
4. **Categorías sensibles.** Si entre las categorías que faltan hay alguna
   **sensible** (genética o salud mental), se marca explícitamente. Un fallo en
   una categoría sensible es siempre una denegación dura, nunca un "casi".

## ¿Por qué REVIEW y no solo ALLOW/DENY?

Porque la incertidumbre debe ser **explícita**. Si el modelo no está seguro de lo
que pide la petición, convertir esa duda en un "sí" silencioso filtraría datos, y
en un "no" silencioso bloquearía una atención legítima. La tercera opción,
REVIEW, pone a un humano en el bucle justo cuando hace falta.

## ¿Por qué una función pura?

Porque así la política es:

- **determinista**: las mismas entradas dan siempre la misma decisión;
- **auditable**: se lee de arriba abajo, sin estado oculto;
- **fácil de probar**: en las pruebas construimos peticiones clasificadas a mano y
  comprobamos cada camino (permitir, denegar por categoría, denegar sin
  consentimiento, revisión por confianza baja, denegar por caducidad, sensible).

## Un ejemplo completo

1. Paciente concede a la clínica consentimiento de **tratamiento** para
   `{diagnoses, medications, lab_results}`, 180 días.
2. Llega: *"The treating physician needs the recent lab results and the current
   medication list to adjust therapy."* → clasificado como TREATMENT,
   `{lab_results, medications}`, confianza alta. La política pregunta al registro:
   ¿cubre tratamiento esas dos categorías y sigue vigente? Sí → **ALLOW**.
3. Llega: *"For an approved research study we request the patient's genetic test
   results."* → clasificado como RESEARCH, `{genetic}`. No hay consentimiento de
   investigación → **DENY**, y además se marca que toca una categoría sensible sin
   consentimiento.
4. El paciente **revoca**. La misma petición de tratamiento ahora → **DENY**.

## Para fijar la idea

- Clasificador = qué pide. Política = si se permite. Separados a propósito.
- Tres decisiones: ALLOW, DENY, REVIEW.
- La confianza baja va a REVIEW; lo sensible que falta es denegación dura.
- La política es pura: determinista, auditable y fácil de probar.

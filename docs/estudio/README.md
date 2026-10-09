# Guía de estudio — ConsentChain

Esta carpeta es una guía en español para entender ConsentChain a fondo. El
código, los comentarios y la documentación técnica están en inglés (nivel B2) a
propósito, para que el proyecto sea creíble y sirva para practicar. Esta guía
explica el "por qué" de cada decisión en tu idioma, para estudiar con calma.

## Orden sugerido de lectura

1. **[01-modelo-de-consentimiento.md](01-modelo-de-consentimiento.md)** — qué es
   el consentimiento por propósito y categoría, y por qué un simple sí/no no
   basta.
2. **[02-clasificador.md](02-clasificador.md)** — cómo el modelo de IA convierte
   una petición en texto libre en propósito + categorías, por qué es explicable, y
   la **validación en datos reales**: el benchmark sobre un dataset clínico público
   (métricas de exactitud y macro-F1 con fórmulas, validación cruzada y held-out,
   over/underfitting y la brecha train/test, el control de etiquetas barajadas y un
   ejemplo trabajado con los números reales).
3. **[03-politica-y-decision.md](03-politica-y-decision.md)** — cómo se decide
   permitir, denegar o revisar, y por qué separamos el clasificador de la política.
4. **[04-registro-on-chain.md](04-registro-on-chain.md)** — el contrato
   `ConsentRegistry`, por qué no hay datos personales en la cadena y cómo se
   audita el historial.
5. **[05-preguntas-de-entrevista.md](05-preguntas-de-entrevista.md)** — preguntas
   típicas y cómo responderlas con seguridad.

## Resumen en una frase

ConsentChain guarda, en un contrato inteligente auditable, qué ha autorizado
cada paciente (para qué propósito, qué categorías de datos y hasta cuándo), y usa
un clasificador de IA explicable para leer una petición de acceso en lenguaje
natural y decidir si encaja con ese consentimiento — sin poner datos personales
ni clínicos en la cadena.
